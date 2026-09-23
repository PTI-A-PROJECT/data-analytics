"""Test endpoint FastAPI: event progress Halaman Materi (resolusi tiket 14),
POST /api/v1/analytics/events/materi-progress. Logika high-water mark
(catat_progress_halaman) sudah diuji lewat tests/test_progress_repository.py
(tiket 02) — test ini hanya lapisan API (validasi request/response, auth,
pemetaan error).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from data_analytics.api import app
from data_analytics.config import get_settings
from data_analytics.db import get_db

TOKEN_HEADER = {"X-Internal-Token": get_settings().internal_api_token}


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    def _override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "siswa_id": 1,
        "materi_id": 100,
        "subkompetensi_id": 10,
        "tingkat_seleksi_id": 1,
        "total_halaman": 12,
        "halaman_dibuka": 5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


class TestCatatEventMateriProgress:
    def test_baris_baru_mengembalikan_high_water_mark(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/analytics/events/materi-progress",
            json=_payload(halaman_dibuka=3, total_halaman=12),
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["halaman_tertinggi_dicapai"] == 3
        assert body["total_halaman"] == 12
        assert body["persentase_selesai"] == 25.0

    def test_navigasi_mundur_tidak_menurunkan_high_water_mark(
        self, client: TestClient
    ) -> None:
        client.post(
            "/api/v1/analytics/events/materi-progress",
            json=_payload(halaman_dibuka=8),
            headers=TOKEN_HEADER,
        )

        response = client.post(
            "/api/v1/analytics/events/materi-progress",
            json=_payload(halaman_dibuka=2),
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 200
        assert response.json()["halaman_tertinggi_dicapai"] == 8

    def test_halaman_dibuka_melebihi_total_halaman_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/analytics/events/materi-progress",
            json=_payload(halaman_dibuka=20, total_halaman=12),
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 422

    def test_halaman_dibuka_kurang_dari_1_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/analytics/events/materi-progress",
            json=_payload(halaman_dibuka=0),
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 422

    def test_tanpa_token_ditolak(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/analytics/events/materi-progress", json=_payload()
        )
        assert response.status_code == 422

    def test_token_salah_ditolak(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/analytics/events/materi-progress",
            json=_payload(),
            headers={"X-Internal-Token": "salah"},
        )
        assert response.status_code == 403
