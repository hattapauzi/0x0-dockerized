#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Copyright © 2020 Mia Herkt
    Licensed under the EUPL, Version 1.2 or - as soon as approved
    by the European Commission - subsequent versions of the EUPL
    (the "License");
    You may not use this work except in compliance with the License.
    You may obtain a copy of the license at:

        https://joinup.ec.europa.eu/software/page/eupl

    Unless required by applicable law or agreed to in writing,
    software distributed under the License is distributed on an
    "AS IS" basis, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
    either express or implied.
    See the License for the specific language governing permissions
    and limitations under the License.
"""

from flask import Flask, abort, make_response, redirect, request, send_from_directory, url_for, Response, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from jinja2.exceptions import *
from jinja2 import ChoiceLoader, FileSystemLoader
from markupsafe import Markup
from hashlib import sha256
from magic import Magic
from mimetypes import guess_extension
import bleach
import csv
import fcntl
import json
import markdown
import os
import re
import secrets
import struct
import sys
import threading
from pathlib import Path

app = Flask(__name__, instance_relative_config=True)
app.config.update(
    SQLALCHEMY_TRACK_MODIFICATIONS = False,
    PREFERRED_URL_SCHEME = "https", # nginx users: make sure to have 'uwsgi_param UWSGI_SCHEME $scheme;' in your config
    MAX_CONTENT_LENGTH = 256 * 1024 * 1024,
    MAX_URL_LENGTH = 4096,
    USE_X_SENDFILE = False,
    FHOST_USE_X_ACCEL_REDIRECT = False,  # disabled - no nginx
    FHOST_STORAGE_PATH = "up",
    FHOST_MAX_EXT_LENGTH = 9,
    FHOST_EXT_OVERRIDE = {
        "audio/flac" : ".flac",
        "image/gif" : ".gif",
        "image/jpeg" : ".jpg",
        "image/png" : ".png",
        "image/svg+xml" : ".svg",
        "video/webm" : ".webm",
        "video/x-matroska" : ".mkv",
        "application/octet-stream" : ".bin",
        "text/plain" : ".log",
        "text/plain" : ".txt",
        "text/x-diff" : ".diff",
    },
    FHOST_MIME_BLACKLIST = [
        "application/xml",
        "application/xhtml+xml",
        "application/x-dosexec",
        "application/java-archive",
        "application/java-vm",
        "image/svg+xml",
        "text/html",
    ],
    FHOST_UPLOAD_BLACKLIST = None,
    NSFW_DETECT = False,
    NSFW_THRESHOLD = 0.608,
    FHOST_TOKEN_LENGTH = 12,
    URL_ALPHABET = "DEQhd2uFteibPwq0SWBInTpA_jcZL5GKz3YCR14Ulk87Jors9vNHgfaOmMXy6Vx-",
)

if not app.config["TESTING"]:
    app.config.from_pyfile("config.py")
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(str(Path(app.instance_path) / "templates")),
        app.jinja_loader
    ])

    if app.config["DEBUG"]:
        app.config["FHOST_USE_X_ACCEL_REDIRECT"] = False

if app.config["NSFW_DETECT"]:
    from nsfw_detect import NSFWDetector
    nsfw = NSFWDetector()

try:
    mimedetect = Magic(mime=True, mime_encoding=False)
except:
    print("""Error: You have installed the wrong version of the 'magic' module.
Please install python-magic.""")
    sys.exit(1)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class URL(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    url = db.Column(db.UnicodeText, unique = True)

    def __init__(self, url):
        self.url = url

    def getname(self):
        return su.enbase(self.id)

    def geturl(self):
        return url_for("get", path=self.getname(), _external=True, _scheme="https") + "\n"

    def get(url):
        u = URL.query.filter_by(url=url).first()

        if not u:
            u = URL(url)
            db.session.add(u)
            db.session.commit()

        return u

class File(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    sha256 = db.Column(db.String)
    token = db.Column(db.String(32), unique = True, nullable = False)
    ext = db.Column(db.UnicodeText)
    mime = db.Column(db.UnicodeText)
    addr = db.Column(db.UnicodeText)
    removed = db.Column(db.Boolean, default=False)
    nsfw_score = db.Column(db.Float)
    original_name = db.Column(db.UnicodeText)

    def __init__(self, sha256, token, ext, mime, addr, original_name=None):
        self.sha256 = sha256
        self.token = token
        self.ext = ext
        self.mime = mime
        self.addr = addr
        self.original_name = original_name

    def getname(self):
        return u"{0}{1}".format(self.token, self.ext)

    def getdownloadname(self):
        return self.original_name or self.getname()

    def geturl(self):
        n = self.getname()

        if self.nsfw_score and self.nsfw_score > app.config["NSFW_THRESHOLD"]:
            return url_for("get", path=n, _external=True, _scheme="https", _anchor="nsfw") + "\n"
        else:
            return url_for("get", path=n, _external=True, _scheme="https") + "\n"

    def store(file_, addr):
        data = file_.stream.read()
        digest = sha256(data).hexdigest()

        def generate_token():
            alphabet = app.config["URL_ALPHABET"]
            length = app.config["FHOST_TOKEN_LENGTH"]
            return "".join(secrets.choice(alphabet) for _ in range(length))

        def get_unique_token():
            while True:
                token = generate_token()
                if not File.query.filter_by(token=token).first():
                    return token

        def get_mime():
            guess = mimedetect.from_buffer(data)
            app.logger.debug(f"MIME - specified: '{file_.content_type}' - detected: '{guess}'")

            if guess and "/" in guess:
                mime = guess
            elif file_.content_type and "/" in file_.content_type:
                mime = file_.content_type
            else:
                mime = "application/octet-stream"

            if mime in app.config["FHOST_MIME_BLACKLIST"] or guess in app.config["FHOST_MIME_BLACKLIST"]:
                abort(415)

            if mime.startswith("text/") and not "charset" in mime:
                mime += "; charset=utf-8"

            return mime

        def get_ext(mime):
            suffixes = Path(file_.filename or "").suffixes[-2:]
            ext = "".join(suffixes)
            gmime = mime.split(";")[0]
            guess = guess_extension(gmime)
            max_len = app.config["FHOST_MAX_EXT_LENGTH"]

            app.logger.debug(f"extension - specified: '{ext}' - detected: '{guess}'")

            if not ext:
                if gmime in app.config["FHOST_EXT_OVERRIDE"]:
                    ext = app.config["FHOST_EXT_OVERRIDE"][gmime]
                else:
                    ext = guess_extension(gmime)

            # Extra dots in a basename are not a compound extension. Keep
            # short pairs such as .tar.gz, otherwise use only the last suffix.
            if ext and len(ext) > max_len and len(suffixes) > 1:
                ext = suffixes[-1]

            return ext[:max_len] or ".bin"

        def get_original_name(ext):
            original_name = Path(file_.filename or "").name

            if not original_name:
                return f"file{ext}"

            if not original_name.endswith(ext):
                return f"{original_name}{ext}"

            return original_name

        mime = get_mime()
        ext = get_ext(mime)
        original_name = get_original_name(ext)
        f = File(digest, get_unique_token(), ext, mime, addr, original_name=original_name)

        f.addr = addr

        storage = Path(app.config["FHOST_STORAGE_PATH"])
        storage.mkdir(parents=True, exist_ok=True)
        p = storage / digest

        if not p.is_file():
            file_.stream.seek(0)
            file_.save(p)
        else:
            p.touch()

        if not f.nsfw_score and app.config["NSFW_DETECT"]:
            f.nsfw_score = nsfw.detect(p)

        db.session.add(f)
        db.session.commit()
        return f



class UrlEncoder(object):
    def __init__(self,alphabet, min_length):
        self.alphabet = alphabet
        self.min_length = min_length

    def enbase(self, x):
        n = len(self.alphabet)
        str = ""
        while x > 0:
            str = (self.alphabet[int(x % n)]) + str
            x = int(x // n)
        padding = self.alphabet[0] * (self.min_length - len(str))
        return '%s%s' % (padding, str)

    def debase(self, x):
        n = len(self.alphabet)
        result = 0
        for i, c in enumerate(reversed(x)):
            result += self.alphabet.index(c) * (n ** i)
        return result

su = UrlEncoder(alphabet=app.config["URL_ALPHABET"], min_length=1)

def in_upload_bl(addr):
    if app.config["FHOST_UPLOAD_BLACKLIST"]:
        with app.open_instance_resource(app.config["FHOST_UPLOAD_BLACKLIST"]) as bl:
            check = addr.lstrip("::ffff:")
            for l in bl.readlines():
                if not l.startswith("#"):
                    if check == l.rstrip():
                        return True

    return False

def store_file(f, addr):
    if in_upload_bl(addr):
        return "Your host is blocked from uploading files.\n", 451

    sf = File.store(f, addr)

    return sf.geturl()

def build_file_response(f, fpath):
    if app.config["FHOST_USE_X_ACCEL_REDIRECT"]:
        response = make_response()
        response.headers["Content-Length"] = fpath.stat().st_size
        response.headers["X-Accel-Redirect"] = "/" + str(fpath)
    else:
        response = send_from_directory(app.config["FHOST_STORAGE_PATH"], f.sha256, mimetype = f.mime)

    response.headers["Content-Type"] = f.mime
    response.headers["Content-Disposition"] = f'attachment; filename="{f.getdownloadname()}"'
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def should_preview_file(f):
    return bool(f.mime and f.mime.startswith("text/"))


def should_render_markdown(f):
    return bool(f.ext and f.ext.lower() == ".md")


def should_preview_video(f):
    return bool(f.mime and f.mime.startswith("video/"))


def should_render_csv(f):
    return bool(f.ext and f.ext.lower().endswith(".csv"))


MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(?P<diagram>[\s\S]*?)\n```", re.IGNORECASE)
MERMAID_PLACEHOLDER_RE = re.compile(r"<p>MERMAID_BLOCK_(?P<index>\d+)</p>")


def extract_mermaid_blocks(content):
    diagrams = []

    def replace_block(match):
        diagrams.append(match.group("diagram"))
        return f"\n\nMERMAID_BLOCK_{len(diagrams) - 1}\n\n"

    return MERMAID_BLOCK_RE.sub(replace_block, content), diagrams


def render_markdown_with_mermaid(sanitized_html, diagrams):
    def replace_placeholder(match):
        diagram = diagrams[int(match.group("index"))]
        return '<div class="mermaid">{}</div>'.format(bleach.clean(diagram, tags=[], strip=True))

    return MERMAID_PLACEHOLDER_RE.sub(replace_placeholder, sanitized_html)


def render_markdown(content):
    markdown_source, mermaid_diagrams = extract_mermaid_blocks(content)
    rendered_html = markdown.markdown(
        markdown_source,
        extensions=["fenced_code", "tables"],
        output_format="html5",
    )
    sanitized_html = bleach.clean(
        rendered_html,
        tags=[
            "p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li",
            "blockquote", "pre", "code", "a", "strong", "em", "table", "thead",
            "tbody", "tr", "th", "td", "br", "hr", "img",
        ],
        attributes={
            "a": ["href", "title"],
            "img": ["src", "alt", "title"],
            "th": ["align"],
            "td": ["align"],
        },
        protocols=["http", "https", "mailto"],
        strip=True,
    )
    return Markup(render_markdown_with_mermaid(sanitized_html, mermaid_diagrams))


def build_markdown_preview_response(f, fpath):
    response = make_response(render_template(
        "markdown_preview.html",
        content=render_markdown(fpath.read_text(encoding="utf-8", errors="replace")),
        download_url=url_for("download", path=f.getname(), _external=True, _scheme="https"),
    ))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def build_preview_response(f, fpath):
    response = make_response(render_template(
        "preview.html",
        content=fpath.read_text(encoding="utf-8", errors="replace"),
        download_url=url_for("download", path=f.getname(), _external=True, _scheme="https"),
    ))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def build_video_preview_response(f, fpath):
    response = make_response(render_template(
        "video_preview.html",
        download_url=url_for("download", path=f.getname(), _external=True, _scheme="https"),
        mime=f.mime,
    ))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


CSV_BLOCK_ROWS = 200
CSV_TILE_COLS = 50
CSV_CELL_PREVIEW_CHARS = 50
CSV_MAX_LINE_BYTES = 4 * 1024 * 1024
CSV_INDEX_HEADER = struct.Struct("<QQQ")
CSV_INDEX_OFFSET = struct.Struct("<Q")
CSV_BOM = b"\xef\xbb\xbf"


def _csv_index_dir():
    return Path(app.config["FHOST_STORAGE_PATH"]) / ".csv-index"


def _write_csv_index(path, rows, cols, stopped, offsets):
    payload = CSV_INDEX_HEADER.pack(rows, cols, 1 if stopped else 0)
    payload += b"".join(CSV_INDEX_OFFSET.pack(off) for off in offsets)
    path.write_bytes(payload)


def _read_csv_index(path):
    data = path.read_bytes()
    rows, cols, stopped = CSV_INDEX_HEADER.unpack_from(data, 0)
    n = (len(data) - CSV_INDEX_HEADER.size) // CSV_INDEX_OFFSET.size
    offsets = [
        CSV_INDEX_OFFSET.unpack_from(data, CSV_INDEX_HEADER.size + i * CSV_INDEX_OFFSET.size)[0]
        for i in range(n)
    ]
    return rows, cols, bool(stopped), offsets


def _scan_csv_file(fpath):
    size = fpath.stat().st_size
    if size == 0:
        return 0, 0, False, []
    if size == 3 and fpath.read_bytes() == CSV_BOM:
        return 0, 0, False, []

    rows = 0
    cols = 0
    stopped = False
    offsets = []
    pos = 0
    first_line = True
    oversize = False

    def lines(raw):
        nonlocal pos, first_line, oversize
        while True:
            line = raw.readline()
            if not line:
                return
            if len(line) > CSV_MAX_LINE_BYTES:
                oversize = True
                return
            pos += len(line)
            text = line.decode("utf-8", "replace")
            if first_line:
                if text.startswith("\ufeff"):
                    text = text[1:]
                first_line = False
            # Python 3.14 treats a lone \r as an empty row; older csv raised Error.
            if "\r" in text and not text.endswith("\n"):
                raise csv.Error("CR line ending")
            yield text

    try:
        with open(fpath, "rb") as raw:
            reader = csv.reader(lines(raw))
            while True:
                start = pos
                try:
                    row = next(reader)
                except StopIteration:
                    break
                if oversize:
                    stopped = True
                    break
                if rows % CSV_BLOCK_ROWS == 0:
                    offsets.append(start)
                rows += 1
                if len(row) > cols:
                    cols = len(row)
            if oversize:
                stopped = True
    except csv.Error:
        stopped = True

    return rows, cols, stopped, offsets


def csv_index(fpath):
    index_path = _csv_index_dir() / fpath.name
    if index_path.is_file():
        rows, cols, stopped, _ = _read_csv_index(index_path)
        return rows, cols, stopped, index_path

    _csv_index_dir().mkdir(parents=True, exist_ok=True)

    try:
        raw = open(fpath, "rb")
    except FileNotFoundError:
        abort(404)

    try:
        fcntl.flock(raw.fileno(), fcntl.LOCK_EX)
        if index_path.is_file():
            rows, cols, stopped, _ = _read_csv_index(index_path)
            return rows, cols, stopped, index_path

        rows, cols, stopped, offsets = _scan_csv_file(fpath)
        # Name must be <sha256>.tmp-<pid>-<thread> so cleanup's split(".")[0] is the sha.
        tmp = _csv_index_dir() / "{}.tmp-{}-{}".format(fpath.name, os.getpid(), threading.get_ident())
        try:
            _write_csv_index(tmp, rows, cols, stopped, offsets)
            os.replace(str(tmp), str(index_path))
        except FileNotFoundError:
            abort(404)
        return rows, cols, stopped, index_path
    finally:
        raw.close()


def _parse_csv_from(fpath, offset, count, strip_bom):
    rows = []
    first_line = True

    def lines(raw):
        nonlocal first_line
        while True:
            line = raw.readline()
            if not line:
                return
            text = line.decode("utf-8", "replace")
            if first_line and strip_bom and text.startswith("\ufeff"):
                text = text[1:]
            first_line = False
            yield text

    with open(fpath, "rb") as raw:
        raw.seek(offset)
        reader = csv.reader(lines(raw))
        for _ in range(count):
            try:
                rows.append(next(reader))
            except (StopIteration, csv.Error):
                break
    return rows


def csv_rows(fpath, index_path, start_row, count):
    rows, cols, stopped, offsets = _read_csv_index(index_path)
    if start_row >= rows or count <= 0:
        return []
    block = start_row // CSV_BLOCK_ROWS
    skip = start_row % CSV_BLOCK_ROWS
    offset = offsets[block]
    parsed = _parse_csv_from(
        fpath, offset, skip + min(count, rows - start_row), strip_bom=(offset == 0)
    )
    return parsed[skip:]


def _csv_json(payload):
    response = make_response(json.dumps(payload, ensure_ascii=False))
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _csv_int_arg(name):
    if name not in request.args:
        return None
    raw = request.args[name]
    if not re.fullmatch(r"[0-9]+", raw):
        abort(400)
    return int(raw)


def build_csv_preview_response(f, fpath):
    try:
        rows, cols, stopped, _ = csv_index(fpath)
    except FileNotFoundError:
        abort(404)
    response = make_response(render_template(
        "csv_preview.html",
        rows=rows,
        cols=cols,
        stopped=stopped,
        download_url=url_for("download", path=f.getname(), _external=True, _scheme="https"),
        data_url=url_for("csv_data", path=f.getname()),
    ))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def lookup_file(path):
    path = Path(path.split("/", 1)[0])
    sufs = "".join(path.suffixes[-2:])
    name = path.name[:-len(sufs) or None]

    if sufs:
        f = File.query.filter_by(token=name).first()

        if f and f.ext == sufs:
            if f.removed:
                abort(451)

            fpath = Path(app.config["FHOST_STORAGE_PATH"]) / f.sha256

            if not fpath.is_file():
                abort(404)

            return f, fpath

    abort(404)


@app.route("/download/<path:path>")
def download(path):
    f, fpath = lookup_file(path)
    return build_file_response(f, fpath)


@app.route("/csv/<path:path>")
def csv_data(path):
    f, fpath = lookup_file(path)
    if not should_render_csv(f):
        abort(404)
    try:
        nrows, ncols, stopped, index_path = csv_index(fpath)
    except FileNotFoundError:
        abort(404)

    try:
        if "r" in request.args or "c" in request.args:
            r = _csv_int_arg("r")
            c = _csv_int_arg("c")
            if r is None or c is None:
                abort(400)
            if r >= nrows or c >= ncols:
                return _csv_json({"text": ""})
            row = csv_rows(fpath, index_path, r, 1)
            if not row or c >= len(row[0]):
                return _csv_json({"text": ""})
            return _csv_json({"text": row[0][c]})

        rb = _csv_int_arg("rb")
        cb = _csv_int_arg("cb")
        if rb is None or cb is None:
            abort(400)
        start = rb * CSV_BLOCK_ROWS
        if start >= nrows:
            return _csv_json({"rows": []})
        n = min(CSV_BLOCK_ROWS, nrows - start)
        col0 = cb * CSV_TILE_COLS
        if col0 >= ncols:
            return _csv_json({"rows": [[] for _ in range(n)]})
        parsed = csv_rows(fpath, index_path, start, n)
        out = []
        for row in parsed:
            slice_ = row[col0:col0 + CSV_TILE_COLS]
            out.append([cell[:CSV_CELL_PREVIEW_CHARS] for cell in slice_])
        return _csv_json({"rows": out})
    except FileNotFoundError:
        abort(404)


@app.route("/<path:path>")
def get(path):
    f, fpath = lookup_file(path)

    if should_render_markdown(f):
        return build_markdown_preview_response(f, fpath)

    if should_render_csv(f):
        return build_csv_preview_response(f, fpath)

    if should_preview_video(f):
        return build_video_preview_response(f, fpath)

    if should_preview_file(f):
        return build_preview_response(f, fpath)

    return build_file_response(f, fpath)

@app.route("/", methods=["GET", "POST"])
def fhost():
    if request.method == "POST":
        if "file" in request.files:
            return store_file(request.files["file"], request.remote_addr)

        abort(400)
    else:
        return render_template("index.html")

@app.route("/robots.txt")
def robots():
    return """User-agent: *
Disallow: /
"""

@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(411)
@app.errorhandler(413)
@app.errorhandler(414)
@app.errorhandler(415)
@app.errorhandler(451)
def ehandler(e):
    try:
        return render_template(f"{e.code}.html", id=id), e.code
    except TemplateNotFound:
        return "Segmentation fault\n", e.code
