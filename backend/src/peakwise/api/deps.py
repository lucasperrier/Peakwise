"""API dependency injection."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from peakwise.db import get_session_factory

_factory = get_session_factory()


def get_db() -> Generator[Session, None, None]:
    session = _factory()
    try:
        yield session
    finally:
        session.close()
