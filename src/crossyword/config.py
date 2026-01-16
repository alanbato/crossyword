"""Configuration for Crossyword."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    """Application configuration."""

    database_url: str = "sqlite:///./crossyword.db"
    puzzles_dir: Path = Path("./puzzles")
    host: str = "localhost"
    port: int = 1965
    certfile: Path | None = None
    keyfile: Path | None = None

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        certfile = os.getenv("CROSSYWORD_CERTFILE")
        keyfile = os.getenv("CROSSYWORD_KEYFILE")

        return cls(
            database_url=os.getenv("CROSSYWORD_DATABASE_URL", cls.database_url),
            puzzles_dir=Path(os.getenv("CROSSYWORD_PUZZLES_DIR", str(cls.puzzles_dir))),
            host=os.getenv("CROSSYWORD_HOST", cls.host),
            port=int(os.getenv("CROSSYWORD_PORT", str(cls.port))),
            certfile=Path(certfile) if certfile else None,
            keyfile=Path(keyfile) if keyfile else None,
        )
