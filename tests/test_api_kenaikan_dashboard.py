"""Test endpoint FastAPI: Kenaikan Tingkat (tiket 03) dan Dashboard Super
Admin (tiket 04).
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
from data_analytics.models import AturanKenaikanTingkat, JenisTes, TingkatSeleksi
from data_analytics.repository import BreakdownSubkompetensi, catat_hasil_tes

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
            "/api/v1/analytics/tingkat/siswa-1/akses", headers=TOKEN_HEADER
        )

        assert response.status_code == 200
        body = response.json()
        assert body["siswa_id"] == "siswa-1"
        by_id = {item["tingkat_seleksi_id"]: item for item in body["daftar_akses"]}
        assert by_id[kab.id]["status"] == "terbuka"
        assert by_id[kab.id]["nama"] == "Kabupaten"
        assert by_id[prov.id]["status"] == "terkunci"

    def test_tanpa_token_ditolak(self, client: TestClient) -> None:
        response = client.get("/api/v1/analytics/tingkat/siswa-1/akses")
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
        assert body["dibuka_karena"] == "manual_admin"


class TestAturanKenaikanEndpoints:
    def test_get_dan_update_aturan(self, client: TestClient, session: Session) -> None:
        kab, prov = _buat_tingkat(session)
        aturan = AturanKenaikanTingkat(
            tingkat_asal_id=kab.id,
            tingkat_tujuan_id=prov.id,
            skor_simulasi_min=75.0,
            persentase_kompetensi_cukup_min=80.0,
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


class TestEvaluasiKenaikan:
    def test_lulus_membuka_akses_tingkat_tujuan(
        self, client: TestClient, session: Session
    ) -> None:
        kab, prov = _buat_tingkat(session)
        session.add(
            AturanKenaikanTingkat(
                tingkat_asal_id=kab.id,
                tingkat_tujuan_id=prov.id,
                skor_simulasi_min=75.0,
                persentase_kompetensi_cukup_min=80.0,
            )
        )
        session.commit()
        hasil_tes = catat_hasil_tes(
            session,
            siswa_id="siswa-1",
            tingkat_seleksi_id="tk-uuid-1",
            jenis_tes=JenisTes.SIMULASI,
            simulasi_id="sim-1",
            total_soal=10,
            jumlah_benar=8,
            breakdown_subkompetensi=[
                BreakdownSubkompetensi(subkompetensi_id="sk-1", jumlah_soal=10, jumlah_benar=8)
            ],
            diselesaikan_pada=datetime.now(timezone.utc),
        )
        session.commit()

        response = client.post(
            "/api/v1/analytics/tingkat/evaluasi",
            json={
                "siswa_id": "siswa-1",
                "hasil_tes_id": hasil_tes.id,
                "tingkat_asal_id": kab.id,
                "skor": 80.0,
                "jumlah_kompetensi_cukup": 4,
                "total_kompetensi_silabus": 5,
            },
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["evaluasi_dilakukan"] is True
        assert body["hasil_evaluasi"] == "lulus"

    def test_tanpa_aturan_evaluasi_dilakukan_false(
        self, client: TestClient, session: Session
    ) -> None:
        kab, _ = _buat_tingkat(session)
        hasil_tes = catat_hasil_tes(
            session,
            siswa_id="siswa-1",
            tingkat_seleksi_id="tk-uuid-1",
            jenis_tes=JenisTes.SIMULASI,
            simulasi_id="sim-1",
            total_soal=10,
            jumlah_benar=8,
            breakdown_subkompetensi=[
                BreakdownSubkompetensi(subkompetensi_id="sk-1", jumlah_soal=10, jumlah_benar=8)
            ],
            diselesaikan_pada=datetime.now(timezone.utc),
        )
        session.commit()

        response = client.post(
            "/api/v1/analytics/tingkat/evaluasi",
            json={
                "siswa_id": "siswa-1",
                "hasil_tes_id": hasil_tes.id,
                "tingkat_asal_id": kab.id,
                "skor": 90.0,
                "jumlah_kompetensi_cukup": 5,
                "total_kompetensi_silabus": 5,
            },
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 200
        assert response.json()["evaluasi_dilakukan"] is False


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
        catat_hasil_tes(
            session,
            siswa_id="siswa-1",
            sekolah_id="sekolah-1",
            tingkat_seleksi_id="tk-uuid-1",
            jenis_tes=JenisTes.SIMULASI,
            simulasi_id="sim-1",
            total_soal=10,
            jumlah_benar=9,
            breakdown_subkompetensi=[
                BreakdownSubkompetensi(subkompetensi_id="sk-1", jumlah_soal=10, jumlah_benar=9)
            ],
            diselesaikan_pada=datetime.now(timezone.utc),
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
            catat_hasil_tes(
                session,
                siswa_id=siswa,
                sekolah_id=sekolah,
                tingkat_seleksi_id="tk-uuid-1",
                jenis_tes=JenisTes.PRE_TEST,
                total_soal=10,
                jumlah_benar=5,
                breakdown_subkompetensi=[
                    BreakdownSubkompetensi(subkompetensi_id="sk-1", jumlah_soal=10, jumlah_benar=5)
                ],
                diselesaikan_pada=datetime.now(timezone.utc),
            )
        session.commit()

        response = client.get(
            "/api/v1/admin/dashboard",
            params={"sekolah_id": "sekolah-A", "rentang_waktu": "all"},
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 200
        assert response.json()["kpi"]["total_siswa_aktif"] == 1
