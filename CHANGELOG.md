# Changelog

## v1.0.0 — 2025-09-17

Added
- Initial automation script to extract chapter ranges and export text (`pdf_to_text.py`).
- PDF outline parsing (digits, Roman numerals, number words) to infer chapter boundaries.
- Manual chapter entry fallback with validation when bookmarks are unavailable.
- `pdftotext` integration with availability check and error handling.
- Safe filename slugging and cleanup of partial files on failure.
- README with setup, usage, troubleshooting; GPLv3 `LICENSE`.

Notes
- Repository history squashed to a single “Initial release” commit for a clean start.
