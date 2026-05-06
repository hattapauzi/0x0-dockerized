# Data Model: Markdown Preview Rendering

## Overview

This feature does not introduce new database tables or migrations. It uses existing upload metadata and derives rendered preview output at request time.

## Existing Entity: Uploaded File

**Source**: Existing `File` model in `0x0/fhost.py`.

### Relevant Fields

| Field | Type | Purpose for this feature |
|---|---|---|
| `id` | Integer | Existing internal primary key |
| `sha256` | String | Locates stored file content under `FHOST_STORAGE_PATH` |
| `token` | String | Randomized public URL identifier |
| `ext` | Text | Determines whether preview should use Markdown rendering (`.md`) |
| `mime` | Text | Determines plain text preview fallback for non-Markdown text files |
| `removed` | Boolean | Preserves existing removed-file behavior (`451`) |
| `original_name` | Text | Preserves uploaded filename for `/download/<path>` attachment responses |

### Validation Rules

- A file must have a matching token and extension to resolve through the existing lookup path.
- Removed files must continue returning the existing removed response.
- Missing stored content must continue returning `404`.
- `.md` extension triggers Markdown preview rendering.
- Non-Markdown `text/*` MIME types trigger the existing plain escaped preview.
- Non-text files trigger the existing attachment response.

### State Transitions

This feature adds no new persisted states.

Existing relevant states remain:

```text
Uploaded -> Available -> Removed
```

- `Uploaded`: file metadata is stored and content is present.
- `Available`: randomized URL resolves and renders preview or download behavior.
- `Removed`: `removed` is set and lookup aborts with the existing removal response.

## Derived Entity: Markdown Preview

**Persistence**: Not persisted.

### Fields / Values

| Value | Source | Purpose |
|---|---|---|
| `source_text` | Stored file bytes decoded as UTF-8 with replacement | Input to Markdown conversion |
| `rendered_html` | Markdown conversion result | Intermediate HTML before sanitization |
| `sanitized_html` | Sanitizer output | Safe HTML inserted into Markdown preview template |
| `download_url` | Existing `url_for("download", path=f.getname())` | Top download link |
| `has_mermaid` | Rendered content or Markdown source inspection | Controls Mermaid initialization if implemented conditionally |

### Validation Rules

- `source_text` must be decoded with replacement behavior so invalid UTF-8 does not fail the request.
- `rendered_html` must not be sent directly to the browser before sanitization.
- `sanitized_html` must remove script tags, inline event attributes, and unsafe URL protocols.
- Non-Mermaid fenced code blocks must remain code content, not active HTML.

## Derived Entity: Mermaid Diagram Block

**Persistence**: Not persisted.

### Fields / Values

| Value | Source | Purpose |
|---|---|---|
| `diagram_source` | Fenced code block labeled `mermaid` | Mermaid diagram input |
| `container_class` | Markdown render/post-process output | Browser-side Mermaid detection |
| `render_status` | Browser-side runtime state | Not stored by server |

### Validation Rules

- Diagram source must be treated as text content inside a Mermaid container.
- Mermaid containers must not allow arbitrary script execution.
- Invalid Mermaid syntax must not prevent the rest of the Markdown preview from displaying.
