"""Evaluasi syarat membuka pre-test Provinsi (fase 2 issue 02) — fungsi murni,
pola sama dengan pemetaan.py/scoring.py. Dua jalur, cukup salah satu:
jalur cepat (skor pre-test Kabupaten) atau jalur simulasi (skor satu attempt
simulasi Kabupaten + rata-rata Level Soal Siswa).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from data_analytics.models import LevelSoal

NILAI_LEVEL: dict[LevelSoal, int] = {
    LevelSoal.MUDAH: 1,
    LevelSoal.MENENGAH: 2,
    LevelSoal.SULIT: 3,
}


def evaluasi_jalur_cepat(*, skor_pretest: float, skor_pretest_jalur_cepat: float) -> bool:
    """Lulus kalau skor pre-test >= ambang jalur cepat (inklusif)."""
    return skor_pretest >= skor_pretest_jalur_cepat


@dataclass(frozen=True, slots=True)
class HasilEvaluasiJalurSimulasi:
    lulus: bool
    syarat_skor_lulus: bool
    syarat_level_lulus: bool
    rata_level_aktual: float


def evaluasi_jalur_simulasi(
    *,
    skor_simulasi: float,
    skor_simulasi_min: float,
    level_per_materi: Sequence[LevelSoal],
    rata_level_min: float,
) -> HasilEvaluasiJalurSimulasi:
    """Lulus kalau DALAM SATU attempt simulasi: skor >= skor_simulasi_min DAN
    rata-rata Level Soal Siswa atas SEMUA Materi tingkat itu (Mudah=1,
    Menengah=2, Sulit=3, level setelah diperbarui simulasi tsb.) >=
    rata_level_min. Kedua ambang inklusif.
    """
    if not level_per_materi:
        raise ValueError("level_per_materi tidak boleh kosong")

    rata_level_aktual = round(
        sum(NILAI_LEVEL[level] for level in level_per_materi) / len(level_per_materi), 2
    )
    syarat_skor_lulus = skor_simulasi >= skor_simulasi_min
    syarat_level_lulus = rata_level_aktual >= rata_level_min
    return HasilEvaluasiJalurSimulasi(
        lulus=syarat_skor_lulus and syarat_level_lulus,
        syarat_skor_lulus=syarat_skor_lulus,
        syarat_level_lulus=syarat_level_lulus,
        rata_level_aktual=rata_level_aktual,
    )
