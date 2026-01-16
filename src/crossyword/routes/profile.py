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
                select(func.count(CompletedPuzzle.id)).where(
                    CompletedPuzzle.user_id == user.id
                )
            ).one()

            in_progress_count = session.exec(
                select(func.count(PlayerProgress.id)).where(
                    PlayerProgress.user_id == user.id
                )
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
                completed_count=completed_count,
                in_progress_count=in_progress_count,
                best_time=format_time(int(best_time)) if best_time else None,
                avg_time=format_time(int(avg_time)) if avg_time else None,
                recent=recent,
            )

    @app.input("/profile/name", prompt="Enter your display name:")
    @require_certificate
    def set_display_name(request: Request, query: str):
        """Set user display name."""
        identity = get_identity(request)

        if len(query) > 20:
            return app.template(
                "error.gmi",
                title="Name Too Long",
                message="Display name must be 20 characters or less.\n\n=> /profile/name Try Again",
            )

        if len(query) < 1:
            return app.template(
                "error.gmi",
                title="Name Too Short",
                message="Please enter a name.\n\n=> /profile/name Try Again",
            )

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)
            user.display_name = query.strip()
            session.commit()

            return app.template("name_updated.gmi", display_name=user.display_name)
