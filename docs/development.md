# 0x0-Dockerized Development & Contributing Guide

This guide describes how to set up a local development environment, run the test suite, manage database migrations, and contribute changes to `0x0-dockerized`.

---

## 1. Prerequisites

- Python 3.10+ (Python 3.14 tested)
- `libmagic` (`libmagic1` and `libmagic-dev` on Debian/Ubuntu, or `file` package on Fedora/Alpine)
- SQLite3 (for local test runner)
- Docker & Docker Compose (for full-stack integration testing)

---

## 2. Local Environment Setup

### Setting Up the Test Virtual Environment

A persistent virtual environment should be configured at `~/.venvs/0x0`:

```bash
# Create the virtual environment
python3 -m venv ~/.venvs/0x0

# Prepare dependency list excluding deploy-only packages (uwsgi, psycopg2)
cat 0x0/requirements.txt <(grep -v -e '^-r' -e '^uwsgi' -e '^psycopg2' 0x0/requirements-dev.txt) \
  | grep -v -e '^uwsgi' -e '^psycopg2' > /tmp/reqs-0x0.txt

# Install dependencies
~/.venvs/0x0/bin/pip install -r /tmp/reqs-0x0.txt
```

---

## 3. Running Tests

Tests use an in-memory or temporary SQLite database configured dynamically in `0x0/tests/test_client.py`. No PostgreSQL instance is required for local unit testing.

### Execute All Tests
Always run pytest from the `0x0/` directory:

```bash
cd 0x0
~/.venvs/0x0/bin/python -m pytest tests/ -q
```

### Running Specific Tests
```bash
# Run tests matching a specific pattern
~/.venvs/0x0/bin/python -m pytest tests/test_client.py -k "video" -v

# Run with verbose output
~/.venvs/0x0/bin/python -m pytest tests/test_client.py -vv
```

---

## 4. Project Layout

```text
0x0-dockerized/
├── 0x0/                          # Flask application package
│   ├── instance/
│   │   └── config.py             # Instance configuration overrides
│   ├── migrations/               # Alembic database migration scripts
│   │   └── versions/             # Migration revision files
│   ├── templates/                # Server-rendered Jinja2 HTML templates
│   │   ├── index.html            # Landing / retention ASCII info page
│   │   ├── preview.html          # Plain text preview template
│   │   ├── markdown_preview.html # Markdown + Mermaid.js preview template
│   │   ├── video_preview.html    # Native HTML5 video player template
│   │   └── 404.html, etc.        # HTTP error pages
│   ├── tests/                    # Pytest test suite
│   │   └── test_client.py        # Upload, preview, download, and header tests
│   ├── cleanup.py                # Retention cleanup script
│   ├── Dockerfile                # App image build recipe
│   ├── fhost.py                  # Main Flask application entrypoint
│   ├── requirements.txt          # Production runtime dependencies
│   └── requirements-dev.txt      # Development & testing dependencies
├── data/                         # Persistent runtime data (untracked)
│   ├── db/                       # PostgreSQL data files
│   └── up/                       # Uploaded file payloads (keyed by SHA-256)
├── docs/                         # Technical documentation
│   ├── api.md                    # HTTP API specification
│   ├── architecture.md           # Architecture design & Mermaid diagrams
│   ├── runbook.md                # Deployment & Operations runbook
│   └── development.md            # Developer guide & test environment
├── source-of-truth/              # Master technical specifications
│   └── 0x0-dockerized-master-tech-spec.md
├── docker-compose.yml            # Docker Compose service definition
├── .env.example                  # Environment template
└── README.md                     # Repository overview & quick start
```

---

## 5. Database Migration Workflow

Database schema evolution is managed via Flask-Migrate (Alembic).

### Creating a New Migration
When modifying the `File` or `URL` models in `0x0/fhost.py`:

```bash
cd 0x0
export FLASK_APP=fhost
export DATABASE_URI="sqlite:///test.db"

~/.venvs/0x0/bin/flask db migrate -m "describe your changes"
```

Inspect the generated migration script under `0x0/migrations/versions/` and ensure both `upgrade()` and `downgrade()` handle SQLite and PostgreSQL compatibility.

### Applying Migrations Locally
```bash
~/.venvs/0x0/bin/flask db upgrade
```

---

## 6. Code Guidelines & Standards

1. **Keep Changes Narrow:** Preserve the single-file simplicity in `0x0/fhost.py` unless modularization is explicitly warranted.
2. **Deterministic MIME Sniffing:** When adding preview or handler logic, use byte-level magic inspection (`python-magic`), not client-declared headers alone.
3. **Security Headers:** Every new endpoint or preview builder MUST include `X-Content-Type-Options: nosniff`.
4. **HTML Sanitization:** Any user-provided content rendered into HTML must be processed through `bleach` or properly escaped.
5. **No Tracked Runtime Data:** Never commit files in `data/` or any `.env` secrets.
6. **Code Style:** Follow PEP 8 guidelines (4 spaces indentation, snake_case functions/variables, UPPER_CASE constants). Match surrounding style.

---

## 7. Submitting Changes

Before opening a pull request:
1. Run the test suite: `~/.venvs/0x0/bin/python -m pytest tests/ -q` (all tests must pass).
2. Test end-to-end in Docker Compose: `docker compose up -d --build` and verify upload/download via `curl`.
3. If new features or routes were added, add corresponding test cases in `0x0/tests/test_client.py`.
4. Update relevant documentation in `docs/` and `source-of-truth/0x0-dockerized-master-tech-spec.md`.
