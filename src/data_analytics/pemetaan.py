"""Algoritma Pemetaan Kompetensi fase 2 (per Materi) — lihat CONTEXT.md
"Status Pemetaan (fase 2)". Fungsi murni, terpisah dari database — pola yang
sama dengan scoring.py. Pemetaan fase 1 per Subkompetensi (Aturan Pemetaan,
ambang representasi, butuh_optimasi) dipensiunkan di fase 2 issue 03.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from data_analytics.models import StatusPemetaan


@dataclass(frozen=True, slots=True)
class PetaMateri:
    """Status Pemetaan satu Materi dalam satu attempt (fase 2)."""

    materi_id: str
    jumlah_soal: int
    jumlah_benar: int
    # Persen benar, None kalau Materi tidak muncul di attempt ini.
    akurasi: float | None
    status: StatusPemetaan


def status_dari_akurasi(
    akurasi: float, *, ambang_lemah: float, ambang_kuat: float
) -> StatusPemetaan:
    """< ambang_lemah → BELUM_CUKUP (Lemah); ambang_lemah..<ambang_kuat → CUKUP;
    >= ambang_kuat → KUAT. Batas bawah inklusif."""
    if akurasi < ambang_lemah:
        return StatusPemetaan.BELUM_CUKUP
    if akurasi < ambang_kuat:
        return StatusPemetaan.CUKUP
    return StatusPemetaan.KUAT


def petakan_per_materi(
    hitungan: Mapping[str, tuple[int, int]],
    *,
    ambang_lemah: float,
    ambang_kuat: float = 80.0,
) -> list[PetaMateri]:
    """Peta Kompetensi fase 2.

    3 status (sesuai aturan final v1):
    - BELUM_TERUJI: materi tidak muncul di attempt ini
    - BELUM_CUKUP:  akurasi < ambang_lemah (default 60%)
    - CUKUP:        ambang_lemah <= akurasi < ambang_kuat
    - KUAT:         akurasi >= ambang_kuat (default 80%)
    """
    peta = []
    for materi_id in sorted(hitungan):
        jumlah_soal, jumlah_benar = hitungan[materi_id]
        if jumlah_benar < 0 or jumlah_benar > jumlah_soal:
            raise ValueError(f"jumlah_benar Materi {materi_id} di luar 0..jumlah_soal")

        if jumlah_soal == 0:
            akurasi = None
            status = StatusPemetaan.BELUM_TERUJI
        else:
            akurasi = round(jumlah_benar / jumlah_soal * 100, 2)
            status = status_dari_akurasi(
                akurasi, ambang_lemah=ambang_lemah, ambang_kuat=ambang_kuat
            )

        peta.append(PetaMateri(materi_id, jumlah_soal, jumlah_benar, akurasi, status))
    return peta

def materi_lemah(peta: Sequence[PetaMateri]) -> list[str]:
    """Materi berstatus Belum Cukup, dari akurasi terendah (seri: materi_id)."""
    lemah = [p for p in peta if p.status is StatusPemetaan.BELUM_CUKUP]
    return [p.materi_id for p in sorted(lemah, key=lambda p: (p.akurasi, p.materi_id))]
