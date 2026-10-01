"""Test endpoint FastAPI: akses tingkat & aturan kenaikan (tiket 03, fase 2
issue 02) dan Dashboard Super Admin (tiket 04).
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
from data_analytics.models import AturanKenaikanTingkat, HasilTes, JenisTes, TingkatSeleksi

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


def _buat_tingkat(session: Session) -> tuple[TingkatSeleksi, TingkatSeleksi]:
    kab = TingkatSeleksi(nama="Kabupaten", urutan=1)
    prov = TingkatSeleksi(nama="Provinsi", urutan=2)
    session.add_all([kab, prov])
    session.flush()
    session.commit()
    return kab, prov


class TestGetAksesTingkat:
    def test_menginisialisasi_dan_mengembalikan_akses(
        self, client: TestClient, session: Session
    ) -> None:
        kab, prov = _buat_tingkat(session)

        response = client.get(
            "/api/v1/siswa/siswa-1/akses", headers=TOKEN_HEADER
        )

        assert response.status_code == 200
        body = response.json()
        assert body["siswa_id"] == "siswa-1"
        by_id = {item["tingkat_seleksi_id"]: item for item in body["daftar_akses"]}
        assert by_id[kab.id]["status"] == "pretest_terbuka"
        assert by_id[kab.id]["nama"] == "Kabupaten"
        assert by_id[prov.id]["status"] == "terkunci"

    def test_tanpa_token_ditolak(self, client: TestClient) -> None:
        response = client.get("/api/v1/siswa/siswa-1/akses")
        assert response.status_code == 422


class TestOverrideAksesTingkat:
    def test_admin_membuka_akses_manual(self, client: TestClient, session: Session) -> None:
        _, prov = _buat_tingkat(session)

        response = client.post(
            "/api/v1/analytics/tingkat/override",
            json={"siswa_id": "siswa-1", "tingkat_seleksi_id": prov.id, "status": "terbuka"},
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "terbuka"
        assert body["dibuka_karena"] == "override_admin"


class TestAturanKenaikanEndpoints:
    def test_get_dan_update_aturan(self, client: TestClient, session: Session) -> None:
        kab, prov = _buat_tingkat(session)
        aturan = AturanKenaikanTingkat(
            tingkat_asal_id=kab.id,
            tingkat_tujuan_id=prov.id,
            skor_simulasi_min=75.0,
            skor_pretest_jalur_cepat=90.0,
            rata_level_min=2.0,
        )
        session.add(aturan)
        session.commit()

        list_response = client.get("/api/v1/analytics/tingkat/aturan", headers=TOKEN_HEADER)
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        update_response = client.put(
            f"/api/v1/analytics/tingkat/aturan/{aturan.id}",
            json={"skor_simulasi_min": 85.0},
            headers=TOKEN_HEADER,
        )
        assert update_response.status_code == 200
        assert update_response.json()["skor_simulasi_min"] == 85.0

    def test_update_aturan_tidak_ditemukan_404(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/analytics/tingkat/aturan/999",
            json={"aktif": False},
            headers=TOKEN_HEADER,
        )
        assert response.status_code == 404


def _hasil_tes(
    session: Session, *, siswa_id: str, sekolah_id: str, jenis_tes: JenisTes, jumlah_benar: int
) -> None:
    """Satu attempt 10 soal apa adanya — Dashboard hanya membaca HasilTes."""
    session.add(
        HasilTes(
            siswa_id=siswa_id,
            sekolah_id=sekolah_id,
            tingkat_seleksi_id="1",
            jenis_tes=jenis_tes,
            simulasi_id="1" if jenis_tes is JenisTes.SIMULASI else None,
            total_soal=10,
            jumlah_benar=jumlah_benar,
            jumlah_salah=10 - jumlah_benar,
            skor=jumlah_benar * 10.0,
            predikat_label="Baik",
            diselesaikan_pada=datetime.now(timezone.utc),
        )
    )


class TestDashboard:
    def test_kpi_kosong_saat_belum_ada_data(self, client: TestClient) -> None:
        response = client.get("/api/v1/admin/dashboard", headers=TOKEN_HEADER)

        assert response.status_code == 200
        body = response.json()
        assert body["kpi"]["total_siswa_aktif"] == 0
        assert body["kpi"]["total_tes_selesai"] == 0
        assert body["distribusi_tingkat"] == []
        assert body["komparasi_sekolah"] == []

    def test_kpi_menghitung_dari_hasil_tes(self, client: TestClient, session: Session) -> None:
        _hasil_tes(
            session,
            siswa_id="siswa-1",
            sekolah_id="sekolah-1",
            jenis_tes=JenisTes.SIMULASI,
            jumlah_benar=9,
        )
        session.commit()

        response = client.get(
            "/api/v1/admin/dashboard",
            params={"rentang_waktu": "all"},
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["kpi"]["total_siswa_aktif"] == 1
        assert body["kpi"]["total_simulasi"] == 1
        assert body["kpi"]["rata_rata_skor_simulasi"] == 90.0
        assert len(body["komparasi_sekolah"]) == 1
        assert body["komparasi_sekolah"][0]["sekolah_id"] == "sekolah-1"

    def test_filter_sekolah_id(self, client: TestClient, session: Session) -> None:
        for sekolah, siswa in [("sekolah-A", "siswa-a"), ("sekolah-B", "siswa-b")]:
            _hasil_tes(
                session, siswa_id=siswa, sekolah_id=sekolah, jenis_tes=JenisTes.PRE_TEST, jumlah_benar=5
            )
        session.commit()

        response = client.get(
            "/api/v1/admin/dashboard",
            params={"sekolah_id": "sekolah-A", "rentang_waktu": "all"},
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 200
        assert response.json()["kpi"]["total_siswa_aktif"] == 1
