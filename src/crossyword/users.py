"""User management utilities."""

import datetime as dt

from sqlmodel import Session, select

from .models import User


def get_or_create_user(session: Session, fingerprint: str) -> User:
    """
    Get existing user or create new one from certificate fingerprint.

    Updates last_seen timestamp on each access.
    """
    statement = select(User).where(User.fingerprint == fingerprint)
    user = session.exec(statement).first()

    if user:
        user.last_seen = dt.datetime.utcnow()
    else:
        user = User(fingerprint=fingerprint)
        session.add(user)

    session.commit()
    session.refresh(user)
    return user
