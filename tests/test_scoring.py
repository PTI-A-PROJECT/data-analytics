import pytest

from data_analytics.scoring import hitung_skor, tentukan_predikat


class TestHitungSkor:
    def test_semua_benar(self) -> None:
        assert hitung_skor(jumlah_benar=10, total_soal=10) == 100.0

    def test_semua_salah(self) -> None:
        assert hitung_skor(jumlah_benar=0, total_soal=10) == 0.0

    def test_persentase_dibulatkan_dua_desimal(self) -> None:
        # 7/9 = 77.777...
        assert hitung_skor(jumlah_benar=7, total_soal=9) == 77.78

    def test_total_soal_nol_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="total_soal"):
            hitung_skor(jumlah_benar=0, total_soal=0)

    def test_jumlah_benar_melebihi_total_soal_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="jumlah_benar"):
            hitung_skor(jumlah_benar=11, total_soal=10)

    def test_jumlah_benar_negatif_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="jumlah_benar"):
            hitung_skor(jumlah_benar=-1, total_soal=10)


class TestTentukanPredikat:
    # aturan tersusun (label, batas_bawah) - tidak harus urut, fungsi yang menyortir
    ATURAN_DEFAULT = [
        ("Sangat Baik", 90),
        ("Baik", 80),
        ("Cukup", 70),
        ("Perlu Latihan", 0),
    ]

    def test_skor_tepat_di_ambang_batas_inklusif(self) -> None:
        assert tentukan_predikat(90.0, self.ATURAN_DEFAULT) == "Sangat Baik"
        assert tentukan_predikat(80.0, self.ATURAN_DEFAULT) == "Baik"
        assert tentukan_predikat(70.0, self.ATURAN_DEFAULT) == "Cukup"

    def test_skor_di_bawah_ambang_batas_predikat_di_atasnya(self) -> None:
        assert tentukan_predikat(89.99, self.ATURAN_DEFAULT) == "Baik"
        assert tentukan_predikat(69.99, self.ATURAN_DEFAULT) == "Perlu Latihan"

    def test_skor_maksimum(self) -> None:
        assert tentukan_predikat(100.0, self.ATURAN_DEFAULT) == "Sangat Baik"

    def test_skor_minimum(self) -> None:
        assert tentukan_predikat(0.0, self.ATURAN_DEFAULT) == "Perlu Latihan"

    def test_aturan_tidak_urut_tetap_benar(self) -> None:
        tidak_urut = [
            ("Perlu Latihan", 0),
            ("Sangat Baik", 90),
            ("Cukup", 70),
            ("Baik", 80),
        ]
        assert tentukan_predikat(85.0, tidak_urut) == "Baik"

    def test_aturan_kosong_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="aturan_predikat"):
            tentukan_predikat(50.0, [])

    def test_tidak_ada_predikat_batas_bawah_nol_menaikkan_error(self) -> None:
        # aturan tanpa predikat "dasar" (batas_bawah=0) berarti ada skor yang tidak
        # tertampung oleh predikat manapun - ini config yang tidak valid.
        tanpa_dasar = [("Sangat Baik", 90), ("Baik", 80)]
        with pytest.raises(ValueError, match="batas_bawah=0"):
            tentukan_predikat(50.0, tanpa_dasar)
