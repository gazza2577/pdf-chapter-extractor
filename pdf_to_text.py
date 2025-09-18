"""Utilities for extracting chapter ranges from PDFs and exporting them to text files."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from pypdf import PdfReader
from pypdf.errors import PdfReadError


PDFTOTEXT_COMMAND = "pdftotext"
DEFAULT_MAX_FILENAME_LENGTH = 60


@dataclass
class ChapterRange:
    """Inclusive page range representing a chapter-like section."""

    title: str
    start_page: int  # 1-based
    end_page: int  # 1-based inclusive


@dataclass
class OutlineEntry:
    """Bookmark entry along with its depth."""

    title: str
    page_index: int  # 0-based
    depth: int


NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

CHAPTER_DIGIT_RE = re.compile(r"^\s*(?:chapter|chap\.?)[\s.-]*0*([0-9]+)\b", re.IGNORECASE)
CHAPTER_ROMAN_RE = re.compile(r"^\s*(?:chapter|chap\.?)[\s.-]*([ivxlcdm]+)\b", re.IGNORECASE)
CHAPTER_WORD_RE = re.compile(r"^\s*(?:chapter|chap\.?)[\s.-]*([A-Za-z]+)\b", re.IGNORECASE)
FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def slugify_for_filename(
    text: str,
    fallback: str = "chapter",
    max_length: int = DEFAULT_MAX_FILENAME_LENGTH,
) -> str:
    """Turn text into a filename-safe slug with a sensible fallback."""

    cleaned = FILENAME_SAFE_RE.sub("_", text)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_.")
    if not cleaned:
        cleaned = fallback
    return cleaned[:max_length]


def roman_to_int(value: str) -> int | None:
    """Convert a Roman numeral to an integer, returning None if invalid."""

    roman_map = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    total = 0
    prev = 0
    try:
        for char in value.lower()[::-1]:
            current = roman_map[char]
            if current < prev:
                total -= current
            else:
                total += current
                prev = current
        return total
    except KeyError:
        return None


def is_chapter_title(title: str) -> bool:
    """Return True if a bookmark title looks like a chapter heading."""

    if CHAPTER_DIGIT_RE.match(title):
        return True
    match = CHAPTER_ROMAN_RE.match(title)
    if match:
        converted = roman_to_int(match.group(1))
        if converted:
            return True
    match = CHAPTER_WORD_RE.match(title)
    if match and match.group(1).lower() in NUMBER_WORDS:
        return True
    return False


def find_pdfs(base_dir: Path) -> list[Path]:
    """Return all PDF files in the given directory."""

    return sorted(base_dir.glob("*.pdf"))


def choose_pdf(pdfs: list[Path]) -> Path | None:
    """Display the PDFs with indices and return the user's selection."""

    if not pdfs:
        print("No PDF files found in this folder.")
        return None

    print("Available PDF files:")
    for i, pdf_path in enumerate(pdfs, start=1):
        print(f"{i}. {pdf_path.name}")

    while True:
        choice = input(f"Select a PDF by number (1-{len(pdfs)}): ").strip()
        try:
            index = int(choice)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if 1 <= index <= len(pdfs):
            return pdfs[index - 1]
        print("Choice out of range. Try again.")


def _iter_outline_items(
    outline: Iterable,
    depth: int = 0,
    seen: set[int] | None = None,
) -> Iterator[tuple[int, object]]:
    """Yield outline entries depth-first while guarding against cycles."""

    if seen is None:
        seen = set()
    for item in outline:
        if isinstance(item, list):
            yield from _iter_outline_items(item, depth, seen)
            continue

        item_id = id(item)
        if item_id in seen:
            continue
        seen.add(item_id)

        yield depth, item

        children = getattr(item, "children", None)
        if not children:
            continue
        if callable(children):
            try:
                child_items = children()
            except TypeError:
                continue
        else:
            child_items = children
        if child_items:
            yield from _iter_outline_items(child_items, depth + 1, seen)


def collect_outline_entries(reader: PdfReader) -> list[OutlineEntry]:
    """Collect bookmark entries from the PDF reader."""

    outline = (
        getattr(reader, "outline", None)
        or getattr(reader, "outlines", None)
        or []
    )
    entries: list[OutlineEntry] = []
    for depth, item in _iter_outline_items(outline):
        title = getattr(item, "title", None)
        if not title:
            continue
        try:
            page_index = reader.get_destination_page_number(item)
        except Exception:
            continue
        entries.append(OutlineEntry(title=title.strip(), page_index=page_index, depth=depth))
    entries.sort(key=lambda entry: entry.page_index)
    return entries


def pick_chapter_entries(entries: list[OutlineEntry]) -> list[OutlineEntry]:
    """Return outline entries that best represent chapter headings."""

    chapters = [entry for entry in entries if is_chapter_title(entry.title)]
    if chapters:
        return chapters
    if not entries:
        return []
    min_depth = min(entry.depth for entry in entries)
    return [entry for entry in entries if entry.depth == min_depth]


def build_chapter_ranges(entries: list[OutlineEntry], total_pages: int) -> list[ChapterRange]:
    """Convert outline entries into user-facing chapter ranges."""

    if not entries:
        return []
    entries = sorted(entries, key=lambda entry: entry.page_index)
    ranges: list[ChapterRange] = []
    for idx, entry in enumerate(entries):
        start_index = entry.page_index
        if idx + 1 < len(entries):
            end_index = entries[idx + 1].page_index - 1
        else:
            end_index = total_pages - 1
        ranges.append(ChapterRange(title=entry.title, start_page=start_index + 1, end_page=end_index + 1))
    return ranges


def extract_chapter_ranges(pdf_path: Path) -> list[ChapterRange]:
    """Derive chapter ranges from the PDF outline if available."""

    reader = PdfReader(str(pdf_path))
    entries = collect_outline_entries(reader)
    chapters = pick_chapter_entries(entries)
    return build_chapter_ranges(chapters, len(reader.pages))


def prompt_manual_chapters() -> list[ChapterRange]:
    """Ask the user to enter chapter titles and page ranges manually."""

    print("No bookmarks detected. Enter manual chapters (blank title to finish).")
    chapters: list[ChapterRange] = []
    index = 1
    while True:
        title = input(f"Chapter {index} title: ").strip()
        if not title:
            break
        while True:
            page_input = input(f"Page range for '{title}' (e.g., 10-25 or 12): ").strip()
            if not page_input:
                print("Please enter a page number or range.")
                continue
            try:
                if "-" in page_input:
                    start_str, end_str = page_input.split("-", 1)
                    start_page = int(start_str)
                    end_page = int(end_str)
                else:
                    start_page = end_page = int(page_input)
            except ValueError:
                print("Enter numbers such as 10 or 10-25.")
                continue
            if start_page < 1 or end_page < 1:
                print("Page numbers must be positive.")
                continue
            if start_page > end_page:
                start_page, end_page = end_page, start_page
            break
        chapters.append(ChapterRange(title=title, start_page=start_page, end_page=end_page))
        index += 1
    return chapters


def display_chapters(chapters: list[ChapterRange]) -> None:
    """Print the discovered or provided chapter ranges."""

    print("Available chapters:")
    for i, chapter in enumerate(chapters, start=1):
        print(f"{i}. {chapter.title} (pages {chapter.start_page}-{chapter.end_page})")


def parse_selection(selection: str) -> list[tuple[int, int]]:
    """Parse a comma-delimited chapter selection string into ranges."""

    ranges: list[tuple[int, int]] = []
    for token in selection.replace(" ", "").split(","):
        if not token:
            continue
        try:
            if "-" in token:
                start_str, end_str = token.split("-", 1)
                start = int(start_str)
                end = int(end_str)
            else:
                start = end = int(token)
        except ValueError as exc:
            raise ValueError("Use chapter numbers like 1 or 1-3.") from exc
        if start < 1 or end < 1:
            raise ValueError("Chapter numbers must be positive.")
        if start > end:
            start, end = end, start
        ranges.append((start, end))
    if not ranges:
        raise ValueError("No chapter numbers detected.")
    return ranges


def prompt_for_chapter_selection(total_chapters: int) -> list[tuple[int, int]]:
    """Prompt the user to choose which chapters to export."""

    while True:
        selection = input("Enter chapters to extract (e.g., 1 or 1-3,5): ").strip()
        if not selection:
            return []
        try:
            ranges = parse_selection(selection)
        except ValueError as error:
            print(error)
            continue
        if any(end > total_chapters for _, end in ranges):
            print(f"Choose numbers between 1 and {total_chapters}.")
            continue
        return ranges


def ensure_pdftotext_available(command: str = PDFTOTEXT_COMMAND) -> str:
    """Return the pdftotext command path or raise if it is missing."""

    resolved = shutil.which(command)
    if not resolved:
        raise FileNotFoundError(
            f"Required '{command}' executable not found on PATH. Install poppler or adjust PATH."
        )
    return resolved


def run_pdftotext(
    command: str,
    pdf_path: Path,
    start_page: int,
    end_page: int,
    output_path: Path,
) -> None:
    """Run pdftotext for the requested page range."""

    args = [
        command,
        "-f",
        str(start_page),
        "-l",
        str(end_page),
        str(pdf_path),
        str(output_path),
    ]
    try:
        subprocess.run(args, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"pdftotext failed for pages {start_page}-{end_page} (exit code {exc.returncode})."
        ) from exc


def build_output_filename(
    book_slug: str,
    subset: list[ChapterRange],
    start_idx: int,
    end_idx: int,
) -> str:
    """Compose an output filename for the selected chapter range."""

    if not subset:
        raise ValueError("subset must not be empty")
    suffix = (
        f"chapter_{start_idx}"
        if start_idx == end_idx
        else f"chapters_{start_idx}-{end_idx}"
    )
    parts = [book_slug, suffix]
    if start_idx == end_idx:
        parts.append(slugify_for_filename(subset[0].title, fallback="chapter"))
    return "_".join(parts) + ".txt"


def main() -> None:
    """Entry point for the interactive chapter extraction workflow."""

    try:
        pdftotext_cmd = ensure_pdftotext_available()
    except FileNotFoundError as error:
        print(error)
        return

    current_dir = Path(__file__).resolve().parent
    pdfs = find_pdfs(current_dir)
    selected_pdf = choose_pdf(pdfs)
    if not selected_pdf:
        return

    print(f"You selected: {selected_pdf.name}")

    try:
        chapters = extract_chapter_ranges(selected_pdf)
    except PdfReadError as error:
        print(f"Could not read chapters automatically: {error}")
        chapters = []

    if not chapters:
        chapters = prompt_manual_chapters()
        if not chapters:
            print("No chapters provided. Exiting.")
            return

    display_chapters(chapters)

    selections = prompt_for_chapter_selection(len(chapters))
    if not selections:
        print("No chapters selected. Exiting.")
        return

    slugged_book = slugify_for_filename(selected_pdf.stem, fallback="book")

    print("You chose the following ranges:")
    for start_idx, end_idx in selections:
        start_chapter = chapters[start_idx - 1]
        end_chapter = chapters[end_idx - 1]
        if start_idx == end_idx:
            label = f"Chapter {start_idx}"
        else:
            label = f"Chapters {start_idx}-{end_idx}"
        print(f"- {label}: pages {start_chapter.start_page}-{end_chapter.end_page}")

    for start_idx, end_idx in selections:
        subset = chapters[start_idx - 1 : end_idx]
        if not subset:
            continue
        range_start = subset[0].start_page
        range_end = subset[-1].end_page
        output_name = build_output_filename(slugged_book, subset, start_idx, end_idx)
        output_path = selected_pdf.with_name(output_name)
        try:
            run_pdftotext(pdftotext_cmd, selected_pdf, range_start, range_end, output_path)
        except RuntimeError as error:
            print(error)
            if output_path.exists():
                try:
                    output_path.unlink()
                except OSError:
                    pass
            continue
        print(f"Created {output_path.name} (pages {range_start}-{range_end}).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
