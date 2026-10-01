"""Penyusunan Paket Tes — fungsi murni (fase 2 issue 02)."""

from __future__ import annotations

from data_analytics.paket import bagi_kuota_rata


class TestBagiKuotaRata:
    def test_dibagi_rata_kalau_stok_cukup(self) -> None:
        assert bagi_kuota_rata(30, {"a": 50, "b": 50, "c": 50}) == {"a": 10, "b": 10, "c": 10}

    def test_sisa_pembagian_jatuh_ke_materi_urutan_id_teratas(self) -> None:
        assert bagi_kuota_rata(10, {"c": 50, "a": 50, "b": 50}) == {"a": 4, "b": 3, "c": 3}

    def test_kekurangan_stok_dialihkan_ke_materi_lain(self) -> None:
        assert bagi_kuota_rata(30, {"a": 2, "b": 50, "c": 50}) == {"a": 2, "b": 14, "c": 14}

    def test_total_stok_kurang_dari_kuota_mengambil_semua_stok(self) -> None:
        assert bagi_kuota_rata(30, {"a": 4, "b": 0, "c": 7}) == {"a": 4, "b": 0, "c": 7}
