"""Kalkulasi dan evaluasi murni kelulusan Pre-Test berjenjang (tiket 15).
Lihat .scratch/osn-data-analytics/issues/15-aturan-kelulusan-dan-akses-pre-test.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HasilEvaluasiPreTest:
    hasil_evaluasi: str  # "lulus" | "tidak_lulus"
    lulus: bool
    skor_aktual: float
    passing_grade: float


def evaluasi_kelulusan_pre_test(
    *,
    skor: float,
    passing_grade: float,
) -> HasilEvaluasiPreTest:
    """Evaluasi apakah skor Pre-Test siswa mencapai batas minimal kelulusan (passing grade).

    Lulus jika skor >= passing_grade (inklusif).
    """
    if not (0 <= skor <= 100):
        raise ValueError(f"skor harus di antara 0 dan 100, dapat {skor}")
    if not (0 <= passing_grade <= 100):
        raise ValueError(f"passing_grade harus di antara 0 dan 100, dapat {passing_grade}")

    lulus = skor >= passing_grade
    return HasilEvaluasiPreTest(
        hasil_evaluasi="lulus" if lulus else "tidak_lulus",
        lulus=lulus,
        skor_aktual=round(skor, 2),
        passing_grade=round(passing_grade, 2),
    )

