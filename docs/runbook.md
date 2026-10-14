# 0x0-Dockerized Operations & Deployment Runbook

This runbook covers the operational procedures for deploying, maintaining, monitoring, backing up, and troubleshooting the `0x0-dockerized` service.

---

## 1. Prerequisites & Environment

### System Requirements
- Linux host (Ubuntu 22.04+, Debian 12+, RHEL/Rocky 9+, or similar)
- Docker Engine 24.0+ with Docker Compose v2.20+
- Host Reverse Proxy (Nginx, Caddy, Traefik, or Cloudflare Tunnel) for TLS/HTTPS termination
- Sufficient disk space under `./data/` for database and uploaded files

### Access Requirements
- SSH access with `sudo` or member of the `docker` group on the hosting server
- Access to DNS records for configuring public domain names

---

## 2. Initial Production Deployment

### Step 1: Clone Repository
```bash
git clone https://github.com/hattapauzi/0x0-dockerized.git /opt/0x0-dockerized
cd /opt/0x0-dockerized
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and generate a strong password:

```bash
cp .env.example .env
```

Edit `.env` and update values:
```ini
POSTGRES_DB=fhost
POSTGRES_USER=fhost
POSTGRES_PASSWORD=generate_a_strong_random_password_here
DATABASE_URI=postgresql://fhost:generate_a_strong_random_password_here@db/fhost
MAX_SIZE_MB=512
MAX_SIZE_NGINX=512M
# Generate a 32-byte (64-character hex) random secret:
# openssl rand -hex 32
FHOST_LINK_SECRET=generate_a_64_hex_secret_with_openssl
```

> [!IMPORTANT]
> - `FHOST_LINK_SECRET` is strictly required outside test mode. The application fails closed on startup (`RuntimeError`) if it is unset or empty.
> - Never commit `.env` or files inside `data/` to version control.

### Step 3: Build and Start Containers
```bash
docker compose up -d --build
```

Verify services are healthy:
```bash
docker compose ps
```
Both `0x0st` and `postgres` containers should report `Up` and `healthy`.

---

## 3. Reverse Proxy Configuration

The application container listens on host port `8081` (`8081:8080`). Set up a reverse proxy on port 80/443 with HTTPS.

### Option A: Nginx Reverse Proxy
Create `/etc/nginx/sites-available/0x0.conf`:

```nginx
server {
    listen 80;
    server_name files.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name files.example.com;

    ssl_certificate /etc/letsencrypt/live/files.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/files.example.com/privkey.pem;

    # Match or exceed MAX_SIZE_MB from .env
    client_max_body_size 512M;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Support streaming and range requests
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

Enable and reload Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/0x0.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Option B: Caddy Reverse Proxy
Add to your `/etc/caddy/Caddyfile`:

```caddy
files.example.com {
    request_body {
        max_size 512MB
    }
    reverse_proxy 127.0.0.1:8081 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

Reload Caddy:
```bash
sudo systemctl reload caddy
```

---

## 4. Verification & Smoke Testing

### Upload Verification
```bash
# Upload a test plain text file
curl -F'file=@0x0/README.rst' https://files.example.com/
```
Output is a 64-character hexadecimal HMAC-SHA256 URL, for example:  
`https://files.example.com/e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.rst`

### Retrieval Verification
```bash
# 1. Test preview retrieval
curl -i https://files.example.com/e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.rst

# 2. Test forced download with original filename
curl -i https://files.example.com/download/e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.rst
```

### CSV Preview Verification
```bash
# 1. Upload a CSV file
curl -F'file=@test.csv' https://files.example.com/

# 2. Test CSV table preview HTML page
curl -i https://files.example.com/<link>.csv

# 3. Test CSV tile JSON API
curl -i "https://files.example.com/csv/<link>.csv?rb=0&cb=0"
```

---

## 5. Maintenance & Retention Cleanup

Old files are subject to expiration based on the retention curve. Run the retention cleanup task regularly.

### Manual Cleanup
```bash
docker compose --profile maintenance run --rm cleanup
```

### Cleanup Operations Explained
Running `cleanup.py` executes two coordinated operations:
1. **Disk Retention Cleanup (`cleanup_expired`):** Computes retention per file size based on the non-linear cubic curve, deletes expired payloads from `data/up/`, and removes orphaned `.csv-index` cache files whose SHA-256 targets have expired.
2. **Database Data Minimization (`prune_rows`):**
   - Performs fresh `is_file()` stat checks against disk storage to prevent TOCTOU races with concurrent uploads.
   - Deletes database rows for unmoderated expired files (`removed=False`), ensuring uploader IP addresses (`addr`) and original filenames do not accumulate indefinitely. Logs `PRUNED_EXPIRED` actions to `file_audit`.
   - Scrubs uploader IP addresses (`addr = NULL`) on expired moderated files (`removed=True`), minimizing PII while retaining the minimal blocklist entry (`sha256, ext, original_name, link`) needed to return HTTP 451 on re-upload attempts. Logs `MODERATED_ADDR_SCRUBBED` actions to `file_audit`.

### Inspecting the Non-PII Audit Table (`file_audit`)
The append-only `file_audit` table tracks compliance, cleanup, and moderation events without storing user IP addresses or payload data:

```bash
docker compose exec db psql -U fhost -d fhost -c "SELECT id, sha256, link, action, created_at FROM file_audit ORDER BY id DESC LIMIT 25;"
```

Action types:
- `MODERATED`: File marked as removed by administrator.
- `PRUNED_EXPIRED`: Expired active database row deleted during retention cleanup.
- `MODERATED_ADDR_SCRUBBED`: Uploader IP address nulled on expired moderated row.

### Automated Cleanup via Systemd / Cron

#### Option A: Host Cron Job
Add to `/etc/cron.d/0x0-cleanup` (runs daily at 03:00 AM):
```cron
0 3 * * * root cd /opt/0x0-dockerized && /usr/bin/docker compose --profile maintenance run --rm cleanup > /var/log/0x0-cleanup.log 2>&1
```

#### Option B: Systemd Timer
Create `/etc/systemd/system/0x0-cleanup.service`:
```ini
[Unit]
Description=0x0 File Retention Cleanup
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/0x0-dockerized
ExecStart=/usr/bin/docker compose --profile maintenance run --rm cleanup
```

Create `/etc/systemd/system/0x0-cleanup.timer`:
```ini
[Unit]
Description=Run 0x0 File Retention Cleanup Daily

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable the timer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now 0x0-cleanup.timer
```

---

## 6. Backup & Disaster Recovery

### What to Back Up
1. `.env` file (contains database credentials and configuration).
2. `./data/up/` (uploaded file payloads).
3. PostgreSQL database dump (`fhost` database).

### Backup Procedure
Create a backup script `backup-0x0.sh`:

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/var/backups/0x0/$(date +%Y-%m-%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

cd /opt/0x0-dockerized

# 1. Backup .env
cp .env "$BACKUP_DIR/.env"

# 2. Dump PostgreSQL database
docker compose exec -T db pg_dump -U fhost fhost > "$BACKUP_DIR/fhost.sql"

# 3. Sync upload storage
rsync -av ./data/up/ "$BACKUP_DIR/up/"

# 4. Create compressed archive
tar -czf "$BACKUP_DIR.tar.gz" -C "/var/backups/0x0" "$(basename "$BACKUP_DIR")"
rm -rf "$BACKUP_DIR"

echo "Backup completed: $BACKUP_DIR.tar.gz"
```

### Restore Procedure
```bash
# 1. Stop app container
docker compose stop app

# 2. Extract backup data
tar -xzf /var/backups/0x0/2026-08-27_000000.tar.gz -C /tmp/

# 3. Restore files
rsync -av /tmp/2026-08-27_000000/up/ /opt/0x0-dockerized/data/up/
chown -R 1000:1000 /opt/0x0-dockerized/data/up/

# 4. Restore database
cat /tmp/2026-08-27_000000/fhost.sql | docker compose exec -T db psql -U fhost -d fhost

# 5. Start app container
docker compose start app
```

---

## 7. Updates & Upgrades

To update to a newer release:
```bash
cd /opt/0x0-dockerized
git pull origin master

# Rebuild images and restart containers
docker compose up -d --build

# Verify migrations ran
docker compose logs app | grep "Running upgrade"
```

---

## 8. Troubleshooting & Common Issues

### Issue 1: `413 Payload Too Large` during upload
**Cause:** Upload size exceeds either Flask's `MAX_SIZE_MB` or reverse proxy `client_max_body_size`.  
**Resolution:**
1. Check `.env`: ensure `MAX_SIZE_MB` is set appropriately.
2. Check Nginx/Caddy config: verify `client_max_body_size` and `proxy_request_buffering off`.
3. Restart stack: `docker compose up -d`.

### Issue 2: `502 Bad Gateway` on reverse proxy
**Cause:** `0x0st` container is not running or crashed.  
**Resolution:**
1. Inspect container logs: `docker compose logs app --tail=100`.
2. Check database connection: `docker compose exec db pg_isready -U fhost`.
3. Restart container: `docker compose restart app`.

### Issue 3: Permission denied on `data/up/`
**Cause:** Storage directory owned by incorrect UID.  
**Resolution:**
```bash
sudo chown -R 1000:1000 ./data/up
docker compose restart app
```

### Issue 4: Database migration failure
**Cause:** Incompatible schema state or locked table.  
**Resolution:**
```bash
# Inspect current revision
docker compose exec app flask db current

# Manually trigger upgrade
docker compose exec app flask db upgrade
```

### Issue 5: Container fails on startup with `FHOST_LINK_SECRET is required outside testing mode`
**Cause:** `FHOST_LINK_SECRET` is missing, blank, or not passed into the container environment.  
**Resolution:**
1. Check `.env`: ensure `FHOST_LINK_SECRET` is set to a 64-hex string (`openssl rand -hex 32`).
2. Verify `docker-compose.yml` passes `FHOST_LINK_SECRET: "${FHOST_LINK_SECRET}"` to both `app` and `cleanup` services.
3. Re-launch stack: `docker compose up -d`.

### Issue 6: PostgreSQL driver URL compatibility
**Cause:** SQLAlchemy 2.x standard `postgresql://` URL expects `psycopg` (v3) by default, while production uses `psycopg2`.  
**Resolution:**
`0x0/instance/config.py` automatically detects when `psycopg` is absent and translates `postgresql://` URIs to `postgresql+psycopg2://`. If using a custom Python environment outside Docker, ensure `psycopg2` (or `psycopg2-binary`) is installed.

---

## 9. Rollback Procedure

If a deployment or upgrade fails:

```bash
# 1. Rollback code to previous git commit/tag
git checkout <previous-stable-tag-or-commit>

# 2. If database migration was applied, downgrade revision
# NOTE: If new uploads occurred since upgrading to revision b2c3d4e5f6a7 (which have token IS NULL),
# the downgrade script will safely refuse to execute to prevent unintended data loss.
# To proceed, restore the pre-upgrade PostgreSQL backup or delete new rows:
# docker compose exec db psql -U fhost -d fhost -c "DELETE FROM file WHERE token IS NULL;"
docker compose exec app flask db downgrade

# 3. Rebuild and restart
docker compose up -d --build
```

---

## 10. Secret Key Incident Response & Rotation

The `FHOST_LINK_SECRET` environment variable controls HMAC derivation:
`link = HMAC-SHA256(secret, sha256\0ext\0original_name)`

### Routine Secret Rotation
Because canonical links are persisted in the `file.link` column:
- Rotating `FHOST_LINK_SECRET` in `.env` causes subsequent uploads to derive links from the new secret.
- **Existing links do not break:** Lookups query `file.link` directly, so URLs created under the previous secret remain valid and fully functional.

### Compromise / Leak Incident Response
If `FHOST_LINK_SECRET` is compromised by an attacker:
1. The attacker can perform offline dictionary existence checks against known file hashes.
2. **Remediation Steps:**
   1. Generate a fresh secret: `openssl rand -hex 32` and update `FHOST_LINK_SECRET` in `.env`.
   2. Restart services: `docker compose up -d`.
   3. Recompute canonical links for existing rows using a Python maintenance script inside the container:
      ```bash
      docker compose exec app python -c '
      import hmac, hashlib
      from fhost import app, db, File

      secret = app.config["FHOST_LINK_SECRET"].encode("utf-8")
      with app.app_context():
          for f in File.query.all():
              msg = f"{f.sha256}\0{f.ext or \"\"}\0{f.original_name or \"\"}".encode("utf-8")
              f.link = hmac.new(secret, msg, hashlib.sha256).hexdigest()
          db.session.commit()
      print("Successfully re-derived canonical links.")
      '
      ```
   4. **Impact Notice:** Re-deriving links changes the canonical URL of all existing hosted files. Any previously distributed URLs will no longer resolve unless re-shared.
