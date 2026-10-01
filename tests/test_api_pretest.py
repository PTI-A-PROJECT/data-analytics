"""Alur Gerbang Pre-Test Kabupaten → Provinsi lewat HTTP API (fase 2 issue 02),
dengan bank soal sintetis.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.api import app
from data_analytics.config import get_settings
from data_analytics.db import get_db
from data_analytics.models import (
    DIMENSI_EMBEDDING,
    AturanAdaptif,
    AturanKenaikanTingkat,
    HalamanMateri,
    LevelSoal,
    LevelSoalSiswa,
    Materi,
    Soal,
    TingkatSeleksi,
)

TOKEN_HEADER = {"X-Internal-Token": get_settings().internal_api_token}
MATERI_IDS = ("m-a", "m-b", "m-c")
JUMLAH_SOAL_PRETEST = 10
HALAMAN_PER_MATERI = 3


@dataclass
class Bank:
    kabupaten: TingkatSeleksi
    provinsi: TingkatSeleksi


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    def _override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _isi_bank_soal(session: Session, tingkat: TingkatSeleksi) -> None:
    """Tiap Materi: 3 halaman, 5 soal Mudah (kunci "A") + 2 soal Sulit."""
    for materi_id in MATERI_IDS:
        id_ = f"{materi_id}-{tingkat.urutan}"
        session.add(
            Materi(
                id=id_,
                tingkat_seleksi_id=tingkat.id,
                judul=f"Materi {id_}",
                embedding=[1.0] * DIMENSI_EMBEDDING,
                hash_konten="h",
                halaman=[
                    HalamanMateri(nomor=n, konten=f"Halaman {n}")
                    for n in range(1, HALAMAN_PER_MATERI + 1)
                ],
            )
        )
        for nomor in range(7):
            session.add(
                Soal(
                    id=f"{id_}-s{nomor}",
                    materi_id=id_,
                    tingkat_seleksi_id=tingkat.id,
                    pertanyaan=f"Pertanyaan {nomor}",
                    pilihan_jawaban={"A": "benar", "B": "salah"},
                    kunci_jawaban="A",
                    pembahasan="Karena A.",
                    level=LevelSoal.MUDAH if nomor < 5 else LevelSoal.SULIT,
                    embedding=[1.0] * DIMENSI_EMBEDDING,
                    hash_konten="h",
                )
            )


@pytest.fixture
def bank(session: Session) -> Bank:
    kabupaten = TingkatSeleksi(nama="Kabupaten", urutan=1)
    provinsi = TingkatSeleksi(nama="Provinsi", urutan=2)
    session.add_all([kabupaten, provinsi])
    session.flush()
    for tingkat in (kabupaten, provinsi):
        _isi_bank_soal(session, tingkat)
        session.add(
            AturanAdaptif(
                tingkat_seleksi_id=tingkat.id,
                jumlah_soal_pretest=JUMLAH_SOAL_PRETEST,
                ambang_lemah=50,
            )
        )
    session.add(
        AturanKenaikanTingkat(
            tingkat_asal_id=kabupaten.id,
            tingkat_tujuan_id=provinsi.id,
            skor_simulasi_min=75,
            skor_pretest_jalur_cepat=90,
            rata_level_min=2.0,
        )
    )
    session.commit()
    return Bank(kabupaten=kabupaten, provinsi=provinsi)


def _status_akses(client: TestClient, siswa_id: str) -> dict[str, str]:
    response = client.get(f"/api/v1/siswa/{siswa_id}/akses", headers=TOKEN_HEADER)
    assert response.status_code == 200
    return {item["nama"]: item["status"] for item in response.json()["daftar_akses"]}


class TestAksesSiswaBaru:
    def test_kabupaten_pretest_terbuka_provinsi_terkunci(
        self, client: TestClient, bank: Bank
    ) -> None:
        assert _status_akses(client, "siswa-1") == {
            "Kabupaten": "pretest_terbuka",
            "Provinsi": "terkunci",
        }


def _minta_paket(client: TestClient, siswa_id: str, tingkat: TingkatSeleksi) -> httpx.Response:
    return client.post(
        "/api/v1/pretest/paket",
        json={"siswa_id": siswa_id, "tingkat_seleksi_id": tingkat.id},
        headers=TOKEN_HEADER,
    )


class TestPaketPretest:
    def test_semua_soal_mudah_rata_per_materi_tanpa_kunci(
        self, client: TestClient, bank: Bank, session: Session
    ) -> None:
        response = _minta_paket(client, "siswa-1", bank.kabupaten)

        assert response.status_code == 200
        soal = response.json()["soal"]
        assert len(soal) == JUMLAH_SOAL_PRETEST
        per_materi: dict[str, int] = {}
        for item in soal:
            per_materi[item["materi_id"]] = per_materi.get(item["materi_id"], 0) + 1
            assert "kunci_jawaban" not in item and "pembahasan" not in item
            baris = session.get(Soal, item["soal_id"])
            assert baris is not None and baris.level is LevelSoal.MUDAH
        assert sorted(per_materi.values()) == [3, 3, 4]
        assert sorted(item["urutan"] for item in soal) == list(range(1, JUMLAH_SOAL_PRETEST + 1))

    def test_idempoten_selama_belum_disubmit(self, client: TestClient, bank: Bank) -> None:
        pertama = _minta_paket(client, "siswa-1", bank.kabupaten).json()
        kedua = _minta_paket(client, "siswa-1", bank.kabupaten).json()

        assert kedua["paket_id"] == pertama["paket_id"]
        assert kedua["soal"] == pertama["soal"]

    def test_provinsi_terkunci_ditolak_403(self, client: TestClient, bank: Bank) -> None:
        response = _minta_paket(client, "siswa-1", bank.provinsi)

        assert response.status_code == 403


def _jawab(paket: dict, benar_per_materi: dict[str, int]) -> list[dict]:  # type: ignore[type-arg]
    """Jawab `n` soal pertama tiap Materi dengan benar ("A"), sisanya salah."""
    sudah: dict[str, int] = {}
    jawaban = []
    for item in paket["soal"]:
        ke = sudah.get(item["materi_id"], 0)
        sudah[item["materi_id"]] = ke + 1
        benar = ke < benar_per_materi.get(item["materi_id"], 0)
        jawaban.append({"soal_id": item["soal_id"], "jawaban_dipilih": "A" if benar else "B"})
    return jawaban


def _submit(client: TestClient, paket_id: int, jawaban: list[dict]) -> httpx.Response:  # type: ignore[type-arg]
    return client.post(
        f"/api/v1/paket/{paket_id}/submit", json={"jawaban": jawaban}, headers=TOKEN_HEADER
    )


class TestSubmitPretest:
    def test_skor_peta_per_materi_dan_akses_kabupaten_terbuka(
        self, client: TestClient, bank: Bank, session: Session
    ) -> None:
        paket = _minta_paket(client, "siswa-1", bank.kabupaten).json()
        # m-a-1 mendapat 4 soal (sisa pembagian), m-b-1 & m-c-1 masing-masing 3.
        jawaban = _jawab(paket, {"m-a-1": 4, "m-b-1": 0, "m-c-1": 2})

        response = _submit(client, paket["paket_id"], jawaban)

        assert response.status_code == 200
        body = response.json()
        assert body["skor"] == 60.0
        assert [
            (p["materi_id"], p["status_pemetaan"], p["akurasi"]) for p in body["peta_kompetensi"]
        ] == [
            ("m-a-1", "Cukup", 100.0),
            ("m-b-1", "Belum Cukup", 0.0),
            ("m-c-1", "Cukup", 66.67),
        ]
        assert body["materi_lemah"] == ["m-b-1"]
        assert {a["nama"]: a["status"] for a in body["daftar_akses"]} == {
            "Kabupaten": "terbuka",
            "Provinsi": "terkunci",
        }
        level = session.scalars(
            select(LevelSoalSiswa.level).where(LevelSoalSiswa.siswa_id == "siswa-1")
        ).all()
        assert level == [LevelSoal.MUDAH] * len(MATERI_IDS)

    def test_soal_yang_tidak_dijawab_dihitung_salah(self, client: TestClient, bank: Bank) -> None:
        paket = _minta_paket(client, "siswa-1", bank.kabupaten).json()
        jawaban = _jawab(paket, {"m-a-1": 4, "m-b-1": 3, "m-c-1": 3})[:5]

        body = _submit(client, paket["paket_id"], jawaban).json()

        assert body["skor"] == 50.0

    def test_submit_ulang_ditolak_409(self, client: TestClient, bank: Bank) -> None:
        paket = _minta_paket(client, "siswa-1", bank.kabupaten).json()
        jawaban = _jawab(paket, {})
        _submit(client, paket["paket_id"], jawaban)

        assert _submit(client, paket["paket_id"], jawaban).status_code == 409

    def test_minta_paket_setelah_pretest_selesai_ditolak_409(
        self, client: TestClient, bank: Bank
    ) -> None:
        paket = _minta_paket(client, "siswa-1", bank.kabupaten).json()
        _submit(client, paket["paket_id"], _jawab(paket, {}))

        assert _minta_paket(client, "siswa-1", bank.kabupaten).status_code == 409

    def test_soal_di_luar_paket_ditolak_422(self, client: TestClient, bank: Bank) -> None:
        paket = _minta_paket(client, "siswa-1", bank.kabupaten).json()
        jawaban = [*_jawab(paket, {}), {"soal_id": "m-a-1-s6", "jawaban_dipilih": "A"}]

        assert _submit(client, paket["paket_id"], jawaban).status_code == 422


def _set_ambang_jalur_cepat(session: Session, bank: Bank, ambang: float) -> None:
    aturan = session.scalars(
        select(AturanKenaikanTingkat).where(
            AturanKenaikanTingkat.tingkat_asal_id == bank.kabupaten.id
        )
    ).one()
    aturan.skor_pretest_jalur_cepat = ambang
    session.commit()


class TestJalurCepat:
    def test_skor_tepat_di_ambang_membuka_pretest_provinsi(
        self, client: TestClient, bank: Bank
    ) -> None:
        paket = _minta_paket(client, "siswa-1", bank.kabupaten).json()
        # 9 dari 10 benar = 90.
        body = _submit(client, paket["paket_id"], _jawab(paket, {"m-a-1": 4, "m-b-1": 3, "m-c-1": 2})).json()

        assert body["skor"] == 90.0
        assert _status_akses(client, "siswa-1")["Provinsi"] == "pretest_terbuka"
        assert _minta_paket(client, "siswa-1", bank.provinsi).status_code == 200

    def test_skor_di_bawah_ambang_provinsi_tetap_terkunci(
        self, client: TestClient, bank: Bank, session: Session
    ) -> None:
        _set_ambang_jalur_cepat(session, bank, 90.01)
        paket = _minta_paket(client, "siswa-1", bank.kabupaten).json()

        _submit(client, paket["paket_id"], _jawab(paket, {"m-a-1": 4, "m-b-1": 3, "m-c-1": 2}))

        assert _status_akses(client, "siswa-1")["Provinsi"] == "terkunci"
        assert _minta_paket(client, "siswa-1", bank.provinsi).status_code == 403


class TestMateriDanSimulasiTerbukaSetelahPretest:
    """Status 'terbuka' = materi & simulasi tingkat itu terbuka. Pre-test
    memetakan kelemahan, bukan menyaring — skor berapa pun membukanya."""

    def test_skor_nol_tetap_membuka_kabupaten(self, client: TestClient, bank: Bank) -> None:
        paket = _minta_paket(client, "siswa-1", bank.kabupaten).json()

        body = _submit(client, paket["paket_id"], _jawab(paket, {})).json()

        assert body["skor"] == 0.0
        assert _status_akses(client, "siswa-1")["Kabupaten"] == "terbuka"

    def test_pretest_provinsi_membuka_provinsi(self, client: TestClient, bank: Bank) -> None:
        semua_benar = {"m-a-1": 4, "m-b-1": 3, "m-c-1": 3}
        paket_kab = _minta_paket(client, "siswa-1", bank.kabupaten).json()
        _submit(client, paket_kab["paket_id"], _jawab(paket_kab, semua_benar))
        paket_prov = _minta_paket(client, "siswa-1", bank.provinsi).json()

        _submit(client, paket_prov["paket_id"], _jawab(paket_prov, {}))

        assert _status_akses(client, "siswa-1") == {"Kabupaten": "terbuka", "Provinsi": "terbuka"}
