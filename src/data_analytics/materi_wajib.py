"""Materi Wajib sebelum simulasi berikutnya — fungsi murni (fase 2
issue 04), pola sama dengan paket.py/adaptif.py. Penyimpanan & Gerbang
Simulasi ada di repository.py.
"""

from __future__ import annotations

from collections.abc import Iterable


def selesai_dipelajari(halaman_dibuka: Iterable[int], *, halaman_materi: Iterable[int]) -> bool:
    """Materi Wajib selesai kalau SETIAP halaman Materi (nomor halaman yang ada
    di katalog — tidak diasumsikan 1..N tanpa celah) sudah dibuka minimal
    sekali sejak diwajibkan. Navigasi bebas — urutan & duplikat tidak
    berpengaruh; melompat ke halaman terakhir saja tidak cukup. Materi tanpa
    halaman langsung selesai."""
    return set(halaman_materi) <= set(halaman_dibuka)
