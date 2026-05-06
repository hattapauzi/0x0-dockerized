# Feature Specification: Markdown Preview Rendering

**Feature Branch**: `001-markdown-preview`  
**Created**: 2026-05-06  
**Status**: Draft  
**Input**: User description: "Improve the existing default text rendering for text-based files so `.md` files render proper Markdown, including Mermaid diagrams, tables, and related Markdown presentation features. Proceed with the recommended approach."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Render uploaded Markdown documents (Priority: P1)

As a visitor who opens the randomized URL for an uploaded `.md` file, I want to see the file rendered as a readable Markdown document instead of raw Markdown text, so that documentation, notes, and technical specs are easy to read in the browser.

**Why this priority**: This is the core value of the feature. Without rendered Markdown, the enhancement does not improve the current text preview experience.

**Independent Test**: Upload a `.md` file containing headings, paragraphs, lists, links, code blocks, and a table; open the returned randomized URL; verify the page renders those Markdown structures as HTML while keeping the download link available.

**Acceptance Scenarios**:

1. **Given** a user uploads a file named `README.md` containing Markdown headings and paragraphs, **When** the user opens the returned randomized URL, **Then** the page displays rendered headings and paragraphs rather than raw Markdown syntax.
2. **Given** a user uploads a `.md` file containing a Markdown table, **When** the user opens the returned randomized URL, **Then** the page displays a rendered HTML table.
3. **Given** a rendered Markdown preview page, **When** the user selects the top `Download` link, **Then** the file downloads through the existing attachment path with the original uploaded filename preserved.

---

### User Story 2 - Render Mermaid diagrams from Markdown (Priority: P2)

As a user sharing technical Markdown files, I want fenced Mermaid code blocks to render as diagrams, so that architecture and flow diagrams embedded in the document are visible without copying the source into another tool.

**Why this priority**: Mermaid support is specifically requested and is important for technical documentation, but standard Markdown rendering is still useful without it.

**Independent Test**: Upload a `.md` file containing a fenced `mermaid` block; open the returned randomized URL; verify the page includes a Mermaid diagram container and initializes Mermaid rendering only for the Markdown preview page.

**Acceptance Scenarios**:

1. **Given** a `.md` file contains a fenced code block labeled `mermaid`, **When** the file preview is opened, **Then** the Mermaid source is presented in a Mermaid-renderable container.
2. **Given** the Markdown preview contains one or more Mermaid blocks, **When** the page loads in a browser, **Then** Mermaid initialization is available for those diagrams.
3. **Given** a non-Markdown text file is previewed, **When** the page loads, **Then** Mermaid initialization is not included for that plain text preview.

---

### User Story 3 - Preserve hardened preview behavior (Priority: P3)

As an operator of a public file host, I want Markdown rendering to remain sanitized and scoped to Markdown files, so that the enhancement does not weaken the existing upload and retrieval hardening.

**Why this priority**: The repository is intentionally hardened for direct upload/retrieval only. Rendering user-uploaded Markdown must not create an active content execution path.

**Independent Test**: Upload Markdown containing raw script tags, inline event handlers, unsafe links, and normal code blocks; open the preview; verify active HTML is sanitized, non-Mermaid code remains escaped, and existing rejection behavior for unsafe uploaded MIME types still passes.

**Acceptance Scenarios**:

1. **Given** a `.md` file contains raw `<script>` content, **When** the rendered preview is opened, **Then** the script is not present as executable HTML.
2. **Given** a `.md` file contains inline event attributes such as `onclick`, **When** the rendered preview is opened, **Then** those attributes are not present as executable HTML.
3. **Given** a `.txt`, `.log`, or `.diff` file is uploaded, **When** the randomized URL is opened, **Then** the file continues using the existing plain escaped text preview instead of Markdown rendering.
4. **Given** a non-text file is uploaded, **When** the randomized URL is opened, **Then** it continues using the existing attachment response behavior.

---

### Edge Cases

- Markdown files with invalid UTF-8 bytes should still render using replacement behavior consistent with the current preview path.
- Empty `.md` files should render a valid preview page with the download link and no document body content.
- Markdown files with malformed tables should render predictably as supported by the Markdown renderer rather than failing the request.
- Mermaid blocks with invalid diagram syntax should not break the whole preview page.
- Markdown containing raw HTML, script tags, unsafe URLs, or inline event handlers must not execute in the browser.
- Non-Mermaid fenced code blocks must remain escaped code content.
- A `.md` file whose detected MIME type is `text/plain` should still receive Markdown preview treatment because the extension identifies the intended rendering mode.
- Plain text files with Markdown-looking content but non-Markdown extensions should remain plain text previews.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST render uploaded `.md` files as Markdown preview pages when their randomized public URLs are opened.
- **FR-002**: The system MUST keep the existing plain escaped preview behavior for non-Markdown text files.
- **FR-003**: The system MUST keep the existing direct attachment behavior for non-text files.
- **FR-004**: Markdown rendering MUST support headings, paragraphs, emphasis, lists, links, blockquotes, fenced code blocks, and tables.
- **FR-005**: The Markdown preview page MUST include the existing top `Download` link behavior.
- **FR-006**: The existing download route MUST preserve the uploaded original filename for `.md` files.
- **FR-007**: Fenced code blocks labeled `mermaid` MUST be represented in the preview as Mermaid-renderable diagram blocks.
- **FR-008**: Mermaid rendering support MUST be included only for Markdown preview pages, not for plain text preview pages.
- **FR-009**: Rendered Markdown HTML MUST be sanitized before being sent to the browser.
- **FR-010**: Sanitization MUST prevent executable script tags, inline event handlers, and unsafe URL protocols from executing from uploaded Markdown.
- **FR-011**: Non-Mermaid fenced code blocks MUST remain escaped as code content.
- **FR-012**: The feature MUST NOT re-enable remote URL import, generic URL shortening, or unsafe MIME-type uploads.
- **FR-013**: Markdown preview responses SHOULD keep the `X-Content-Type-Options: nosniff` response header used by existing preview/download behavior.
- **FR-014**: Automated tests MUST cover Markdown rendering, table rendering, Mermaid block handling, sanitization, download filename preservation, and regression behavior for non-Markdown previews.

### Key Entities *(include if feature involves data)*

- **Uploaded File**: Existing stored upload record with randomized token, extension, MIME type, content hash, removal status, and original uploaded filename. Markdown preview behavior uses this existing metadata and does not require a new persisted entity.
- **Markdown Preview**: A rendered HTML representation of an uploaded `.md` file generated from stored file content at request time. It is not separately persisted.
- **Mermaid Diagram Block**: A fenced Markdown code block labeled `mermaid` that is exposed in the rendered preview as diagram source for client-side diagram initialization.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A `.md` upload containing a heading, list, code block, and table renders those elements as HTML at the returned randomized URL.
- **SC-002**: A `.md` upload containing a fenced Mermaid block produces a preview page with Mermaid-renderable diagram markup and Mermaid initialization available.
- **SC-003**: A `.md` upload containing raw script content or inline event handlers does not produce executable script or event-handler HTML in the preview response.
- **SC-004**: A `.txt` upload continues to render as escaped plain text rather than Markdown.
- **SC-005**: A binary upload continues to return a direct attachment response rather than a preview page.
- **SC-006**: Downloading a previewed `.md` file returns `Content-Disposition` with the uploaded original filename.
- **SC-007**: Existing upload, retrieval, hardening, randomized-token, and filename-preservation tests continue passing alongside the new Markdown preview tests.

## Assumptions

- Markdown rendering will be server-side for standard Markdown features.
- Mermaid diagram rendering will be client-side using Mermaid.js because Mermaid is browser-oriented.
- Mermaid.js should be pinned; a local static asset is preferred if static asset handling is added, while a pinned CDN URL is acceptable if local static asset handling is intentionally deferred.
- The initial Markdown extension scope is `.md` only.
- The existing randomized URL, preview, and download route structure will be reused.
- The feature does not add user accounts, document editing, remote URL import, generic URL shortening, or a document library.
- The existing code-grounded baseline is the current Flask preview implementation: text previews route through `0x0/fhost.py:337-344`, preview responses are built in `0x0/fhost.py:299-306`, and the plain preview template is `0x0/templates/preview.html:1-2`.
