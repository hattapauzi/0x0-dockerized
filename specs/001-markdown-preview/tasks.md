---

description: "Task list for Markdown Preview Rendering feature implementation"
---

# Tasks: Markdown Preview Rendering

**Input**: Design documents from `/specs/001-markdown-preview/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included per feature specification requirement FR-014

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add required dependencies and document Mermaid asset strategy.

- [X] T001 Add `Markdown` and `bleach` packages to `0x0/requirements.txt` (server-side Markdown rendering and HTML sanitization)
- [X] T002 [P] Document Mermaid asset strategy in `specs/001-markdown-preview/research.md` — choose between pinned CDN URL or local static asset; note the decision for implementation in US2

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core helper functions that MUST be complete before any user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Add `should_render_markdown(f)` helper in `0x0/fhost.py` — returns `True` when file extension is `.md`; called before plain text preview decision
- [X] T004 Add `render_markdown(content)` helper in `0x0/fhost.py` — converts Markdown source to sanitized HTML using Python-Markdown with `fenced_code` and `tables` extensions, then sanitizes output with Bleach allowing safe tags: `p, h1, h2, h3, h4, h5, h6, ul, ol, li, blockquote, pre, code, a[href], strong, em, table, thead, tbody, tr, th, td, br, hr, img[src]`
- [X] T005 Add `build_markdown_preview_response(f, fpath)` function in `0x0/fhost.py` — reads file as UTF-8 with replacement, calls `render_markdown()`, returns HTML response with `X-Content-Type-Options: nosniff` and `content-type: text/html`

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Render uploaded Markdown documents (Priority: P1) — MVP

**Goal**: Uploaded `.md` files render as readable Markdown preview pages with download link.

**Independent Test**: Upload a `.md` file containing headings, paragraphs, lists, links, code blocks, and a table; open the returned randomized URL; verify the page renders those Markdown structures as HTML while keeping the download link available.

### Tests for User Story 1

> Write tests FIRST, ensure they FAIL before implementation

- [X] T006 [P] [US1] Add test in `0x0/tests/test_client.py`: `.md` upload returns a randomized URL ending with `.md`
- [X] T007 [P] [US1] Add test in `0x0/tests/test_client.py`: `.md` preview renders headings (`<h1>`-`<h6>`), paragraphs (`<p>`), lists (`<ul>`/`<ol>`), links (`<a>`), blockquotes (`<blockquote>`), and fenced code blocks (`<pre>`/`<code>`) as HTML
- [X] T008 [P] [US1] Add test in `0x0/tests/test_client.py`: `.md` preview renders Markdown tables as `<table>` with `<thead>`/`<tbody>`/`<tr>`/`<th>`/`<td>` elements
- [X] T009 [P] [US1] Add test in `0x0/tests/test_client.py`: `.md` preview includes top `Download` link and downloads via `/download/<path>` route
- [X] T010 [P] [US1] Add test in `0x0/tests/test_client.py`: Downloading a previewed `.md` file returns `Content-Disposition` with the original uploaded filename preserved

### Implementation for User Story 1

- [X] T011 [P] [US1] Create `0x0/templates/markdown_preview.html` — Jinja2 template with top `Download` link, rendered Markdown content, and Mermaid initialization block (stubbed for now)
- [X] T012 [US1] Modify `get()` route in `0x0/fhost.py:337-344` — add Markdown preview branch: when `should_render_markdown(f)` is `True`, call `build_markdown_preview_response(f, fpath)` instead of `build_preview_response`
- [X] T013 [US1] Run pytest to verify US1 tests pass; all previous tests continue passing

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - Render Mermaid diagrams from Markdown (Priority: P2)

**Goal**: Fenced Mermaid code blocks in `.md` files render as diagram containers with client-side Mermaid rendering.

**Independent Test**: Upload a `.md` file containing a fenced `mermaid` block; open the returned randomized URL; verify the page includes a Mermaid diagram container and initializes Mermaid rendering only for the Markdown preview page.

### Tests for User Story 2

> Write tests FIRST, ensure they FAIL before implementation

- [X] T014 [P] [US2] Add test in `0x0/tests/test_client.py`: `.md` preview contains a Mermaid diagram container (`<div class="mermaid">` or similar) when source contains a fenced `mermaid` block
- [X] T015 [P] [US2] Add test in `0x0/tests/test_client.py`: non-Mermaid fenced code blocks remain escaped code content (`<pre><code>`) and are not converted to diagram containers
- [X] T016 [P] [US2] Add test in `0x0/tests/test_client.py`: plain text `.txt` preview does not include Mermaid script or initialization

### Implementation for User Story 2

- [X] T017 [P] [US2] Add `render_markdown_with_mermaid(content)` in `0x0/fhost.py` — post-process sanitized HTML: detect fenced ` ```mermaid` blocks in original Markdown source, convert them to Mermaid-compatible `<div class="mermaid">` diagram containers in the rendered output, keeping diagram source as text content inside the container
- [X] T018 [P] [US2] Update `render_markdown()` in `0x0/fhost.py` to use `render_markdown_with_mermaid()` so Mermaid blocks are handled
- [X] T019 [US2] Update `0x0/templates/markdown_preview.html` — include Mermaid.js from the pinned CDN (per research.md decision) or local static asset; add `mermaid.initialize()` call scoped to `.mermaid` selector; do NOT include Mermaid assets in `preview.html`
- [X] T020 [US2] Run pytest to verify US2 tests pass; all US1 and previous tests continue passing

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: User Story 3 - Preserve hardened preview behavior (Priority: P3)

**Goal**: Markdown rendering is sanitized, scoped to `.md` files, and does not weaken existing upload/retrieval hardening.

**Independent Test**: Upload Markdown containing raw script tags, inline event handlers, unsafe links, and normal code blocks; open the preview; verify active HTML is sanitized, non-Mermaid code remains escaped, and existing rejection behavior for unsafe uploaded MIME types still passes.

### Tests for User Story 3

> Write tests FIRST, ensure they FAIL before implementation

- [X] T021 [P] [US3] Add test in `0x0/tests/test_client.py`: `.md` file containing `<script>` tags renders preview without executable `<script>` HTML
- [X] T022 [P] [US3] Add test in `0x0/tests/test_client.py`: `.md` file containing inline event attributes (`onclick`, `onerror`, `onload`) renders preview without those attributes in output
- [X] T023 [P] [US3] Add test in `0x0/tests/test_client.py`: `.md` file containing `javascript:` URLs renders preview without `javascript:` links
- [X] T024 [P] [US3] Add test in `0x0/tests/test_client.py`: `.txt` file with Markdown-looking content renders as escaped plain text, not rendered Markdown
- [X] T025 [P] [US3] Add test in `0x0/tests/test_client.py`: non-text file (e.g. `.png`) continues to return direct attachment response, not a preview page

### Implementation for User Story 3

- [X] T026 [P] [US3] Verify Bleach sanitization in `render_markdown()` covers all required vectors: `<script>`, `on*` attributes, `javascript:` protocol in `href`/`src`; adjust Bleach allowed tags/attributes if needed
- [X] T027 [US3] Add explicit test for the existing MIME blacklist still rejects `text/html` uploads after changes (regression check)
- [X] T028 [US3] Run full pytest suite to verify all hardening tests pass alongside new tests

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and documentation alignment.

- [X] T029 [P] Run full pytest suite from `0x0/` with `python -m pytest -q` — all tests must pass
- [X] T030 [P] Verify Docker Compose build succeeds: `docker compose up -d --build` from repository root; upload a `.md` file via curl; open preview URL in browser; verify Markdown renders, tables render, Download link is present
- [X] T031 [P] Verify security smoke checks: upload Markdown with `<script>`, `javascript:` links, and inline event handlers; open preview; confirm no executable behavior
- [X] T032 Update `quickstart.md` in `specs/001-markdown-preview/` if any implementation details changed (e.g., Mermaid CDN URL)
- [X] T033 [P] Final code review of `0x0/fhost.py` changes — ensure no new routes added, no hardening regression, no unintended side effects on existing text preview path

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately
- **Phase 2 (Foundational)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1, US2, US3 can proceed in parallel once Phase 2 is done
  - Or sequentially in priority order: US1 → US2 → US3
- **Phase 6 (Polish)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 — no dependencies on other stories — MVP
- **User Story 2 (P2)**: Can start after Phase 2 — depends on US1 template structure but should be independently testable
- **User Story 3 (P3)**: Can start after Phase 2 — regression tests run independently alongside US1/US2

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Foundational helpers (T003-T005) before template/route work
- Template work (T011) before route wiring (T012)
- US2 Mermaid logic (T017) after US1 Markdown rendering baseline
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks T001, T002 marked [P] can run in parallel
- All Foundational tasks T003, T004, T005 marked [P] can run in parallel
- Once Foundational phase completes, all user stories can start in parallel
- All tests for a user story marked [P] can run in parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
