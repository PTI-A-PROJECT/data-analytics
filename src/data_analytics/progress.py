"""Formula progress murni — lihat resolusi tiket 02 (Definisi & Formula Progress
Belajar) di .scratch/osn-data-analytics/issues/02-definisi-progress-belajar.md.
"""


def validasi_halaman(*, halaman: int, total_halaman: int, nama_field: str) -> None:
    """Guard bersama: halaman (baik halaman_dicapai yang masuk maupun
    halaman_tertinggi_dicapai yang tersimpan) harus di antara 1 dan
    total_halaman inklusif.
    """
    if total_halaman <= 0:
        raise ValueError("total_halaman harus lebih dari 0")
    if halaman < 1:
        raise ValueError(f"{nama_field} harus minimal 1")
    if halaman > total_halaman:
        raise ValueError(f"{nama_field} tidak boleh melebihi total_halaman")


def persentase_selesai(*, halaman_tertinggi_dicapai: int, total_halaman: int) -> float:
    """Persentase halaman_tertinggi_dicapai/total_halaman, dibulatkan dua desimal.

    Materi yang belum pernah dibuka tidak punya baris progress_materi sama
    sekali (lihat repository.catat_progress_halaman) — fungsi ini hanya dipanggil
    untuk Materi yang sudah punya baris, jadi halaman_tertinggi_dicapai minimal 1.
    """
    validasi_halaman(
        halaman=halaman_tertinggi_dicapai,
        total_halaman=total_halaman,
        nama_field="halaman_tertinggi_dicapai",
    )
    return round((halaman_tertinggi_dicapai / total_halaman) * 100, 2)
