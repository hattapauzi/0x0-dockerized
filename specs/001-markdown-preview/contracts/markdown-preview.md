# Contract: Markdown Preview Rendering

## Interface Scope

This feature modifies the rendering behavior of an existing public file retrieval interface. It does not add new public routes.

## Existing Upload Interface

### `POST /`

Uploads a file and returns a randomized public URL.

#### Request

- Content type: `multipart/form-data`
- File field: `file`
- Example uploaded filename: `README.md`

#### Success Response

- Status: `200`
- Body: randomized HTTPS URL ending with the stored extension, for example:

```text
https://localhost/AbCdEfGhIjKl.md
```

#### Required Behavior for `.md`

- Upload validation remains unchanged.
- Unsafe MIME types remain rejected.
- Remote URL import fields remain rejected.
- URL-shortening fields remain rejected.

## Existing Preview / Retrieval Interface

### `GET /<token>.md`

Retrieves the public randomized URL for an uploaded Markdown file.

#### Success Response

- Status: `200`
- Content type: `text/html`
- Header: `X-Content-Type-Options: nosniff`
- Body: HTML preview page containing:
  - a top `Download` link
  - sanitized rendered Markdown document HTML
  - rendered table markup for Markdown tables
  - Mermaid-renderable diagram containers for fenced `mermaid` blocks
  - Mermaid initialization scoped to Markdown preview pages

#### Security Contract

The response body must not include executable uploaded content from Markdown source:

- No active `<script>` tags from uploaded Markdown.
- No inline event handler attributes such as `onclick` from uploaded Markdown.
- No unsafe URL protocols such as `javascript:` in rendered links.
- Non-Mermaid fenced code blocks remain escaped code content.

## Existing Plain Text Preview Interface

### `GET /<token>.txt` or other non-Markdown text URL

Retrieves the public randomized URL for a non-Markdown text file.

#### Required Behavior

- Status: `200` for available text files.
- Content type: `text/html` preview page.
- Body continues using the existing escaped plain text preview structure.
- Mermaid script or initialization is not included.
- Markdown syntax is not interpreted unless the stored extension is `.md`.

## Existing Download Interface

### `GET /download/<token>.md`

Downloads the original Markdown file as an attachment.

#### Success Response

- Status: `200`
- Header: `Content-Disposition: attachment; filename="<original uploaded filename>"`
- Header: `X-Content-Type-Options: nosniff`
- Body: original file content

#### Required Behavior

- Markdown preview rendering must not alter download payloads.
- Original uploaded filename preservation must continue working.

## Error Behavior

Existing error behavior remains unchanged:

- Missing token or extension mismatch: `404`
- Removed file: `451`
- Unsafe uploaded MIME type: `415`
- Unsupported POST payload without `file`: `400`
