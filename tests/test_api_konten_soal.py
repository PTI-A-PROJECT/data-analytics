"""Konten soal bank OSN di Paket Tes: tipe soal, deskripsi, kode, gambar, dan
penilaian isian singkat."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from data_analytics.api import app
from data_analytics.config import Settings, get_settings
from data_analytics.db import get_db
from data_analytics.models import (
    DIMENSI_EMBEDDING,
    AturanAdaptif,
    LevelSoal,
    Materi,
    Soal,
    TingkatSeleksi,
    TipeSoal,
)

TOKEN_HEADER = {"X-Internal-Token": get_settings().internal_api_token}


@pytest.fixture
def folder_soal(tmp_path: Path) -> Path:
    (tmp_path / "gambar_kabupaten").mkdir()
    (tmp_path / "gambar_kabupaten" / "soal_1.png").write_bytes(b"\x89PNG-isi")
    return tmp_path


@pytest.fixture
def client(session: Session, folder_soal: Path) -> Iterator[TestClient]:
    def _db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_settings] = lambda: Settings(folder_soal=str(folder_soal))
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def tingkat(session: Session) -> TingkatSeleksi:
    kabupaten = TingkatSeleksi(nama="Kabupaten", urutan=1)
    session.add(kabupaten)
    session.flush()
    session.add(
        Materi(
            id="kab-a",
            tingkat_seleksi_id=kabupaten.id,
            judul="Materi A",
            embedding=[1.0] * DIMENSI_EMBEDDING,
            hash_konten="h",
        )
    )
    umum = {
        "materi_id": "kab-a",
        "tingkat_seleksi_id": kabupaten.id,
        "level": LevelSoal.MUDAH,
        "embedding": [1.0] * DIMENSI_EMBEDDING,
        "hash_konten": "h",
        "pembahasan": None,
    }
    session.add_all(
        [
            Soal(
                id="kab-2020-001",
                tipe=TipeSoal.PILIHAN_GANDA,
                deskripsi="Cerita bebek",
                pertanyaan="Berapa bebek?",
                kode="x := 1;",
                gambar="kabupaten/soal_1.png",
                tahun=2020,
                pilihan_jawaban={"A": "1", "B": "2"},
                kunci_jawaban="B",
                **umum,
            ),
            Soal(
                id="kab-2020-002",
                tipe=TipeSoal.ISIAN_SINGKAT,
                pertanyaan="Berapa permutasi?",
                tahun=2020,
                pilihan_jawaban={},
                kunci_jawaban="1260",
                **umum,
            ),
        ]
    )
    session.add(AturanAdaptif(tingkat_seleksi_id=kabupaten.id, jumlah_soal_pretest=2, ambang_lemah=50))
    session.commit()
    return kabupaten


class TestKontenSoalDiPaket:
    def test_paket_membawa_tipe_deskripsi_kode_gambar(
        self, client: TestClient, tingkat: TingkatSeleksi
    ) -> None:
        paket = client.post(
            "/api/v1/pretest/paket",
            json={"siswa_id": "s1", "tingkat_seleksi_id": tingkat.id},
            headers=TOKEN_HEADER,
        ).json()

        soal = {s["soal_id"]: s for s in paket["soal"]}
        assert {k: soal["kab-2020-001"][k] for k in ("tipe", "deskripsi", "kode", "gambar")} == {
            "tipe": "pilihan_ganda",
            "deskripsi": "Cerita bebek",
            "kode": "x := 1;",
            "gambar": "/api/v1/konten/gambar/kabupaten/soal_1.png",
        }
        assert (soal["kab-2020-002"]["tipe"], soal["kab-2020-002"]["pilihan_jawaban"]) == (
            "isian_singkat",
            {},
        )

    def test_isian_singkat_dinilai_dengan_pencocokan_ternormalisasi(
        self, client: TestClient, tingkat: TingkatSeleksi
    ) -> None:
        paket = client.post(
            "/api/v1/pretest/paket",
            json={"siswa_id": "s1", "tingkat_seleksi_id": tingkat.id},
            headers=TOKEN_HEADER,
        ).json()

        body = client.post(
            f"/api/v1/paket/{paket['paket_id']}/submit",
            json={
                "jawaban": [
                    {"soal_id": "kab-2020-001", "jawaban_dipilih": "b"},
                    {"soal_id": "kab-2020-002", "jawaban_dipilih": " 1260 "},
                ]
            },
            headers=TOKEN_HEADER,
        ).json()

        assert body["skor"] == 100.0


class TestGambarSoal:
    def test_menyajikan_file_gambar(self, client: TestClient) -> None:
        response = client.get("/api/v1/konten/gambar/kabupaten/soal_1.png", headers=TOKEN_HEADER)

        assert response.status_code == 200
        assert response.content == b"\x89PNG-isi"

    def test_path_di_luar_folder_gambar_ditolak(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/konten/gambar/kabupaten/..%2F..%2Fsecret.txt", headers=TOKEN_HEADER
        )

        assert response.status_code == 404

    def test_file_tidak_ada_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/konten/gambar/kabupaten/tidak_ada.png", headers=TOKEN_HEADER)

        assert response.status_code == 404
