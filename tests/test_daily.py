"""Tests for crossyword.daily module - requires freezegun for date mocking."""

import datetime as dt

from freezegun import freeze_time
from sqlmodel import Session, select

from crossyword.daily import (
    assign_daily_puzzle,
    get_or_assign_todays_puzzle,
    get_puzzle_for_date,
    get_todays_puzzle,
)
from crossyword.models import DailyPuzzle, Puzzle


class TestGetTodaysPuzzle:
    """Tests for get_todays_puzzle function."""

    @freeze_time("2025-01-15")
    def test_returns_none_when_no_assignment(self, db_session: Session):
        """Returns None when no puzzle assigned for today."""
        result = get_todays_puzzle(db_session)
        assert result is None

    @freeze_time("2025-01-15")
    def test_returns_puzzle_when_assigned(
        self, db_session: Session, test_puzzle: Puzzle
    ):
        """Returns puzzle when one is assigned for today."""
        daily = DailyPuzzle(date=dt.date(2025, 1, 15), puzzle_id=test_puzzle.id)
        db_session.add(daily)
        db_session.commit()

        result = get_todays_puzzle(db_session)

        assert result is not None
        assert result.id == test_puzzle.id

    @freeze_time("2025-01-15")
    def test_does_not_return_other_dates(
        self, db_session: Session, test_puzzle: Puzzle
    ):
        """Does not return puzzles assigned to other dates."""
        # Assign to yesterday
        daily = DailyPuzzle(date=dt.date(2025, 1, 14), puzzle_id=test_puzzle.id)
        db_session.add(daily)
        db_session.commit()

        result = get_todays_puzzle(db_session)

        assert result is None


class TestAssignDailyPuzzle:
    """Tests for assign_daily_puzzle function."""

    @freeze_time("2025-01-15")
    def test_assigns_puzzle_to_today(self, db_session: Session, test_puzzle: Puzzle):
        """Assigns a puzzle to today's date."""
        result = assign_daily_puzzle(db_session)

        assert result is not None
        assert result.id == test_puzzle.id

        # Verify DailyPuzzle was created
        daily = db_session.exec(
            select(DailyPuzzle).where(DailyPuzzle.date == dt.date(2025, 1, 15))
        ).first()
        assert daily is not None
        assert daily.puzzle_id == test_puzzle.id

    @freeze_time("2025-01-15")
    def test_assigns_to_specific_date(self, db_session: Session, test_puzzle: Puzzle):
        """Assigns puzzle to a specified target date."""
        target = dt.date(2025, 2, 1)

        result = assign_daily_puzzle(db_session, target_date=target)

        assert result is not None
        daily = db_session.exec(
            select(DailyPuzzle).where(DailyPuzzle.date == target)
        ).first()
        assert daily is not None
        assert daily.puzzle_id == test_puzzle.id

    @freeze_time("2025-01-15")
    def test_returns_existing_assignment(
        self, db_session: Session, test_puzzle: Puzzle
    ):
        """Returns existing puzzle if already assigned."""
        # First assignment
        first = assign_daily_puzzle(db_session)
        # Second call should return same
        second = assign_daily_puzzle(db_session)

        assert first.id == second.id

    @freeze_time("2025-01-15")
    def test_returns_none_when_no_puzzles(self, db_session: Session):
        """Returns None when no puzzles exist in database."""
        result = assign_daily_puzzle(db_session)
        assert result is None

    @freeze_time("2025-01-15")
    def test_recycles_oldest_when_all_assigned(
        self, db_session: Session, test_puzzle: Puzzle
    ):
        """Recycles oldest puzzle when all have been assigned."""
        # Assign the only puzzle to a past date
        past_date = dt.date(2025, 1, 1)
        past_daily = DailyPuzzle(date=past_date, puzzle_id=test_puzzle.id)
        db_session.add(past_daily)
        db_session.commit()

        # Now assign for today - should recycle
        result = assign_daily_puzzle(db_session)

        assert result is not None
        assert result.id == test_puzzle.id

    @freeze_time("2025-01-15")
    def test_prefers_unassigned_puzzles(self, db_session: Session, test_puz_path):
        """Prefers unassigned puzzles over recycling."""
        import puz

        # Create two puzzles
        p = puz.read(str(test_puz_path))
        numbering = p.clue_numbering()

        puzzle1 = Puzzle(
            filename="puzzle1.puz",
            title="Puzzle 1",
            width=p.width,
            height=p.height,
            clue_count=len(numbering.across) + len(numbering.down),
        )
        puzzle2 = Puzzle(
            filename="puzzle2.puz",
            title="Puzzle 2",
            width=p.width,
            height=p.height,
            clue_count=len(numbering.across) + len(numbering.down),
        )
        db_session.add(puzzle1)
        db_session.add(puzzle2)
        db_session.commit()
        db_session.refresh(puzzle1)
        db_session.refresh(puzzle2)

        # Assign puzzle1 to a past date
        past_daily = DailyPuzzle(date=dt.date(2025, 1, 1), puzzle_id=puzzle1.id)
        db_session.add(past_daily)
        db_session.commit()

        # Assign for today - should pick puzzle2 (unassigned)
        result = assign_daily_puzzle(db_session)

        assert result is not None
        assert result.id == puzzle2.id


class TestGetOrAssignTodaysPuzzle:
    """Tests for get_or_assign_todays_puzzle function."""

    @freeze_time("2025-01-15")
    def test_returns_existing(self, db_session: Session, test_puzzle: Puzzle):
        """Returns existing assignment if present."""
        daily = DailyPuzzle(date=dt.date(2025, 1, 15), puzzle_id=test_puzzle.id)
        db_session.add(daily)
        db_session.commit()

        result = get_or_assign_todays_puzzle(db_session)

        assert result.id == test_puzzle.id

    @freeze_time("2025-01-15")
    def test_creates_assignment_if_missing(
        self, db_session: Session, test_puzzle: Puzzle
    ):
        """Creates new assignment if none exists."""
        result = get_or_assign_todays_puzzle(db_session)

        assert result is not None

        # Verify it was persisted
        daily = db_session.exec(
            select(DailyPuzzle).where(DailyPuzzle.date == dt.date(2025, 1, 15))
        ).first()
        assert daily is not None

    @freeze_time("2025-01-15")
    def test_idempotent(self, db_session: Session, test_puzzle: Puzzle):
        """Multiple calls return same puzzle."""
        first = get_or_assign_todays_puzzle(db_session)
        second = get_or_assign_todays_puzzle(db_session)

        assert first.id == second.id


class TestGetPuzzleForDate:
    """Tests for get_puzzle_for_date function."""

    def test_returns_puzzle_for_date(self, db_session: Session, test_puzzle: Puzzle):
        """Returns puzzle assigned to specific date."""
        target = dt.date(2025, 3, 15)
        daily = DailyPuzzle(date=target, puzzle_id=test_puzzle.id)
        db_session.add(daily)
        db_session.commit()

        result = get_puzzle_for_date(db_session, target)

        assert result is not None
        assert result.id == test_puzzle.id

    def test_returns_none_for_unassigned_date(self, db_session: Session):
        """Returns None for dates without assignment."""
        result = get_puzzle_for_date(db_session, dt.date(2099, 12, 31))
        assert result is None

    def test_does_not_auto_assign(self, db_session: Session, test_puzzle: Puzzle):
        """Does not create assignment for missing dates."""
        target = dt.date(2025, 6, 1)

        result = get_puzzle_for_date(db_session, target)

        assert result is None
        # Verify no DailyPuzzle was created
        daily = db_session.exec(
            select(DailyPuzzle).where(DailyPuzzle.date == target)
        ).first()
        assert daily is None

    def test_returns_correct_puzzle_among_many(
        self, db_session: Session, test_puz_path
    ):
        """Returns correct puzzle when multiple dates are assigned."""
        import puz

        p = puz.read(str(test_puz_path))
        numbering = p.clue_numbering()

        # Create multiple puzzles and assignments
        puzzles = []
        for i in range(3):
            puzzle = Puzzle(
                filename=f"puzzle{i}.puz",
                title=f"Puzzle {i}",
                width=p.width,
                height=p.height,
                clue_count=len(numbering.across) + len(numbering.down),
            )
            db_session.add(puzzle)
            puzzles.append(puzzle)
        db_session.commit()

        for i, puzzle in enumerate(puzzles):
            db_session.refresh(puzzle)
            daily = DailyPuzzle(
                date=dt.date(2025, 1, 10 + i),
                puzzle_id=puzzle.id,
            )
            db_session.add(daily)
        db_session.commit()

        # Query middle date
        result = get_puzzle_for_date(db_session, dt.date(2025, 1, 11))

        assert result is not None
        assert result.title == "Puzzle 1"
