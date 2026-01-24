"""Utility for importing .puz files into the database."""

import datetime as dt
import os
import re
from pathlib import Path

import puz
from sqlmodel import Session, select

from .models import Puzzle

# Mapping of filename prefixes to source names (for short prefix format)
SOURCE_PREFIX_MAP = {
    "nd": "Newsday",
    "nyt": "New York Times",
    "lat": "LA Times",
    "wsj": "Wall Street Journal",
    "usa": "USA Today",
}


def parse_filename_metadata(filename: str) -> tuple[str | None, dt.date | None]:
    """
    Parse source and date from puzzle filename.

    Expected formats:
    - YY-MM-DD_Source_Title_By Author.puz (e.g., 25-01-15_USA Today_Title_By Author.puz)
    - source-YYYY-MM-DD.puz (e.g., nd-2024-01-15.puz)
    - source_YYYY-MM-DD.puz
    - YYYY-MM-DD.puz (date only)

    Returns (source, date) tuple.
    """
    stem = filename.rsplit(".", 1)[0]  # Remove .puz extension

    # Try underscore-separated format: YY-MM-DD_Source_Title_By Author
    parts = stem.split("_")
    if len(parts) >= 2:
        date_part = parts[0]
        source_part = parts[1]

        # Try parsing YY-MM-DD format
        match = re.match(r"^(\d{2})-(\d{2})-(\d{2})$", date_part)
        if match:
            try:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                # Assume 2000s for YY format
                full_year = 2000 + year if year < 100 else year
                original_date = dt.date(full_year, month, day)
                return source_part, original_date
            except ValueError:
                pass

    # Try to match source-date pattern (e.g., nd-2024-01-15)
    match = re.match(r"^([a-zA-Z]+)[-_](\d{4}-\d{2}-\d{2})$", stem)
    if match:
        prefix = match.group(1).lower()
        date_str = match.group(2)
        source = SOURCE_PREFIX_MAP.get(prefix, prefix.upper())
        try:
            original_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            return source, original_date
        except ValueError:
            return source, None

    # Try date-only pattern
    match = re.match(r"^(\d{4}-\d{2}-\d{2})$", stem)
    if match:
        try:
            original_date = dt.datetime.strptime(match.group(1), "%Y-%m-%d").date()
            return None, original_date
        except ValueError:
            pass

    return None, None


def import_puzzles(session: Session, puzzles_dir: Path) -> list[Puzzle]:
    """
    Import all .puz files from directory into database.

    Returns list of newly imported puzzles.
    """
    imported = []

    if not puzzles_dir.exists():
        return imported

    for filename in os.listdir(puzzles_dir):
        if not filename.endswith(".puz"):
            continue

        existing = session.exec(
            select(Puzzle).where(Puzzle.filename == filename)
        ).first()
        if existing:
            continue

        filepath = puzzles_dir / filename
        try:
            p = puz.read(str(filepath))
        except Exception as e:
            print(f"Failed to parse {filename}: {e}")
            continue

        numbering = p.clue_numbering()
        clue_count = len(numbering.across) + len(numbering.down)

        source, original_date = parse_filename_metadata(filename)

        puzzle = Puzzle(
            filename=filename,
            title=p.title or filename,
            author=p.author or None,
            copyright=getattr(p, "copyright", None),
            source=source,
            original_date=original_date,
            width=p.width,
            height=p.height,
            clue_count=clue_count,
        )

        session.add(puzzle)
        imported.append(puzzle)

    if imported:
        session.commit()

    return imported


def import_puzzle_file(
    session: Session, filepath: Path, puzzles_dir: Path
) -> Puzzle | None:
    """
    Import a single .puz file.

    Copies the file to puzzles_dir if not already there.
    """
    import shutil

    filename = filepath.name
    target_path = puzzles_dir / filename

    if filepath != target_path and not target_path.exists():
        puzzles_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(filepath, target_path)

    imported = import_puzzles(session, puzzles_dir)

    for puzzle in imported:
        if puzzle.filename == filename:
            return puzzle

    return session.exec(select(Puzzle).where(Puzzle.filename == filename)).first()
