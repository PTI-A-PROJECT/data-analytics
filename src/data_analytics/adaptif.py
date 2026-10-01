"""Mesin soal adaptif simulasi — fungsi murni (fase 2 issue 03), pola sama
dengan paket.py/pemetaan.py. Langkah 1 (perbarui Level Soal Siswa) & langkah 2
(alokasi kuota per Materi) ada di sini; langkah 3 (pilih soal via vector
search) ada di repository.susun_paket_simulasi.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from data_analytics.models import LevelSoal

URUTAN_LEVEL: tuple[LevelSoal, ...] = (LevelSoal.MUDAH, LevelSoal.MENENGAH, LevelSoal.SULIT)


@dataclass(frozen=True, slots=True)
class LevelSoalSiswaMateri:
    """Level Soal Siswa untuk satu Materi beserta status lemahnya (lihat
    CONTEXT.md — Materi sendiri tidak punya level)."""

    level: LevelSoal
    lemah: bool
    # Persen benar di attempt terakhir; None kalau belum pernah teruji.
    akurasi: float | None


def validasi_aturan_adaptif(
    *,
    jumlah_soal_simulasi: int,
    kuota_min: int,
    bobot_lemah: int,
    ambang_naik: float,
    ambang_lemah: float,
    jumlah_materi: int,
) -> None:
    """ValueError kalau aturan_adaptif satu tingkat tidak konsisten: kuota_min
    x jumlah Materi harus muat di jumlah_soal_simulasi, 0 <= ambang_lemah <
    ambang_naik <= 100, bobot_lemah >= 1, kuota_min >= 1."""
    masalah = []
    if kuota_min < 1:
        masalah.append("kuota_min minimal 1")
    if bobot_lemah < 1:
        masalah.append("bobot_lemah minimal 1")
    if not 0 <= ambang_lemah < ambang_naik <= 100:
        masalah.append("harus 0 <= ambang_lemah < ambang_naik <= 100")
    if kuota_min * jumlah_materi > jumlah_soal_simulasi:
        masalah.append(
            f"kuota_min ({kuota_min}) x {jumlah_materi} Materi melebihi "
            f"jumlah_soal_simulasi ({jumlah_soal_simulasi})"
        )
    if masalah:
        raise ValueError("; ".join(masalah))


def perbarui_level(
    sekarang: LevelSoalSiswaMateri,
    *,
    jumlah_soal: int,
    jumlah_benar: int,
    kuota_min: int,
    ambang_naik: float,
    ambang_lemah: float,
) -> LevelSoalSiswaMateri:
    """Level Soal Siswa setelah satu attempt simulasi di Materi ini.

    akurasi >= ambang_naik → naik satu level (mentok Sulit), tidak lemah;
    ambang_lemah <= akurasi < ambang_naik → tetap, tidak lemah;
    akurasi < ambang_lemah → tetap (level TIDAK PERNAH turun), lemah.
    Materi dengan < kuota_min soal di attempt ini tidak diubah — datanya
    terlalu sedikit — dan objek `sekarang` dikembalikan apa adanya (pemanggil
    boleh memakai `is` untuk mendeteksinya).
    """
    if jumlah_benar < 0 or jumlah_benar > jumlah_soal:
        raise ValueError("jumlah_benar harus di antara 0 dan jumlah_soal")
    if jumlah_soal < kuota_min or jumlah_soal == 0:
        return sekarang

    akurasi = round(jumlah_benar / jumlah_soal * 100, 2)
    if akurasi >= ambang_naik:
        indeks = min(URUTAN_LEVEL.index(sekarang.level) + 1, len(URUTAN_LEVEL) - 1)
        return LevelSoalSiswaMateri(level=URUTAN_LEVEL[indeks], lemah=False, akurasi=akurasi)
    return LevelSoalSiswaMateri(level=sekarang.level, lemah=akurasi < ambang_lemah, akurasi=akurasi)


def bagi_proporsional(jumlah: int, bobot: Mapping[str, int]) -> dict[str, int]:
    """Bagi `jumlah` proporsional terhadap bobot dengan metode largest
    remainder — total selalu tepat `jumlah`. Sisa pembulatan seri jatuh ke
    id terkecil."""
    if jumlah < 0:
        raise ValueError("jumlah tidak boleh negatif")
    ids = sorted(bobot)
    total_bobot = sum(bobot[i] for i in ids)
    if not ids or total_bobot <= 0:
        raise ValueError("bobot harus punya total positif")
    # Fraction: pembagian eksak, tanpa galat float saat membandingkan sisa.
    bagian = {i: Fraction(jumlah * bobot[i], total_bobot) for i in ids}
    hasil = {i: int(bagian[i]) for i in ids}
    sisa = jumlah - sum(hasil.values())
    for i in sorted(ids, key=lambda i: (-(bagian[i] - hasil[i]), i))[:sisa]:
        hasil[i] += 1
    return hasil


def bobot_materi(lemah_per_materi: Mapping[str, bool], *, bobot_lemah: int) -> dict[str, int]:
    """Bobot pembagian sisa kuota: Materi lemah bobot_lemah, lainnya 1."""
    return {m: bobot_lemah if lemah else 1 for m, lemah in lemah_per_materi.items()}


def alokasi_kuota(
    jumlah_soal: int, lemah_per_materi: Mapping[str, bool], *, kuota_min: int, bobot_lemah: int
) -> dict[str, int]:
    """Kuota soal simulasi per Materi (total tepat jumlah_soal). Setiap Materi
    mendapat kuota_min — semua Materi selalu tercakup — lalu sisanya dibagi
    proporsional: Materi lemah berbobot bobot_lemah, lainnya 1.
    """
    if kuota_min * len(lemah_per_materi) > jumlah_soal:
        raise ValueError(
            f"kuota_min ({kuota_min}) x {len(lemah_per_materi)} Materi melebihi "
            f"jumlah_soal ({jumlah_soal})"
        )
    if not lemah_per_materi:
        return {}
    sisa = jumlah_soal - kuota_min * len(lemah_per_materi)
    tambahan = bagi_proporsional(sisa, bobot_materi(lemah_per_materi, bobot_lemah=bobot_lemah))
    return {m: kuota_min + tambahan[m] for m in sorted(lemah_per_materi)}


def urutan_level_fallback(target: LevelSoal) -> list[LevelSoal]:
    """Level dari yang terdekat ke target (target sendiri pertama); jarak
    sama → yang lebih mudah dulu. Menengah → [Menengah, Mudah, Sulit]."""
    posisi = URUTAN_LEVEL.index(target)
    return sorted(
        URUTAN_LEVEL,
        key=lambda level: (abs(URUTAN_LEVEL.index(level) - posisi), URUTAN_LEVEL.index(level)),
    )


def gabung_bergiliran(daftar_per_acuan: Sequence[Sequence[str]], jumlah: int) -> list[str]:
    """Ambil `jumlah` id secara round-robin: tiap soal acuan bergiliran
    menyumbang tetangga terdekatnya yang belum terambil. Setiap daftar sudah
    terurut dari yang paling mirip."""
    terambil: list[str] = []
    sudah: set[str] = set()
    posisi = [0] * len(daftar_per_acuan)
    ada_sisa = True
    while len(terambil) < jumlah and ada_sisa:
        ada_sisa = False
        for i, daftar in enumerate(daftar_per_acuan):
            if len(terambil) == jumlah:
                break
            while posisi[i] < len(daftar) and daftar[posisi[i]] in sudah:
                posisi[i] += 1
            if posisi[i] < len(daftar):
                terambil.append(daftar[posisi[i]])
                sudah.add(daftar[posisi[i]])
                posisi[i] += 1
                ada_sisa = True
    return terambil
