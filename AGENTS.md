# Repository Guidelines

## Project Structure & Module Organization
This repository packages the `0x0` Flask file host with Docker, PostgreSQL, and nginx. Core application code lives in `0x0/`: `fhost.py` is the main app entrypoint, `instance/config.py` holds environment-backed settings, `migrations/` contains Alembic files, `templates/` contains default pages, and `tests/` contains pytest coverage. Container orchestration lives at the repo root in `docker-compose.yml`. Web proxy assets live in `nginx/`.

## Build, Test, and Development Commands
- `docker compose up -d`: start the app, database, and nginx stack from the compose file.
- `docker compose logs -f app nginx db`: follow service logs while testing uploads or proxy behavior.
- `docker build -t 0x0-app ./0x0`: build the Flask/uWSGI image from local source.
- `docker build -t 0x0-nginx ./nginx`: build the nginx image with the bundled config.
- `cd 0x0 && FLASK_APP=fhost flask db upgrade`: apply Alembic migrations before first run.
- `cd 0x0 && pytest -q`: run the automated test suite in `0x0/tests/test_client.py`.

## Coding Style & Naming Conventions
Follow the existing Python style in `0x0/`: 4-space indentation, snake_case for functions and variables, and concise Flask-oriented modules. Keep configuration keys uppercase in `instance/config.py`. Preserve the current layout for templates and migrations instead of introducing new top-level folders. No formatter or linter is configured here, so match the surrounding code closely and keep imports and whitespace tidy.

## Testing Guidelines
Tests use `pytest` with Flask’s test client and temporary SQLite storage. Add new tests under `0x0/tests/` and prefer `test_<behavior>.py` or `test_<feature>()` naming. Cover routing, upload validation, and migration-sensitive changes whenever behavior changes.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commit prefixes such as `feat:`, `fix(nginx):`, `chore:`, and `style:`. Keep subjects imperative and scoped when useful. Pull requests should explain the behavioral change, list any config or migration impact, link the relevant issue, and include curl output or screenshots when nginx pages or upload flows change.

## Configuration & Operations Notes
Keep `DATABASE_URI`, upload limits, and storage paths environment-driven. When changing upload size or proxy behavior, update both `docker-compose.yml` and nginx settings together. Do not commit real uploaded data or secrets.
