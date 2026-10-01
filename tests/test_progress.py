"""Formula progress baca Materi murni (fase 2 issue 04)."""

import pytest

from data_analytics.progress import persentase_selesai


class TestPersentaseSelesai:
    def test_sebagian_halaman(self) -> None:
        assert persentase_selesai(halaman_dibuka=2, total_halaman=3) == 66.67

    def test_semua_halaman(self) -> None:
        assert persentase_selesai(halaman_dibuka=5, total_halaman=5) == 100.0

    def test_belum_ada_halaman_dibuka(self) -> None:
        assert persentase_selesai(halaman_dibuka=0, total_halaman=5) == 0.0

    def test_total_halaman_nol_ditolak(self) -> None:
        with pytest.raises(ValueError, match="total_halaman"):
            persentase_selesai(halaman_dibuka=0, total_halaman=0)

    def test_melebihi_total_ditolak(self) -> None:
        with pytest.raises(ValueError, match="halaman_dibuka"):
            persentase_selesai(halaman_dibuka=6, total_halaman=5)
