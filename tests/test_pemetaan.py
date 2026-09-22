"""Test algoritma Pemetaan Kompetensi murni (FR-07, tiket 11)."""

import pytest

from data_analytics.models import StatusPemetaan
from data_analytics.pemetaan import tentukan_butuh_optimasi, tentukan_status_pemetaan

AMBANG_CUKUP = 70
AMBANG_REPRESENTASI = 20


class TestTentukanStatusPemetaan:
    def test_representasi_di_bawah_ambang_belum_teruji(self) -> None:
        # 1/10 soal = 10% representasi, di bawah ambang 20% -> Belum Teruji
        # walau seluruhnya benar.
        status = tentukan_status_pemetaan(
            jumlah_soal_subkompetensi=1,
            jumlah_benar=1,
            total_soal_tes=10,
            ambang_cukup_persen=AMBANG_CUKUP,
            ambang_representasi_persen=AMBANG_REPRESENTASI,
        )
        assert status == StatusPemetaan.BELUM_TERUJI

    def test_representasi_cukup_dan_benar_di_atas_ambang_cukup(self) -> None:
        # 4/10 soal = 40% representasi (valid), 3/4 benar = 75% >= ambang 70%.
        status = tentukan_status_pemetaan(
            jumlah_soal_subkompetensi=4,
            jumlah_benar=3,
            total_soal_tes=10,
            ambang_cukup_persen=AMBANG_CUKUP,
            ambang_representasi_persen=AMBANG_REPRESENTASI,
        )
        assert status == StatusPemetaan.CUKUP

    def test_representasi_cukup_tapi_benar_di_bawah_ambang_cukup(self) -> None:
        # 4/10 soal = 40% representasi (valid), 2/4 benar = 50% < ambang 70%.
        status = tentukan_status_pemetaan(
            jumlah_soal_subkompetensi=4,
            jumlah_benar=2,
            total_soal_tes=10,
            ambang_cukup_persen=AMBANG_CUKUP,
            ambang_representasi_persen=AMBANG_REPRESENTASI,
        )
        assert status == StatusPemetaan.BELUM_CUKUP

    def test_representasi_tepat_di_ambang_inklusif(self) -> None:
        # representasi 2/10=20%, tepat di ambang -> valid (bukan Belum Teruji).
        status = tentukan_status_pemetaan(
            jumlah_soal_subkompetensi=2,
            jumlah_benar=2,
            total_soal_tes=10,
            ambang_cukup_persen=AMBANG_CUKUP,
            ambang_representasi_persen=AMBANG_REPRESENTASI,
        )
        assert status != StatusPemetaan.BELUM_TERUJI

    def test_korektnes_tepat_di_ambang_cukup_inklusif(self) -> None:
        status = tentukan_status_pemetaan(
            jumlah_soal_subkompetensi=10,
            jumlah_benar=7,
            total_soal_tes=10,
            ambang_cukup_persen=AMBANG_CUKUP,
            ambang_representasi_persen=AMBANG_REPRESENTASI,
        )
        assert status == StatusPemetaan.CUKUP  # 70% == ambang, inklusif

    def test_total_soal_nol_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="total_soal_tes"):
            tentukan_status_pemetaan(
                jumlah_soal_subkompetensi=1,
                jumlah_benar=1,
                total_soal_tes=0,
                ambang_cukup_persen=AMBANG_CUKUP,
                ambang_representasi_persen=AMBANG_REPRESENTASI,
            )

    def test_jumlah_benar_melebihi_jumlah_soal_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="jumlah_benar"):
            tentukan_status_pemetaan(
                jumlah_soal_subkompetensi=2,
                jumlah_benar=3,
                total_soal_tes=10,
                ambang_cukup_persen=AMBANG_CUKUP,
                ambang_representasi_persen=AMBANG_REPRESENTASI,
            )


class TestTentukanButuhOptimasi:
    def test_cukup_dan_mayoritas_lambat_true(self) -> None:
        # 3 dari 4 benar juga lambat = 75% > 50%.
        assert (
            tentukan_butuh_optimasi(
                status=StatusPemetaan.CUKUP, jumlah_benar=4, jumlah_benar_lambat=3
            )
            is True
        )

    def test_cukup_tapi_minoritas_lambat_false(self) -> None:
        # 1 dari 4 benar juga lambat = 25% <= 50%.
        assert (
            tentukan_butuh_optimasi(
                status=StatusPemetaan.CUKUP, jumlah_benar=4, jumlah_benar_lambat=1
            )
            is False
        )

    def test_tepat_50_persen_tidak_melebihi_ambang(self) -> None:
        # >50% (ketat), bukan >=50%.
        assert (
            tentukan_butuh_optimasi(
                status=StatusPemetaan.CUKUP, jumlah_benar=4, jumlah_benar_lambat=2
            )
            is False
        )

    def test_belum_cukup_selalu_false_walau_semua_lambat(self) -> None:
        assert (
            tentukan_butuh_optimasi(
                status=StatusPemetaan.BELUM_CUKUP, jumlah_benar=2, jumlah_benar_lambat=2
            )
            is False
        )

    def test_belum_teruji_selalu_false(self) -> None:
        assert (
            tentukan_butuh_optimasi(
                status=StatusPemetaan.BELUM_TERUJI, jumlah_benar=1, jumlah_benar_lambat=1
            )
            is False
        )

    def test_jumlah_benar_nol_tidak_pembagian_dengan_nol(self) -> None:
        assert (
            tentukan_butuh_optimasi(
                status=StatusPemetaan.CUKUP, jumlah_benar=0, jumlah_benar_lambat=0
            )
            is False
        )

    def test_jumlah_benar_lambat_melebihi_jumlah_benar_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="jumlah_benar_lambat"):
            tentukan_butuh_optimasi(
                status=StatusPemetaan.CUKUP, jumlah_benar=2, jumlah_benar_lambat=3
            )
