"""Daily puzzle selection and assignment."""

import random
import datetime as dt

from sqlmodel import Session, select

from .models import DailyPuzzle, Puzzle


def get_todays_puzzle(session: Session) -> Puzzle | None:
    """Get today's assigned puzzle."""
    today = dt.date.today()

    statement = select(DailyPuzzle).where(DailyPuzzle.date == today)
    daily = session.exec(statement).first()

    if daily:
        return daily.puzzle

    return None


def assign_daily_puzzle(
    session: Session, target_date: dt.date | None = None
) -> Puzzle | None:
    """
    Assign a puzzle to a date.

    Selection strategy:
    1. Find puzzles not yet assigned to any date
    2. Random selection from candidates
    3. If all assigned, recycle oldest
    """
    target_date = target_date or dt.date.today()

    existing = session.exec(
        select(DailyPuzzle).where(DailyPuzzle.date == target_date)
    ).first()
    if existing:
        return existing.puzzle

    assigned_ids = list(session.exec(select(DailyPuzzle.puzzle_id)).all())

    if assigned_ids:
        statement = select(Puzzle).where(Puzzle.id.not_in(assigned_ids))
    else:
        statement = select(Puzzle)

    candidates = list(session.exec(statement).all())

    if not candidates:
        oldest = session.exec(select(DailyPuzzle).order_by(DailyPuzzle.date)).first()
        if oldest:
            candidates = [oldest.puzzle]

    if not candidates:
        return None

    selected = random.choice(candidates)

    daily = DailyPuzzle(date=target_date, puzzle_id=selected.id)
    session.add(daily)
    session.commit()

    return selected


def get_or_assign_todays_puzzle(session: Session) -> Puzzle | None:
    """Get today's puzzle, assigning one if needed."""
    puzzle = get_todays_puzzle(session)
    if puzzle:
        return puzzle
    return assign_daily_puzzle(session)


def get_puzzle_for_date(session: Session, target_date: dt.date) -> Puzzle | None:
    """Get puzzle assigned to a specific date (no auto-assignment)."""
    statement = select(DailyPuzzle).where(DailyPuzzle.date == target_date)
    daily = session.exec(statement).first()
    return daily.puzzle if daily else None
