"""Mesin soal adaptif simulasi — fungsi murni (fase 2 issue 03)."""

from __future__ import annotations

import pytest

from data_analytics.adaptif import LevelSoalSiswaMateri, alokasi_kuota, perbarui_level
from data_analytics.models import LevelSoal

MUDAH, SEDANG, SULIT = LevelSoal.MUDAH, LevelSoal.SEDANG, LevelSoal.SULIT


def _perbarui(level: LevelSoal, jumlah_soal: int, jumlah_benar: int) -> LevelSoalSiswaMateri:
    return perbarui_level(
        LevelSoalSiswaMateri(level=level, lemah=False, akurasi=None),
        jumlah_soal=jumlah_soal,
        jumlah_benar=jumlah_benar,
        kuota_min=2,
        ambang_naik=80,
        ambang_lemah=50,
    )


class TestPerbaruiLevel:
    def test_akurasi_tepat_ambang_naik_menaikkan_satu_level(self) -> None:
        assert _perbarui(MUDAH, 5, 4) == LevelSoalSiswaMateri(level=SEDANG, lemah=False, akurasi=80.0)

    def test_akurasi_di_bawah_ambang_naik_level_tetap(self) -> None:
        assert _perbarui(SEDANG, 10, 7) == LevelSoalSiswaMateri(
            level=SEDANG, lemah=False, akurasi=70.0
        )

    def test_akurasi_tepat_ambang_lemah_tidak_lemah(self) -> None:
        assert _perbarui(MUDAH, 4, 2) == LevelSoalSiswaMateri(level=MUDAH, lemah=False, akurasi=50.0)

    def test_akurasi_di_bawah_ambang_lemah_lemah_tapi_level_tidak_turun(self) -> None:
        assert _perbarui(SULIT, 3, 1) == LevelSoalSiswaMateri(level=SULIT, lemah=True, akurasi=33.33)

    def test_mentok_di_sulit(self) -> None:
        assert _perbarui(SULIT, 2, 2) == LevelSoalSiswaMateri(level=SULIT, lemah=False, akurasi=100.0)

    def test_naik_menghapus_status_lemah(self) -> None:
        lemah = LevelSoalSiswaMateri(level=MUDAH, lemah=True, akurasi=0.0)

        hasil = perbarui_level(
            lemah, jumlah_soal=2, jumlah_benar=2, kuota_min=2, ambang_naik=80, ambang_lemah=50
        )

        assert hasil == LevelSoalSiswaMateri(level=SEDANG, lemah=False, akurasi=100.0)

    def test_materi_di_bawah_kuota_min_tidak_berubah(self) -> None:
        sekarang = LevelSoalSiswaMateri(level=SEDANG, lemah=True, akurasi=20.0)

        hasil = perbarui_level(
            sekarang, jumlah_soal=1, jumlah_benar=1, kuota_min=2, ambang_naik=80, ambang_lemah=50
        )

        assert hasil == sekarang


def _alokasi(jumlah_soal: int, lemah: dict[str, bool], kuota_min: int = 2) -> dict[str, int]:
    return alokasi_kuota(jumlah_soal, lemah, kuota_min=kuota_min, bobot_lemah=3)


class TestAlokasiKuota:
    def test_sisa_dibagi_sesuai_bobot_lemah(self) -> None:
        # Dasar 4x2=8, sisa 12 dibagi 3:1:1:1 → 6,2,2,2.
        assert _alokasi(20, {"a": True, "b": False, "c": False, "d": False}) == {
            "a": 8,
            "b": 4,
            "c": 4,
            "d": 4,
        }

    def test_pembulatan_largest_remainder_total_tepat_n(self) -> None:
        # Sisa 4 dibagi 3:1:1 → 2.4, 0.8, 0.8 → 2,1,1.
        assert _alokasi(10, {"a": True, "b": False, "c": False}) == {"a": 4, "b": 3, "c": 3}

    def test_sisa_seri_jatuh_ke_materi_id_terkecil(self) -> None:
        assert _alokasi(7, {"c": False, "b": False, "a": False}) == {"a": 3, "b": 2, "c": 2}

    def test_sisa_nol_semua_mendapat_kuota_min(self) -> None:
        assert _alokasi(6, {"a": True, "b": False, "c": False}) == {"a": 2, "b": 2, "c": 2}

    def test_tanpa_materi_lemah_dibagi_rata(self) -> None:
        assert _alokasi(12, {"a": False, "b": False, "c": False}) == {"a": 4, "b": 4, "c": 4}

    @pytest.mark.parametrize("jumlah_soal", [10, 17, 23, 30, 41])
    def test_total_selalu_n_dan_setiap_materi_minimal_kuota_min(self, jumlah_soal: int) -> None:
        lemah = {"a": True, "b": False, "c": True, "d": False, "e": False}

        alokasi = _alokasi(jumlah_soal, lemah)

        assert sum(alokasi.values()) == jumlah_soal
        assert min(alokasi.values()) >= 2

    def test_kuota_min_melebihi_jumlah_soal_ditolak(self) -> None:
        with pytest.raises(ValueError):
            _alokasi(5, {"a": False, "b": False, "c": False})
