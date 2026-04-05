from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from peakwise.config import Settings


def get_engine(settings: Settings | None = None):
    if settings is None:
        settings = Settings()
    return create_engine(settings.database_url, echo=settings.debug)


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    engine = get_engine(settings)
    return sessionmaker(bind=engine)
