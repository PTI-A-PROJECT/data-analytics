"""Penilaian stateless untuk endpoint /hitung/* — fungsi murni, tanpa database.

Laravel mengirim kunci, jawaban, level, dan materi tiap soal; modul ini
mengembalikan skor berbobot (Mudah=1, Sedang=2, Sulit=3), predikat (opsional),
dan Peta Kompetensi per Materi. Semua rumus dipakai ulang dari scoring.py dan
pemetaan.py agar satu sumber kebenaran.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from data_analytics.models import LevelSoal, TipeSoal
from data_analytics.pemetaan import PetaMateri, materi_lemah, petakan_per_materi
from data_analytics.scoring import (
    bobot_dari_level,
    cocokkan_jawaban,
    hitung_skor,
    tentukan_predikat,
)


@dataclass(frozen=True, slots=True)
class SoalDijawab:
    soal_id: str
    level: LevelSoal
    tipe: TipeSoal
    kunci: str
    jawaban: str | None
    materi_id: str | None = None


@dataclass(frozen=True, slots=True)
class HasilSoal:
    soal_id: str
    benar: bool
    bobot: int


@dataclass(frozen=True, slots=True)
class HasilPenilaian:
    skor: float
    bobot_benar: int
    bobot_total: int
    jumlah_soal: int
    jumlah_benar: int
    jumlah_salah: int
    predikat: str | None
    hasil_soal: list[HasilSoal]


def nilai_jawaban(
    soal: Sequence[SoalDijawab],
    *,
    aturan_predikat: Sequence[tuple[str, float]] | None = None,
) -> HasilPenilaian:
    """Skor = Σ bobot soal benar / Σ bobot semua soal × 100. Soal tanpa
    jawaban dihitung salah. Predikat hanya dihitung kalau aturan dikirim."""
    if not soal:
        raise ValueError("daftar soal tidak boleh kosong")
    ids = [s.soal_id for s in soal]
    if len(set(ids)) != len(ids):
        raise ValueError("soal_id harus unik")

    hasil_soal = []
    for s in soal:
        benar = cocokkan_jawaban(s.kunci, s.jawaban, s.tipe)
        hasil_soal.append(HasilSoal(s.soal_id, benar, bobot_dari_level(s.level)))

    bobot_benar = sum(h.bobot for h in hasil_soal if h.benar)
    bobot_total = sum(h.bobot for h in hasil_soal)
    jumlah_benar = sum(1 for h in hasil_soal if h.benar)
    skor = hitung_skor(bobot_benar=bobot_benar, bobot_total=bobot_total)
    predikat = tentukan_predikat(skor, aturan_predikat) if aturan_predikat else None

    return HasilPenilaian(
        skor=skor,
        bobot_benar=bobot_benar,
        bobot_total=bobot_total,
        jumlah_soal=len(soal),
        jumlah_benar=jumlah_benar,
        jumlah_salah=len(soal) - jumlah_benar,
        predikat=predikat,
        hasil_soal=hasil_soal,
    )


def hitung_pemetaan(
    soal: Sequence[SoalDijawab],
    *,
    ambang_lemah: float,
    ambang_kuat: float,
) -> tuple[list[PetaMateri], list[str]]:
    """Peta Kompetensi per Materi (akurasi berbasis jumlah soal, bukan bobot —
    sama dengan pemetaan.petakan_per_materi) dan daftar Materi lemah."""
    if ambang_lemah > ambang_kuat:
        raise ValueError("ambang_lemah tidak boleh melebihi ambang_kuat")
    if any(s.materi_id is None for s in soal):
        raise ValueError("materi_id wajib diisi untuk setiap soal pada /hitung/pretest")

    hitungan: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for s in soal:
        hitungan[s.materi_id][0] += 1  # type: ignore[index]
        if cocokkan_jawaban(s.kunci, s.jawaban, s.tipe):
            hitungan[s.materi_id][1] += 1  # type: ignore[index]

    peta = petakan_per_materi(
        {m: (n, b) for m, (n, b) in hitungan.items()},
        ambang_lemah=ambang_lemah,
        ambang_kuat=ambang_kuat,
    )
    return peta, materi_lemah(peta)
