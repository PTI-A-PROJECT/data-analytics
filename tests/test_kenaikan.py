"""Test algoritma murni evaluasi Kenaikan Tingkat (FR-17, tiket 03)."""

import pytest

from data_analytics.kenaikan import evaluasi_syarat_kenaikan


class TestEvaluasiSyaratKenaikan:
    def test_lulus_kalau_skor_dan_kompetensi_memenuhi_ambang(self) -> None:
        hasil = evaluasi_syarat_kenaikan(
            skor=80.0,
            skor_simulasi_min=75.0,
            jumlah_kompetensi_cukup=4,
            total_kompetensi_silabus=5,
            persentase_kompetensi_cukup_min=80.0,
        )
        assert hasil.hasil_evaluasi == "lulus"
        assert hasil.syarat_skor_lulus is True
        assert hasil.syarat_kompetensi_lulus is True
        assert hasil.persentase_cukup_aktual == 80.0

    def test_tidak_lulus_kalau_skor_di_bawah_ambang(self) -> None:
        hasil = evaluasi_syarat_kenaikan(
            skor=70.0,
            skor_simulasi_min=75.0,
            jumlah_kompetensi_cukup=5,
            total_kompetensi_silabus=5,
            persentase_kompetensi_cukup_min=80.0,
        )
        assert hasil.hasil_evaluasi == "tidak_lulus"
        assert hasil.syarat_skor_lulus is False
        assert hasil.syarat_kompetensi_lulus is True

    def test_tidak_lulus_kalau_persentase_kompetensi_di_bawah_ambang(self) -> None:
        hasil = evaluasi_syarat_kenaikan(
            skor=90.0,
            skor_simulasi_min=75.0,
            jumlah_kompetensi_cukup=2,
            total_kompetensi_silabus=5,
            persentase_kompetensi_cukup_min=80.0,
        )
        assert hasil.hasil_evaluasi == "tidak_lulus"
        assert hasil.syarat_skor_lulus is True
        assert hasil.syarat_kompetensi_lulus is False
        assert hasil.persentase_cukup_aktual == 40.0

    def test_skor_tepat_di_ambang_lulus(self) -> None:
        # Ambang inklusif — skor == batas minimum tetap lulus syarat skor.
        hasil = evaluasi_syarat_kenaikan(
            skor=75.0,
            skor_simulasi_min=75.0,
            jumlah_kompetensi_cukup=4,
            total_kompetensi_silabus=5,
            persentase_kompetensi_cukup_min=80.0,
        )
        assert hasil.syarat_skor_lulus is True

    def test_total_kompetensi_silabus_nol_raise_value_error(self) -> None:
        with pytest.raises(ValueError):
            evaluasi_syarat_kenaikan(
                skor=90.0,
                skor_simulasi_min=75.0,
                jumlah_kompetensi_cukup=0,
                total_kompetensi_silabus=0,
                persentase_kompetensi_cukup_min=80.0,
            )
