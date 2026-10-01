"""Pemotongan teks panjang menjadi jendela token untuk embedder (fase 2
issue 01) — fungsi murni, tanpa model."""

from __future__ import annotations

import pytest

from data_analytics.embedding import potong_jendela


class TestPotongJendela:
    def test_teks_pendek_satu_jendela(self) -> None:
        assert potong_jendela([1, 2, 3], panjang=5, tumpang=2) == [[1, 2, 3]]

    def test_tepat_sepanjang_jendela_satu_jendela(self) -> None:
        assert potong_jendela([1, 2, 3, 4, 5], panjang=5, tumpang=2) == [[1, 2, 3, 4, 5]]

    def test_teks_panjang_bergeser_dengan_tumpang_tindih_sampai_akhir(self) -> None:
        assert potong_jendela(list(range(1, 11)), panjang=4, tumpang=1) == [
            [1, 2, 3, 4],
            [4, 5, 6, 7],
            [7, 8, 9, 10],
        ]

    def test_jendela_terakhir_tidak_pernah_kosong_atau_duplikat(self) -> None:
        assert potong_jendela(list(range(1, 9)), panjang=4, tumpang=1) == [
            [1, 2, 3, 4],
            [4, 5, 6, 7],
            [7, 8],
        ]

    def test_tumpang_harus_lebih_kecil_dari_panjang(self) -> None:
        with pytest.raises(ValueError):
            potong_jendela([1, 2, 3], panjang=2, tumpang=2)
