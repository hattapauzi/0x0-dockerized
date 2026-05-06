# Implementation Plan: Markdown Preview Rendering

**Branch**: `001-markdown-preview` | **Date**: 2026-05-06 | **Spec**: `specs/001-markdown-preview/spec.md`
**Input**: Feature specification from `specs/001-markdown-preview/spec.md`

**Note**: This plan was generated for the `/speckit.plan` workflow and stops after Phase 1 design artifacts. Task generation is handled separately.

## Summary

Enhance the existing Flask text-preview path so uploaded `.md` files render as sanitized Markdown documents with table support and Mermaid diagram blocks, while preserving the current randomized URL flow, download link behavior, original filename preservation, plain text preview fallback, non-text attachment responses, and hardening against active uploaded content.

## Technical Context

**Language/Version**: Python 3.10 in Docker runtime; local development follows the existing Python/pytest workflow  
**Primary Dependencies**: Flask, Jinja2, Flask-SQLAlchemy, Flask-Migrate, python-magic; planned additions are `Markdown` for server-side Markdown conversion and `bleach` for HTML sanitization  
**Storage**: Existing filesystem upload storage under `data/up/` via `FHOST_STORAGE_PATH`; existing relational DB metadata via SQLAlchemy/Alembic; no new persisted tables required  
**Testing**: pytest from `0x0/` using existing `tests/test_client.py` patterns  
**Target Platform**: Linux container/runtime via Docker Compose; Flask app served from `0x0/`  
**Project Type**: Web service / server-rendered Flask application  
**Performance Goals**: Markdown conversion occurs only for `.md` previews and reads the stored file once per request; preserve existing upload/retrieval responsiveness within current upload-size bounds  
**Constraints**: Preserve direct upload/retrieval-only hardening; do not re-enable remote URL import or URL shortening; sanitize rendered Markdown; keep non-Markdown text previews and binary downloads unchanged  
**Scale/Scope**: Single Flask application entrypoint with focused changes to preview rendering, templates, dependencies, and pytest coverage

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The current constitution file is still the generated placeholder and does not define enforceable project-specific gates. In lieu of formal constitution rules, this plan applies the repository baseline from the Master Technical Specification and current implementation:

- **Structure-aware changes**: PASS — plan keeps the existing single-file Flask entrypoint and adds only focused helper functions/templates.
- **Hardening preserved**: PASS — Markdown rendering is scoped to `.md` uploads and requires sanitization; remote import, URL shortening, and unsafe MIME support remain out of scope.
- **Validation required**: PASS — plan requires pytest coverage for Markdown, Mermaid, sanitization, preserved downloads, and regressions.
- **Runtime data separation**: PASS — no runtime data or secrets are introduced.
- **Schema impact**: PASS — no migration or new persistent entity is required.

No gate violations are identified.

## Project Structure

### Documentation (this feature)

```text
specs/001-markdown-preview/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── markdown-preview.md
└── tasks.md             # Generated later by /speckit.tasks, not by this plan
```

### Source Code (repository root)

```text
0x0/
├── fhost.py                    # Add Markdown detection/render helpers and route selection
├── requirements.txt            # Add Markdown and sanitization dependencies
├── templates/
│   ├── preview.html            # Keep plain text preview behavior
│   └── markdown_preview.html   # Add rendered Markdown preview template
└── tests/
    └── test_client.py          # Add Markdown/Mermaid/sanitization regression tests
```

**Structure Decision**: Use the existing nested Flask application under `0x0/` and preserve the current single-entrypoint architecture. Add a dedicated Markdown preview template rather than overloading the plain text preview template, so non-Markdown text rendering remains unchanged and Mermaid assets are scoped to Markdown previews.

## Complexity Tracking

No constitution violations or complexity exceptions are required.

## Phase 0 Research Summary

Research output is captured in `specs/001-markdown-preview/research.md`.

## Phase 1 Design Summary

Design output is captured in:

- `specs/001-markdown-preview/data-model.md`
- `specs/001-markdown-preview/contracts/markdown-preview.md`
- `specs/001-markdown-preview/quickstart.md`

## Post-Design Constitution Check

Re-check after Phase 1 design remains PASS:

- Design uses existing `File` metadata and no new persistence.
- Interface contract preserves existing routes and adds only alternate rendering for `.md` previews.
- Quickstart validation includes pytest and curl/browser checks for security and regression behavior.
- Sanitization remains an explicit design requirement before rendered HTML reaches the template.
