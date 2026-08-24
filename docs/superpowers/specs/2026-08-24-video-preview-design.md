# Video Preview Design — 2026-08-24

## Overview
Add a browser video playback preview for `video/*` uploads, matching the existing preview pattern (`0x0/fhost.py:306`, `0x0/templates/preview.html:1`, `0x0/templates/markdown_preview.html:1`). Visiting the short URL `GET /<token><ext>` renders an HTML page with a native `<video controls>` player and a top Download link; `GET /download/<token><ext>` (`0x0/fhost.py:404`) remains the forced-download endpoint. Byte source for the player reuses `/download/` (Approach A) — simplest, no new byte route.

Decisions: minimal page (player + Download link, no filename/size extras), plain `<video>` (no video.js/CDN), all `video/*` MIME types eligible. Analytics separation not needed.

## Architecture & Routing

### New helpers in `0x0/fhost.py`
- `should_preview_video(f) -> bool`: `bool(f.mime and f.mime.startswith("video/"))`. Mirrors `should_preview_file` at `0x0/fhost.py:306` and `should_render_markdown` at `0x0/fhost.py:310`.
- `build_video_preview_response(f, fpath) -> Response`: `make_response(render_template("video_preview.html", download_url=url_for("download", path=f.getname(), _external=True, _scheme="https"), mime=f.mime))` with `X-Content-Type-Options: nosniff` (same as `0x0/fhost.py:362`, `0x0/fhost.py:372`).

### Updated route `get(path)` at `0x0/fhost.py:411`
Order after `lookup_file` (`0x0/fhost.py:382`):
1. `should_render_markdown(f)` → `build_markdown_preview_response`
2. `should_preview_video(f)` → `build_video_preview_response`
3. `should_preview_file(f)` → `build_preview_response`
4. fallback → `build_file_response` (`0x0/fhost.py:292`)

`download(path)` at `0x0/fhost.py:404` unchanged. No new route. If `FHOST_USE_X_ACCEL_REDIRECT` is later enabled, no change needed for preview.

## Template `0x0/templates/video_preview.html`
Standalone HTML (like `markdown_preview.html:1`), inline `<style>`, no external assets:
- `<head>`: charset/viewport, title "Video preview", centered `max-width: 960px` layout, `video { max-width:100%; width:100%; height:auto; background:#000; }`.
- `<body>`: top `<p><a href="{{ download_url }}">Download</a></p>` (consistent with `preview.html:1`), then `<video controls preload="metadata"><source src="{{ download_url }}" type="{{ mime }}"></video>`.
- Jinja auto-escapes `mime`; no raw HTML injection.

## Data Flow
1. Upload → `File.store` detects MIME via `python-magic` (`0x0/fhost.py:172`), ext via `FHOST_EXT_OVERRIDE`/`guess_extension` (`0x0/fhost.py:191`), persisted as `File.mime/ext`.
2. `GET /<token>.mp4` → `lookup_file` validates token+ext, checks `removed`/file existence → video check → `video_preview.html` with `download_url` pointing at `/download/<token>.mp4`.
3. Browser loads preview HTML, then fetches `<source src>` from `/download/` via `build_file_response` (`send_from_directory` at `0x0/fhost.py:298` + `Content-Type`/`Content-Disposition: attachment` at `0x0/fhost.py:300`). For `<video>` subresource fetches, browsers ignore `attachment` and play inline. Flask 3.1 `send_file` handles `Range`/`206` for seeking.

## Error Handling / Edge Cases
- Non-playable container (e.g. `.avi`, `video/x-msvideo`): native `<video>` shows browser error; Download link remains functional — same hosting-service UX.
- `video/x-matroska` (`.mkv`), `video/quicktime` (`.mov`): plays where the browser's demuxer supports the codecs (Chrome often yes, Firefox/Safari vary); download fallback covers the rest.
- Missing file / `lookup_file` fails → `404`; `removed` → `451` (existing).
- No JS — no CDN failure mode. `preload="metadata"` avoids fetching full file on page load.

## Security
- `X-Content-Type-Options: nosniff` on preview response, same as other previews.
- `mime` rendered only as `<source type>` attribute; Jinja escaping prevents injection.
- No user-controlled HTML in template beyond the URL/mime.

## Testing
Extend `0x0/tests/test_client.py` (patterns at `0x0/tests/test_client.py:150`, `0x0/tests/test_client.py:191`):
- Upload `video/mp4` → `GET /<path>` returns `200` `text/html` with `<video`, `controls`, `<source type="video/mp4">`, top Download link, `X-Content-Type-Options: nosniff`; `GET` on extracted download URL returns `200` `video/mp4` with `Content-Disposition: attachment; filename="..."`.
- Upload `video/webm` similarly.
- Non-video (e.g. `image/png` at `0x0/tests/test_client.py:191`) still returns direct attachment (no `<video>`).
- Text/markdown previews unchanged.

## Non-Goals
- No video.js/CDN, no custom controls, no transcoding, no poster/thumbnail generation, no audio preview expansion, no filename/size/copy-link extras, no new `/stream` route, no analytics distinction between views and downloads.
