"""Algoritma Evaluasi Kenaikan Tingkat (FR-17, tiket 03) — fungsi murni,
pola sama dengan pemetaan.py/scoring.py.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HasilEvaluasiKenaikan:
    hasil_evaluasi: str  # "lulus" | "tidak_lulus"
    syarat_skor_lulus: bool
    syarat_kompetensi_lulus: bool
    persentase_cukup_aktual: float


def evaluasi_syarat_kenaikan(
    *,
    skor: float,
    skor_simulasi_min: float,
    jumlah_kompetensi_cukup: int,
    total_kompetensi_silabus: int,
    persentase_kompetensi_cukup_min: float,
) -> HasilEvaluasiKenaikan:
    """Lulus kalau DUA syarat terpenuhi (resolusi tiket 03): skor simulasi >=
    ambang minimum, DAN persentase Kompetensi berstatus Cukup (dihitung
    terhadap total silabus Kompetensi tingkat asal) >= ambang minimum. Kedua
    ambang inklusif.
    """
    if total_kompetensi_silabus <= 0:
        raise ValueError("total_kompetensi_silabus harus lebih dari 0")
    if jumlah_kompetensi_cukup < 0 or jumlah_kompetensi_cukup > total_kompetensi_silabus:
        raise ValueError(
            "jumlah_kompetensi_cukup harus di antara 0 dan total_kompetensi_silabus"
        )

    syarat_skor_lulus = skor >= skor_simulasi_min
    persentase_cukup_aktual = round(
        (jumlah_kompetensi_cukup / total_kompetensi_silabus) * 100, 2
    )
    syarat_kompetensi_lulus = persentase_cukup_aktual >= persentase_kompetensi_cukup_min

    lulus = syarat_skor_lulus and syarat_kompetensi_lulus
    return HasilEvaluasiKenaikan(
        hasil_evaluasi="lulus" if lulus else "tidak_lulus",
        syarat_skor_lulus=syarat_skor_lulus,
        syarat_kompetensi_lulus=syarat_kompetensi_lulus,
        persentase_cukup_aktual=persentase_cukup_aktual,
    )
