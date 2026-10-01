"""Penyusunan Paket Tes — fungsi murni (fase 2 issue 02), pola sama dengan
scoring.py/pemetaan.py. Query & penyimpanan ada di repository.py.
"""

from __future__ import annotations

from collections.abc import Mapping


def bagi_kuota_rata(jumlah_soal: int, stok_per_materi: Mapping[str, int]) -> dict[str, int]:
    """Bagi jumlah_soal serata mungkin ke setiap Materi, dibatasi stok
    masing-masing. Kekurangan stok satu Materi dialihkan ke Materi lain; sisa
    pembagian jatuh ke Materi dengan id terkecil. Kalau total stok kurang dari
    jumlah_soal, semua stok diambil (paket lebih kecil dari yang diminta).
    """
    alokasi = dict.fromkeys(sorted(stok_per_materi), 0)
    sisa = min(jumlah_soal, sum(stok_per_materi.values()))
    while sisa > 0:
        for materi_id in alokasi:
            if sisa == 0:
                break
            if alokasi[materi_id] < stok_per_materi[materi_id]:
                alokasi[materi_id] += 1
                sisa -= 1
    return alokasi
