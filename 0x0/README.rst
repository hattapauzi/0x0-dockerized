The Null Pointer (0x0 Application Package)
===========================================

This directory contains the core Flask application package for 0x0-dockerized.

For the primary Docker-based deployment, architecture, and operational runbook, see the repository root `README.md` and the `docs/` directory.

Features in this Package
------------------------

* **Direct Uploads & Retrieval:** Lightweight HTTP file host running under uWSGI / Flask.
* **Random 12-character Tokens:** Unique unguessable URLs for hosted files.
* **Preview Handlers:**
  - Server-rendered Markdown preview (`.md`) with Bleach sanitization and Mermaid diagram rendering.
  - Video preview (`video/*`) with native HTML5 player and HTTP Range seeking support.
  - Plain text preview (`text/*`).
* **Original Filename Preservation:** Retains original filenames for attachment downloads via `/download/<token><ext>`.
* **Content-Addressed Storage:** Storage deduplication by SHA-256 digest in `up/`.

Configuration
-------------

To change settings, modify `instance/config.py`. For more information on instance configuration, see the `Flask documentation <https://flask.palletsprojects.com/en/2.0.x/config/#instance-folders>`_.

To customize the home and error pages, create a `templates` directory in your instance directory and copy any templates you want to modify there.

Retention & Cleanup
-------------------

To expire files based on the dynamic retention curve, run `python cleanup.py` periodically (or via the Docker Compose `cleanup` maintenance profile).

Development & Testing
---------------------

Local development virtual environment setup:

::

    python3 -m venv ~/.venvs/0x0
    cat requirements.txt <(grep -v -e '^-r' -e '^uwsgi' -e '^psycopg2' requirements-dev.txt) \
      | grep -v -e '^uwsgi' -e '^psycopg2' > /tmp/reqs-0x0.txt
    ~/.venvs/0x0/bin/pip install -r /tmp/reqs-0x0.txt

Run the test suite from inside this directory:

::

    ~/.venvs/0x0/bin/python -m pytest tests/ -q

For complete documentation, see `docs/development.md` and `docs/api.md` in the repository root.
