"""User profile routes."""

from sqlmodel import Session, func, select
from xitzin import Request, Xitzin
from xitzin.auth import get_identity, require_certificate

from ..models import CompletedPuzzle, PlayerProgress
from ..rendering import format_time
from ..users import get_or_create_user


def register_routes(app: Xitzin) -> None:
    """Register profile routes."""

    @app.gemini("/profile")
    @require_certificate
    def user_profile(request: Request):
        """User statistics and history."""
        identity = get_identity(request)

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)

            completed_count = session.exec(
                select(func.count(CompletedPuzzle.id)).where(CompletedPuzzle.user_id == user.id)
            ).one()

            in_progress_count = session.exec(
                select(func.count(PlayerProgress.id)).where(PlayerProgress.user_id == user.id)
            ).one()

            best_time = session.exec(
                select(func.min(CompletedPuzzle.completion_time_seconds)).where(
                    CompletedPuzzle.user_id == user.id
                )
            ).one()

            avg_time = session.exec(
                select(func.avg(CompletedPuzzle.completion_time_seconds)).where(
                    CompletedPuzzle.user_id == user.id
                )
            ).one()

            lines = [
                "# Your Profile",
                "",
                f"Certificate ID: {identity.short_id}",
            ]

            if user.display_name:
                lines.append(f"Display Name: {user.display_name}")
            else:
                lines.append("=> /profile/name Set Display Name")

            lines.extend(
                [
                    "",
                    "## Statistics",
                    "",
                    f"Puzzles Completed: {completed_count}",
                    f"Puzzles In Progress: {in_progress_count}",
                ]
            )

            if best_time:
                lines.append(f"Best Time: {format_time(int(best_time))}")

            if avg_time:
                lines.append(f"Average Time: {format_time(int(avg_time))}")

            recent = session.exec(
                select(CompletedPuzzle)
                .where(CompletedPuzzle.user_id == user.id)
                .order_by(CompletedPuzzle.completed_at.desc())
                .limit(5)
            ).all()

            if recent:
                lines.extend(
                    [
                        "",
                        "## Recent Completions",
                        "",
                    ]
                )
                for completed in recent:
                    date_str = completed.completed_at.strftime("%Y-%m-%d")
                    time_str = format_time(completed.completion_time_seconds)
                    lines.append(f"* {date_str} - {time_str}")

            lines.extend(
                [
                    "",
                    "=> /puzzle Today's Puzzle",
                    "=> / Home",
                ]
            )

            return "\n".join(lines)

    @app.input("/profile/name", prompt="Enter your display name:")
    @require_certificate
    def set_display_name(request: Request, query: str):
        """Set user display name."""
        identity = get_identity(request)

        if len(query) > 20:
            return "# Name Too Long\n\nDisplay name must be 20 characters or less.\n\n=> /profile/name Try Again"

        if len(query) < 1:
            return "# Name Too Short\n\nPlease enter a name.\n\n=> /profile/name Try Again"

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)
            user.display_name = query.strip()
            session.commit()

            return f"""# Name Updated

Your display name is now: {user.display_name}

=> /profile Back to Profile
=> / Home
"""
