"""Leaderboard lewat HTTP API: dihitung otomatis dari setiap submit simulasi di
jenjang yang diikuti siswa, 5 teratas, dengan nama siswa & asal sekolah.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import AturanAdaptif
from tests.test_api_pretest import (  # noqa: F401 — fixture bank & client
    TOKEN_HEADER,
    Bank,
    _jawab,
    _minta_paket,
    bank,
    client,
)

SEMUA_BENAR = {"m-a-1": 99, "m-b-1": 99, "m-c-1": 99}
# Pre-test 8/10: tanpa Materi lemah (Gerbang Simulasi terbuka), jalur cepat gagal.
TANPA_MATERI_LEMAH = {"m-a-1": 4, "m-b-1": 2, "m-c-1": 2}
T0 = datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc)


def _submit(
    client: TestClient,
    paket: dict,  # type: ignore[type-arg]
    benar: dict[str, int],
    *,
    detik_per_soal: int | None = None,
    nama: str | None = None,
    sekolah: str | None = None,
) -> httpx.Response:
    jawaban = _jawab(paket, benar)
    if detik_per_soal is not None:
        for i, j in enumerate(jawaban):
            j["dibuka_pada"] = (T0 + timedelta(seconds=i * detik_per_soal)).isoformat()
            j["dijawab_pada"] = (T0 + timedelta(seconds=(i + 1) * detik_per_soal)).isoformat()
    body: dict[str, object] = {"jawaban": jawaban, "sekolah_id": f"id-{sekolah}"}
    if nama is not None:
        body.update(nama_siswa=nama, nama_sekolah=sekolah)
    return client.post(f"/api/v1/paket/{paket['paket_id']}/submit", json=body, headers=TOKEN_HEADER)


def _simulasi(
    client: TestClient,
    bank: Bank,
    siswa_id: str,
    *,
    benar: dict[str, int],
    detik_per_soal: int | None,
    nama: str,
    sekolah: str,
) -> None:
    pretest = _minta_paket(client, siswa_id, bank.kabupaten).json()
    assert _submit(client, pretest, TANPA_MATERI_LEMAH).status_code == 200
    paket = client.post(
        "/api/v1/simulasi/paket",
        json={"siswa_id": siswa_id, "tingkat_seleksi_id": bank.kabupaten.id},
        headers=TOKEN_HEADER,
    ).json()
    response = _submit(
        client, paket, benar, detik_per_soal=detik_per_soal, nama=nama, sekolah=sekolah
    )
    assert response.status_code == 200


def _leaderboard(client: TestClient, siswa_id: str) -> dict:  # type: ignore[type-arg]
    response = client.get(f"/api/v1/siswa/{siswa_id}/leaderboard", headers=TOKEN_HEADER)
    assert response.status_code == 200
    return response.json()  # type: ignore[no-any-return]


def _set_jumlah_soal_simulasi(session: Session, bank: Bank, jumlah: int) -> None:
    aturan = session.scalars(
        select(AturanAdaptif).where(AturanAdaptif.tingkat_seleksi_id == bank.kabupaten.id)
    ).one()
    aturan.jumlah_soal_simulasi = jumlah
    session.commit()


class TestLeaderboard:
    def test_urut_skor_gabungan_dengan_nama_dan_sekolah(
        self, client: TestClient, bank: Bank, session: Session
    ) -> None:
        _set_jumlah_soal_simulasi(session, bank, 6)
        # Ani: skor 100, 60 dtk/soal → 0.5*100 + 0.5*50 = 75.
        _simulasi(client, bank, "ani", benar=SEMUA_BENAR, detik_per_soal=60, nama="Ani", sekolah="SMAN 1")
        # Budi: skor 50 (m-a & m-b saja), 30 dtk/soal → 0.5*50 + 0.5*100 = 75; seri, skor lebih rendah.
        _simulasi(
            client, bank, "budi", benar={"m-a-1": 99, "m-b-1": 1}, detik_per_soal=30, nama="Budi", sekolah="SMAN 2"
        )
        # Cici: skor 100, 30 dtk/soal → 100.
        _simulasi(client, bank, "cici", benar=SEMUA_BENAR, detik_per_soal=30, nama="Cici", sekolah="SMAN 1")

        body = _leaderboard(client, "budi")

        assert (body["tingkat_seleksi_id"], body["nama_tingkat"]) == (bank.kabupaten.id, "Kabupaten")
        assert [
            (p["peringkat"], p["nama_siswa"], p["nama_sekolah"], p["skor_gabungan"])
            for p in body["peringkat"]
        ] == [(1, "Cici", "SMAN 1", 100.0), (2, "Ani", "SMAN 1", 75.0), (3, "Budi", "SMAN 2", 75.0)]
        assert body["peringkat"][0]["durasi_detik"] == 180.0

    def test_simulasi_tanpa_waktu_pengerjaan_tidak_masuk_peringkat(
        self, client: TestClient, bank: Bank, session: Session
    ) -> None:
        _set_jumlah_soal_simulasi(session, bank, 6)
        _simulasi(client, bank, "ani", benar=SEMUA_BENAR, detik_per_soal=None, nama="Ani", sekolah="SMAN 1")

        assert _leaderboard(client, "ani")["peringkat"] == []

    def test_jenjang_yang_diikuti_siswa_provinsi(self, client: TestClient, bank: Bank) -> None:
        paket = _minta_paket(client, "dewi", bank.kabupaten).json()
        _submit(client, paket, SEMUA_BENAR)  # 100 ≥ 90: jalur cepat
        provinsi = _minta_paket(client, "dewi", bank.provinsi).json()
        _submit(client, provinsi, SEMUA_BENAR)

        body = _leaderboard(client, "dewi")

        assert (body["tingkat_seleksi_id"], body["nama_tingkat"]) == (bank.provinsi.id, "Provinsi")
