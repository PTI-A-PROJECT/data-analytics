from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_analytics.models import Base


@pytest.fixture
def session() -> Iterator[Session]:
    # StaticPool + check_same_thread=False: satu koneksi in-memory yang sama
    # dipakai di semua thread, supaya fixture ini juga bisa dipakai lewat
    # FastAPI TestClient (jalan di thread terpisah via anyio portal).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()
