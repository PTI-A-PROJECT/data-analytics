"""Test algoritma murni evaluasi Pre-Test berjenjang (tiket 15)."""

import pytest

from data_analytics.pre_test import evaluasi_kelulusan_pre_test


class TestEvaluasiKelulusanPreTest:
    def test_lulus_skor_di_atas_passing_grade(self) -> None:
        hasil = evaluasi_kelulusan_pre_test(skor=85.0, passing_grade=70.0)
        assert hasil.lulus is True
        assert hasil.skor_aktual == 85.0
        assert hasil.passing_grade == 70.0

    def test_lulus_skor_tepat_di_passing_grade(self) -> None:
        # Ambang batas inklusif: skor == passing_grade tetap lulus
        hasil = evaluasi_kelulusan_pre_test(skor=70.0, passing_grade=70.0)
        assert hasil.lulus is True
        assert hasil.skor_aktual == 70.0
        assert hasil.passing_grade == 70.0

    def test_tidak_lulus_skor_di_bawah_passing_grade(self) -> None:
        hasil = evaluasi_kelulusan_pre_test(skor=69.9, passing_grade=70.0)
        assert hasil.lulus is False
        assert hasil.skor_aktual == 69.9
        assert hasil.passing_grade == 70.0

    def test_skor_negatif_raise_value_error(self) -> None:
        with pytest.raises(ValueError, match="skor harus di antara 0 dan 100"):
            evaluasi_kelulusan_pre_test(skor=-1.0, passing_grade=70.0)

    def test_skor_di_atas_100_raise_value_error(self) -> None:
        with pytest.raises(ValueError, match="skor harus di antara 0 dan 100"):
            evaluasi_kelulusan_pre_test(skor=100.1, passing_grade=70.0)

    def test_passing_grade_negatif_raise_value_error(self) -> None:
        with pytest.raises(ValueError, match="passing_grade harus di antara 0 dan 100"):
            evaluasi_kelulusan_pre_test(skor=70.0, passing_grade=-5.0)

    def test_passing_grade_di_atas_100_raise_value_error(self) -> None:
        with pytest.raises(ValueError, match="passing_grade harus di antara 0 dan 100"):
            evaluasi_kelulusan_pre_test(skor=70.0, passing_grade=105.0)
