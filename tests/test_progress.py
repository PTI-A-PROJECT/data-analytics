import pytest

from data_analytics.progress import persentase_selesai


class TestPersentaseSelesai:
    def test_baru_mulai(self) -> None:
        assert persentase_selesai(halaman_tertinggi_dicapai=1, total_halaman=5) == 20.0

    def test_selesai_penuh(self) -> None:
        assert persentase_selesai(halaman_tertinggi_dicapai=5, total_halaman=5) == 100.0

    def test_dibulatkan_dua_desimal(self) -> None:
        # 2/3 = 66.666...
        assert persentase_selesai(halaman_tertinggi_dicapai=2, total_halaman=3) == 66.67

    def test_total_halaman_nol_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="total_halaman"):
            persentase_selesai(halaman_tertinggi_dicapai=0, total_halaman=0)

    def test_halaman_tertinggi_dicapai_nol_menaikkan_error(self) -> None:
        # minimal 1 - materi yang belum pernah dibuka tidak punya baris progress
        # sama sekali (lihat repository.catat_progress_halaman), bukan baris dengan 0.
        with pytest.raises(ValueError, match="halaman_tertinggi_dicapai"):
            persentase_selesai(halaman_tertinggi_dicapai=0, total_halaman=5)

    def test_halaman_tertinggi_dicapai_melebihi_total_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="halaman_tertinggi_dicapai"):
            persentase_selesai(halaman_tertinggi_dicapai=6, total_halaman=5)
