"""Test endpoint FastAPI: Pre-Test berjenjang (tiket 15)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from data_analytics.api import app
from data_analytics.config import get_settings
from data_analytics.db import get_db
from data_analytics.models import AturanPreTest, JenisTes, TingkatSeleksi
from data_analytics.repository import BreakdownSubkompetensi, catat_hasil_tes, get_or_create_aturan_pre_test

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


def _buat_tingkat(session: Session) -> tuple[TingkatSeleksi, TingkatSeleksi, TingkatSeleksi]:
    kab = TingkatSeleksi(nama="Kabupaten", urutan=1)
    prov = TingkatSeleksi(nama="Provinsi", urutan=2)
    nas = TingkatSeleksi(nama="Nasional", urutan=3)
    session.add_all([kab, prov, nas])
    session.flush()
    session.commit()
    return kab, prov, nas


def _buat_hasil_tes(session: Session, *, siswa_id: str = "siswa-1") -> int:
    hasil = catat_hasil_tes(
        session,
        siswa_id=siswa_id,
        tingkat_seleksi_id="tk-uuid-1",
        jenis_tes=JenisTes.PRE_TEST,
        simulasi_id=None,
        total_soal=10,
        jumlah_benar=8,
        breakdown_subkompetensi=[
            BreakdownSubkompetensi(subkompetensi_id="sk-1", jumlah_soal=10, jumlah_benar=8)
        ],
        diselesaikan_pada=datetime.now(timezone.utc),
    )
    session.commit()
    return hasil.id


class TestAturanPreTestEndpoints:
    def test_get_dan_put_aturan_pre_test(
        self, client: TestClient, session: Session
    ) -> None:
        kab, prov, nas = _buat_tingkat(session)
        get_or_create_aturan_pre_test(session)
        session.commit()

        # GET aturan
        get_resp = client.get("/api/v1/analytics/pre-test/aturan", headers=TOKEN_HEADER)
        assert get_resp.status_code == 200
        aturan_list = get_resp.json()
        assert len(aturan_list) == 3

        aturan_kab = next(a for a in aturan_list if a["tingkat_seleksi_id"] == kab.id)
        assert aturan_kab["skor_min"] == 70.0

        # PUT aturan
        put_resp = client.put(
            f"/api/v1/analytics/pre-test/aturan/{aturan_kab['id']}",
            json={"skor_min": 75.0},
            headers=TOKEN_HEADER,
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["skor_min"] == 75.0

    def test_put_aturan_tidak_ditemukan_404(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/analytics/pre-test/aturan/9999",
            json={"skor_min": 75.0},
            headers=TOKEN_HEADER,
        )
        assert resp.status_code == 404

    def test_get_aturan_tanpa_token_422(self, client: TestClient) -> None:
        resp = client.get("/api/v1/analytics/pre-test/aturan")
        assert resp.status_code == 422


class TestEvaluasiPreTestEndpoint:
    def test_evaluasi_lulus_membuka_simulasi_dan_tingkat_berikutnya(
        self, client: TestClient, session: Session
    ) -> None:
        kab, prov, _ = _buat_tingkat(session)
        get_or_create_aturan_pre_test(session)
        session.commit()
        hasil_tes_id = _buat_hasil_tes(session)

        resp = client.post(
            "/api/v1/analytics/pre-test/evaluasi",
            json={
                "siswa_id": "siswa-1",
                "hasil_tes_id": hasil_tes_id,
                "tingkat_seleksi_id": kab.id,
                "skor": 75.0,
            },
            headers=TOKEN_HEADER,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["evaluasi_dilakukan"] is True
        assert data["lulus"] is True
        assert data["hasil_evaluasi"] == "lulus"
        assert data["simulasi_terbuka"] is True
        assert data["tingkat_berikutnya_terbuka"] is True

        # Verifikasi via endpoint akses tingkat bahwa status simulasi_terbuka = True
        akses_resp = client.get(
            "/api/v1/analytics/tingkat/siswa-1/akses", headers=TOKEN_HEADER
        )
        assert akses_resp.status_code == 200
        akses_data = akses_resp.json()["daftar_akses"]
        kab_akses = next(a for a in akses_data if a["tingkat_seleksi_id"] == kab.id)
        prov_akses = next(a for a in akses_data if a["tingkat_seleksi_id"] == prov.id)
        assert kab_akses["simulasi_terbuka"] is True
        assert prov_akses["status"] == "terbuka"
        assert prov_akses["dibuka_karena"] == "lulus_pre_test"

    def test_evaluasi_tidak_lulus_tetap_terkunci(
        self, client: TestClient, session: Session
    ) -> None:
        kab, prov, _ = _buat_tingkat(session)
        get_or_create_aturan_pre_test(session)
        session.commit()
        hasil_tes_id = _buat_hasil_tes(session)

        resp = client.post(
            "/api/v1/analytics/pre-test/evaluasi",
            json={
                "siswa_id": "siswa-2",
                "hasil_tes_id": hasil_tes_id,
                "tingkat_seleksi_id": kab.id,
                "skor": 60.0,
            },
            headers=TOKEN_HEADER,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["evaluasi_dilakukan"] is True
        assert data["lulus"] is False
        assert data["hasil_evaluasi"] == "tidak_lulus"
        assert data["simulasi_terbuka"] is False
        assert data["tingkat_berikutnya_terbuka"] is False

        # Verifikasi via endpoint akses tingkat bahwa status simulasi_terbuka = False
        akses_resp = client.get(
            "/api/v1/analytics/tingkat/siswa-2/akses", headers=TOKEN_HEADER
        )
        assert akses_resp.status_code == 200
        akses_data = akses_resp.json()["daftar_akses"]
        kab_akses = next(a for a in akses_data if a["tingkat_seleksi_id"] == kab.id)
        prov_akses = next(a for a in akses_data if a["tingkat_seleksi_id"] == prov.id)
        assert kab_akses["simulasi_terbuka"] is False
        assert prov_akses["status"] == "terkunci"

