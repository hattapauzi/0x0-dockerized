# Quickstart: Markdown Preview Rendering

## Purpose

Validate the Markdown preview implementation after development. Run commands from the repository root unless noted otherwise.

## 1. Install / Update Local Development Dependencies

From `0x0/`:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
```

The implementation should add Markdown rendering and sanitization dependencies to `0x0/requirements.txt`, which are included through `requirements-dev.txt`.

## 2. Run Database Migrations for Local Validation

From `0x0/` with the virtual environment active:

```bash
FLASK_APP=fhost flask db upgrade
```

No new migration is expected for this feature.

## 3. Run Automated Tests

From `0x0/`:

```bash
python -m pytest -q
```

Expected coverage includes:

- `.md` upload returns randomized `.md` URL.
- `.md` preview renders headings and tables.
- Mermaid fenced blocks are represented for Mermaid rendering.
- Markdown sanitization removes active script/event-handler content.
- Non-Markdown text files remain plain escaped previews.
- Non-text files remain direct attachment responses.
- Download preserves the uploaded `.md` filename.

## 4. Docker Compose Smoke Test

From the repository root:

```bash
docker compose up -d --build
```

Upload a Markdown file:

```bash
curl -F'file=@README.md' http://localhost:8081/
```

Open the returned URL in a browser and verify:

- Markdown renders as a document.
- Tables render visually as tables.
- Mermaid diagrams render or are prepared in Mermaid diagram containers.
- The top `Download` link is present.

## 5. Security Smoke Checks

Create a temporary Markdown file containing active HTML attempts:

```markdown
# Unsafe sample

<script>alert('x')</script>

[bad](javascript:alert('x'))

<img src=x onerror=alert('x')>
```

Upload and open it. Verify the preview does not execute script, does not preserve inline event handlers, and does not expose unsafe links as active browser behavior.

## 6. Regression Checks

Upload a `.txt` file with Markdown-looking content and verify it is still displayed as escaped plain text, not rendered Markdown.

Upload a binary file and verify it still downloads directly as an attachment.

## 7. Cleanup

When finished:

```bash
docker compose down
```
