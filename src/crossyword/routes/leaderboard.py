"""Leaderboard routes."""

import datetime as dt

from sqlmodel import Session, select
from xitzin import Request, Xitzin
from xitzin.auth import optional_certificate

from ..daily import get_todays_puzzle
from ..game import auto_pause_active_puzzles
from ..models import CompletedPuzzle, DailyPuzzle, User
from ..rendering import format_time
from ..users import get_or_create_user


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

            if not puzzle:
                return app.template(
                    "leaderboard.gmi",
                    title="Leaderboard",
                    puzzle={"title": "No puzzle assigned yet"},
                    entries=[],
                )

            return app.template(
                "leaderboard.gmi",
                title="Today's Leaderboard",
                puzzle=puzzle,
                entries=get_leaderboard_entries(session, puzzle.id),
            )

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

            if not daily:
                return app.template(
                    "leaderboard.gmi",
                    title=f"Leaderboard for {date_str}",
                    puzzle={"title": "No puzzle assigned"},
                    entries=[],
                )

            return app.template(
                "leaderboard.gmi",
                title=f"Leaderboard for {date_str}",
                puzzle=daily.puzzle,
                entries=get_leaderboard_entries(session, daily.puzzle.id),
            )
