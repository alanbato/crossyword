"""Shared test fixtures for Crossyword."""

import datetime as dt
from pathlib import Path

import puz
import pytest
from sqlmodel import Session, SQLModel, create_engine

from crossyword.config import Config
from crossyword.models import (
    CompletedPuzzle,
    DailyPuzzle,
    PlayerProgress,
    Puzzle,
    User,
)


# --- Path fixtures ---


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def puzzles_dir(project_root: Path) -> Path:
    """Return the puzzles directory with existing .puz files."""
    return project_root / "puzzles"


@pytest.fixture
def test_puz_path(puzzles_dir: Path) -> Path:
    """Return path to a known test puzzle file."""
    return (
        puzzles_dir / "21-01-01_Newsday_WHO'S WHAT_S.N., edited by Stanley Newman.puz"
    )


# --- Puzzle data fixtures ---


@pytest.fixture
def puz_data(test_puz_path: Path) -> puz.Puzzle:
    """Load and return puz.Puzzle object from test file."""
    return puz.read(str(test_puz_path))


@pytest.fixture
def empty_fill(puz_data: puz.Puzzle) -> str:
    """Return an empty fill string matching puzzle dimensions."""
    fill = []
    for char in puz_data.solution:
        if char == ".":
            fill.append(".")
        else:
            fill.append(" ")
    return "".join(fill)


@pytest.fixture
def partial_fill(puz_data: puz.Puzzle, empty_fill: str) -> str:
    """Return a partially filled grid (first across answer filled correctly)."""
    fill = list(empty_fill)
    numbering = puz_data.clue_numbering()
    if numbering.across:
        first_clue = numbering.across[0]
        cell = first_clue["cell"]
        length = first_clue["len"]
        for i in range(length):
            fill[cell + i] = puz_data.solution[cell + i]
    return "".join(fill)


# --- Database fixtures ---


@pytest.fixture
def db_engine(tmp_path: Path):
    """Create an in-memory SQLite database engine."""
    db_url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(db_url)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Provide a database session for tests."""
    with Session(db_engine) as session:
        yield session


# --- Model fixtures ---


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create and return a test user."""
    user = User(
        fingerprint="test-fingerprint-abc123",
        display_name="TestPlayer",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_puzzle(db_session: Session, test_puz_path: Path) -> Puzzle:
    """Create and return a test puzzle record in the database."""
    p = puz.read(str(test_puz_path))
    numbering = p.clue_numbering()

    puzzle = Puzzle(
        filename=test_puz_path.name,
        title=p.title or "Test Puzzle",
        author=p.author or None,
        copyright=p.copyright or None,
        width=p.width,
        height=p.height,
        clue_count=len(numbering.across) + len(numbering.down),
    )
    db_session.add(puzzle)
    db_session.commit()
    db_session.refresh(puzzle)
    return puzzle


@pytest.fixture
def test_daily_puzzle(db_session: Session, test_puzzle: Puzzle) -> DailyPuzzle:
    """Create a daily puzzle assignment for today."""
    daily = DailyPuzzle(
        date=dt.date.today(),
        puzzle_id=test_puzzle.id,
    )
    db_session.add(daily)
    db_session.commit()
    db_session.refresh(daily)
    return daily


@pytest.fixture
def test_progress(
    db_session: Session, test_user: User, test_puzzle: Puzzle, empty_fill: str
) -> PlayerProgress:
    """Create player progress for test user."""
    progress = PlayerProgress(
        user_id=test_user.id,
        puzzle_id=test_puzzle.id,
        current_fill=empty_fill,
        solved_clues="[]",
    )
    db_session.add(progress)
    db_session.commit()
    db_session.refresh(progress)
    return progress


@pytest.fixture
def test_completed(
    db_session: Session, test_user: User, test_puzzle: Puzzle
) -> CompletedPuzzle:
    """Create a completed puzzle record."""
    completed = CompletedPuzzle(
        user_id=test_user.id,
        puzzle_id=test_puzzle.id,
        completion_time_seconds=300,
    )
    db_session.add(completed)
    db_session.commit()
    db_session.refresh(completed)
    return completed


# --- App fixtures ---


@pytest.fixture
def test_config(tmp_path: Path, puzzles_dir: Path) -> Config:
    """Create test configuration with temporary database."""
    return Config(
        database_url=f"sqlite:///{tmp_path}/test.db",
        puzzles_dir=puzzles_dir,
    )


@pytest.fixture
def app(test_config: Config):
    """Create test application instance."""
    from crossyword.app import create_app

    return create_app(test_config)


@pytest.fixture
def client(app):
    """Create test client with lifecycle (startup/shutdown)."""
    from xitzin.testing import test_app

    with test_app(app) as client:
        yield client


@pytest.fixture
def auth_client(client):
    """Create authenticated test client with display name."""
    # First create user with display name via direct DB access
    from sqlmodel import Session

    with Session(client._app.state.engine) as session:
        user = User(
            fingerprint="test-fingerprint-abc123",
            display_name="TestPlayer",
        )
        session.add(user)
        session.commit()

    return client.with_certificate("test-fingerprint-abc123")
