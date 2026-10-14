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

# Install Chromium for CSV preview browser regression tests
~/.venvs/0x0/bin/python -m playwright install chromium
```

---

## 3. Running Tests

Tests use an in-memory or temporary SQLite database configured dynamically in `0x0/tests/test_client.py`. The test fixture automatically configures `FHOST_LINK_SECRET = "test-secret"`. No PostgreSQL instance is required for local unit testing.

### Execute All Tests
Always run pytest from the `0x0/` directory:

```bash
cd 0x0
~/.venvs/0x0/bin/python -m pytest tests/ -q
```

All 67 tests across uploads, HMAC derivation, CSV indexing and virtualization, Markdown, Video, and retention pruning should pass cleanly.

### Running Specific Tests
```bash
# Run HMAC link derivation & deduplication tests
~/.venvs/0x0/bin/python -m pytest tests/test_client.py -k "hmac or legacy" -v

# Run CSV table preview and tile API tests
~/.venvs/0x0/bin/python -m pytest tests/test_client.py -k "csv" -v

# Run Video player tests
~/.venvs/0x0/bin/python -m pytest tests/test_client.py -k "video" -v

# Run Retention and audit cleanup tests
~/.venvs/0x0/bin/python -m pytest tests/test_client.py -k "prune or cleanup" -v
```

---

## 4. Project Layout

```text
0x0-dockerized/
├── 0x0/                          # Flask application package
│   ├── instance/
│   │   └── config.py             # Instance configuration overrides & driver fallback
│   ├── migrations/               # Alembic database migration scripts
│   │   └── versions/             # Migration revision files (0d5b8c4b9f0d, a1b2c3d4e5f6, b2c3d4e5f6a7)
│   ├── templates/                # Server-rendered Jinja2 HTML templates
│   │   ├── index.html            # Landing / retention ASCII info page
│   │   ├── preview.html          # Plain text preview template
│   │   ├── markdown_preview.html # Markdown + Mermaid.js preview template
│   │   ├── video_preview.html    # Native HTML5 video player template
│   │   ├── csv_preview.html      # Virtualized CSV table preview template
│   │   └── 404.html, etc.        # HTTP error pages
│   ├── tests/                    # Pytest test suite
│   │   └── test_client.py        # 67 comprehensive unit & integration tests
│   ├── cleanup.py                # Retention cleanup (storage) and prune_rows (DB minimization)
│   ├── Dockerfile                # App image build recipe
│   ├── fhost.py                  # Main Flask application entrypoint & routing
│   ├── requirements.txt          # Production runtime dependencies
│   └── requirements-dev.txt      # Development & testing dependencies (pytest, playwright)
├── data/                         # Persistent runtime data (untracked)
│   ├── db/                       # PostgreSQL data files
│   └── up/                       # Uploaded file payloads (keyed by SHA-256)
│       └── .csv-index/           # Binary block offset indexes for fast CSV seeking
├── docs/                         # Technical documentation
│   ├── api.md                    # HTTP API specification
│   ├── architecture.md           # Architecture design & Mermaid diagrams
│   ├── runbook.md                # Deployment & Operations runbook
│   └── development.md            # Developer guide & test environment
├── docker-compose.yml            # Docker Compose service definition
├── .env.example                  # Environment template
└── README.md                     # Repository overview & quick start
```

---

## 5. Database Migration Workflow

Database schema evolution is managed via Flask-Migrate (Alembic).

### Creating a New Migration
When modifying models (`File`, `FileAudit`, or `URL`) in `0x0/fhost.py`:

```bash
cd 0x0
export FLASK_APP=fhost
export DATABASE_URI="sqlite:///test.db"
export FHOST_LINK_SECRET="test-secret"

~/.venvs/0x0/bin/flask db migrate -m "describe your changes"
```

Inspect the generated migration script under `0x0/migrations/versions/`. Ensure:
- Both `upgrade()` and `downgrade()` handle SQLite and PostgreSQL compatibility (`op.batch_alter_table`).
- Backfills safely read `current_app.config.get("FHOST_LINK_SECRET")`.
- Partial indexes use `postgresql_where` and `sqlite_where`.

### Applying Migrations Locally
```bash
~/.venvs/0x0/bin/flask db upgrade
```

---

## 6. Code Guidelines & Standards

1. **Keep Changes Narrow:** Preserve the single-file simplicity in `0x0/fhost.py` unless modularization is explicitly warranted.
2. **Deterministic MIME Sniffing:** When adding preview or handler logic, use byte-level magic inspection (`python-magic`), not client-declared headers alone.
3. **Secret Enforcement:** Any code deriving links must use `make_link(...)` with `FHOST_LINK_SECRET`. The application must fail closed outside testing if the secret is absent.
4. **Data Minimization & Zero PII:** Never write user IP addresses (`addr`), query strings, or personal data to `file_audit` or permanent audit trails.
5. **Security Headers:** Every new endpoint or preview builder MUST include `X-Content-Type-Options: nosniff`.
6. **HTML Sanitization:** Any user-provided content rendered into HTML must be processed through `bleach` or properly escaped.
7. **No Tracked Runtime Data:** Never commit files in `data/` or any `.env` secrets.
8. **Code Style:** Follow PEP 8 guidelines (4 spaces indentation, snake_case functions/variables, UPPER_CASE constants). Match surrounding style.

---

## 7. Submitting Changes

Before opening a pull request:
1. Run the test suite: `cd 0x0 && ~/.venvs/0x0/bin/python -m pytest tests/ -q` (all 67 tests must pass).
2. Test end-to-end in Docker Compose: `docker compose up -d --build` and verify upload/download via `curl`.
3. If new features or routes were added, add corresponding test cases in `0x0/tests/test_client.py`.
4. **Branch & Documentation Policy:** Keep feature working documentation, specs, and plans on a dedicated `docs/...` branch. Do not merge feature docs branches into `master`; only merge the implementation branch (`feat/...` or `fix/...`), leaving the docs branch behind, and reference the docs branch in the merge commit message.

