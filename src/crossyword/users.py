"""User management utilities."""

import datetime as dt
import re

from sqlmodel import Session, select

from .logging import get_logger
from .models import User

logger = get_logger(__name__)


def validate_username(username: str) -> tuple[bool, str]:
    """
    Validate username format.

    Returns (is_valid, error_message).
    """
    if len(username) < 1:
        return False, "Username cannot be empty."
    if len(username) > 20:
        return False, "Username must be 20 characters or less."
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores."
    return True, ""


def requires_registration(user: User) -> bool:
    """Check if user needs to register a username."""
    return user.display_name is None


def get_or_create_user(session: Session, fingerprint: str) -> User:
    """
    Get existing user or create new one from certificate fingerprint.

    Updates last_seen timestamp on each access.
    """
    statement = select(User).where(User.fingerprint == fingerprint)
    user = session.exec(statement).first()

    if user:
        user.last_seen = dt.datetime.utcnow()
        logger.debug("user_accessed", fingerprint=fingerprint)
    else:
        user = User(fingerprint=fingerprint)
        session.add(user)
        logger.info("user_created", fingerprint=fingerprint)

    session.commit()
    session.refresh(user)
    return user
