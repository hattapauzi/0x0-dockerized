import pytest
import tempfile
import os
import sys
import importlib
from flask_migrate import upgrade as db_upgrade
from io import BytesIO

app = None
db = None
url_for = None
File = None
URL = None

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
        ({ "file" : (BytesIO(b"hello"), "hello.txt") }, 200, b"https://localhost/E.txt\n"),
        ({ "file" : (BytesIO(b"hello"), "hello.ignorethis") }, 200, b"https://localhost/E.txt\n"),
        ({ "file" : (BytesIO(b"bye"), "bye.truncatethis") }, 200, b"https://localhost/Q.truncate\n"),
        ({ "file" : (BytesIO(b"hi"), "hi.tar.gz") }, 200, b"https://localhost/h.tar.gz\n"),
        ({ "file" : (BytesIO(b"lea!"), "lea!") }, 200, b"https://localhost/d.txt\n"),
        ({ "file" : (BytesIO(b"why?"), "balls", "application/x-dosexec") }, 200, None),
        ({}, 400, None),
    ]

    for p, s, r in payloads:
        rv = client.post("/", buffered=True,
                        content_type="multipart/form-data",
                        data=p)
        assert rv.status_code == s
        if r:
            assert rv.data == r

    f = File.query.get(2)
    f.removed = True
    db.session.add(f)
    db.session.commit()

    rq = [
        (200, [
            "/",
            "robots.txt",
            "E.txt",
            "E.txt/test",
            "E.txt/test.py",
            "d.txt",
            "h.tar.gz",
        ]),
        (404, [
            "E",
            "E/test",
            "E/test.bin",
            "test.bin",
            "test.bin/test",
            "test.bin/test.py",
            "test",
            "test/test",
            "test.bin/test.py",
            "E.bin",
        ]),
        (451, [
            "Q.truncate",
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


def test_rejects_generic_url_shortening(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"shorten": "https://example.com"},
    )
    assert rv.status_code == 400


def test_uploaded_file_response_sets_nosniff(client):
    client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"hello"), "hello.txt")},
    )

    rv = client.get("E.txt")
    assert rv.status_code == 200
    assert rv.headers["X-Content-Type-Options"] == "nosniff"


def test_html_upload_is_rejected(client):
    rv = client.post(
        "/",
        buffered=True,
        content_type="multipart/form-data",
        data={"file": (BytesIO(b"<html></html>"), "index.html", "text/html")},
    )
    assert rv.status_code == 415
