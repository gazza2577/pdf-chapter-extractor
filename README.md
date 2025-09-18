# PDF to Text Automation Script

A CLI helper that extracts chapter-sized ranges from a PDF and exports each selection to plain text. It relies on PDF bookmarks when available and gracefully falls back to manual chapter entry when the document lacks a usable outline.


*Developed in collaboration with GPT-5-Codex. If you adapt or share AI-written code, please consider licensing it under GPL v3 to keep derivative works open and accessible.*

## Features
- Auto-discovers PDF files in the script directory and prompts you to pick one.
- Detects likely chapter headings from the PDF outline (digits, Roman numerals, and word-based numbers).
- Falls back to manual chapter definitions when bookmarks cannot be parsed.
- Generates filename-safe slugs for exported chapters and removes incomplete files if extraction fails.

## Requirements
- Python 3.10+
- `pdftotext` from [Poppler](https://poppler.freedesktop.org/) available on your `PATH`

## Installation
1. (Optional) create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell
   .venv\Scripts\Activate.ps1
   # macOS / Linux
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
1. Place the PDF(s) you want to process alongside `pdf_to_text.py`.
2. Run the script:
   ```bash
   python pdf_to_text.py
   ```
3. Choose a PDF and follow the prompts:
   - Accept detected chapters or enter them manually.
   - Provide chapter numbers or ranges (e.g., `1`, `2-4`, `1-3,5`).
4. The script creates `.txt` exports next to the PDF, named like `book_slug_chapter_3_Title.txt`.

## Troubleshooting
- `pdftotext` not found: install Poppler and ensure the executable is on your `PATH`.
- Odd chapter boundaries: outlines vary between PDFs; use the manual entry workflow to fine-tune ranges.
- Text encoding issues: adjust the `run_pdftotext` call to include flags such as `-enc UTF-8` if needed.

## License
Distributed under the GNU General Public License v3.0. See `LICENSE` for full terms.
