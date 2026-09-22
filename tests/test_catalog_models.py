"""Skema katalog lokal (tiket 09): TingkatSeleksi, AturanPemetaan, Kompetensi,
Subkompetensi, Soal — data uji/seed supaya Peta Kompetensi & Rekomendasi Materi
bisa dikembangkan sebelum data pilot nyata tersedia. Lihat docs/adr/0003.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from data_analytics.models import (
    AturanPemetaan,
    Kompetensi,
    Soal,
    Subkompetensi,
    TingkatSeleksi,
)


def _tingkat_seleksi(session: Session, *, nama: str = "Kabupaten", urutan: int = 1) -> TingkatSeleksi:
    tingkat = TingkatSeleksi(nama=nama, urutan=urutan)
    session.add(tingkat)
    session.flush()
    return tingkat


def _kompetensi(session: Session, *, nama: str = "Struktur Data") -> Kompetensi:
    kompetensi = Kompetensi(nama=nama, deskripsi=None)
    session.add(kompetensi)
    session.flush()
    return kompetensi


class TestTingkatSeleksi:
    def test_simpan_dan_baca(self, session: Session) -> None:
        tingkat = _tingkat_seleksi(session, nama="Nasional", urutan=3)

        assert tingkat.id is not None
        assert tingkat.nama == "Nasional"
        assert tingkat.urutan == 3

    def test_urutan_harus_unik(self, session: Session) -> None:
        _tingkat_seleksi(session, nama="Kabupaten", urutan=1)
        session.add(TingkatSeleksi(nama="Provinsi", urutan=1))

        with pytest.raises(IntegrityError):
            session.flush()


class TestAturanPemetaan:
    def test_simpan_dan_baca(self, session: Session) -> None:
        tingkat = _tingkat_seleksi(session)

        aturan = AturanPemetaan(
            tingkat_seleksi_id=str(tingkat.id),
            ambang_cukup_persen=70,
            ambang_representasi_persen=20,
        )
        session.add(aturan)
        session.flush()

        assert aturan.ambang_cukup_persen == 70
        assert aturan.ambang_representasi_persen == 20

    def test_satu_tingkat_seleksi_hanya_satu_aturan(self, session: Session) -> None:
        tingkat = _tingkat_seleksi(session)
        session.add(
            AturanPemetaan(
                tingkat_seleksi_id=str(tingkat.id),
                ambang_cukup_persen=70,
                ambang_representasi_persen=20,
            )
        )
        session.flush()

        session.add(
            AturanPemetaan(
                tingkat_seleksi_id=str(tingkat.id),
                ambang_cukup_persen=80,
                ambang_representasi_persen=30,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()

    def test_menolak_ambang_di_luar_rentang(self, session: Session) -> None:
        tingkat = _tingkat_seleksi(session)
        session.add(
            AturanPemetaan(
                tingkat_seleksi_id=str(tingkat.id),
                ambang_cukup_persen=150,
                ambang_representasi_persen=20,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


class TestSubkompetensi:
    def test_simpan_dan_baca(self, session: Session) -> None:
        kompetensi = _kompetensi(session)

        sub = Subkompetensi(kompetensi_id=kompetensi.id, nama="Graph", deskripsi=None)
        session.add(sub)
        session.flush()

        assert sub.id is not None
        assert sub.kompetensi_id == kompetensi.id


class TestSoal:
    def test_simpan_dan_baca(self, session: Session) -> None:
        tingkat = _tingkat_seleksi(session)
        kompetensi = _kompetensi(session)
        sub = Subkompetensi(kompetensi_id=kompetensi.id, nama="Graph", deskripsi=None)
        session.add(sub)
        session.flush()

        soal = Soal(
            subkompetensi_id=sub.id,
            tingkat_seleksi_id=tingkat.id,
            nomor=1,
            pertanyaan="Apa itu graph?",
            pilihan_jawaban={"A": "Struktur data", "B": "Algoritma", "C": "Bahasa", "D": "OS"},
            kunci_jawaban="A",
        )
        session.add(soal)
        session.flush()

        assert soal.id is not None
        assert soal.pilihan_jawaban["A"] == "Struktur data"

    def test_nomor_unik_per_tingkat_seleksi(self, session: Session) -> None:
        tingkat = _tingkat_seleksi(session)
        kompetensi = _kompetensi(session)
        sub = Subkompetensi(kompetensi_id=kompetensi.id, nama="Graph", deskripsi=None)
        session.add(sub)
        session.flush()

        def _soal(nomor: int) -> Soal:
            return Soal(
                subkompetensi_id=sub.id,
                tingkat_seleksi_id=tingkat.id,
                nomor=nomor,
                pertanyaan="Q",
                pilihan_jawaban={"A": "x", "B": "y"},
                kunci_jawaban="A",
            )

        session.add(_soal(1))
        session.flush()
        session.add(_soal(1))

        with pytest.raises(IntegrityError):
            session.flush()
