"""Leaderboard routes."""

import datetime as dt

from sqlmodel import Session, func, select
from xitzin import Request, Xitzin
from xitzin.auth import optional_certificate

from ..daily import get_todays_puzzle
from ..game import auto_pause_active_puzzles
from ..models import CompletedPuzzle, DailyPuzzle, User
from ..rendering import format_time
from ..users import get_or_create_user


def get_adjacent_puzzle_dates(
    session: Session, current_date: dt.date
) -> tuple[str | None, str | None]:
    """Get previous and next dates that have puzzles.

    Returns:
        Tuple of (prev_date_str, next_date_str), either can be None if not available
    """
    today = dt.date.today()

    # Get previous date with puzzle
    prev_stmt = (
        select(DailyPuzzle.date)
        .where(DailyPuzzle.date < current_date)
        .order_by(DailyPuzzle.date.desc())
        .limit(1)
    )
    prev_result = session.exec(prev_stmt).first()
    prev_date = prev_result.strftime("%Y-%m-%d") if prev_result else None

    # Get next date with puzzle (but not future dates)
    next_stmt = (
        select(DailyPuzzle.date)
        .where(DailyPuzzle.date > current_date)
        .where(DailyPuzzle.date <= today)
        .order_by(DailyPuzzle.date.asc())
        .limit(1)
    )
    next_result = session.exec(next_stmt).first()
    next_date = next_result.strftime("%Y-%m-%d") if next_result else None

    return prev_date, next_date


def get_leaderboard_entries(
    session: Session, puzzle_id: int, limit: int | None = None
) -> list[dict]:
    """Get leaderboard entries for a puzzle.

    Args:
        session: Database session
        puzzle_id: ID of the puzzle to get leaderboard for
        limit: Optional max number of entries to return
    """
    statement = (
        select(CompletedPuzzle, User)
        .join(User)
        .where(CompletedPuzzle.puzzle_id == puzzle_id)
        .order_by(CompletedPuzzle.completion_time_seconds)
    )
    if limit:
        statement = statement.limit(limit)
    return [
        {
            "name": user.display_name or user.fingerprint[:8],
            "username": user.display_name,
            "time": format_time(completed.completion_time_seconds),
        }
        for completed, user in session.exec(statement).all()
    ]


def register_routes(app: Xitzin) -> None:
    """Register leaderboard routes."""

    @app.gemini("/leaderboard")
    @optional_certificate
    def today_leaderboard(request: Request):
        """Show today's puzzle leaderboard."""
        with Session(request.app.state.engine) as session:
            # Auto-pause any active puzzles when navigating away
            identity = request.state.identity
            if identity:
                user = get_or_create_user(session, identity.fingerprint)
                auto_pause_active_puzzles(session, user.id)

            puzzle = get_todays_puzzle(session)
            today = dt.date.today()

            if not puzzle:
                return app.template(
                    "leaderboard.gmi",
                    title="Leaderboard",
                    puzzle={"title": "No puzzle assigned yet"},
                    entries=[],
                    prev_date=None,
                    next_date=None,
                    current_date=today.strftime("%Y-%m-%d"),
                    is_today=True,
                )

            prev_date, next_date = get_adjacent_puzzle_dates(session, today)

            return app.template(
                "leaderboard.gmi",
                title="Today's Leaderboard",
                puzzle=puzzle,
                entries=get_leaderboard_entries(session, puzzle.id),
                prev_date=prev_date,
                next_date=next_date,
                current_date=today.strftime("%Y-%m-%d"),
                is_today=True,
            )

    @app.gemini("/leaderboard/archive")
    @optional_certificate
    def leaderboard_archive(request: Request):
        """Browse all available leaderboards by date."""
        with Session(request.app.state.engine) as session:
            # Auto-pause any active puzzles when navigating away
            identity = request.state.identity
            if identity:
                user = get_or_create_user(session, identity.fingerprint)
                auto_pause_active_puzzles(session, user.id)

            # Get all daily puzzles up to today
            today = dt.date.today()

            # Get completion counts per puzzle
            completion_counts = dict(
                session.exec(
                    select(
                        CompletedPuzzle.puzzle_id, func.count(CompletedPuzzle.id)
                    ).group_by(CompletedPuzzle.puzzle_id)
                ).all()
            )

            # Get all daily puzzles up to today
            statement = (
                select(DailyPuzzle)
                .where(DailyPuzzle.date <= today)
                .order_by(DailyPuzzle.date.desc())
            )
            daily_puzzles = session.exec(statement).all()

            # Build archive entries
            entries = [
                {
                    "date": daily.date.strftime("%Y-%m-%d"),
                    "title": daily.puzzle.title,
                    "completions": completion_counts.get(daily.puzzle.id, 0),
                }
                for daily in daily_puzzles
            ]

            return app.template("leaderboard_archive.gmi", entries=entries)

    @app.gemini("/leaderboard/{date_str}")
    @optional_certificate
    def historical_leaderboard(request: Request, date_str: str):
        """Show leaderboard for a specific date."""
        try:
            target_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return app.template(
                "error.gmi",
                title="Invalid Date",
                message="Use format: YYYY-MM-DD\n\n=> /leaderboard Today's Leaderboard",
            )

        with Session(request.app.state.engine) as session:
            # Auto-pause any active puzzles when navigating away
            identity = request.state.identity
            if identity:
                user = get_or_create_user(session, identity.fingerprint)
                auto_pause_active_puzzles(session, user.id)

            daily = session.exec(
                select(DailyPuzzle).where(DailyPuzzle.date == target_date)
            ).first()

            today = dt.date.today()
            is_today = target_date == today
            prev_date, next_date = get_adjacent_puzzle_dates(session, target_date)

            if not daily:
                return app.template(
                    "leaderboard.gmi",
                    title=f"Leaderboard for {date_str}",
                    puzzle={"title": "No puzzle assigned"},
                    entries=[],
                    prev_date=prev_date,
                    next_date=next_date,
                    current_date=date_str,
                    is_today=is_today,
                )

            return app.template(
                "leaderboard.gmi",
                title=f"Leaderboard for {date_str}",
                puzzle=daily.puzzle,
                entries=get_leaderboard_entries(session, daily.puzzle.id),
                prev_date=prev_date,
                next_date=next_date,
                current_date=date_str,
                is_today=is_today,
            )
