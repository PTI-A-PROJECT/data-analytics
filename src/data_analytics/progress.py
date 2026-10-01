"""Formula progress baca Materi murni. Sejak fase 2 issue 04 progres dihitung
dari jumlah halaman UNIK yang pernah dibuka (navigasi bebas), bukan high-water
mark halaman tertinggi.
"""


def persentase_selesai(*, halaman_dibuka: int, total_halaman: int) -> float:
    """Persentase halaman unik yang pernah dibuka dari total_halaman,
    dibulatkan dua desimal."""
    if total_halaman <= 0:
        raise ValueError("total_halaman harus lebih dari 0")
    if not 0 <= halaman_dibuka <= total_halaman:
        raise ValueError("halaman_dibuka harus di antara 0 dan total_halaman")
    return round(halaman_dibuka / total_halaman * 100, 2)
