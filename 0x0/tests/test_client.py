import pytest
import tempfile
import os
import sys
import importlib
import json
import re
from urllib.parse import urlparse
from flask_migrate import upgrade as db_upgrade
from io import BytesIO
from pathlib import Path

app = None
db = None
url_for = None
File = None
URL = None
TOKEN_RE = re.compile(r"^https://localhost/[A-Za-z0-9_-]{12}(?:\.[A-Za-z0-9._-]+)?\n$")


def get_uploaded_path(response):
    return response.data.decode().removeprefix("https://localhost/").strip()


def get_download_path(html):
    match = re.search(r'href="([^"]+)"', html)
    assert match is not None
    return urlparse(match.group(1)).path


def get_csv_cfg(html):
    match = re.search(r"const CFG = (\{.*?\});", html, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))

@pytest.fixture
def client():
    global app, db, url_for, File, URL

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DATABASE_URI"] = f"sqlite:///{tmpdir}/db.sqlite"
        os.environ["FHOST_LINK_SECRET"] = "test-secret-value-32-chars-long"

        if "fhost" in sys.modules:
            fhost = importlib.reload(sys.modules["fhost"])
        else:
            fhost = importlib.import_module("fhost")

        app = fhost.app
        db = fhost.db
        url_for = fhost.url_for
        File = fhost.File
        URL = fhost.URL
        app.config["FHOST_STORAGE_PATH"] = os.path.join(tmpdir, "up")
        os.makedirs(app.config["FHOST_STORAGE_PATH"], exist_ok=True)
        app.config["TESTING"] = True

        with app.test_client() as client:
            with app.app_context():
                db_upgrade()
            yield client


def test_missing_link_secret_raises_outside_testing():
    old_secret = os.environ.get("FHOST_LINK_SECRET")
    old_uri = os.environ.get("DATABASE_URI")
    try:
        if "FHOST_LINK_SECRET" in os.environ:
            del os.environ["FHOST_LINK_SECRET"]
        os.environ["DATABASE_URI"] = "sqlite:///:memory:"
        if "fhost" in sys.modules:
            sys.modules["fhost"].app.config["TESTING"] = False
            with pytest.raises(RuntimeError, match="FHOST_LINK_SECRET is required"):
                importlib.reload(sys.modules["fhost"])
        else:
            with pytest.raises(RuntimeError, match="FHOST_LINK_SECRET is required"):
                importlib.import_module("fhost")
    finally:
        if old_secret is not None:
            os.environ["FHOST_LINK_SECRET"] = old_secret
        if old_uri is not None:
            os.environ["DATABASE_URI"] = old_uri
        if "fhost" in sys.modules:
            sys.modules["fhost"].app.config["TESTING"] = True


def test_models_have_link_and_file_audit(client):
    import fhost
    File = fhost.File
    FileAudit = fhost.FileAudit
    assert hasattr(File, "link")
    assert File.token.property.columns[0].nullable is True
    assert FileAudit.__tablename__ == "file_audit"

    with app.app_context():
        audit = FileAudit(sha256="test-sha", link="test-link", action="TEST_ACTION")
        db.session.add(audit)
        db.session.commit()
        assert audit.id is not None
        assert audit.created_at is not None


def test_client(client):
    payloads = [
        ({ "file" : (BytesIO(b"hello"), "hello.txt") }, 200),
        ({ "file" : (BytesIO(b"hello"), "hello.ignorethis") }, 200),
        ({ "file" : (BytesIO(b"bye"), "bye.truncatethis") }, 200),
        ({ "file" : (BytesIO(b"hi"), "hi.tar.gz") }, 200),
        ({ "file" : (BytesIO(b"lea!"), "lea!") }, 200),
        ({ "file" : (BytesIO(b"why?"), "balls", "application/x-dosexec") }, 200),
        ({}, 400),
    ]

    paths = []
    for p, s in payloads:
        rv = client.post("/", buffered=True,
                        content_type="multipart/form-data",
                        data=p)
        assert rv.status_code == s
        if rv.status_code == 200:
            location = rv.data.decode()
            assert TOKEN_RE.match(location)
            paths.append(location.removeprefix("https://localhost/").strip())

    assert paths[0] != paths[1]
    assert paths[0].endswith(".txt")
    assert paths[2].endswith(".truncate")
    assert paths[3].endswith(".tar.gz")
    assert paths[4].endswith(".txt")

    f = File.query.get(3)
    f.removed = True
    db.session.add(f)
    db.session.commit()

    rq = [
        (200, [
            "/",
            "robots.txt",
            paths[0],
            f"{paths[0]}/test",
            f"{paths[0]}/test.py",
            paths[4],
            paths[3],
        ]),
        (404, [
            paths[0].split(".", 1)[0],
            f"{paths[0].split('.', 1)[0]}/test",
            f"{paths[0].split('.', 1)[0]}/test.bin",
            "test.bin",
            "test.bin/test",
            "test.bin/test.py",
            "test",
            "test/test",
            "test.bin/test.py",
            f"{paths[0].split('.', 1)[0]}.bin",
        ]),
        (451, [
            paths[2],
        ]),
    ]

    for code, paths in rq:
        for p in paths:
            app.logger.info(f"GET {p}")
            rv = client.get(p)
            assert rv.status_code == code


def test_rejects_remote_url_import(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"url": "https://example.com/file.txt"},
    )
    assert rv.status_code == 400


def test_html_upload_is_rejected(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"<html></html>"), "index.html", "text/html")},
    )
    assert rv.status_code == 415


def test_rejects_generic_url_shortening(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"shorten": "https://example.com"},
    )
    assert rv.status_code == 400


def test_randomized_links_render_text_preview_with_download_link(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"line one\nline two\n"), "preview.txt")},
    )

    preview_path = get_uploaded_path(rv)
    preview = client.get(preview_path)
    preview_html = preview.get_data(as_text=True)

    assert preview.status_code == 200
    assert preview.mimetype == "text/html"
    assert '<a href="https://localhost/download/' in preview_html
    assert ">Download</a>" in preview_html
    assert "line one" in preview_html
    assert "line two" in preview_html

    download = client.get(get_download_path(preview_html))

    assert download.status_code == 200
    assert download.headers["Content-Disposition"] == 'attachment; filename="preview.txt"'


def test_text_preview_escapes_html_like_content(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"<b>bold</b>\n"), "escaped.txt")},
    )

    preview = client.get(get_uploaded_path(rv))
    preview_html = preview.get_data(as_text=True)

    assert preview.status_code == 200
    assert "&lt;b&gt;bold&lt;/b&gt;" in preview_html
    assert "<b>bold</b>" not in preview_html


def test_non_text_files_still_download_directly(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={
            "file": (
                BytesIO(
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x02"
                    b"\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
                ),
                "image.png",
                "image/png",
            )
        },
    )

    file_path = get_uploaded_path(rv)
    download = client.get(file_path)

    assert download.status_code == 200
    assert download.mimetype == "image/png"
    assert download.headers["Content-Disposition"] == 'attachment; filename="image.png"'
    assert "href=" not in download.get_data(as_text=False).decode("latin1", errors="ignore")


def test_randomized_links_preserve_uploaded_filename_on_download(client):
    first = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"same-bytes"), "first-name.txt")},
    )
    second = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"same-bytes"), "second name.txt")},
    )

    first_path = get_uploaded_path(first)
    second_path = get_uploaded_path(second)

    assert first_path != second_path

    first_preview = client.get(first_path)
    second_preview = client.get(second_path)

    assert first_preview.status_code == 200
    assert second_preview.status_code == 200

    first_download = client.get(get_download_path(first_preview.get_data(as_text=True)))
    second_download = client.get(get_download_path(second_preview.get_data(as_text=True)))

    assert first_download.headers["Content-Disposition"] == 'attachment; filename="first-name.txt"'
    assert second_download.headers["Content-Disposition"] == 'attachment; filename="second name.txt"'


def test_uploaded_file_urls_use_long_random_tokens(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"randomized"), "sample.txt")},
    )

    assert rv.status_code == 200
    assert TOKEN_RE.match(rv.data.decode())


def test_dotted_filenames_keep_real_file_extension_in_public_url(client):
    pdf = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={
            "file": (
                BytesIO(b"%PDF-1.4 dummy receipt"),
                "cepat.smartselangor.com.my_fpx-receipt.pdf",
            )
        },
    )
    video = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={
            "file": (
                BytesIO(b"\x00\x00\x00\x18ftypmp42"),
                "Sophia_Xing_-_The_AI_labs_finally_made_peace._Jensen_brought_the_chips._created_in_b5xhFt.mp4",
            )
        },
    )

    pdf_path = get_uploaded_path(pdf)
    video_path = get_uploaded_path(video)

    assert pdf.status_code == 200
    assert video.status_code == 200
    assert pdf_path.endswith(".pdf")
    assert not pdf_path.endswith(".my_fpx-r")
    assert video_path.endswith(".mp4")
    assert not video_path.endswith("._created")
    assert TOKEN_RE.match(pdf.data.decode())
    assert TOKEN_RE.match(video.data.decode())

    pdf_download = client.get(f"/download/{pdf_path}")
    video_download = client.get(f"/download/{video_path}")

    assert pdf_download.status_code == 200
    assert video_download.status_code == 200
    assert pdf_download.headers["Content-Disposition"] == (
        'attachment; filename="cepat.smartselangor.com.my_fpx-receipt.pdf"'
    )
    assert video_download.headers["Content-Disposition"] == (
        'attachment; filename="Sophia_Xing_-_The_AI_labs_finally_made_peace._Jensen_brought_the_chips._created_in_b5xhFt.mp4"'
    )


def test_uploaded_file_response_sets_nosniff(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"hello"), "hello.txt")},
    )

    preview = client.get(get_uploaded_path(rv))
    download = client.get(get_download_path(preview.get_data(as_text=True)))

    assert download.status_code == 200
    assert download.headers["X-Content-Type-Options"] == "nosniff"


def test_markdown_upload_returns_md_url(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"# Title\n"), "README.md")},
    )

    assert rv.status_code == 200
    assert get_uploaded_path(rv).endswith(".md")
    assert TOKEN_RE.match(rv.data.decode())


def test_markdown_preview_renders_common_markdown(client):
    content = b"""# Heading

Paragraph with [link](https://example.com).

- one
- two

> quoted

```python
print('<safe>')
```
"""
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(content), "doc.md")},
    )

    preview = client.get(get_uploaded_path(rv))
    html = preview.get_data(as_text=True)

    assert preview.status_code == 200
    assert preview.mimetype == "text/html"
    assert "<h1>Heading</h1>" in html
    assert '<p>Paragraph with <a href="https://example.com">link</a>.</p>' in html
    assert "<ul>" in html
    assert "<li>one</li>" in html
    assert "<blockquote>" in html
    assert "<pre><code" in html
    assert "&lt;safe&gt;" in html


def test_markdown_preview_renders_tables(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"| A | B |\n|---|---|\n| 1 | 2 |\n"), "table.md")},
    )

    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)

    assert "<table>" in html
    assert "<thead>" in html
    assert "<tbody>" in html
    assert "<tr>" in html
    assert "<th>A</th>" in html
    assert "<td>1</td>" in html


def test_markdown_preview_download_link_preserves_filename(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"# Download me\n"), "original name.md")},
    )

    preview = client.get(get_uploaded_path(rv))
    html = preview.get_data(as_text=True)
    download = client.get(get_download_path(html))

    assert '<a href="https://localhost/download/' in html
    assert ">Download</a>" in html
    assert download.status_code == 200
    assert download.headers["Content-Disposition"] == 'attachment; filename="original name.md"'


def test_markdown_preview_renders_mermaid_container(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"```mermaid\ngraph TD\n  A-->B\n```\n"), "diagram.md")},
    )

    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)

    assert '<div class="mermaid">' in html
    assert "graph TD" in html
    assert "A--&gt;B" in html
    assert "mermaid@10.9.1" in html
    assert "mermaid.initialize" in html


def test_markdown_preview_keeps_non_mermaid_code_as_code(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"```python\nprint('hello')\n```\n"), "code.md")},
    )

    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)

    assert '<div class="mermaid">' not in html
    assert "<pre><code" in html
    assert "print('hello')" in html


def test_plain_text_preview_does_not_include_mermaid(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"```mermaid\ngraph TD\n```\n"), "plain.txt")},
    )

    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)

    assert "mermaid@10.9.1" not in html
    assert "mermaid.initialize" not in html
    assert "```mermaid" in html


def test_markdown_preview_sanitizes_script_tags(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"# Safe\n\nRegular Markdown paragraph before raw HTML.\n\n<script>alert('x')</script>\n"), "unsafe.md")},
    )

    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)

    assert "<script>alert('x')</script>" not in html
    assert "<script" not in html


def test_markdown_preview_sanitizes_inline_event_attributes(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"<img src='https://example.com/x.png' onerror='alert(1)' onclick='alert(2)'>"), "events.md")},
    )

    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)

    assert "onerror" not in html
    assert "onclick" not in html
    assert "onload" not in html


def test_markdown_preview_sanitizes_javascript_urls(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"[bad](javascript:alert('x'))"), "link.md")},
    )

    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)

    assert "javascript:" not in html


def test_text_with_markdown_content_remains_plain_text(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"# Not rendered\n\n| A | B |\n|---|---|\n"), "markdown-looking.txt")},
    )

    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)

    assert "<pre>" in html
    assert "# Not rendered" in html
    assert "<h1>Not rendered</h1>" not in html
    assert "<table>" not in html


def test_video_upload_renders_player_preview_with_download_link(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"\x00\x00\x00\x18ftypmp42"), "clip.mp4")},
    )

    preview_path = get_uploaded_path(rv)
    preview = client.get(preview_path)
    preview_html = preview.get_data(as_text=True)

    assert preview.status_code == 200
    assert preview.mimetype == "text/html"
    assert preview.headers["X-Content-Type-Options"] == "nosniff"
    assert '<a href="https://localhost/download/' in preview_html
    assert ">Download</a>" in preview_html
    assert "<video controls" in preview_html
    assert '<source src="https://localhost/download/' in preview_html
    assert 'type="video/mp4"' in preview_html

    download = client.get(get_download_path(preview_html))

    assert download.status_code == 200
    assert download.mimetype == "video/mp4"
    assert download.headers["Content-Disposition"] == 'attachment; filename="clip.mp4"'


def test_webm_upload_renders_player_preview(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"\x1a\x45\xdf\xa3\x93\x42\x82\x84webm"), "clip.webm")},
    )

    preview = client.get(get_uploaded_path(rv))
    preview_html = preview.get_data(as_text=True)

    assert preview.status_code == 200
    assert preview.mimetype == "text/html"
    assert "<video controls" in preview_html
    assert 'type="video/webm"' in preview_html


def test_csv_upload_renders_table_preview_with_download_link(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"a,b\n1,2\n"), "sheet.csv")},
    )
    preview_path = get_uploaded_path(rv)
    preview = client.get(preview_path)
    html = preview.get_data(as_text=True)

    assert preview.status_code == 200
    assert preview.mimetype == "text/html"
    assert preview.headers["X-Content-Type-Options"] == "nosniff"
    assert '<a href="https://localhost/download/' in html
    assert ">Download</a>" in html
    assert "<pre>a,b" not in html

    download = client.get(get_download_path(html))
    assert download.status_code == 200
    assert download.headers["Content-Disposition"] == 'attachment; filename="sheet.csv"'
    assert download.get_data() == b"a,b\n1,2\n"


def test_compound_csv_extension_gets_table_preview(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"a,b\n"), "report.2024.csv")},
    )
    preview = client.get(get_uploaded_path(rv))
    html = preview.get_data(as_text=True)
    assert preview.status_code == 200
    assert preview.mimetype == "text/html"
    assert ">Download</a>" in html
    assert "<pre>a,b" not in html


def test_txt_with_commas_stays_plain_text_preview(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"a,b\n1,2\n"), "notes.txt")},
    )
    preview = client.get(get_uploaded_path(rv))
    html = preview.get_data(as_text=True)
    assert "<pre>" in html
    assert "a,b" in html
    assert "const CFG" not in html


def test_csv_preview_empty_file_message(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b""), "empty.csv")},
    )
    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)
    assert "Empty file." in html
    assert "Couldn't read past row" not in html
    assert 'class="scrollbox"' not in html
    assert 'type="number"' not in html
    cfg = get_csv_cfg(html)
    assert cfg["rows"] == 0
    assert cfg["cols"] == 0


def test_csv_preview_bom_only_is_empty(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"\xef\xbb\xbf"), "bom.csv")},
    )
    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)
    assert "Empty file." in html
    assert get_csv_cfg(html)["rows"] == 0


def test_csv_preview_crlf_only_is_one_empty_row(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"\r\n"), "crlf.csv")},
    )
    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)
    assert "Empty file." not in html
    assert get_csv_cfg(html)["rows"] == 1


def test_csv_preview_bom_plus_newline_is_one_row(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"\xef\xbb\xbf\n"), "bomnl.csv")},
    )
    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)
    assert "Empty file." not in html
    assert get_csv_cfg(html)["rows"] == 1


def test_csv_preview_cr_only_stops_at_row_zero(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"\r"), "mac.csv")},
    )
    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)
    assert "Couldn't read past row 0." in html
    assert "Empty file." not in html
    assert 'class="scrollbox"' not in html
    assert get_csv_cfg(html)["rows"] == 0


def test_csv_preview_huge_field_keeps_prior_rows(client):
    payload = b"a\nb\n" + b"x" * 131073 + b"\n"
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(payload), "widefield.csv")},
    )
    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)
    assert "Couldn't read past row 2." in html
    assert get_csv_cfg(html)["rows"] == 2


def test_csv_preview_overlong_line_stops_at_row_zero(client):
    payload = b"x" * (4 * 1024 * 1024 + 1)
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(payload), "longline.csv")},
    )
    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)
    assert "Couldn't read past row 0." in html
    assert get_csv_cfg(html)["rows"] == 0


def test_csv_preview_grid_chrome_when_rows_exist(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"a,b\n1,2\n"), "grid.csv")},
    )
    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)
    cfg = get_csv_cfg(html)
    assert cfg["rows"] == 2
    assert cfg["cols"] == 2
    assert cfg["dataUrl"].startswith("/csv/")
    assert 'class="scrollbox"' in html
    assert 'class="sizer"' in html
    assert "<dialog" in html
    assert 'id="goto"' in html
    assert 'id="gotocol"' in html
    assert "Couldn't read past row" not in html


def test_csv_preview_no_grid_when_empty(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b""), "nogrid.csv")},
    )
    html = client.get(get_uploaded_path(rv)).get_data(as_text=True)
    assert 'class="scrollbox"' not in html
    assert "<dialog" not in html


@pytest.mark.parametrize("width", [240, 900])
def test_csv_preview_adapts_columns_and_preserves_horizontal_scroll(client, width):
    from playwright.sync_api import sync_playwright

    long_cell = "BEGIN_" + "W" * 200 + "_employees"
    rv = client.post(
        "/",
        content_type="multipart/form-data",
        data={"file": (BytesIO((
            "Id,Number of employees,Details\n1,1234," + long_cell + "\n"
        ).encode()), "wide.csv")},
    )
    path = get_uploaded_path(rv)
    responses = {
        "/" + path: client.get(path),
        "/csv/" + path + "?rb=0&cb=0": client.get(
            "/csv/" + path, query_string={"rb": "0", "cb": "0"},
        ),
        "/csv/" + path + "?r=1&c=2": client.get(
            "/csv/" + path, query_string={"r": "1", "c": "2"},
        ),
    }

    def serve(route):
        url = urlparse(route.request.url)
        response = responses[url.path + ("?" + url.query if url.query else "")]
        route.fulfill(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.data,
        )

    with sync_playwright() as playwright:
        with playwright.chromium.launch(
            channel="chromium",
            executable_path=os.environ.get("CHROMIUM_EXECUTABLE_PATH"),
        ) as browser:
            page = browser.new_page(viewport={"width": width, "height": 300})
            page.set_default_timeout(5000)
            page.route("http://localhost/**", serve)
            page.goto("http://localhost/" + path)
            page.wait_for_function("document.querySelector('tbody td').textContent.length > 0")
            dimensions = page.evaluate("""() => {
                const box = document.querySelector('.scrollbox');
                const cells = document.querySelector('tbody tr').cells;
                return [...cells].map(cell => cell.offsetWidth);
            }""")
            assert dimensions[0] == 80
            assert dimensions[1] < dimensions[2] < dimensions[3]
            label = page.locator('tbody tr').first.locator('td').nth(1)
            assert label.text_content() == "Number of employees"
            assert label.evaluate("cell => cell.scrollWidth === cell.clientWidth")
            detail = page.locator('tbody tr').nth(1).locator('td').nth(2)
            assert detail.text_content().startswith("BEGIN_")
            assert detail.text_content().endswith("_employees")
            assert "…" in detail.text_content()

            page.evaluate("document.querySelector('.scrollbox').scrollLeft = 50")
            page.wait_for_function("document.querySelector('tbody td').getBoundingClientRect().x === 30")
            assert page.locator('tbody th').first.bounding_box()["x"] == 0
            assert page.locator('thead .cell').first.bounding_box()["x"] == 30
            page.evaluate("document.querySelector('.scrollbox').scrollLeft = 1000000")
            page.wait_for_function("""() => {
                const cell = [...document.querySelectorAll('thead .cell')].find(cell => cell.textContent === 'C');
                return cell && cell.getBoundingClientRect().right <= innerWidth;
            }""")
            page.locator('tbody tr').nth(1).locator('td:visible').last.click()
            page.wait_for_function("document.querySelector('dialog pre').textContent.endsWith('_employees')")
            assert page.locator('dialog pre').text_content() == long_cell


def test_csv_preview_scaled_wheel_advances_variable_width_columns(client):
    from playwright.sync_api import sync_playwright

    rv = client.post(
        "/",
        content_type="multipart/form-data",
        data={"file": (BytesIO((",".join(["x"] * 100000) + "\n").encode()), "scaled.csv")},
    )
    path = get_uploaded_path(rv)
    html = client.get(path)
    tile = client.get("/csv/" + path, query_string={"rb": "0", "cb": "0"})

    def serve(route):
        response = tile if urlparse(route.request.url).path.startswith("/csv/") else html
        route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.data)

    with sync_playwright() as playwright:
        with playwright.chromium.launch(
            channel="chromium",
            executable_path=os.environ.get("CHROMIUM_EXECUTABLE_PATH"),
        ) as browser:
            page = browser.new_page(viewport={"width": 900, "height": 300})
            page.set_default_timeout(5000)
            page.route("http://localhost/**", serve)
            page.goto("http://localhost/" + path)
            page.wait_for_function("document.querySelector('tbody td').textContent === 'x'")
            page.mouse.move(450, 150)
            for label in ["B", "C", "D"]:
                page.mouse.wheel(1, 0)
                page.wait_for_function(
                    "label => document.querySelector('thead .cell').textContent === label", arg=label,
                )
            page.mouse.wheel(-1, 0)
            page.wait_for_function("document.querySelector('thead .cell').textContent === 'C'")


def test_csv_preview_column_finder_jumps_to_column(client):
    from playwright.sync_api import sync_playwright

    header = ",".join([f"col_{i+1}" for i in range(54)]) + "\n"
    row = ",".join([f"val_{i+1}" for i in range(54)]) + "\n"
    rv = client.post(
        "/",
        content_type="multipart/form-data",
        data={"file": (BytesIO((header + row).encode()), "finder.csv")},
    )
    path = get_uploaded_path(rv)
    html = client.get(path)
    assert 'id="gotocol"' in html.get_data(as_text=True)

    responses = {
        "/" + path: html,
        "/csv/" + path + "?rb=0&cb=0": client.get("/csv/" + path, query_string={"rb": "0", "cb": "0"}),
        "/csv/" + path + "?rb=0&cb=1": client.get("/csv/" + path, query_string={"rb": "0", "cb": "1"}),
    }

    def serve(route):
        url = urlparse(route.request.url)
        response = responses.get(url.path + ("?" + url.query if url.query else ""), html)
        route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.data)

    with sync_playwright() as playwright:
        with playwright.chromium.launch(
            channel="chromium",
            executable_path=os.environ.get("CHROMIUM_EXECUTABLE_PATH"),
        ) as browser:
            page = browser.new_page(viewport={"width": 600, "height": 400})
            page.set_default_timeout(5000)
            page.route("http://localhost/**", serve)
            page.goto("http://localhost/" + path)
            page.wait_for_function("document.querySelector('tbody td').textContent.length > 0")

            assert page.locator("thead .cell").first.text_content() == "A"

            col_input = page.locator("#gotocol")
            col_input.fill("AA")
            col_input.press("Enter")
            page.wait_for_function("document.querySelector('thead .cell').textContent === 'AA'")
            assert col_input.input_value() == "AA"

            col_input.fill("28")
            col_input.press("Enter")
            page.wait_for_function("document.querySelector('thead .cell').textContent === 'AB'")
            assert col_input.input_value() == "AB"

            col_input.fill("bb")
            col_input.press("Enter")
            page.wait_for_function("""() => {
                const cell = [...document.querySelectorAll('thead .cell')].find(c => c.textContent === 'BB');
                return cell && cell.style.visibility !== 'hidden';
            }""")
            assert col_input.input_value() == "BB"


def test_csv_index_is_reused_on_second_get(client, monkeypatch):
    fhost = sys.modules["fhost"]
    calls = {"n": 0}
    real = fhost._scan_csv_file

    def wrapped(fpath):
        calls["n"] += 1
        return real(fpath)

    monkeypatch.setattr(fhost, "_scan_csv_file", wrapped)
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"a,b\n1,2\n"), "reuse.csv")},
    )
    path = get_uploaded_path(rv)
    client.get(path)
    client.get(path)
    assert calls["n"] == 1


def test_csv_truncated_index_rescans_instead_of_500(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"a,b\n1,2\n"), "truncidx.csv")},
    )
    path = get_uploaded_path(rv)
    preview = client.get(path)
    assert preview.status_code == 200
    assert get_csv_cfg(preview.get_data(as_text=True))["rows"] == 2
    storage = Path(app.config["FHOST_STORAGE_PATH"])
    index = next(p for p in (storage / ".csv-index").iterdir() if p.is_file())
    index.write_bytes(index.read_bytes()[:10])
    preview = client.get(path)
    assert preview.status_code == 200
    assert get_csv_cfg(preview.get_data(as_text=True))["rows"] == 2
    tile = client.get("/csv/" + path, query_string={"rb": "0", "cb": "0"})
    assert tile.status_code == 200
    assert tile.get_json()["rows"][0] == ["a", "b"]


def test_csv_tile_does_not_load_whole_index(client, monkeypatch):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"a,b\n1,2\n"), "seek.csv")},
    )
    path = get_uploaded_path(rv)
    client.get(path)

    def boom(self):
        raise AssertionError("whole index loaded")

    monkeypatch.setattr(Path, "read_bytes", boom)
    assert client.get(path).status_code == 200
    assert client.get("/csv/" + path, query_string={"rb": "0", "cb": "0"}).status_code == 200
    assert client.get("/csv/" + path, query_string={"r": "0", "c": "0"}).status_code == 200


def test_csv_tile_parses_quoted_fields_and_escapes(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(
            b'\xef\xbb\xbfname,note\n'
            b'Ada,"hello, world"\n'
            b'Bea,"line1\nline2"\n'
            b'Cal,"a""b"\n'
            b'\n'
            b'1\n'
            b'<b>,x\n'
            b'bad,\xff\n'
        ), "edges.csv")},
    )
    path = get_uploaded_path(rv)
    tile = client.get("/csv/" + path, query_string={"rb": "0", "cb": "0"})
    assert tile.status_code == 200
    assert tile.mimetype == "application/json"
    assert tile.headers["X-Content-Type-Options"] == "nosniff"
    rows = tile.get_json()["rows"]
    assert rows[0] == ["name", "note"]
    assert rows[1] == ["Ada", "hello, world"]
    assert rows[2] == ["Bea", "line1\nline2"]
    assert rows[3] == ["Cal", 'a"b']
    assert rows[4] == []
    assert rows[5] == ["1"]
    assert rows[6] == ["<b>", "x"]
    assert rows[7] == ["bad", "\ufffd"]


def test_csv_tile_straddling_quoted_newline_at_block_boundary(client):
    lines = [b"h\n"]
    # rows 1..199 ordinary; row 200 (0-based) starts with a quoted newline so block 1 must resume mid-record
    lines.extend(b"%d\n" % i for i in range(1, 200))
    lines.append(b'"a\nb"\n')
    payload = b"".join(lines)
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(payload), "span.csv")},
    )
    path = get_uploaded_path(rv)
    assert get_csv_cfg(client.get(path).get_data(as_text=True))["rows"] == 201
    tile = client.get("/csv/" + path, query_string={"rb": "1", "cb": "0"})
    assert tile.get_json()["rows"] == [["a\nb"]]


def test_csv_cell_returns_full_text_tile_truncates_in_middle(client):
    cell = "begin_" + "x" * 60 + "_employees"
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(("a\n" + cell + "\n").encode()), "long.csv")},
    )
    path = get_uploaded_path(rv)
    tile = client.get("/csv/" + path, query_string={"rb": "0", "cb": "0"}).get_json()
    assert tile["rows"][1] == ["begin_" + "x" * 18 + "…" + "x" * 15 + "_employees"]
    full = client.get("/csv/" + path, query_string={"r": "1", "c": "0"}).get_json()
    assert full["text"] == cell


def test_csv_tile_bounds_and_bad_params(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"a,b\n1,2\n"), "bounds.csv")},
    )
    path = get_uploaded_path(rv)
    client.get(path)
    base = "/csv/" + path
    assert client.get(base, query_string={"rb": "1", "cb": "0"}).get_json() == {"rows": []}
    assert client.get(base, query_string={"rb": "0", "cb": "1"}).get_json() == {"rows": [[], []]}
    assert client.get(base, query_string={"r": "9", "c": "0"}).get_json() == {"text": ""}
    assert client.get(base, query_string={"r": "0", "c": "9"}).get_json() == {"text": ""}
    assert client.get(base, query_string={"rb": "0"}).status_code == 400
    assert client.get(base, query_string={"rb": "-1", "cb": "0"}).status_code == 400
    assert client.get(base).status_code == 400


def test_csv_data_rejects_non_csv_and_removed(client):
    txt = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"hello\n"), "plain.txt")},
    )
    assert client.get("/csv/" + get_uploaded_path(txt), query_string={"rb": "0", "cb": "0"}).status_code == 404

    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"a\n"), "gone.csv")},
    )
    path = get_uploaded_path(rv)
    token = path[:-4]
    f = File.query.filter_by(token=token).first()
    f.removed = True
    db.session.commit()
    assert client.get("/csv/" + path, query_string={"rb": "0", "cb": "0"}).status_code == 451


def test_cleanup_skips_csv_index_dir_and_missing_dir(client):
    import cleanup as cleanup_mod
    storage = app.config["FHOST_STORAGE_PATH"]
    Path(storage, ".csv-index").mkdir()
    cleanup_mod.cleanup_expired(storage, app.config["MAX_CONTENT_LENGTH"])
    assert Path(storage, ".csv-index").is_dir()
    import shutil
    shutil.rmtree(Path(storage, ".csv-index"))
    cleanup_mod.cleanup_expired(storage, app.config["MAX_CONTENT_LENGTH"])


def test_cleanup_deletes_orphan_csv_index(client):
    import cleanup as cleanup_mod
    storage = Path(app.config["FHOST_STORAGE_PATH"])
    index_dir = storage / ".csv-index"
    index_dir.mkdir()
    orphan = index_dir / "deadbeef"
    tmp = index_dir / "deadbeef.tmp-1-2"
    orphan.write_bytes(b"x")
    tmp.write_bytes(b"y")
    cleanup_mod.cleanup_expired(str(storage), app.config["MAX_CONTENT_LENGTH"])
    assert not orphan.exists()
    assert not tmp.exists()


def test_cleanup_keeps_index_for_live_csv_and_drops_it_after_expiry(client):
    import cleanup as cleanup_mod
    import time
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"a,b\n"), "keep.csv")},
    )
    client.get(get_uploaded_path(rv))
    fhost = sys.modules["fhost"]
    storage = Path(app.config["FHOST_STORAGE_PATH"])
    sha = next(p.name for p in storage.iterdir() if p.is_file())
    index = storage / ".csv-index" / sha
    assert index.is_file()
    cleanup_mod.cleanup_expired(str(storage), app.config["MAX_CONTENT_LENGTH"])
    assert index.is_file()
    old = time.time() - 400 * 86400
    os.utime(storage / sha, (old, old))
    cleanup_mod.cleanup_expired(str(storage), app.config["MAX_CONTENT_LENGTH"])
    assert not (storage / sha).exists()
    assert not index.exists()


