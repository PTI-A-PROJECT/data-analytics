"""Konfigurasi aturan_adaptif oleh Super Admin (fase 2 issue 03) — validasi di
depan supaya penyusunan paket tidak pernah gagal karena konfigurasi.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_api_pretest import (  # noqa: F401 — fixture bank & client
    TOKEN_HEADER,
    Bank,
    bank,
    client,
)

URL = "/api/v1/analytics/aturan-adaptif"


def _put(client: TestClient, tingkat_id: int, **payload: float) -> tuple[int, dict]:  # type: ignore[type-arg]
    response = client.put(f"{URL}/{tingkat_id}", json=payload, headers=TOKEN_HEADER)
    return response.status_code, response.json()


class TestAturanAdaptif:
    def test_daftar_aturan_per_tingkat(self, client: TestClient, bank: Bank) -> None:
        response = client.get(URL, headers=TOKEN_HEADER)

        assert response.status_code == 200
        kabupaten = next(
            a for a in response.json() if a["tingkat_seleksi_id"] == bank.kabupaten.id
        )
        assert kabupaten == {
            "tingkat_seleksi_id": bank.kabupaten.id,
            "jumlah_soal_pretest": 10,
            "jumlah_soal_simulasi": 30,
            "kuota_min": 2,
            "bobot_lemah": 3,
            "ambang_naik": 80.0,
            "ambang_lemah": 50.0,
        }

    def test_update_sebagian(self, client: TestClient, bank: Bank) -> None:
        status, body = _put(client, bank.kabupaten.id, bobot_lemah=4, ambang_naik=85)

        assert status == 200
        assert (body["bobot_lemah"], body["ambang_naik"], body["kuota_min"]) == (4, 85.0, 2)

    def test_kuota_min_kali_jumlah_materi_melebihi_jumlah_soal_ditolak_422(
        self, client: TestClient, bank: Bank
    ) -> None:
        # 3 Materi x kuota_min 2 = 6 > 5.
        status, _ = _put(client, bank.kabupaten.id, jumlah_soal_simulasi=5)

        assert status == 422

    def test_ambang_lemah_harus_di_bawah_ambang_naik_422(
        self, client: TestClient, bank: Bank
    ) -> None:
        status, _ = _put(client, bank.kabupaten.id, ambang_lemah=80)

        assert status == 422

    def test_nilai_di_luar_rentang_422(self, client: TestClient, bank: Bank) -> None:
        assert _put(client, bank.kabupaten.id, bobot_lemah=0)[0] == 422
        assert _put(client, bank.kabupaten.id, ambang_naik=101)[0] == 422

    def test_tingkat_tidak_ada_404(self, client: TestClient, bank: Bank) -> None:
        assert _put(client, 999_999, bobot_lemah=2)[0] == 404
