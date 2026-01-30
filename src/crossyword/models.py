"""Database models for Crossyword."""

import datetime as dt

from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    """User identified by certificate fingerprint."""

    id: int | None = Field(default=None, primary_key=True)
    fingerprint: str = Field(unique=True, index=True)
    display_name: str | None = Field(default=None, unique=True, index=True)
    bio: str | None = Field(default=None)
    link: str | None = Field(default=None)
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    last_seen: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    use_colors: bool = Field(default=False)

    progress: list["PlayerProgress"] = Relationship(back_populates="user")
    completed_puzzles: list["CompletedPuzzle"] = Relationship(back_populates="user")


class Puzzle(SQLModel, table=True):
    """Puzzle metadata from .puz files."""

    id: int | None = Field(default=None, primary_key=True)
    filename: str = Field(unique=True, index=True)
    title: str
    author: str | None = None
    copyright: str | None = None
    source: str | None = None
    original_date: dt.date | None = None
    width: int
    height: int
    clue_count: int
    imported_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)

    daily_assignments: list["DailyPuzzle"] = Relationship(back_populates="puzzle")
    player_progress: list["PlayerProgress"] = Relationship(back_populates="puzzle")
    completed_by: list["CompletedPuzzle"] = Relationship(back_populates="puzzle")


class DailyPuzzle(SQLModel, table=True):
    """Maps dates to puzzles for daily puzzle selection."""

    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(unique=True, index=True)
    puzzle_id: int = Field(foreign_key="puzzle.id")

    puzzle: Puzzle = Relationship(back_populates="daily_assignments")


class PlayerProgress(SQLModel, table=True):
    """Tracks in-progress puzzle state for each user."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    puzzle_id: int = Field(foreign_key="puzzle.id", index=True)
    current_fill: str
    solved_clues: str = Field(default="[]")
    started_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    last_updated: dt.datetime = Field(default_factory=dt.datetime.utcnow)

    # Pause feature fields
    is_paused: bool = Field(default=False)
    accumulated_seconds: int = Field(default=0)
    pause_started_at: dt.datetime | None = Field(default=None)

    user: User = Relationship(back_populates="progress")
    puzzle: Puzzle = Relationship(back_populates="player_progress")


class CompletedPuzzle(SQLModel, table=True):
    """Leaderboard entries for completed puzzles."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    puzzle_id: int = Field(foreign_key="puzzle.id", index=True)
    completion_time_seconds: int
    completed_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    hints_used: int = Field(default=0)

    user: User = Relationship(back_populates="completed_puzzles")
    puzzle: Puzzle = Relationship(back_populates="completed_by")
