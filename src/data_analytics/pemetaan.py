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


def petakan_per_materi(
    hitungan: Mapping[str, tuple[int, int]], *, ambang_lemah: float
) -> list[PetaMateri]:
    """Peta Kompetensi fase 2 dari (jumlah_soal, jumlah_benar) per Materi.
    Satu definisi lemah (issue fase 2 #03): Belum Cukup ≡ akurasi <
    ambang_lemah; Cukup kalau >= (inklusif); Belum Teruji kalau Materi tidak
    punya soal di attempt ini. Terurut menurut materi_id.
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
            status = (
                StatusPemetaan.BELUM_CUKUP if akurasi < ambang_lemah else StatusPemetaan.CUKUP
            )
        peta.append(PetaMateri(materi_id, jumlah_soal, jumlah_benar, akurasi, status))
    return peta


def materi_lemah(peta: Sequence[PetaMateri]) -> list[str]:
    """Materi berstatus Belum Cukup, dari akurasi terendah (seri: materi_id)."""
    lemah = [p for p in peta if p.status is StatusPemetaan.BELUM_CUKUP]
    return [p.materi_id for p in sorted(lemah, key=lambda p: (p.akurasi, p.materi_id))]
