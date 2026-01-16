"""Crossyword - Daily crossword puzzles over Gemini."""

from .app import create_app
from .config import Config

__all__ = ["main", "create_app", "Config"]


def main() -> None:
    """Entry point for the crossyword application."""
    config = Config.from_env()
    app = create_app(config)
    app.run(
        host=config.host,
        port=config.port,
        certfile=str(config.certfile) if config.certfile else None,
        keyfile=str(config.keyfile) if config.keyfile else None,
    )
