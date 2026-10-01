"""Kriteria "selesai dipelajari" Materi Wajib — fungsi murni (fase 2 issue 04)."""

from __future__ import annotations

from data_analytics.materi_wajib import selesai_dipelajari


class TestSelesaiDipelajari:
    def test_semua_halaman_dibuka_selesai(self) -> None:
        assert selesai_dipelajari([1, 2, 3, 4], halaman_materi=[1, 2, 3, 4]) is True

    def test_urutan_acak_tetap_selesai(self) -> None:
        assert selesai_dipelajari([3, 1, 4, 2], halaman_materi=[1, 2, 3, 4]) is True

    def test_halaman_duplikat_tidak_menggantikan_halaman_yang_belum_dibuka(self) -> None:
        assert selesai_dipelajari([1, 1, 2, 2, 3], halaman_materi=[1, 2, 3, 4]) is False

    def test_lompat_ke_halaman_terakhir_saja_belum_selesai(self) -> None:
        assert selesai_dipelajari([4], halaman_materi=[1, 2, 3, 4]) is False

    def test_belum_membuka_apa_pun_belum_selesai(self) -> None:
        assert selesai_dipelajari([], halaman_materi=[1, 2, 3]) is False

    def test_materi_tanpa_halaman_langsung_selesai(self) -> None:
        assert selesai_dipelajari([], halaman_materi=[]) is True

    def test_nomor_halaman_tidak_berurutan_mengikuti_halaman_yang_ada(self) -> None:
        assert selesai_dipelajari([5, 1, 2], halaman_materi=[1, 2, 5]) is True
