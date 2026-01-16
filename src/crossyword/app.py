"""Xitzin application factory for Crossyword."""

from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine
from xitzin import Xitzin

from .config import Config
from .puzzle_import import import_puzzles


def create_app(config: Config | None = None) -> Xitzin:
    """Create and configure the Xitzin application."""
    config = config or Config.from_env()

    templates_dir = Path(__file__).parent / "templates"

    app = Xitzin(
        title="Crossyword",
        version="0.1.0",
        templates_dir=templates_dir,
    )

    engine = create_engine(config.database_url)
    app.state.engine = engine
    app.state.config = config

    @app.on_startup
    async def startup():
        """Initialize database and import puzzles."""
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            imported = import_puzzles(session, config.puzzles_dir)
            if imported:
                print(f"Imported {len(imported)} puzzle(s)")

    from .routes import home, leaderboard, profile, puzzle

    home.register_routes(app)
    puzzle.register_routes(app)
    leaderboard.register_routes(app)
    profile.register_routes(app)

    return app


def get_session(app: Xitzin) -> Session:
    """Get a database session from the app."""
    return Session(app.state.engine)
