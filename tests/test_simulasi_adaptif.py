"""Mesin soal adaptif simulasi di Postgres + pgvector (fase 2 issue 03).

Embedding sintetis: vektor satuan di bidang dua dimensi pertama (sisanya nol),
sehingga jarak cosine antarsoal ditentukan sudutnya saja.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import (
    DIMENSI_EMBEDDING,
    AlasanPilihSoal,
    AturanAdaptif,
    LevelSoal,
    Materi,
    PaketTes,
    PaketTesSoal,
    Soal,
    TingkatSeleksi,
)
from data_analytics.repository import (
    JawabanPaket,
    submit_paket,
    susun_paket_pretest,
    susun_paket_simulasi,
)

MUDAH, SEDANG, SULIT = LevelSoal.MUDAH, LevelSoal.SEDANG, LevelSoal.SULIT
SISWA = "siswa-1"


def _embedding(sudut: float) -> list[float]:
    vektor = [0.0] * DIMENSI_EMBEDDING
    vektor[0] = math.cos(math.radians(sudut))
    vektor[1] = math.sin(math.radians(sudut))
    return vektor


@dataclass
class Bank:
    session: Session
    tingkat: TingkatSeleksi

    def soal(self, id_: str, materi_id: str, level: LevelSoal, sudut: float = 0.0) -> None:
        self.session.add(
            Soal(
                id=id_,
                materi_id=materi_id,
                tingkat_seleksi_id=self.tingkat.id,
                pertanyaan=f"Pertanyaan {id_}",
                pilihan_jawaban={"A": "benar", "B": "salah"},
                kunci_jawaban="A",
                pembahasan=None,
                level=level,
                embedding=_embedding(sudut),
                hash_konten="h",
            )
        )
        self.session.flush()


@pytest.fixture
def bank(session: Session) -> Bank:
    """Kabupaten dengan Materi ma & mb, tanpa soal. Pre-test 4 soal (2 per
    Materi), simulasi 4 soal dengan kuota_min 2 → 2 per Materi."""
    tingkat = TingkatSeleksi(nama="Kabupaten", urutan=1)
    session.add(tingkat)
    session.flush()
    for materi_id in ("ma", "mb"):
        session.add(
            Materi(
                id=materi_id,
                tingkat_seleksi_id=tingkat.id,
                judul=f"Materi {materi_id}",
                embedding=_embedding(0),
                hash_konten="h",
            )
        )
    session.add(
        AturanAdaptif(
            tingkat_seleksi_id=tingkat.id,
            jumlah_soal_pretest=4,
            ambang_lemah=50,
            jumlah_soal_simulasi=4,
            kuota_min=2,
            bobot_lemah=3,
            ambang_naik=80,
        )
    )
    session.flush()
    return Bank(session=session, tingkat=tingkat)


def _kerjakan(session: Session, paket: PaketTes, salah: Iterable[str] = ()) -> None:
    """Submit paket: semua benar kecuali soal milik Materi di `salah`."""
    salah = set(salah)
    submit_paket(
        session,
        paket_id=paket.id,
        jawaban=[
            JawabanPaket(soal_id=b.soal_id, jawaban_dipilih="B" if b.materi_id in salah else "A")
            for b in paket.soal
        ],
        diselesaikan_pada=datetime.now(timezone.utc),
    )


def _pretest(bank: Bank, salah: Iterable[str] = ()) -> PaketTes:
    paket = susun_paket_pretest(bank.session, siswa_id=SISWA, tingkat_seleksi_id=bank.tingkat.id)
    _kerjakan(bank.session, paket, salah)
    return paket


def _simulasi(bank: Bank) -> PaketTes:
    return susun_paket_simulasi(
        bank.session, siswa_id=SISWA, tingkat_seleksi_id=bank.tingkat.id, seed=7
    )


def _soal_materi(paket: PaketTes, materi_id: str) -> list[PaketTesSoal]:
    return [b for b in paket.soal if b.materi_id == materi_id]


def _id_aturan(bank: Bank) -> int:
    return bank.session.scalars(
        select(AturanAdaptif.id).where(AturanAdaptif.tingkat_seleksi_id == bank.tingkat.id)
    ).one()


def _isi_pretest(bank: Bank) -> None:
    """Stok Mudah tepat 2 per Materi → pre-test memakai semuanya."""
    for materi_id in ("ma", "mb"):
        bank.soal(f"{materi_id}-p1", materi_id, MUDAH, 0)
        bank.soal(f"{materi_id}-p2", materi_id, MUDAH, 90)


class TestSimulasiPertama:
    def test_semua_soal_mudah_dan_kuota_min_per_materi(self, bank: Bank) -> None:
        _isi_pretest(bank)
        _pretest(bank)
        for materi_id in ("ma", "mb"):
            for nomor in range(3):
                bank.soal(f"{materi_id}-m{nomor}", materi_id, MUDAH)
                bank.soal(f"{materi_id}-s{nomor}", materi_id, SULIT)

        paket = _simulasi(bank)

        assert len(paket.soal) == 4
        assert sorted(b.urutan for b in paket.soal) == [1, 2, 3, 4]
        assert {(b.level_target, b.level_aktual, b.alasan) for b in paket.soal} == {
            (MUDAH, MUDAH, AlasanPilihSoal.ACAK)
        }
        assert len(_soal_materi(paket, "ma")) == len(_soal_materi(paket, "mb")) == 2
        assert paket.seed == 7


class TestMateriLemah:
    def test_memilih_tetangga_terdekat_soal_yang_dijawab_salah(self, bank: Bank) -> None:
        _isi_pretest(bank)  # acuan ma: ma-p1 (0°) & ma-p2 (90°)
        _pretest(bank, salah={"ma"})
        bank.soal("ma-5", "ma", MUDAH, 5)
        bank.soal("ma-85", "ma", MUDAH, 85)
        bank.soal("ma-45", "ma", MUDAH, 45)
        bank.soal("ma-180", "ma", MUDAH, 180)
        bank.soal("mb-x", "mb", MUDAH)
        bank.soal("mb-y", "mb", MUDAH)

        paket = _simulasi(bank)

        assert {(b.soal_id, b.alasan) for b in _soal_materi(paket, "ma")} == {
            ("ma-5", AlasanPilihSoal.VEKTOR_MIRIP),
            ("ma-85", AlasanPilihSoal.VEKTOR_MIRIP),
        }

    def test_materi_lemah_mendapat_porsi_lebih_besar(self, bank: Bank) -> None:
        aturan = bank.session.get(AturanAdaptif, _id_aturan(bank))
        assert aturan is not None
        aturan.jumlah_soal_simulasi = 8  # sisa 4 dibagi 3:1 → ma 5, mb 3
        _isi_pretest(bank)
        _pretest(bank, salah={"ma"})
        for nomor in range(6):
            bank.soal(f"ma-{nomor}", "ma", MUDAH, nomor * 30)
            bank.soal(f"mb-{nomor}", "mb", MUDAH)

        paket = _simulasi(bank)

        assert len(_soal_materi(paket, "ma")) == 5
        assert len(_soal_materi(paket, "mb")) == 3


class TestSoalTidakTerulang:
    def test_soal_pretest_dan_simulasi_sebelumnya_tidak_muncul_lagi(self, bank: Bank) -> None:
        _isi_pretest(bank)
        pretest = _pretest(bank, salah={"ma"})
        for nomor in range(4):
            bank.soal(f"ma-{nomor}", "ma", MUDAH, nomor)
            bank.soal(f"mb-{nomor}", "mb", MUDAH)
        pertama = _simulasi(bank)
        _kerjakan(bank.session, pertama, salah={"ma"})

        kedua = _simulasi(bank)

        sebelumnya = {b.soal_id for b in [*pretest.soal, *pertama.soal]}
        assert not sebelumnya & {b.soal_id for b in kedua.soal}
        assert len(kedua.soal) == 4


def _isi_semua_level(bank: Bank, jumlah: int = 8) -> None:
    for materi_id in ("ma", "mb"):
        for level in (MUDAH, SEDANG, SULIT):
            for nomor in range(jumlah):
                bank.soal(f"{materi_id}-{level}-{nomor}", materi_id, level, nomor * 10)


def _level_target(paket: PaketTes, materi_id: str) -> LevelSoal:
    (level,) = {b.level_target for b in _soal_materi(paket, materi_id)}
    return level


class TestPerbaruiLevelSaatSubmit:
    def test_performa_bagus_berulang_menaikkan_level_hingga_sulit(self, bank: Bank) -> None:
        _isi_pretest(bank)
        _pretest(bank)
        _isi_semua_level(bank)

        level_per_simulasi = []
        for _ in range(4):
            paket = _simulasi(bank)
            level_per_simulasi.append(_level_target(paket, "ma"))
            assert {b.level_aktual for b in paket.soal} == {level_per_simulasi[-1]}
            _kerjakan(bank.session, paket)

        assert level_per_simulasi == [MUDAH, SEDANG, SULIT, SULIT]

    def test_materi_lemah_level_tidak_turun_dan_hasil_submit_mencatat_perubahan(
        self, bank: Bank
    ) -> None:
        _isi_pretest(bank)
        _pretest(bank)
        _isi_semua_level(bank)
        _kerjakan(bank.session, _simulasi(bank))  # semua benar → Sedang
        paket = _simulasi(bank)

        hasil = submit_paket(
            bank.session,
            paket_id=paket.id,
            jawaban=[
                JawabanPaket(b.soal_id, "B" if b.materi_id == "ma" else "A") for b in paket.soal
            ],
            diselesaikan_pada=datetime.now(timezone.utc),
        )

        assert [
            (p.materi_id, p.level_sebelum, p.level_sesudah, p.lemah, p.akurasi)
            for p in hasil.perubahan_level
        ] == [
            ("ma", SEDANG, SEDANG, True, 0.0),
            ("mb", SEDANG, SULIT, False, 100.0),
        ]
        assert _level_target(_simulasi(bank), "ma") == SEDANG


class TestFallbackStokHabis:
    def _siap_simulasi(self, bank: Bank, salah: Iterable[str] = ()) -> None:
        """Pre-test memakai semua soal Mudah; mb diberi stok Mudah cukup."""
        _isi_pretest(bank)
        _pretest(bank, salah=salah)
        for nomor in range(4):
            bank.soal(f"mb-{nomor}", "mb", MUDAH)

    def test_level_terdekat_dipakai_saat_level_target_habis(self, bank: Bank) -> None:
        self._siap_simulasi(bank)
        bank.soal("ma-sulit", "ma", SULIT)
        bank.soal("ma-sedang-1", "ma", SEDANG)
        bank.soal("ma-sedang-2", "ma", SEDANG)

        paket = _simulasi(bank)

        assert {
            (b.soal_id, b.level_target, b.level_aktual, b.alasan) for b in _soal_materi(paket, "ma")
        } == {
            ("ma-sedang-1", MUDAH, SEDANG, AlasanPilihSoal.FALLBACK_LEVEL),
            ("ma-sedang-2", MUDAH, SEDANG, AlasanPilihSoal.FALLBACK_LEVEL),
        }

    def test_jarak_level_sama_yang_lebih_mudah_dulu(self, bank: Bank) -> None:
        _isi_pretest(bank)
        _pretest(bank)
        for materi_id in ("ma", "mb"):
            for nomor in range(2):
                bank.soal(f"{materi_id}-mudah-{nomor}", materi_id, MUDAH)
        _kerjakan(bank.session, _simulasi(bank))  # semua benar → Sedang
        for nomor in range(2):
            bank.soal(f"ma-mudah-baru-{nomor}", "ma", MUDAH)
            bank.soal(f"ma-sulit-{nomor}", "ma", SULIT)
            bank.soal(f"mb-sedang-{nomor}", "mb", SEDANG)

        paket = _simulasi(bank)

        assert {(b.level_target, b.level_aktual) for b in _soal_materi(paket, "ma")} == {
            (SEDANG, MUDAH)
        }

    def test_materi_lemah_level_terdekat_tetap_lewat_vector_search(self, bank: Bank) -> None:
        self._siap_simulasi(bank, salah={"ma"})  # acuan ma: 0° & 90°
        bank.soal("ma-sedang-5", "ma", SEDANG, 5)
        bank.soal("ma-sedang-85", "ma", SEDANG, 85)
        bank.soal("ma-sedang-200", "ma", SEDANG, 200)

        paket = _simulasi(bank)

        assert {(b.soal_id, b.alasan) for b in _soal_materi(paket, "ma")} == {
            ("ma-sedang-5", AlasanPilihSoal.FALLBACK_LEVEL),
            ("ma-sedang-85", AlasanPilihSoal.FALLBACK_LEVEL),
        }

    def test_soal_lama_diulang_yang_paling_lama_tidak_muncul_dulu(self, bank: Bank) -> None:
        self._siap_simulasi(bank)
        bank.soal("ma-baru-1", "ma", MUDAH)
        bank.soal("ma-baru-2", "ma", MUDAH)
        _kerjakan(bank.session, _simulasi(bank), salah={"ma", "mb"})  # level tetap Mudah

        paket = _simulasi(bank)

        # ma-p1/ma-p2 muncul di pre-test, ma-baru-* di simulasi pertama.
        assert {(b.soal_id, b.alasan) for b in _soal_materi(paket, "ma")} == {
            ("ma-p1", AlasanPilihSoal.FALLBACK_ULANG),
            ("ma-p2", AlasanPilihSoal.FALLBACK_ULANG),
        }

    def test_sisa_kuota_dialihkan_ke_materi_lain(self, bank: Bank) -> None:
        bank.soal("ma-satu", "ma", MUDAH)
        for nomor in range(8):
            bank.soal(f"mb-{nomor}", "mb", MUDAH)
        _pretest(bank)  # ma 1 soal, mb 3 soal

        paket = _simulasi(bank)

        assert [b.soal_id for b in _soal_materi(paket, "ma")] == ["ma-satu"]
        assert len(_soal_materi(paket, "mb")) == 3
        assert len(paket.soal) == 4


class TestSeed:
    def test_seed_sama_dan_bank_sama_menghasilkan_paket_sama(self, bank: Bank) -> None:
        _isi_pretest(bank)
        _pretest(bank, salah={"ma"})
        _isi_semua_level(bank)
        pertama = _simulasi(bank)
        susunan = [(b.urutan, b.soal_id, b.alasan) for b in pertama.soal]
        bank.session.delete(pertama)
        bank.session.flush()

        ulang = _simulasi(bank)

        assert [(b.urutan, b.soal_id, b.alasan) for b in ulang.soal] == susunan


class TestKonfigurasiTidakMuat:
    def test_paket_diperbesar_supaya_setiap_materi_tetap_mendapat_kuota_min(
        self, bank: Bank
    ) -> None:
        aturan = bank.session.get(AturanAdaptif, _id_aturan(bank))
        assert aturan is not None
        aturan.jumlah_soal_simulasi = 3  # < kuota_min 2 x 2 Materi
        _isi_pretest(bank)
        _pretest(bank)
        _isi_semua_level(bank)

        paket = _simulasi(bank)

        assert len(_soal_materi(paket, "ma")) == len(_soal_materi(paket, "mb")) == 2
        assert paket.jumlah_soal_diminta == 4


class TestSoalAcuan:
    def test_materi_lemah_tanpa_jawaban_salah_di_attempt_terakhir_memakai_attempt_sebelumnya(
        self, bank: Bank
    ) -> None:
        bank.soal("ma-1", "ma", MUDAH, 0)  # stok ma hanya 1 soal
        for nomor in range(8):
            bank.soal(f"mb-{nomor}", "mb", MUDAH)
        _pretest(bank, salah={"ma"})  # ma-1 salah → ma lemah
        # ma tampil 1 soal (< kuota_min) dan dijawab benar → lemah tidak diubah.
        _kerjakan(bank.session, _simulasi(bank))
        bank.soal("ma-dekat", "ma", MUDAH, 10)

        paket = _simulasi(bank)

        assert ("ma-dekat", AlasanPilihSoal.VEKTOR_MIRIP) in {
            (b.soal_id, b.alasan) for b in _soal_materi(paket, "ma")
        }


class TestSoalNonaktif:
    def test_soal_nonaktif_tidak_pernah_dipilih_termasuk_lewat_fallback(self, bank: Bank) -> None:
        _isi_pretest(bank)
        _pretest(bank)
        for nomor in range(3):
            bank.soal(f"ma-mati-{nomor}", "ma", MUDAH)
            bank.soal(f"mb-{nomor}", "mb", MUDAH)
        bank.soal("ma-hidup", "ma", SEDANG)
        for soal in bank.session.scalars(select(Soal).where(Soal.id.like("ma-mati-%"))):
            soal.aktif = False
        bank.session.flush()

        paket = _simulasi(bank)

        dipilih = {b.soal_id for b in _soal_materi(paket, "ma")}
        assert not any(s.startswith("ma-mati") for s in dipilih)
        assert "ma-hidup" in dipilih
