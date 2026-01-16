"""Leaderboard routes."""

import datetime as dt

from sqlmodel import Session, select
from xitzin import Request, Xitzin

from ..daily import get_todays_puzzle
from ..models import CompletedPuzzle, DailyPuzzle, User
from ..rendering import format_time


def register_routes(app: Xitzin) -> None:
    """Register leaderboard routes."""

    @app.gemini("/leaderboard")
    def today_leaderboard(request: Request):
        """Show today's puzzle leaderboard."""
        with Session(request.app.state.engine) as session:
            puzzle = get_todays_puzzle(session)

            if not puzzle:
                return app.template(
                    "leaderboard.gmi",
                    title="Leaderboard",
                    puzzle={"title": "No puzzle assigned yet"},
                    entries=[],
                )

            statement = (
                select(CompletedPuzzle, User)
                .join(User)
                .where(CompletedPuzzle.puzzle_id == puzzle.id)
                .order_by(CompletedPuzzle.completion_time_seconds)
            )
            results = session.exec(statement).all()

            entries = [
                {
                    "name": user.display_name or user.fingerprint[:8],
                    "time": format_time(completed.completion_time_seconds),
                }
                for completed, user in results
            ]

            return app.template(
                "leaderboard.gmi",
                title="Today's Leaderboard",
                puzzle=puzzle,
                entries=entries,
            )

    @app.gemini("/leaderboard/{date_str}")
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

            puzzle = daily.puzzle

            statement = (
                select(CompletedPuzzle, User)
                .join(User)
                .where(CompletedPuzzle.puzzle_id == puzzle.id)
                .order_by(CompletedPuzzle.completion_time_seconds)
            )
            results = session.exec(statement).all()

            entries = [
                {
                    "name": user.display_name or user.fingerprint[:8],
                    "time": format_time(completed.completion_time_seconds),
                }
                for completed, user in results
            ]

            return app.template(
                "leaderboard.gmi",
                title=f"Leaderboard for {date_str}",
                puzzle=puzzle,
                entries=entries,
            )
