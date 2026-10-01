"""Formula skor & predikat murni — versi revisi aturan final v1.

Perubahan dari versi lama:
- hitung_skor menerima bobot_benar & bobot_total (bukan jumlah_benar & total_soal).
- Tambah bobot_dari_level(): konversi LevelSoal → bobot (Mudah=1, Sedang=2, Sulit=3).
- tentukan_predikat & cocokkan_jawaban tidak berubah.
"""

from collections.abc import Sequence
import re
from fractions import Fraction

from data_analytics.models import LevelSoal, TipeSoal


# --- Bobot Level Soal ---------------------------------------------------------

BOBOT_LEVEL: dict[LevelSoal, int] = {
    LevelSoal.MUDAH: 1,
    LevelSoal.MENENGAH: 2,
    LevelSoal.SULIT: 3,
}


def bobot_dari_level(level: LevelSoal) -> int:
    """Konversi LevelSoal ke bobot: Mudah=1, Sedang=2, Sulit=3.

    Kalau level tidak dikenali, default 1 (Mudah) — defensif.
    """
    return BOBOT_LEVEL.get(level, 1)


# --- Skor ---------------------------------------------------------------------

def hitung_skor(*, bobot_benar: float, bobot_total: float) -> float:
    """Nilai = (Σ bobot×benar / Σ bobot) × 100, dibulatkan dua desimal.

    Pemanggil bertanggung jawab menghitung bobot_benar (jumlah bobot soal
    yang dijawab benar) dan bobot_total (jumlah bobot semua soal).
    Soal tidak dijawab dihitung salah → tidak menyumbang ke bobot_benar.
    """
    if bobot_total <= 0:
        raise ValueError("bobot_total harus lebih dari 0")
    if bobot_benar < 0:
        raise ValueError("bobot_benar tidak boleh negatif")
    if bobot_benar > bobot_total:
        raise ValueError("bobot_benar tidak boleh melebihi bobot_total")

    return round((bobot_benar / bobot_total) * 100, 2)


# --- Predikat -----------------------------------------------------------------

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


# --- Pencocokan Jawaban -------------------------------------------------------

def cocokkan_jawaban(kunci: str, jawaban: str | None, tipe: TipeSoal) -> bool:
    """Apakah jawaban siswa sama dengan kunci. Pilihan ganda: huruf pilihan,
    tanpa peduli kapital. Isian singkat: spasi tepi & ganda serta kapital
    diabaikan; kalau keduanya bilangan (koma desimal diterima), dibandingkan
    nilainya (1260 = 1260.0). Tidak dijawab/kosong selalu salah.
    """
    if jawaban is None or not jawaban.strip():
        return False
    if tipe is TipeSoal.PILIHAN_GANDA:
        return jawaban.strip().upper() == kunci.strip().upper()
    a, b = _normalisasi(kunci), _normalisasi(jawaban)
    angka_a, angka_b = _sebagai_bilangan(a), _sebagai_bilangan(b)
    if angka_a is not None and angka_b is not None:
        return angka_a == angka_b
    return a == b


def _normalisasi(teks: str) -> str:
    # "26, 17, 11" = "26,17,11": spasi di sekitar koma diabaikan untuk jawaban daftar.
    return re.sub(r"\s*,\s*", ",", " ".join(teks.split())).casefold()


def _sebagai_bilangan(teks: str) -> Fraction | None:
    try:
        return Fraction(teks.replace(",", "."))
    except (ValueError, ZeroDivisionError):
        return None