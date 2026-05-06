# Phase 0 Research: Markdown Preview Rendering

## Decision 1: Render standard Markdown server-side with Python-Markdown

**Decision**: Use the `Markdown` Python package for server-side Markdown conversion with extensions for fenced code blocks and tables.

**Rationale**: The application is already a Flask server-rendered app, so server-side Markdown conversion fits the existing rendering model. It allows headings, lists, tables, code blocks, and links to be present in the HTML response without requiring JavaScript for standard Markdown. Python-Markdown is a widely used Python library and supports the required table and fenced-code extensions.

**Alternatives considered**:
- Client-side Markdown rendering only: rejected because it would make all Markdown presentation dependent on browser JavaScript and increase exposure of raw user content to client-side parsing.
- Mistune/markdown-it-py: viable, but Python-Markdown provides sufficient support for this feature and keeps the implementation straightforward.
- Custom Markdown parsing: rejected as unsafe and unnecessary.

## Decision 2: Sanitize rendered Markdown with Bleach

**Decision**: Use `bleach` to sanitize rendered HTML after Markdown conversion and before template rendering.

**Rationale**: Rendering user-uploaded Markdown can create active HTML if raw HTML is allowed through. A maintained whitelist sanitizer is safer than hand-written filtering and directly satisfies the security requirement to remove executable script tags, inline event handlers, and unsafe URL protocols.

**Alternatives considered**:
- Escaping all rendered Markdown: rejected because it would prevent Markdown rendering from working.
- Disabling raw HTML only at the Markdown parser level: insufficient as a sole control because defense-in-depth requires sanitizing final HTML.
- Hand-written filtering: rejected because HTML sanitization is subtle and error-prone.

## Decision 3: Keep Markdown detection extension-scoped to `.md`

**Decision**: Render Markdown only when the stored upload extension is `.md`.

**Rationale**: The existing upload path stores an extension derived from the original filename or MIME fallback. The feature request specifically targets `.md` files. Extension-based detection prevents accidental Markdown rendering for ordinary `.txt`, `.log`, and `.diff` files whose content happens to contain Markdown-like syntax.

**Alternatives considered**:
- MIME-based Markdown detection: rejected because `.md` files often detect as `text/plain`, and MIME alone cannot distinguish Markdown from plain text.
- Render every text file as Markdown: rejected because it would change existing plain text preview behavior.
- Add `.markdown` immediately: deferred to keep the first implementation narrow.

## Decision 4: Render Mermaid diagrams client-side with a pinned Mermaid asset

**Decision**: Convert fenced `mermaid` code blocks into Mermaid diagram containers and initialize Mermaid client-side using the pinned CDN asset `https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js` for this implementation.

**Rationale**: Mermaid is designed for browser-side diagram rendering. Server-side rendering would require additional tooling and runtime complexity. Scoping Mermaid initialization to Markdown preview pages prevents Mermaid script loading on plain text previews. A pinned CDN URL avoids adding local static asset handling to the existing minimal Flask app while preserving a deterministic Mermaid version.

**Alternatives considered**:
- Server-side Mermaid rendering: rejected for initial implementation because it adds significant runtime/tooling complexity.
- No Mermaid rendering: rejected because Mermaid support is a requested feature goal.
- Load Mermaid on every preview page: rejected to keep non-Markdown text previews unchanged and lighter.

## Decision 5: Preserve current route shape and response behavior

**Decision**: Keep the existing `/<path:path>` preview/download route and `/download/<path:path>` attachment route. Add Markdown preview handling before the existing plain text preview fallback.

**Rationale**: The current architecture already separates preview from download behavior and has tests for randomized links, preserved filenames, and direct downloads. The feature can be implemented as a narrow extension of preview selection without new routes or persistence.

**Alternatives considered**:
- Add a separate Markdown route: rejected because it would fragment preview behavior and create unnecessary public surface area.
- Replace plain preview template with Markdown template for all text: rejected because plain text behavior must remain unchanged.

## Decision 6: No database migration required

**Decision**: Reuse the existing `File` model fields: `token`, `ext`, `mime`, `sha256`, `removed`, and `original_name`.

**Rationale**: Markdown preview behavior is derived from existing stored file content and metadata at request time. No new persisted state is needed.

**Alternatives considered**:
- Persist rendered HTML: rejected because it adds invalidation, sanitization, and storage complexity without a clear need.
- Add a file type column: rejected because the extension already provides the needed initial signal.
