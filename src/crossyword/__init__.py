"""Crossyword - Daily crossword puzzles over Gemini."""

from .app import create_app
from .config import Config
from .logging import configure_logging, get_logger

__all__ = ["main", "create_app", "Config"]


def main() -> None:
    """Entry point for the crossyword application."""
    config = Config.from_env()

    configure_logging(
        log_level=config.log_level,
        log_file=config.log_file,
        json_logs=config.json_logs,
        hash_fingerprints=config.hash_fingerprints,
    )

    logger = get_logger(__name__)
    logger.info(
        "application_starting",
        host=config.host,
        port=config.port,
        log_level=config.log_level,
    )

    app = create_app(config)
    app.run(
        host=config.host,
        port=config.port,
        certfile=str(config.certfile) if config.certfile else None,
        keyfile=str(config.keyfile) if config.keyfile else None,
    )
