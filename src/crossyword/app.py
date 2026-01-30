"""Xitzin application factory for Crossyword."""

from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlmodel import SQLModel, Session, create_engine
from xitzin import Xitzin

from .config import Config
from .logging import get_logger
from .puzzle_import import import_puzzles

logger = get_logger(__name__)


def stamp_new_database(engine, database_url: str) -> None:
    """Stamp a newly created database with current migration head.

    This ensures future migrations will run correctly on databases
    that were created via create_all() rather than migrations.
    """
    from sqlalchemy import inspect

    project_root = Path(__file__).parent.parent.parent
    alembic_ini = project_root / "alembic.ini"

    if not alembic_ini.exists():
        return

    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    # If tables exist but no alembic_version, stamp the database
    if "puzzle" in table_names and "alembic_version" not in table_names:
        alembic_cfg = AlembicConfig(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        command.stamp(alembic_cfg, "head")


def run_migrations(engine, database_url: str) -> None:
    """Run Alembic migrations to upgrade database schema.

    Handles three cases:
    1. Existing database with alembic_version: run upgrade to head
    2. Existing database without alembic_version: stamp with head (schema is current)
    3. New database: will be created by create_all(), then stamped
    """
    from sqlalchemy import inspect

    # Find alembic.ini relative to this file
    project_root = Path(__file__).parent.parent.parent
    alembic_ini = project_root / "alembic.ini"

    if not alembic_ini.exists():
        # In development/testing, migrations might not be available
        return

    alembic_cfg = AlembicConfig(str(alembic_ini))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "alembic_version" in table_names:
        # Existing database with migration tracking - run any pending migrations
        command.upgrade(alembic_cfg, "head")
    elif "puzzle" in table_names:
        # Existing database without alembic_version - stamp it as current
        # This handles databases created before Alembic was added
        command.stamp(alembic_cfg, "head")


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
        logger.debug("database_migrations_starting")
        # Run migrations for existing databases first
        run_migrations(engine, config.database_url)
        # Create any missing tables (for new databases or new models)
        SQLModel.metadata.create_all(engine)
        # Stamp new databases so future migrations work correctly
        stamp_new_database(engine, config.database_url)
        logger.debug("database_setup_complete")

        with Session(engine) as session:
            imported = import_puzzles(session, config.puzzles_dir)
            if imported:
                logger.info("puzzles_imported", count=len(imported))

        logger.info("startup_complete")

    from .routes import home, leaderboard, profile, puzzle

    home.register_routes(app)
    puzzle.register_routes(app)
    leaderboard.register_routes(app)
    profile.register_routes(app)

    return app


def get_session(app: Xitzin) -> Session:
    """Get a database session from the app."""
    return Session(app.state.engine)
