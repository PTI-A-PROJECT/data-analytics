"""Evaluasi syarat pre-test Provinsi (fase 2 issue 02) — fungsi murni."""

import pytest

from data_analytics.kenaikan import evaluasi_jalur_cepat, evaluasi_jalur_simulasi
from data_analytics.models import LevelSoal

M, N, S = LevelSoal.MUDAH, LevelSoal.SEDANG, LevelSoal.SULIT


class TestEvaluasiJalurCepat:
    def test_skor_tepat_di_ambang_lulus(self) -> None:
        assert evaluasi_jalur_cepat(skor_pretest=90, skor_pretest_jalur_cepat=90) is True

    def test_skor_di_bawah_ambang_tidak_lulus(self) -> None:
        assert evaluasi_jalur_cepat(skor_pretest=89.99, skor_pretest_jalur_cepat=90) is False


class TestEvaluasiJalurSimulasi:
    def test_lulus_kalau_skor_dan_rata_level_tepat_di_ambang(self) -> None:
        hasil = evaluasi_jalur_simulasi(
            skor_simulasi=75, skor_simulasi_min=75, level_per_materi=[M, N, S], rata_level_min=2.0
        )

        assert hasil.lulus is True
        assert hasil.rata_level_aktual == 2.0

    def test_tidak_lulus_kalau_rata_level_di_bawah_ambang(self) -> None:
        hasil = evaluasi_jalur_simulasi(
            skor_simulasi=100, skor_simulasi_min=75, level_per_materi=[M, M, S], rata_level_min=2.0
        )

        assert hasil.lulus is False
        assert hasil.syarat_skor_lulus is True
        assert hasil.syarat_level_lulus is False
        assert hasil.rata_level_aktual == pytest.approx(1.67, abs=0.01)

    def test_tidak_lulus_kalau_skor_di_bawah_ambang(self) -> None:
        hasil = evaluasi_jalur_simulasi(
            skor_simulasi=74.99, skor_simulasi_min=75, level_per_materi=[S, S], rata_level_min=2.0
        )

        assert hasil.lulus is False
        assert hasil.syarat_skor_lulus is False
        assert hasil.syarat_level_lulus is True

    def test_tanpa_materi_raise_value_error(self) -> None:
        with pytest.raises(ValueError):
            evaluasi_jalur_simulasi(
                skor_simulasi=100, skor_simulasi_min=75, level_per_materi=[], rata_level_min=2.0
            )
