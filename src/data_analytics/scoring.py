"""Formula skor & predikat murni — lihat resolusi tiket 01 (Aturan Skor & Hasil
Simulasi) di .scratch/osn-data-analytics/issues/01-aturan-skor-hasil-simulasi.md.
"""

from collections.abc import Sequence


def hitung_skor(*, jumlah_benar: int, total_soal: int) -> float:
    """Persentase jumlah_benar/total_soal, dibulatkan dua desimal.

    Soal yang tidak dijawab sudah harus dihitung sebagai salah oleh pemanggil
    sebelum jumlah_benar/total_soal dihitung — fungsi ini tidak membedakan
    "salah" dari "tidak dijawab".
    """
    if total_soal <= 0:
        raise ValueError("total_soal harus lebih dari 0")
    if jumlah_benar < 0:
        raise ValueError("jumlah_benar tidak boleh negatif")
    if jumlah_benar > total_soal:
        raise ValueError("jumlah_benar tidak boleh melebihi total_soal")

    return round((jumlah_benar / total_soal) * 100, 2)


def tentukan_predikat(skor: float, aturan_predikat: Sequence[tuple[str, float]]) -> str:
    """Predikat = label dengan batas_bawah tertinggi yang <= skor (inklusif).

    aturan_predikat adalah pasangan (label, batas_bawah); urutan input tidak
    relevan. Aturan wajib punya predikat berambang batas_bawah=0 sebagai
    "dasar" agar setiap skor 0-100 selalu tertampung oleh satu predikat.
    """
    if not aturan_predikat:
        raise ValueError("aturan_predikat tidak boleh kosong")
    if not any(batas_bawah == 0 for _, batas_bawah in aturan_predikat):
        raise ValueError(
            "aturan_predikat harus menyertakan predikat dengan batas_bawah=0"
        )

    berlaku = [item for item in aturan_predikat if item[1] <= skor]
    label, _ = max(berlaku, key=lambda item: item[1])
    return label
