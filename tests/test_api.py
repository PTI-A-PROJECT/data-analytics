"""Test endpoint FastAPI: health (tiket 09) dan admin internal (tiket 10)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from data_analytics.api import app
from data_analytics.config import get_settings
from data_analytics.db import get_db
from data_analytics.models import HasilTes

RETENSI_BULAN = get_settings().data_retention_months


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    def _override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestHealth:
    def test_liveness_ok_tanpa_db(self) -> None:
        response = TestClient(app).get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_readiness_ping_db(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestAnonymizeExpired:
    def test_tanpa_header_token_ditolak_422(self, client: TestClient) -> None:
        response = client.post("/api/v1/admin/anonymize-expired")

        assert response.status_code == 422

    def test_token_salah_ditolak_403(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/admin/anonymize-expired",
            headers={"X-Internal-Token": "salah"},
        )

        assert response.status_code == 403

    def test_dry_run_tidak_mengubah_data(
        self, client: TestClient, session: Session, buat_hasil_tes: Callable[..., HasilTes]
    ) -> None:
        lama = datetime.now(timezone.utc) - timedelta(days=RETENSI_BULAN * 31)
        hasil = buat_hasil_tes(dibuat_pada=lama)

        response = client.post(
            "/api/v1/admin/anonymize-expired?dry_run=true",
            headers={"X-Internal-Token": get_settings().internal_api_token},
        )

        assert response.status_code == 200
        assert response.json() == {"jumlah_dianonimkan": 1, "dry_run": True}
        session.refresh(hasil)
        assert hasil.siswa_id == "1"

    def test_live_run_menganonimkan_dan_menyimpan(
        self, client: TestClient, session: Session, buat_hasil_tes: Callable[..., HasilTes]
    ) -> None:
        lama = datetime.now(timezone.utc) - timedelta(days=RETENSI_BULAN * 31)
        hasil = buat_hasil_tes(dibuat_pada=lama)

        response = client.post(
            "/api/v1/admin/anonymize-expired",
            headers={"X-Internal-Token": get_settings().internal_api_token},
        )

        assert response.status_code == 200
        assert response.json() == {"jumlah_dianonimkan": 1, "dry_run": False}
        session.refresh(hasil)
        assert hasil.siswa_id is None
        assert hasil.is_anonymized is True
        assert hasil.sekolah_id == "7"  # agregat tetap utuh

    def test_data_belum_kedaluwarsa_dilewati(
        self, client: TestClient, session: Session, buat_hasil_tes: Callable[..., HasilTes]
    ) -> None:
        baru = datetime.now(timezone.utc) - timedelta(days=10)
        hasil = buat_hasil_tes(dibuat_pada=baru)

        response = client.post(
            "/api/v1/admin/anonymize-expired",
            headers={"X-Internal-Token": get_settings().internal_api_token},
        )

        assert response.json() == {"jumlah_dianonimkan": 0, "dry_run": False}
        session.refresh(hasil)
        assert hasil.siswa_id == "1"
