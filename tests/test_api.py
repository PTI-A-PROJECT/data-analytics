"""Test endpoint health FastAPI (tiket 09)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from data_analytics.api import app
from data_analytics.db import get_db


class TestHealth:
    def test_liveness_ok_tanpa_db(self) -> None:
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_readiness_ping_db(self, session: Session) -> None:
        def _override() -> Iterator[Session]:
            yield session

        app.dependency_overrides[get_db] = _override
        try:
            client = TestClient(app)
            response = client.get("/api/v1/health")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
