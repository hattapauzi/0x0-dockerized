The Null Pointer (0x0 Application Package)
===========================================

This directory contains the core Flask application package for 0x0-dockerized.

For the primary Docker-based deployment, architecture, and operational runbook, see the repository root `README.md` and the `docs/` directory.

Features in this Package
------------------------

* **Direct Uploads & Retrieval:** Lightweight HTTP file host running under uWSGI / Flask.
* **Deterministic HMAC-SHA256 Links:** Public canonical URLs use 64-character hexadecimal HMAC-SHA256 digests derived from a server secret, file hash, extension, and original filename. Legacy 12-character tokens return HTTP 301 redirects to canonical links.
* **Preview Handlers:**
  - Server-rendered Markdown preview (`.md`) with Bleach sanitization and Mermaid diagram rendering.
  - Interactive virtualized CSV table preview (`.csv`) with on-disk block seeking (`.csv-index`), row/col jump boxes, and a paginated JSON tile/cell API (`GET /csv/`).
  - Video playback preview (`video/*`) with native HTML5 player and HTTP byte range seeking support (`206 Partial Content`).
  - Plain text preview (`text/*`).
* **Original Filename Preservation:** Retains original filenames for attachment downloads via `/download/<link><ext>`.
* **Content-Addressed Storage & Deduplication:** Storage deduplication by SHA-256 digest in `up/`. Duplicate uploads of the same file and filename reuse the canonical link and touch storage to refresh retention.
* **Data Minimization:** Automated pruning of expired database records and address scrubbing on moderated rows, logged to a zero-PII `file_audit` table.

Configuration
-------------

To change settings, modify `instance/config.py` or set environment variables:
* ``FHOST_LINK_SECRET``: 32-byte hex secret key (e.g. via ``openssl rand -hex 32``). Strictly required outside testing mode.
* ``DATABASE_URI``: SQLAlchemy database connection URI (supports ``postgresql://`` with automatic fallback to ``psycopg2``).
* ``MAX_SIZE``: Maximum upload size in megabytes.

To customize the home and error pages, create a `templates` directory in your instance directory and copy any templates you want to modify there.

Retention & Cleanup
-------------------

To expire files based on the dynamic retention curve and minimize database rows, run `python cleanup.py` periodically (or via the Docker Compose `cleanup` maintenance profile):
1. **Disk Cleanup (``cleanup_expired``):** Deletes expired storage payloads from disk and cleans up orphan ``.csv-index`` scan files.
2. **Database Minimization (``prune_rows``):** Prunes expired unmoderated database rows and scrubs uploader IP addresses on moderated records, logging non-PII events to ``file_audit``.

Development & Testing
---------------------

Local development virtual environment setup:

::

    python3 -m venv ~/.venvs/0x0
    cat requirements.txt <(grep -v -e '^-r' -e '^uwsgi' -e '^psycopg2' requirements-dev.txt) \
      | grep -v -e '^uwsgi' -e '^psycopg2' > /tmp/reqs-0x0.txt
    ~/.venvs/0x0/bin/pip install -r /tmp/reqs-0x0.txt
    ~/.venvs/0x0/bin/python -m playwright install chromium

Run the test suite from inside this directory:

::

    ~/.venvs/0x0/bin/python -m pytest tests/ -q

For complete documentation, see `docs/development.md` and `docs/api.md` in the repository root.
