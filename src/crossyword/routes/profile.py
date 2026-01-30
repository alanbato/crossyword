"""User profile routes."""

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select
from xitzin import Redirect, Request, Xitzin
from xitzin.auth import get_identity, optional_certificate, require_certificate

from ..game import auto_pause_active_puzzles
from ..models import CompletedPuzzle, PlayerProgress, Puzzle, User
from ..rendering import format_time
from ..users import (
    get_or_create_user,
    validate_bio,
    validate_link,
    validate_username,
)


def get_user_stats(
    session: Session, user_id: int
) -> tuple[int, int | None, float | None]:
    """Get completed count, best time, avg time for a user."""
    return session.exec(
        select(
            func.count(CompletedPuzzle.id),
            func.min(CompletedPuzzle.completion_time_seconds),
            func.avg(CompletedPuzzle.completion_time_seconds),
        ).where(CompletedPuzzle.user_id == user_id)
    ).one()


def get_recent_completions(
    session: Session, user_id: int, limit: int = 5
) -> list[dict]:
    """Get recent puzzle completions with titles."""
    recent_completions = session.exec(
        select(CompletedPuzzle, Puzzle)
        .join(Puzzle)
        .where(CompletedPuzzle.user_id == user_id)
        .order_by(CompletedPuzzle.completed_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "date": c.completed_at.strftime("%Y-%m-%d"),
            "time": format_time(c.completion_time_seconds),
            "title": puzzle.title,
        }
        for c, puzzle in recent_completions
    ]


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

            completed_count, best_time, avg_time = get_user_stats(session, user.id)

            in_progress_count = session.exec(
                select(func.count(PlayerProgress.id)).where(
                    PlayerProgress.user_id == user.id
                )
            ).one()

            recent = get_recent_completions(session, user.id)

            return app.template(
                "profile.gmi",
                short_id=identity.short_id,
                display_name=user.display_name,
                bio=user.bio,
                link=user.link,
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

    @app.input("/profile/bio", prompt="Enter your bio (max 500 chars):")
    @require_certificate
    def set_bio(request: Request, query: str):
        """Set user bio."""
        identity = get_identity(request)
        bio = query.strip()

        is_valid, error_msg = validate_bio(bio)
        if not is_valid:
            return app.template(
                "error.gmi",
                title="Invalid Bio",
                message=f"{error_msg}\n\n=> /profile/bio Try Again",
            )

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)

            # Auto-pause any active puzzles when navigating away
            auto_pause_active_puzzles(session, user.id)

            user.bio = bio if bio else None
            session.commit()

            return app.template("bio_updated.gmi", bio=user.bio)

    @app.input(
        "/profile/link", prompt="Enter your link (URL, or leave empty to clear):"
    )
    @require_certificate
    def set_link(request: Request, query: str):
        """Set user link."""
        identity = get_identity(request)
        link = query.strip()

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)

            # Auto-pause any active puzzles when navigating away
            auto_pause_active_puzzles(session, user.id)

            # Allow clearing the link by submitting empty string
            if not link:
                user.link = None
                session.commit()
                return app.template("link_updated.gmi", link=user.link)

            is_valid, error_msg = validate_link(link)
            if not is_valid:
                return app.template(
                    "error.gmi",
                    title="Invalid Link",
                    message=f"{error_msg}\n\n=> /profile/link Try Again",
                )

            user.link = link
            session.commit()

            return app.template("link_updated.gmi", link=user.link)

    @app.gemini("/profile/{username}")
    @optional_certificate
    def public_profile(request: Request, username: str):
        """View a user's public profile."""
        with Session(request.app.state.engine) as session:
            # Auto-pause current user's puzzles if authenticated
            identity = request.state.identity
            if identity:
                current_user = get_or_create_user(session, identity.fingerprint)
                auto_pause_active_puzzles(session, current_user.id)

            # Find the requested user by display_name
            user = session.exec(
                select(User).where(User.display_name == username)
            ).first()

            if not user:
                return app.template(
                    "error.gmi",
                    title="User Not Found",
                    message=f"User '{username}' not found.\n\n=> /leaderboard Back to Leaderboard",
                )

            completed_count, best_time, avg_time = get_user_stats(session, user.id)
            recent = get_recent_completions(session, user.id)

            return app.template(
                "public_profile.gmi",
                display_name=user.display_name,
                bio=user.bio,
                link=user.link,
                completed_count=completed_count,
                best_time=format_time(int(best_time)) if best_time else None,
                avg_time=format_time(int(avg_time)) if avg_time else None,
                recent=recent,
            )
