# Public File Host Hardening Implementation Plan

**Goal:** turn this repository into a stable public-facing file host for direct uploads only, with reproducible local tests and safer deployment defaults.

**Architecture:** keep the existing Flask app + PostgreSQL + nginx layout, but narrow the product surface to direct file uploads and file retrieval only. Remove remote URL import and generic URL-shortening behavior, harden upload/serve behavior for public exposure, and replace fragile deployment defaults with explicit local builds, env-driven secrets, and predictable maintenance tasks. Execute implementation in an in-repo `.worktrees/` worktree and use a fork-first workflow.

## Task 0: Prepare isolated fork-first workspace

- Verify the current branch and worktree prerequisites.
- Ignore `.worktrees/` in `.gitignore`.
- Create `.worktrees/public-file-host-hardening` with branch `public-file-host-hardening`.
- Create a writable GitHub fork remote named `fork`.
- Keep the upstream repo read-only and do not open an upstream pull request.

## Task 1: Make local installs and tests reproducible

Files:
- `0x0/requirements-dev.txt`
- `0x0/README.rst`
- `0x0/tests/test_client.py`

Steps:
- Confirm `python -m pytest -q` fails before dependencies are installed.
- Add `requirements-dev.txt` with:

```txt
-r requirements.txt
pytest
```

- Document a local venv-based workflow in `0x0/README.rst`.
- Ensure tests can import the app under current Flask-SQLAlchemy behavior by setting the database env before importing `fhost` in the test fixture.
- Verify the suite passes from an isolated venv.

## Task 2: Remove non-file-host behaviors from the public API

Files:
- `0x0/fhost.py`
- `0x0/templates/index.html`
- `0x0/tests/test_client.py`
- `0x0/README.rst`

Steps:
- Add failing tests showing `url` import and `shorten` are rejected.
- Remove the `url` and `shorten` POST branches so the public API accepts direct file uploads only.
- Update the homepage and README text to describe direct file uploads and retrieval only.
- Re-run focused tests and the full file-host suite.

## Task 3: Harden MIME handling and file responses

Files:
- `0x0/fhost.py`
- `0x0/tests/test_client.py`

Steps:
- Add failing tests for `X-Content-Type-Options: nosniff` and HTML upload rejection.
- Prefer `python-magic` detected MIME over client-provided MIME for storage decisions.
- Expand the MIME blacklist to reject active web content such as `text/html`, `application/xhtml+xml`, `image/svg+xml`, and `application/xml`.
- Add a shared file-response helper that sets:

```python
response.headers["Content-Disposition"] = f'attachment; filename="{f.getname()}"'
response.headers["X-Content-Type-Options"] = "nosniff"
```

- Apply the helper to both the nginx `X-Accel-Redirect` path and the Flask `send_from_directory` path.

## Task 4: Harden deployment defaults

Files:
- `docker-compose.yml`
- `0x0/Dockerfile`
- `nginx/Dockerfile`
- `.env.example`
- `.gitignore`

Steps:
- Replace floating app images with local builds from `./0x0` and `./nginx`.
- Move credentials and upload limits to `.env`.
- Add `restart: unless-stopped` to long-running services.
- Remove cron from the app container and add a separate `cleanup` maintenance service/profile.
- Update the app image so required build/runtime libraries are installed for `uwsgi`, `psycopg2`, and `python_magic`.
- Validate with `docker compose config` and `docker compose build app nginx`.

## Task 5: Document operations and verify the live workflow

Files:
- `README.md`
- `0x0/README.rst`

Steps:
- Add a root deployment guide covering `.env`, build/start commands, direct upload smoke tests, and cleanup operations.
- Bring the stack up with `docker compose up -d --build`.
- Upload a real file with `curl -F'file=@0x0/README.rst' http://localhost/`.
- Confirm the live response returns a short file URL and the served file includes the hardened attachment behavior.
- Re-run `python -m pytest -q`.

## Git Handling

- Push the branch to `fork`, not upstream.
- Keep upstream as the read-only reference remote.
- Do not open a pull request against the upstream repository as part of this workflow.
