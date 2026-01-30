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
    log_level: str = "INFO"
    log_file: Path | None = None
    json_logs: bool = False
    hash_fingerprints: bool = True

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        certfile = os.getenv("CROSSYWORD_CERTFILE")
        keyfile = os.getenv("CROSSYWORD_KEYFILE")
        log_file = os.getenv("CROSSYWORD_LOG_FILE")

        return cls(
            database_url=os.getenv("CROSSYWORD_DATABASE_URL", cls.database_url),
            puzzles_dir=Path(os.getenv("CROSSYWORD_PUZZLES_DIR", str(cls.puzzles_dir))),
            host=os.getenv("CROSSYWORD_HOST", cls.host),
            port=int(os.getenv("CROSSYWORD_PORT", str(cls.port))),
            certfile=Path(certfile) if certfile else None,
            keyfile=Path(keyfile) if keyfile else None,
            log_level=os.getenv("CROSSYWORD_LOG_LEVEL", cls.log_level),
            log_file=Path(log_file) if log_file else None,
            json_logs=os.getenv("CROSSYWORD_JSON_LOGS", "").lower()
            in ("true", "1", "yes"),
            hash_fingerprints=os.getenv("CROSSYWORD_HASH_FINGERPRINTS", "true").lower()
            not in ("false", "0", "no"),
        )
