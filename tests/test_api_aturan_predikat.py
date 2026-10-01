"""Aturan Predikat per Tingkat Seleksi — label pengelompokan rentang skor yang
tampil di samping skor saat submit (tiket 01).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_api_pretest import (  # noqa: F401 — fixture bank & client
    TOKEN_HEADER,
    Bank,
    _jawab,
    _minta_paket,
    _submit,
    bank,
    client,
)

URL = "/api/v1/analytics/aturan-predikat"


def _predikat_tingkat(client: TestClient, tingkat_id: int) -> list[tuple[str, float]]:
    response = client.get(URL, headers=TOKEN_HEADER)
    assert response.status_code == 200
    item = next(a for a in response.json() if a["tingkat_seleksi_id"] == tingkat_id)
    return [(p["label"], p["batas_bawah"]) for p in item["predikat"]]


class TestAturanPredikat:
    def test_default_rentang_skor(self, client: TestClient, bank: Bank) -> None:
        assert _predikat_tingkat(client, bank.kabupaten.id) == [
            ("Sangat Baik", 90.0),
            ("Baik", 80.0),
            ("Cukup", 70.0),
            ("Perlu Latihan", 0.0),
        ]

    def test_ubah_rentang_dipakai_saat_submit(self, client: TestClient, bank: Bank) -> None:
        response = client.put(
            f"{URL}/{bank.kabupaten.id}",
            json={"predikat": [{"label": "Lulus", "batas_bawah": 50}, {"label": "Belum Lulus", "batas_bawah": 0}]},
            headers=TOKEN_HEADER,
        )
        assert response.status_code == 200
        paket = _minta_paket(client, "siswa-1", bank.kabupaten).json()

        # 6 dari 10 benar = 60.
        body = _submit(client, paket["paket_id"], _jawab(paket, {"m-a-1": 4, "m-b-1": 2})).json()

        assert (body["skor"], body["predikat"]) == (60.0, "Lulus")
        assert _predikat_tingkat(client, bank.kabupaten.id) == [("Lulus", 50.0), ("Belum Lulus", 0.0)]

    def test_tanpa_predikat_dasar_nol_ditolak_422(self, client: TestClient, bank: Bank) -> None:
        response = client.put(
            f"{URL}/{bank.kabupaten.id}",
            json={"predikat": [{"label": "Lulus", "batas_bawah": 60}]},
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 422

    def test_tingkat_tidak_ada_404(self, client: TestClient, bank: Bank) -> None:
        response = client.put(
            f"{URL}/999999",
            json={"predikat": [{"label": "Semua", "batas_bawah": 0}]},
            headers=TOKEN_HEADER,
        )

        assert response.status_code == 404


class TestDashboardTanpaPredikat:
    def test_distribusi_predikat_tidak_dikirim(self, client: TestClient, bank: Bank) -> None:
        response = client.get("/api/v1/admin/dashboard", headers=TOKEN_HEADER)

        assert response.status_code == 200
        assert "distribusi_predikat" not in response.json()
