"""Home page routes."""

from sqlmodel import Session
from xitzin import Request, Xitzin
from xitzin.auth import optional_certificate

from ..daily import get_or_assign_todays_puzzle
from ..game import auto_pause_active_puzzles
from ..rendering import apply_colors, render_logo
from ..users import get_or_create_user
from .leaderboard import get_leaderboard_entries


def register_routes(app: Xitzin) -> None:
    """Register home page routes."""

    @app.gemini("/")
    @optional_certificate
    def home(request: Request):
        """Home page with welcome and navigation."""
        identity = request.state.identity

        with Session(request.app.state.engine) as session:
            if identity:
                user = get_or_create_user(session, identity.fingerprint)
                puzzle = get_or_assign_todays_puzzle(session)

                # Auto-pause any active puzzles when navigating away
                auto_pause_active_puzzles(session, user.id)

                logo = render_logo()
                if user.use_colors:
                    logo = apply_colors(logo)

                # Get top 5 leaderboard entries for homepage preview
                leaderboard = []
                if puzzle:
                    leaderboard = get_leaderboard_entries(session, puzzle.id, limit=5)

                return app.template(
                    "home.gmi",
                    user=user,
                    display_name=user.display_name or identity.short_id,
                    puzzle=puzzle,
                    logo=logo,
                    leaderboard=leaderboard,
                )

            # Non-authenticated user - still show puzzle and leaderboard
            puzzle = get_or_assign_todays_puzzle(session)
            leaderboard = []
            if puzzle:
                leaderboard = get_leaderboard_entries(session, puzzle.id, limit=5)

            return app.template(
                "home.gmi",
                user=None,
                puzzle=puzzle,
                logo=render_logo(),
                leaderboard=leaderboard,
            )

    @app.gemini("/help")
    def help_page(request: Request):
        """How to play instructions."""
        return app.template("help.gmi")
