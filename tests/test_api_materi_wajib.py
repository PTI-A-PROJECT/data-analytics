"""Materi Wajib & Gerbang Simulasi lewat HTTP API (fase 2 issue 04), dengan bank
soal sintetis dari test_api_pretest (3 Materi, masing-masing 3 halaman).
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import AturanAdaptif, TingkatSeleksi
from tests.test_api_pretest import (  # noqa: F401 — fixture bank & client
    HALAMAN_PER_MATERI,
    TOKEN_HEADER,
    Bank,
    _jawab,
    _minta_paket,
    _submit,
    bank,
    client,
)

# Pre-test 10 soal: m-a-1 4 soal, m-b-1 & m-c-1 masing-masing 3.
SEMUA_BENAR = {"m-a-1": 99, "m-b-1": 99, "m-c-1": 99}


def _minta_simulasi(client: TestClient, tingkat: TingkatSeleksi) -> httpx.Response:
    return client.post(
        "/api/v1/simulasi/paket",
        json={"siswa_id": "siswa-1", "tingkat_seleksi_id": tingkat.id},
        headers=TOKEN_HEADER,
    )


def _baca(client: TestClient, materi_id: str, halaman: int) -> httpx.Response:
    return client.post(
        "/api/v1/analytics/events/materi-progress",
        json={
            "siswa_id": "siswa-1",
            "materi_id": materi_id,
            "halaman": halaman,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers=TOKEN_HEADER,
    )


def _gerbang(client: TestClient, tingkat: TingkatSeleksi) -> dict:  # type: ignore[type-arg]
    response = client.get(
        "/api/v1/siswa/siswa-1/remedial",
        params={"tingkat_seleksi_id": tingkat.id},
        headers=TOKEN_HEADER,
    )
    assert response.status_code == 200
    return response.json()  # type: ignore[no-any-return]


def _pretest(client: TestClient, bank: Bank, benar: dict[str, int]) -> None:
    paket = _minta_paket(client, "siswa-1", bank.kabupaten).json()
    assert _submit(client, paket["paket_id"], _jawab(paket, benar)).status_code == 200


def _set_jumlah_soal_simulasi(session: Session, bank: Bank, jumlah: int) -> None:
    aturan = session.scalars(
        select(AturanAdaptif).where(AturanAdaptif.tingkat_seleksi_id == bank.kabupaten.id)
    ).one()
    aturan.jumlah_soal_simulasi = jumlah
    session.commit()


class TestGerbangSimulasi:
    def test_materi_lemah_menahan_simulasi_sampai_semua_halaman_dibaca(
        self, client: TestClient, bank: Bank
    ) -> None:
        # m-b-1 0/3, m-c-1 1/3 → keduanya lemah; m-a-1 4/4.
        _pretest(client, bank, {"m-a-1": 4, "m-b-1": 0, "m-c-1": 1})

        ditolak = _minta_simulasi(client, bank.kabupaten)

        assert ditolak.status_code == 409
        body = ditolak.json()
        assert body["boleh_simulasi"] is False
        assert [
            (m["materi_id"], m["urutan"], m["akurasi"], m["halaman_dibuka"], m["selesai"])
            for m in body["materi_wajib"]
        ] == [("m-b-1", 1, 0.0, 0, False), ("m-c-1", 2, 33.33, 0, False)]
        assert body["materi_wajib"][0]["judul"] == "Materi m-b-1"
        assert body["materi_wajib"][0]["total_halaman"] == HALAMAN_PER_MATERI

        for materi_id, halaman in [
            ("m-c-1", 3), ("m-b-1", 2), ("m-c-1", 1), ("m-b-1", 3), ("m-b-1", 1), ("m-c-1", 2)
        ]:
            assert _baca(client, materi_id, halaman).status_code == 200

        assert _minta_simulasi(client, bank.kabupaten).status_code == 200

    def test_lompat_ke_halaman_terakhir_saja_tetap_ditahan(
        self, client: TestClient, bank: Bank
    ) -> None:
        _pretest(client, bank, {"m-a-1": 4, "m-b-1": 0, "m-c-1": 3})
        _baca(client, "m-b-1", HALAMAN_PER_MATERI)

        assert _minta_simulasi(client, bank.kabupaten).status_code == 409

    def test_tanpa_materi_lemah_langsung_boleh_simulasi(
        self, client: TestClient, bank: Bank
    ) -> None:
        _pretest(client, bank, SEMUA_BENAR)

        assert _gerbang(client, bank.kabupaten) == {
            "boleh_simulasi": True,
            "jumlah_materi_wajib": 0,
            "jumlah_selesai": 0,
            "materi_wajib": [],
        }
        assert _minta_simulasi(client, bank.kabupaten).status_code == 200

    def test_materi_yang_pernah_tamat_dan_lemah_lagi_harus_dibaca_ulang(
        self, client: TestClient, bank: Bank, session: Session
    ) -> None:
        _set_jumlah_soal_simulasi(session, bank, 6)
        _pretest(client, bank, {"m-a-1": 4, "m-b-1": 0, "m-c-1": 3})
        for halaman in range(1, HALAMAN_PER_MATERI + 1):
            _baca(client, "m-b-1", halaman)
        simulasi = _minta_simulasi(client, bank.kabupaten).json()
        _submit(
            client,
            simulasi["paket_id"],
            _jawab(simulasi, {"m-a-1": 99, "m-b-1": 0, "m-c-1": 99}),
        )

        status = _gerbang(client, bank.kabupaten)

        assert [(m["materi_id"], m["halaman_dibuka"]) for m in status["materi_wajib"]] == [
            ("m-b-1", 0)
        ]
        assert _minta_simulasi(client, bank.kabupaten).status_code == 409


class TestStatusMateriWajib:
    def test_progress_belajar_materi_wajib(self, client: TestClient, bank: Bank) -> None:
        _pretest(client, bank, {"m-a-1": 4, "m-b-1": 0, "m-c-1": 0})
        for halaman in range(1, HALAMAN_PER_MATERI + 1):
            _baca(client, "m-c-1", halaman)
        _baca(client, "m-b-1", 2)
        _baca(client, "m-b-1", 2)

        body = _gerbang(client, bank.kabupaten)

        assert body["boleh_simulasi"] is False
        assert (body["jumlah_materi_wajib"], body["jumlah_selesai"]) == (2, 1)
        assert [
            (m["materi_id"], m["halaman_dibuka"], m["selesai"]) for m in body["materi_wajib"]
        ] == [("m-b-1", 1, False), ("m-c-1", 3, True)]

    def test_sebelum_pretest_belum_boleh_simulasi(self, client: TestClient, bank: Bank) -> None:
        body = _gerbang(client, bank.kabupaten)

        assert body["boleh_simulasi"] is False
        assert body["materi_wajib"] == []


class TestEventBacaHalaman:
    def test_menghitung_halaman_unik_yang_pernah_dibuka(
        self, client: TestClient, bank: Bank
    ) -> None:
        _baca(client, "m-a-1", 3)
        _baca(client, "m-a-1", 1)

        body = _baca(client, "m-a-1", 3).json()

        assert (body["halaman_dibuka"], body["total_halaman"], body["persentase_selesai"]) == (
            2,
            HALAMAN_PER_MATERI,
            66.67,
        )

    def test_materi_tidak_ada_422(self, client: TestClient, bank: Bank) -> None:
        assert _baca(client, "tidak-ada", 1).status_code == 422

    def test_halaman_di_luar_rentang_422(self, client: TestClient, bank: Bank) -> None:
        assert _baca(client, "m-a-1", 0).status_code == 422
        assert _baca(client, "m-a-1", HALAMAN_PER_MATERI + 1).status_code == 422
