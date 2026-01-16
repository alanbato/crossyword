"""Utility for importing .puz files into the database."""

import os
from pathlib import Path

import puz
from sqlmodel import Session, select

from .models import Puzzle


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

        existing = session.exec(select(Puzzle).where(Puzzle.filename == filename)).first()
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

        puzzle = Puzzle(
            filename=filename,
            title=p.title or filename,
            author=p.author or None,
            copyright=getattr(p, "copyright", None),
            width=p.width,
            height=p.height,
            clue_count=clue_count,
        )

        session.add(puzzle)
        imported.append(puzzle)

    if imported:
        session.commit()

    return imported


def import_puzzle_file(session: Session, filepath: Path, puzzles_dir: Path) -> Puzzle | None:
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
