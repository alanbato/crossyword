"""Logging configuration for Crossyword.

This module provides structured logging configuration using structlog.
"""

import hashlib
import sys
from pathlib import Path
from typing import Any

import structlog


def hash_fingerprint_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Hash user fingerprints in log events for privacy.

    Certificate fingerprints are hashed in logs to protect user privacy
    while still allowing correlation of user activity.

    Args:
        logger: The logger instance.
        method_name: The logging method name.
        event_dict: The event dictionary.

    Returns:
        The event dictionary with fingerprint replaced by fingerprint_hash.
    """
    if "fingerprint" in event_dict:
        fp = event_dict["fingerprint"]
        if fp and fp != "unknown":
            # SHA256 hash, truncated to 12 chars for readability
            hashed = hashlib.sha256(fp.encode()).hexdigest()[:12]
            event_dict["fingerprint_hash"] = hashed
            del event_dict["fingerprint"]
    return event_dict


def _level_to_int(level: str) -> int:
    """Convert string log level to integer.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        Integer log level.
    """
    levels = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50,
    }
    return levels.get(level.upper(), 20)


def configure_logging(
    log_level: str = "INFO",
    log_file: Path | None = None,
    json_logs: bool = False,
    hash_fingerprints: bool = True,
) -> None:
    """Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional path to log file. If None, logs to stdout.
        json_logs: If True, output logs in JSON format. Otherwise, use
            human-readable format.
        hash_fingerprints: If True (default), hash user fingerprints in logs
            for privacy protection.

    Examples:
        >>> # Configure for development (human-readable console output)
        >>> configure_logging(log_level="DEBUG")

        >>> # Configure for production (JSON logs to file, hashed fingerprints)
        >>> configure_logging(
        ...     log_level="INFO",
        ...     log_file=Path("/var/log/crossyword.log"),
        ...     json_logs=True,
        ...     hash_fingerprints=True
        ... )
    """
    # Determine output stream
    if log_file:
        output_stream = open(log_file, "a")
    else:
        output_stream = sys.stdout

    # Build base processors
    base_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(
            fmt="iso" if json_logs else "%Y-%m-%d %H:%M:%S"
        ),
    ]

    # Add fingerprint hashing processor if enabled (for privacy)
    if hash_fingerprints:
        base_processors.append(hash_fingerprint_processor)

    # Configure output format
    if json_logs:
        # JSON format for production/structured logging
        processors = base_processors + [structlog.processors.JSONRenderer()]
    else:
        # Human-readable format for development
        processors = base_processors + [
            structlog.dev.ConsoleRenderer(colors=output_stream.isatty())
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(_level_to_int(log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=output_stream),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__).

    Returns:
        A structlog BoundLogger instance.

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("puzzle_completed", user_id=123, puzzle_id=456)
    """
    return structlog.get_logger(name)
