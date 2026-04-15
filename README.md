# 0x0 Dockerized

Public-facing deployment wrapper for the `0x0/` Flask file host. This version is hardened for direct file uploads and file retrieval only.

## ⚠️ Hardening Changes ⚠️

Compared with the upstream app behavior, this branch is intentionally narrower and more explicit about its public deployment posture:

- direct file uploads are supported
- uploaded files are retrievable through short hosted URLs
- remote URL import is disabled
- generic external URL shortening is disabled
- active web payloads such as HTML, SVG, and XML are rejected
- served files are returned as attachments with `X-Content-Type-Options: nosniff`
- Docker Compose now uses local image builds and `.env`-driven secrets instead of committed credentials and floating app images

This makes the service safer for self-hosted public exposure, but it is still a simple public file host, not a full storage platform with user accounts, quotas, abuse workflows, or object-storage offload.

## Prerequisites

- Docker Engine with Compose support
- A public domain or reverse proxy in front of port `80`
- Strong credentials stored in a local `.env` file

## Initial Setup

```bash
cp .env.example .env
```

Set strong values for:

- `POSTGRES_PASSWORD`
- `DATABASE_URI`
- optional upload limits `MAX_SIZE_MB` and `MAX_SIZE_NGINX`

## Start the Stack

```bash
docker compose up -d --build
```

The app container runs `flask db upgrade` on startup before launching uWSGI. nginx serves public traffic and uses `X-Accel-Redirect` for uploaded files.

## Public Scope

This deployment is for file hosting only. Users can upload a file and receive a short hosted link back. They cannot ask the server to fetch remote URLs, and they cannot use the service as a generic redirect shortener.

## Smoke Test

Upload a file directly to the host:

```bash
curl -F'file=@0x0/README.rst' http://localhost/
```

The response should be a short file URL such as `http://localhost/E.txt`. Open that URL from a second client to verify retrieval works externally.

## Maintenance

Run the cleanup job manually or from host cron:

```bash
docker compose --profile maintenance run --rm cleanup
```

Uploaded data lives under `data/up/` and PostgreSQL data lives under `data/db/`. Do not commit `.env` or anything under `data/`.

## Notes

- This stack currently serves HTTP on port `80`. For real internet exposure, place it behind HTTPS or extend nginx with TLS certificates.
- PostgreSQL is intended to stay internal to the Compose network and should not be exposed publicly.
