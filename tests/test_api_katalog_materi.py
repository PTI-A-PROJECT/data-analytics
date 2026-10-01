"""Katalog Materi: daftar Materi, daftar isi, dan konten Halaman Materi."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from data_analytics.api import app
from data_analytics.config import get_settings
from data_analytics.db import get_db
from data_analytics.models import (
    DIMENSI_EMBEDDING,
    HalamanMateri,
    Materi,
    RiwayatBacaHalaman,
    TingkatSeleksi,
)

TOKEN_HEADER = {"X-Internal-Token": get_settings().internal_api_token}


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    def _db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = _db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _materi(id_: str, tingkat: TingkatSeleksi, topik: int | None, halaman: int) -> Materi:
    return Materi(
        id=id_,
        tingkat_seleksi_id=tingkat.id,
        judul=f"Judul {id_}",
        topik=topik,
        embedding=[1.0] * DIMENSI_EMBEDDING,
        hash_konten="h",
        halaman=[
            HalamanMateri(nomor=n, judul=f"{n}. Bagian", konten=f"Isi {id_} {n}")
            for n in range(1, halaman + 1)
        ],
    )


@pytest.fixture
def tingkat(session: Session) -> tuple[TingkatSeleksi, TingkatSeleksi]:
    kab = TingkatSeleksi(nama="Kabupaten", urutan=1)
    prov = TingkatSeleksi(nama="Provinsi", urutan=2)
    session.add_all([kab, prov])
    session.flush()
    session.add_all(
        [
            _materi("prov-a", prov, 1, 1),
            _materi("kab-b", kab, 2, 2),
            _materi("kab-a", kab, 1, 3),
        ]
    )
    session.flush()
    return kab, prov


def test_daftar_materi_urut_tingkat_lalu_topik(
    client: TestClient, tingkat: tuple[TingkatSeleksi, TingkatSeleksi]
) -> None:
    respons = client.get("/api/v1/materi", headers=TOKEN_HEADER)

    assert respons.status_code == 200
    body = respons.json()
    assert [m["materi_id"] for m in body] == ["kab-a", "kab-b", "prov-a"]
    assert body[0] == {
        "materi_id": "kab-a",
        "tingkat_seleksi_id": tingkat[0].id,
        "nama_tingkat": "Kabupaten",
        "topik": 1,
        "judul": "Judul kab-a",
        "total_halaman": 3,
        "halaman_dibaca": None,
        "persentase_dibaca": None,
    }


def test_daftar_materi_per_tingkat_dengan_progres_baca_siswa(
    client: TestClient, session: Session, tingkat: tuple[TingkatSeleksi, TingkatSeleksi]
) -> None:
    waktu = datetime(2026, 9, 30, tzinfo=timezone.utc)
    session.add(
        RiwayatBacaHalaman(
            siswa_id="s1",
            materi_id="kab-a",
            nomor_halaman=2,
            pertama_dibuka_pada=waktu,
            terakhir_dibuka_pada=waktu,
        )
    )
    session.flush()

    respons = client.get(
        "/api/v1/materi",
        params={"tingkat_seleksi_id": tingkat[0].id, "siswa_id": "s1"},
        headers=TOKEN_HEADER,
    )

    body = respons.json()
    assert [m["materi_id"] for m in body] == ["kab-a", "kab-b"]
    assert body[0]["halaman_dibaca"] == 1
    assert body[0]["persentase_dibaca"] == pytest.approx(33.33, abs=0.01)
    assert body[1]["halaman_dibaca"] == 0


def test_daftar_materi_tingkat_tidak_ada_404(
    client: TestClient, tingkat: tuple[TingkatSeleksi, TingkatSeleksi]
) -> None:
    respons = client.get("/api/v1/materi", params={"tingkat_seleksi_id": 999}, headers=TOKEN_HEADER)

    assert respons.status_code == 404


def test_detail_materi_berisi_daftar_isi(
    client: TestClient, tingkat: tuple[TingkatSeleksi, TingkatSeleksi]
) -> None:
    respons = client.get("/api/v1/materi/kab-b", headers=TOKEN_HEADER)

    assert respons.status_code == 200
    body = respons.json()
    assert body["total_halaman"] == 2
    assert body["halaman"] == [
        {"nomor": 1, "judul": "1. Bagian", "sudah_dibaca": None},
        {"nomor": 2, "judul": "2. Bagian", "sudah_dibaca": None},
    ]


def test_halaman_materi_dengan_navigasi(
    client: TestClient, tingkat: tuple[TingkatSeleksi, TingkatSeleksi]
) -> None:
    respons = client.get("/api/v1/materi/kab-a/halaman/2", headers=TOKEN_HEADER)

    assert respons.status_code == 200
    assert respons.json() == {
        "materi_id": "kab-a",
        "judul_materi": "Judul kab-a",
        "nomor": 2,
        "judul": "2. Bagian",
        "konten": "Isi kab-a 2",
        "total_halaman": 3,
        "nomor_sebelumnya": 1,
        "nomor_berikutnya": 3,
    }


@pytest.mark.parametrize("url", ["/api/v1/materi/tidak-ada", "/api/v1/materi/kab-a/halaman/9"])
def test_materi_atau_halaman_tidak_ada_404(
    client: TestClient, tingkat: tuple[TingkatSeleksi, TingkatSeleksi], url: str
) -> None:
    assert client.get(url, headers=TOKEN_HEADER).status_code == 404


def test_tanpa_token_ditolak(client: TestClient) -> None:
    assert client.get("/api/v1/materi").status_code == 422
    assert client.get("/api/v1/materi", headers={"X-Internal-Token": "salah"}).status_code == 403
