"""Simulasi adaptif lewat HTTP API (fase 2 issue 03) — memakai bank soal
sintetis & helper alur pre-test dari test_api_pretest.
"""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import AturanAdaptif, TingkatSeleksi
from tests.test_api_pretest import (  # noqa: F401 — fixture bank & client
    TOKEN_HEADER,
    Bank,
    _jawab,
    _minta_paket,
    _status_akses,
    _submit,
    bank,
    client,
)

SEMUA_BENAR = {"m-a-1": 99, "m-b-1": 99, "m-c-1": 99}
# Pre-test 8/10 = 80: tidak ada Materi lemah (Gerbang Simulasi terbuka) dan
# jalur cepat (90) tidak lulus.
TANPA_MATERI_LEMAH = {"m-a-1": 4, "m-b-1": 2, "m-c-1": 2}


def _minta_simulasi(
    client: TestClient, siswa_id: str, tingkat: TingkatSeleksi
) -> httpx.Response:
    return client.post(
        "/api/v1/simulasi/paket",
        json={"siswa_id": siswa_id, "tingkat_seleksi_id": tingkat.id},
        headers=TOKEN_HEADER,
    )


def _pretest_kabupaten(client: TestClient, bank: Bank, benar: dict[str, int]) -> None:
    paket = _minta_paket(client, "siswa-1", bank.kabupaten).json()
    assert _submit(client, paket["paket_id"], _jawab(paket, benar)).status_code == 200


def _set_jumlah_soal_simulasi(session: Session, bank: Bank, jumlah: int) -> None:
    aturan = session.scalars(
        select(AturanAdaptif).where(AturanAdaptif.tingkat_seleksi_id == bank.kabupaten.id)
    ).one()
    aturan.jumlah_soal_simulasi = jumlah
    session.commit()


class TestPaketSimulasi:
    def test_sebelum_pretest_ditolak_403(self, client: TestClient, bank: Bank) -> None:
        assert _minta_simulasi(client, "siswa-1", bank.kabupaten).status_code == 403

    def test_setelah_pretest_paket_tanpa_kunci_dan_idempoten(
        self, client: TestClient, bank: Bank, session: Session
    ) -> None:
        _set_jumlah_soal_simulasi(session, bank, 6)
        _pretest_kabupaten(client, bank, TANPA_MATERI_LEMAH)

        pertama = _minta_simulasi(client, "siswa-1", bank.kabupaten)
        kedua = _minta_simulasi(client, "siswa-1", bank.kabupaten)

        assert pertama.status_code == 200
        body = pertama.json()
        assert body["jenis_tes"] == "simulasi"
        assert len(body["soal"]) == 6
        assert all("kunci_jawaban" not in s and "pembahasan" not in s for s in body["soal"])
        assert kedua.json() == body

    def test_tingkat_tidak_ada_404(self, client: TestClient, bank: Bank) -> None:
        response = client.post(
            "/api/v1/simulasi/paket",
            json={"siswa_id": "siswa-1", "tingkat_seleksi_id": 999_999},
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 404


class TestSubmitSimulasi:
    def test_perubahan_level_dan_jalur_simulasi_membuka_pretest_provinsi(
        self, client: TestClient, bank: Bank, session: Session
    ) -> None:
        _set_jumlah_soal_simulasi(session, bank, 6)
        _pretest_kabupaten(client, bank, TANPA_MATERI_LEMAH)
        paket = _minta_simulasi(client, "siswa-1", bank.kabupaten).json()

        response = _submit(client, paket["paket_id"], _jawab(paket, SEMUA_BENAR))

        assert response.status_code == 200
        body = response.json()
        assert [
            (p["materi_id"], p["level_sebelum"], p["level_sesudah"], p["lemah"])
            for p in body["perubahan_level"]
        ] == [
            ("m-a-1", "mudah", "menengah", False),
            ("m-b-1", "mudah", "menengah", False),
            ("m-c-1", "mudah", "menengah", False),
        ]
        assert body["evaluasi_jalur_simulasi"] == {
            "lulus": True,
            "syarat_skor_lulus": True,
            "syarat_level_lulus": True,
            "rata_level_aktual": 2.0,
        }
        assert _status_akses(client, "siswa-1")["Provinsi"] == "pretest_terbuka"

    def test_skor_di_bawah_minimum_provinsi_tetap_terkunci(
        self, client: TestClient, bank: Bank, session: Session
    ) -> None:
        _set_jumlah_soal_simulasi(session, bank, 6)
        _pretest_kabupaten(client, bank, TANPA_MATERI_LEMAH)
        paket = _minta_simulasi(client, "siswa-1", bank.kabupaten).json()

        body = _submit(client, paket["paket_id"], _jawab(paket, {})).json()

        assert body["evaluasi_jalur_simulasi"]["lulus"] is False
        assert _status_akses(client, "siswa-1")["Provinsi"] == "terkunci"

    def test_setelah_submit_paket_simulasi_berikutnya_baru(
        self, client: TestClient, bank: Bank, session: Session
    ) -> None:
        _set_jumlah_soal_simulasi(session, bank, 6)
        _pretest_kabupaten(client, bank, TANPA_MATERI_LEMAH)
        pertama = _minta_simulasi(client, "siswa-1", bank.kabupaten).json()
        _submit(client, pertama["paket_id"], _jawab(pertama, SEMUA_BENAR))

        kedua = _minta_simulasi(client, "siswa-1", bank.kabupaten).json()

        assert kedua["paket_id"] != pertama["paket_id"]


class TestEndpointFase1Dipensiunkan:
    def test_assessment_submit_tidak_ada_lagi(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/analytics/assessment/submit", json={}, headers=TOKEN_HEADER
        )

        assert response.status_code == 404
