"""Algoritma Pemetaan Kompetensi (FR-07) & flag butuh_optimasi (tiket 05) —
lihat CONTEXT.md "Status Pemetaan"/"Aturan Pemetaan" dan resolusi tiket 11.
Fungsi murni, terpisah dari database — pola yang sama dengan scoring.py.
"""

from typing import Final

from data_analytics.models import StatusPemetaan

# >50% (ketat) jawaban benar yang juga lambat -> butuh_optimasi (resolusi tiket 05).
AMBANG_BUTUH_OPTIMASI_PERSEN: Final = 50


def tentukan_status_pemetaan(
    *,
    jumlah_soal_subkompetensi: int,
    jumlah_benar: int,
    total_soal_tes: int,
    ambang_cukup_persen: float,
    ambang_representasi_persen: float,
) -> StatusPemetaan:
    """Belum Teruji kalau representasi soal subkompetensi ini (terhadap total
    soal tes) di bawah ambang representasi — representasinya dianggap terlalu
    kecil untuk klasifikasi valid. Selain itu, Cukup kalau % jawaban benar >=
    ambang cukup, else Belum Cukup. Kedua ambang inklusif.
    """
    if total_soal_tes <= 0:
        raise ValueError("total_soal_tes harus lebih dari 0")
    if jumlah_soal_subkompetensi <= 0:
        raise ValueError("jumlah_soal_subkompetensi harus lebih dari 0")
    if jumlah_benar < 0 or jumlah_benar > jumlah_soal_subkompetensi:
        raise ValueError(
            "jumlah_benar harus di antara 0 dan jumlah_soal_subkompetensi"
        )

    representasi_persen = (jumlah_soal_subkompetensi / total_soal_tes) * 100
    if representasi_persen < ambang_representasi_persen:
        return StatusPemetaan.BELUM_TERUJI

    correctness_persen = (jumlah_benar / jumlah_soal_subkompetensi) * 100
    if correctness_persen >= ambang_cukup_persen:
        return StatusPemetaan.CUKUP
    return StatusPemetaan.BELUM_CUKUP


def tentukan_butuh_optimasi(
    *, status: StatusPemetaan, jumlah_benar: int, jumlah_benar_lambat: int
) -> bool:
    """True hanya kalau status Cukup DAN >50% jawaban benar di subkompetensi
    ini juga lambat. "Butuh optimasi kecepatan" tidak relevan kalau
    pemahamannya sendiri belum cukup (Belum Cukup/Belum Teruji selalu False).
    """
    if jumlah_benar_lambat < 0 or jumlah_benar_lambat > jumlah_benar:
        raise ValueError(
            "jumlah_benar_lambat harus di antara 0 dan jumlah_benar"
        )
    if status is not StatusPemetaan.CUKUP or jumlah_benar == 0:
        return False
    return (jumlah_benar_lambat / jumlah_benar) * 100 > AMBANG_BUTUH_OPTIMASI_PERSEN
