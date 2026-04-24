import pytest
import tempfile
import os
import sys
import importlib
import re
from urllib.parse import urlparse
from flask_migrate import upgrade as db_upgrade
from io import BytesIO

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

@pytest.fixture
def client():
    global app, db, url_for, File, URL

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DATABASE_URI"] = f"sqlite:///{tmpdir}/db.sqlite"

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
        app.config["TESTING"] = True

        with app.test_client() as client:
            with app.app_context():
                db_upgrade()
            yield client

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


