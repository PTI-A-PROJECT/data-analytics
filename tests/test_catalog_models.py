"""Skema katalog lokal: TingkatSeleksi (tiket 09) dan bank konten
fase 2 — Materi, HalamanMateri, Soal ber-embedding pgvector (issue fase 2 #01,
docs/adr/0004).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from data_analytics.models import (
    DIMENSI_EMBEDDING,
    HalamanMateri,
    LevelSoal,
    Materi,
    Soal,
    TingkatSeleksi,
)


def vektor(*awal: float) -> list[float]:
    """Embedding sintetis: komponen awal ditentukan test, sisanya nol."""
    return [*awal, *([0.0] * (DIMENSI_EMBEDDING - len(awal)))]


def _tingkat_seleksi(session: Session, *, nama: str = "Kabupaten", urutan: int = 1) -> TingkatSeleksi:
    tingkat = TingkatSeleksi(nama=nama, urutan=urutan)
    session.add(tingkat)
    session.flush()
    return tingkat


def _materi(session: Session, tingkat: TingkatSeleksi, *, id: str = "m-graph") -> Materi:
    materi = Materi(
        id=id,
        tingkat_seleksi_id=tingkat.id,
        judul="Graph",
        embedding=vektor(1.0),
        hash_konten="h",
        halaman=[
            HalamanMateri(nomor=1, konten="Definisi graph"),
            HalamanMateri(nomor=2, konten="BFS dan DFS"),
        ],
    )
    session.add(materi)
    session.flush()
    return materi


def _soal(
    materi: Materi,
    *,
    id: str,
    level: LevelSoal = LevelSoal.MUDAH,
    embedding: list[float] | None = None,
) -> Soal:
    return Soal(
        id=id,
        materi_id=materi.id,
        tingkat_seleksi_id=materi.tingkat_seleksi_id,
        pertanyaan="Berapa derajat simpul A?",
        pilihan_jawaban={"A": "1", "B": "2", "C": "3", "D": "4"},
        kunci_jawaban="B",
        pembahasan="A terhubung ke B dan C.",
        level=level,
        embedding=embedding if embedding is not None else vektor(1.0),
        hash_konten="h",
    )


class TestTingkatSeleksi:
    def test_simpan_dan_baca(self, session: Session) -> None:
        tingkat = _tingkat_seleksi(session, nama="Provinsi", urutan=2)

        assert tingkat.id is not None
        assert tingkat.nama == "Provinsi"
        assert tingkat.urutan == 2

    def test_urutan_harus_unik(self, session: Session) -> None:
        _tingkat_seleksi(session, nama="Kabupaten", urutan=1)
        session.add(TingkatSeleksi(nama="Provinsi", urutan=1))

        with pytest.raises(IntegrityError):
            session.flush()


class TestMateri:
    def test_simpan_dengan_halaman_berurutan(self, session: Session) -> None:
        materi = _materi(session, _tingkat_seleksi(session))
        session.expire_all()

        dibaca = session.get(Materi, materi.id)

        assert dibaca is not None
        assert dibaca.total_halaman == 2
        assert [h.konten for h in dibaca.halaman] == ["Definisi graph", "BFS dan DFS"]

    def test_nomor_halaman_unik_per_materi(self, session: Session) -> None:
        materi = _materi(session, _tingkat_seleksi(session))
        materi.halaman.append(HalamanMateri(nomor=1, konten="duplikat"))

        with pytest.raises(IntegrityError):
            session.flush()


class TestSoal:
    def test_simpan_dan_baca(self, session: Session) -> None:
        materi = _materi(session, _tingkat_seleksi(session))
        session.add(_soal(materi, id="s-1", level=LevelSoal.MENENGAH))
        session.flush()
        session.expire_all()

        soal = session.get(Soal, "s-1")

        assert soal is not None
        assert soal.level is LevelSoal.MENENGAH
        assert soal.pilihan_jawaban["B"] == "2"
        assert len(soal.embedding) == DIMENSI_EMBEDDING

    def test_harus_milik_materi_yang_ada(self, session: Session) -> None:
        tingkat = _tingkat_seleksi(session)
        session.add(
            Soal(
                id="s-yatim",
                materi_id="tidak-ada",
                tingkat_seleksi_id=tingkat.id,
                pertanyaan="Q",
                pilihan_jawaban={"A": "x"},
                kunci_jawaban="A",
                pembahasan=None,
                level=LevelSoal.MUDAH,
                embedding=vektor(1.0),
                hash_konten="h",
            )
        )

        with pytest.raises(IntegrityError):
            session.flush()

    def test_bisa_diurutkan_berdasarkan_kemiripan_kosinus(self, session: Session) -> None:
        materi = _materi(session, _tingkat_seleksi(session))
        session.add_all(
            [
                _soal(materi, id="jauh", embedding=vektor(0.0, 1.0)),
                _soal(materi, id="dekat", embedding=vektor(1.0, 0.1)),
                _soal(materi, id="tengah", embedding=vektor(1.0, 1.0)),
            ]
        )
        session.flush()

        urutan = session.scalars(
            select(Soal.id).order_by(Soal.embedding.cosine_distance(vektor(1.0)))
        ).all()

        assert urutan == ["dekat", "tengah", "jauh"]
