# 0x0 Dockerized

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![License: EUPL 1.2](https://img.shields.io/badge/License-EUPL%201.2-blue.svg)](https://joinup.ec.europa.eu/software/page/eupl)

A hardened, lightweight, self-hosted file hosting service built on top of [0x0 / The Null Pointer](https://0x0.st). Packaged with Docker Compose, PostgreSQL persistence, and automatic retention cleanup.

---

## ✨ Features & Hardening

- **Fast & Direct Uploads:** Simple `multipart/form-data` uploads via `curl`, browser, or scripts.
- **Deterministic HMAC-SHA256 Links:** Canonical public URLs use 64-character hexadecimal HMAC-SHA256 digests derived from a server secret, file hash, extension, and original filename. This prevents enumeration, protects against offline dictionary attacks, and deduplicates identical uploads.
- **Legacy URL Support:** Legacy 12-character random tokens are permanently redirected (`301 Moved Permanently`) to their canonical 64-hex URLs, maintaining backward compatibility.
- **Smart Browser Previews:**
  - **Markdown (`.md`):** Server-rendered Markdown with Bleach HTML sanitization, table formatting, and client-side **Mermaid diagram rendering**.
  - **CSV (`.csv`):** Interactive virtualized table preview grid with on-disk block seeking (`.csv-index`), row and column jump boxes, adaptive column widths, and a paginated JSON tile/cell API (`GET /csv/`).
  - **Video (`video/*`):** Standalone preview with native HTML5 `<video>` player and HTTP byte range-seeking support (`206 Partial Content`).
  - **Plain Text (`text/*`):** Clean `<pre>`-formatted browser preview.
- **Filename Preservation:** Original uploaded filenames are preserved when downloading via the `/download/` route or direct binary links.
- **Smart Deduplication & Privacy:** Identical uploads (matching bytes, extension, and original filename) deduplicate to the same canonical link and touch storage to refresh retention without inserting duplicate rows. Distinct filenames for identical bytes derive distinct links pointing to the same deduplicated storage payload (`data/up/<sha256>`).
- **Dynamic Retention & Data Minimization:** Sliding-scale retention policy from 30 days (max file size) up to 365 days (small files). Retention cleanup prunes expired database rows and disk files, scrubs uploader IP addresses on moderated records, and logs compliance events to a zero-PII `file_audit` table.
- **Security Hardened:**
  - Server secret (`FHOST_LINK_SECRET`) strictly required outside test mode.
  - Moderated content checks return `451 Unavailable For Legal Reasons` immediately on re-upload.
  - Active web payloads (HTML, SVG, XML, Java archives, Windows executables) are blocked by default (`415 Unsupported Media Type`).
  - Remote URL import and generic URL shortening are disabled.
  - `X-Content-Type-Options: nosniff` sent on all responses.
  - Application runs as an unprivileged user (`app`, UID/GID 1000).

---

## 🚀 Quick Start (< 5 Minutes)

### 1. Clone & Configure
```bash
git clone https://github.com/hattapauzi/0x0-dockerized.git
cd 0x0-dockerized

cp .env.example .env
```

Edit `.env` and set a strong database password and HMAC secret key:
```ini
POSTGRES_DB=fhost
POSTGRES_USER=fhost
POSTGRES_PASSWORD=your_secure_password_here
DATABASE_URI=postgresql://fhost:your_secure_password_here@db/fhost
MAX_SIZE_MB=512
MAX_SIZE_NGINX=512M
# Generate a 32-byte (64-character hex) random secret:
# openssl rand -hex 32
FHOST_LINK_SECRET=your_secure_random_64_hex_secret_here
```

### 2. Start the Stack
```bash
docker compose up -d --build
```

The application runs on host port **`8081`** (`8081:8080`). Database migrations run automatically on startup.

### 3. Smoke Test
Upload a test file using `curl`:
```bash
curl -F'file=@0x0/README.rst' http://localhost:8081/
```

**Output:**
```text
https://localhost/e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.rst
```

---

## 📖 Usage & API Quick Reference

### Uploading Files
```bash
# Upload a file
curl -F'file=@image.png' https://your-domain.example/

# Upload with a specific filename
curl -F'file=@document.md;filename=architecture-spec.md' https://your-domain.example/
```

### Retrieving & Downloading Files
- **View / Preview:** `GET /<link><ext>` (e.g., `https://your-domain.example/e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.md`)
  - `.md` files render a Markdown preview with Mermaid diagrams and a top Download link.
  - `.csv` files render an interactive virtualized CSV table preview with jump boxes and a top Download link.
  - `video/*` files render an HTML5 video playback preview.
  - `text/*` files render a plain text preview.
  - Binary/media files download directly as attachments.
  - Legacy URLs (`GET /<token><ext>`) automatically return `301 Moved Permanently` to the canonical link.
- **Forced Download:** `GET /download/<link><ext>` (e.g., `https://your-domain.example/download/e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.md`)
  - Bypasses preview pages and downloads the file with its original filename preserved in `Content-Disposition`.
- **CSV Data Tiles:** `GET /csv/<link><ext>?rb=0&cb=0` (or `?r=0&c=0` for cell inspection)
  - Returns paginated 200×50 JSON cell matrices for the virtualized CSV table preview.

For the complete API specification, see **[API Documentation](docs/api.md)**.

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `FHOST_LINK_SECRET` | *None (Required)* | 32-byte hex secret (`openssl rand -hex 32`) used for HMAC-SHA256 link derivation. Application fails closed on startup if unset. |
| `DATABASE_URI` | `postgresql://fhost:...@db/fhost` | SQLAlchemy connection string (supports `postgresql://` with automatic `psycopg2` fallback). |
| `POSTGRES_DB` | `fhost` | PostgreSQL database name |
| `POSTGRES_USER` | `fhost` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `change-me` | PostgreSQL user password |
| `MAX_SIZE_MB` | `512` | Max upload size in megabytes |
| `PREFERRED_URL_SCHEME`| `https` | URL scheme used for generated public links |
| `FHOST_TOKEN_LENGTH` | `12` | Length of generated legacy random tokens (legacy mode) |

---

## 🛠️ Maintenance & Retention Cleanup

Run the cleanup job manually or via cron to prune files exceeding the retention duration and minimize database records:

```bash
docker compose --profile maintenance run --rm cleanup
```

The maintenance worker executes:
1. **Disk Retention Cleanup (`cleanup_expired`):** Deletes expired payloads from disk and clears orphaned `.csv-index` cache files.
2. **Database Data Minimization (`prune_rows`):** Deletes database rows for unmoderated expired files, scrubs uploader IP addresses (`addr = NULL`) on moderated records, and logs non-PII compliance events in `file_audit`.

See **[Operations Runbook](docs/runbook.md)** for automated cron / systemd timer setup, backup procedures, audit table inspection, secret rotation, and reverse proxy templates (Nginx & Caddy).

---

## 🧪 Local Development & Testing

A local virtual environment can be configured to run tests without starting Docker:

```bash
cd 0x0
~/.venvs/0x0/bin/python -m pytest tests/ -q
```

For full setup instructions, see **[Development Guide](docs/development.md)** and **[Contributing Guide](CONTRIBUTING.md)**.

---

## 📚 Documentation Index

- **[API Reference](docs/api.md):** Complete HTTP endpoint documentation, CSV tile API, status codes, and examples.
- **[Architecture & Design](docs/architecture.md):** Architecture diagrams, HMAC-SHA256 link derivation, CSV indexing, deduplication, and security models.
- **[Operations Runbook](docs/runbook.md):** Production deployment, Nginx/Caddy proxy setup, backups, audit table queries, secret rotation, and troubleshooting.
- **[Development & Testing](docs/development.md):** Local virtualenv setup, pytest suite, Playwright browser tests, and database migrations.

---

## 📄 License

Licensed under the **EUPL, Version 1.2** (or subsequent approved versions). See [LICENSE](0x0/LICENSE) for details.
