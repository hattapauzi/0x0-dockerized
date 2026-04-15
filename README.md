# 0x0 Dockerized

Public-facing deployment wrapper for the `0x0/` Flask file host. This version is hardened for direct file uploads and file retrieval only.

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
