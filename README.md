# 0x0 Dockerized

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![License: EUPL 1.2](https://img.shields.io/badge/License-EUPL%201.2-blue.svg)](https://joinup.ec.europa.eu/software/page/eupl)

A hardened, lightweight, self-hosted file hosting service built on top of [0x0 / The Null Pointer](https://0x0.st). Packaged with Docker Compose, PostgreSQL persistence, and automatic retention cleanup.

---

## ✨ Features & Hardening

- **Fast & Direct Uploads:** Simple `multipart/form-data` uploads via `curl`, browser, or scripts.
- **Random URL Tokens:** 12-character URL-safe random tokens (`64^12` combinations) replacing sequential IDs.
- **Smart Browser Previews:**
  - **Markdown (`.md`):** Server-rendered Markdown with Bleach HTML sanitization, table formatting, and client-side **Mermaid diagram rendering**.
  - **Video (`video/*`):** Standalone preview with native HTML5 `<video>` player and range-seeking support.
  - **Plain Text (`text/*`):** Clean `<pre>`-formatted browser preview.
- **Filename Preservation:** Original uploaded filenames are preserved when downloading via the `/download/` route or direct links.
- **Storage Deduplication:** Content is stored by SHA-256 digest on disk to save space while maintaining distinct URL tokens per upload.
- **Dynamic Retention:** Sliding-scale retention policy from 30 days (max file size) up to 365 days (small files).
- **Security Hardened:**
  - Active web payloads (HTML, SVG, XML, Java archives, Windows executables) are blocked by default.
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

Edit `.env` and set a strong database password:
```ini
POSTGRES_DB=fhost
POSTGRES_USER=fhost
POSTGRES_PASSWORD=your_secure_password_here
DATABASE_URI=postgresql://fhost:your_secure_password_here@db/fhost
MAX_SIZE_MB=512
MAX_SIZE_NGINX=512M
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
https://localhost/aK7mQ2xPdL8N.rst
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
- **View / Preview:** `GET /<token><ext>` (e.g., `https://your-domain.example/aK7mQ2xPdL8N.md`)
  - `.md` files render a Markdown preview with Mermaid diagrams and a top Download link.
  - `video/*` files render an HTML5 video playback preview.
  - `text/*` files render a plain text preview.
  - Binary/media files download directly as attachments.
- **Forced Download:** `GET /download/<token><ext>` (e.g., `https://your-domain.example/download/aK7mQ2xPdL8N.md`)
  - Bypasses preview pages and downloads the file with its original filename preserved in `Content-Disposition`.

For the complete API specification, see **[API Documentation](docs/api.md)**.

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URI` | `postgresql://fhost:...@db/fhost` | SQLAlchemy connection string |
| `POSTGRES_DB` | `fhost` | PostgreSQL database name |
| `POSTGRES_USER` | `fhost` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `change-me` | PostgreSQL user password |
| `MAX_SIZE_MB` | `512` | Max upload size in megabytes |
| `PREFERRED_URL_SCHEME`| `https` | URL scheme used for generated public links |
| `FHOST_TOKEN_LENGTH` | `12` | Length of generated random URL tokens |

---

## 🛠️ Maintenance & Retention Cleanup

Run the cleanup job manually or via cron to prune files exceeding the retention duration:

```bash
docker compose --profile maintenance run --rm cleanup
```

See **[Operations Runbook](docs/runbook.md)** for automated cron / systemd timer setup, backup procedures, and reverse proxy templates (Nginx & Caddy).

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

- **[API Reference](docs/api.md):** Complete HTTP endpoint documentation, status codes, and examples.
- **[Architecture & Design](docs/architecture.md):** Architecture diagrams, token generation, deduplication, and security models.
- **[Operations Runbook](docs/runbook.md):** Production deployment, Nginx/Caddy proxy setup, backups, and troubleshooting.
- **[Development & Testing](docs/development.md):** Local virtualenv setup, pytest suite, and database migrations.
- **[Master Technical Specification](source-of-truth/0x0-dockerized-master-tech-spec.md):** Source of truth technical specification.

---

## 📄 License

Licensed under the **EUPL, Version 1.2** (or subsequent approved versions). See [LICENSE](0x0/LICENSE) for details.
