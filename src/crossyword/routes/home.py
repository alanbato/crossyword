"""Home page routes."""

from sqlmodel import Session
from xitzin import Request, Xitzin
from xitzin.auth import optional_certificate

from ..daily import get_or_assign_todays_puzzle
from ..rendering import apply_colors, render_logo
from ..users import get_or_create_user


def register_routes(app: Xitzin) -> None:
    """Register home page routes."""

    @app.gemini("/")
    @optional_certificate
    def home(request: Request):
        """Home page with welcome and navigation."""
        identity = request.state.identity

        if identity:
            with Session(request.app.state.engine) as session:
                user = get_or_create_user(session, identity.fingerprint)
                puzzle = get_or_assign_todays_puzzle(session)

                logo = render_logo()
                if user.use_colors:
                    logo = apply_colors(logo)

                return app.template(
                    "home.gmi",
                    user=user,
                    display_name=user.display_name or identity.short_id,
                    puzzle=puzzle,
                    logo=logo,
                )

        return app.template("home.gmi", user=None, puzzle=None, logo=render_logo())

    @app.gemini("/help")
    def help_page(request: Request):
        """How to play instructions."""
        return app.template("help.gmi")
