"""Test endpoint FastAPI: health (tiket 09) dan admin internal (tiket 10)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.api import app
from data_analytics.config import get_settings
from data_analytics.db import get_db
from data_analytics.models import HasilTes, JawabanSiswa

RETENSI_BULAN = get_settings().data_retention_months


def _jawaban(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "soal_id": "soal-1",
        "subkompetensi_id": "sub-1",
        "jawaban_dipilih": "A",
        "is_benar": True,
        "durasi_detik": 30,
        "batas_waktu_detik": 60,
    }
    base.update(overrides)
    return base


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "siswa_id": "siswa-1",
        "sekolah_id": "sekolah-1",
        "tingkat_seleksi_id": "tingkat-1",
        "jenis_tes": "PRE_TEST",
        "jawaban_siswa": [_jawaban()],
    }
    base.update(overrides)
    return base


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


class TestSubmitAssessment:
    def test_tanpa_header_token_ditolak_422(self, client: TestClient) -> None:
        response = client.post("/api/v1/analytics/assessment/submit", json=_payload())

        assert response.status_code == 422

    def test_token_salah_ditolak_403(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/analytics/assessment/submit",
            json=_payload(),
            headers={"X-Internal-Token": "salah"},
        )

        assert response.status_code == 403

    def test_submit_sukses_mengembalikan_peta_kompetensi(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/analytics/assessment/submit",
            json=_payload(),
            headers={"X-Internal-Token": get_settings().internal_api_token},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["data"]["peta_kompetensi"] == [
            {
                "subkompetensi_id": "sub-1",
                "status_pemetaan": "Cukup",
                "butuh_optimasi": False,
            }
        ]

    def test_data_tersimpan_ke_db(self, client: TestClient, session: Session) -> None:
        client.post(
            "/api/v1/analytics/assessment/submit",
            json=_payload(),
            headers={"X-Internal-Token": get_settings().internal_api_token},
        )

        hasil = session.scalars(select(HasilTes)).one()
        assert hasil.siswa_id == "siswa-1"
        assert hasil.sekolah_id == "sekolah-1"
        assert hasil.total_soal == 1
        assert hasil.jumlah_benar == 1

        jawaban = session.scalars(select(JawabanSiswa)).one()
        assert jawaban.hasil_tes_id == hasil.id
        assert jawaban.soal_id == "soal-1"
        assert jawaban.is_lambat is False

    def test_jawaban_kosong_ditolak_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/analytics/assessment/submit",
            json=_payload(jawaban_siswa=[]),
            headers={"X-Internal-Token": get_settings().internal_api_token},
        )

        assert response.status_code == 422

    def test_simulasi_tanpa_simulasi_id_ditolak_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/analytics/assessment/submit",
            json=_payload(jenis_tes="SIMULASI"),
            headers={"X-Internal-Token": get_settings().internal_api_token},
        )

        assert response.status_code == 422

    def test_soal_lambat_membawa_flag_butuh_optimasi(self, client: TestClient) -> None:
        payload = _payload(
            jawaban_siswa=[
                _jawaban(soal_id="s1", durasi_detik=90, batas_waktu_detik=60),
                _jawaban(soal_id="s2", durasi_detik=90, batas_waktu_detik=60),
                _jawaban(soal_id="s3", durasi_detik=90, batas_waktu_detik=60),
                _jawaban(soal_id="s4", durasi_detik=30, batas_waktu_detik=60),
            ]
        )

        response = client.post(
            "/api/v1/analytics/assessment/submit",
            json=payload,
            headers={"X-Internal-Token": get_settings().internal_api_token},
        )

        assert response.status_code == 200
        peta = response.json()["data"]["peta_kompetensi"][0]
        assert peta["status_pemetaan"] == "Cukup"
        assert peta["butuh_optimasi"] is True
