"""User profile routes."""

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select
from xitzin import Redirect, Request, Xitzin
from xitzin.auth import get_identity, require_certificate

from ..game import auto_pause_active_puzzles
from ..models import CompletedPuzzle, PlayerProgress
from ..rendering import format_time
from ..users import get_or_create_user, validate_username


def register_routes(app: Xitzin) -> None:
    """Register profile routes."""

    @app.gemini("/profile")
    @require_certificate
    def user_profile(request: Request):
        """User statistics and history."""
        identity = get_identity(request)

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)

            # Auto-pause any active puzzles when navigating away
            auto_pause_active_puzzles(session, user.id)

            # Combine aggregations into single query
            stats = session.exec(
                select(
                    func.count(CompletedPuzzle.id),
                    func.min(CompletedPuzzle.completion_time_seconds),
                    func.avg(CompletedPuzzle.completion_time_seconds),
                ).where(CompletedPuzzle.user_id == user.id)
            ).one()
            completed_count, best_time, avg_time = stats

            in_progress_count = session.exec(
                select(func.count(PlayerProgress.id)).where(
                    PlayerProgress.user_id == user.id
                )
            ).one()

            recent_completions = session.exec(
                select(CompletedPuzzle)
                .where(CompletedPuzzle.user_id == user.id)
                .order_by(CompletedPuzzle.completed_at.desc())
                .limit(5)
            ).all()

            recent = [
                {
                    "date": c.completed_at.strftime("%Y-%m-%d"),
                    "time": format_time(c.completion_time_seconds),
                }
                for c in recent_completions
            ]

            return app.template(
                "profile.gmi",
                short_id=identity.short_id,
                display_name=user.display_name,
                use_colors=user.use_colors,
                completed_count=completed_count,
                in_progress_count=in_progress_count,
                best_time=format_time(int(best_time)) if best_time else None,
                avg_time=format_time(int(avg_time)) if avg_time else None,
                recent=recent,
            )

    @app.input("/profile/name", prompt="Enter your username:")
    @require_certificate
    def set_display_name(request: Request, query: str):
        """Set user display name (username)."""
        identity = get_identity(request)
        username = query.strip()

        is_valid, error_msg = validate_username(username)
        if not is_valid:
            return app.template(
                "error.gmi",
                title="Invalid Username",
                message=f"{error_msg}\n\n=> /profile/name Try Again",
            )

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)

            # Auto-pause any active puzzles when navigating away
            auto_pause_active_puzzles(session, user.id)

            user.display_name = username
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return app.template(
                    "error.gmi",
                    title="Username Taken",
                    message=f"The username '{username}' is already taken.\n\n=> /profile/name Try Again",
                )

            return app.template("name_updated.gmi", display_name=user.display_name)

    @app.gemini("/profile/colors")
    @require_certificate
    def toggle_colors(request: Request):
        """Toggle ANSI color support for grid rendering."""
        identity = get_identity(request)

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)

            # Auto-pause any active puzzles when navigating away
            auto_pause_active_puzzles(session, user.id)

            user.use_colors = not user.use_colors
            session.commit()

        return Redirect("/profile")
