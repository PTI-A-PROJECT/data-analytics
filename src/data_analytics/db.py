"""Engine & session factory SQLAlchemy (tiket 09) — dipakai FastAPI app dan
alembic/env.py. Test memakai engine Postgres sendiri lewat tests/conftest.py
(TEST_DATABASE_URL), tidak lewat modul ini.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from data_analytics.config import get_settings

engine = create_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
