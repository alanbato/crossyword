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
                return "# Leaderboard\n\nNo puzzle assigned for today yet.\n\n=> / Home"

            statement = (
                select(CompletedPuzzle, User)
                .join(User)
                .where(CompletedPuzzle.puzzle_id == puzzle.id)
                .order_by(CompletedPuzzle.completion_time_seconds)
            )
            results = session.exec(statement).all()

            lines = [
                "# Today's Leaderboard",
                "",
                f"Puzzle: {puzzle.title}",
                "",
            ]

            if not results:
                lines.append("No completions yet. Be the first!")
            else:
                lines.append(f"{len(results)} completion(s)")
                lines.append("")

                for i, (completed, user) in enumerate(results, 1):
                    name = user.display_name or user.fingerprint[:8]
                    time_str = format_time(completed.completion_time_seconds)
                    lines.append(f"{i}. {name} - {time_str}")

            lines.extend(
                [
                    "",
                    "=> /puzzle Play Today's Puzzle",
                    "=> / Home",
                ]
            )

            return "\n".join(lines)

    @app.gemini("/leaderboard/{date_str}")
    def historical_leaderboard(request: Request, date_str: str):
        """Show leaderboard for a specific date."""
        try:
            target_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return "# Invalid Date\n\nUse format: YYYY-MM-DD\n\n=> /leaderboard Today's Leaderboard"

        with Session(request.app.state.engine) as session:
            daily = session.exec(select(DailyPuzzle).where(DailyPuzzle.date == target_date)).first()

            if not daily:
                return f"# No Puzzle for {date_str}\n\nNo puzzle was assigned for this date.\n\n=> /leaderboard Today's Leaderboard"

            puzzle = daily.puzzle

            statement = (
                select(CompletedPuzzle, User)
                .join(User)
                .where(CompletedPuzzle.puzzle_id == puzzle.id)
                .order_by(CompletedPuzzle.completion_time_seconds)
            )
            results = session.exec(statement).all()

            lines = [
                f"# Leaderboard for {date_str}",
                "",
                f"Puzzle: {puzzle.title}",
                "",
            ]

            if not results:
                lines.append("No completions recorded.")
            else:
                lines.append(f"{len(results)} completion(s)")
                lines.append("")

                for i, (completed, user) in enumerate(results, 1):
                    name = user.display_name or user.fingerprint[:8]
                    time_str = format_time(completed.completion_time_seconds)
                    lines.append(f"{i}. {name} - {time_str}")

            today = dt.date.today()
            yesterday = today.replace(day=today.day - 1) if today.day > 1 else today

            lines.extend(
                [
                    "",
                    "=> /leaderboard Today's Leaderboard",
                    "=> / Home",
                ]
            )

            return "\n".join(lines)
