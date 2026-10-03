import pytest

from data_analytics.models import TipeSoal
from data_analytics.scoring import cocokkan_jawaban, hitung_skor, tentukan_predikat


class TestHitungSkor:
    def test_semua_benar(self) -> None:
        assert hitung_skor(bobot_benar=10, bobot_total=10) == 100.0

    def test_semua_salah(self) -> None:
        assert hitung_skor(bobot_benar=0, bobot_total=10) == 0.0

    def test_persentase_dibulatkan_dua_desimal(self) -> None:
        # 7/9 = 77.777...
        assert hitung_skor(bobot_benar=7, bobot_total=9) == 77.78

    def test_total_soal_nol_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="bobot_total"):
            hitung_skor(bobot_benar=0, bobot_total=0)

    def test_jumlah_benar_melebihi_total_soal_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="bobot_benar"):
            hitung_skor(bobot_benar=11, bobot_total=10)

    def test_jumlah_benar_negatif_menaikkan_error(self) -> None:
        with pytest.raises(ValueError, match="bobot_benar"):
            hitung_skor(bobot_benar=-1, bobot_total=10)


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
        tanpa_dasar = [("Sangat Baik", 90), ("Baik", 80)]
        with pytest.raises(ValueError, match="batas_bawah=0"):
            tentukan_predikat(50.0, tanpa_dasar)


class TestCocokkanJawaban:
    def test_pilihan_ganda_huruf_tanpa_peduli_kapital(self) -> None:
        assert cocokkan_jawaban("C", "c", TipeSoal.PILIHAN_GANDA) is True
        assert cocokkan_jawaban("C", "B", TipeSoal.PILIHAN_GANDA) is False

    def test_tidak_dijawab_selalu_salah(self) -> None:
        assert cocokkan_jawaban("C", None, TipeSoal.PILIHAN_GANDA) is False
        assert cocokkan_jawaban("12", None, TipeSoal.ISIAN_SINGKAT) is False
        assert cocokkan_jawaban("12", "   ", TipeSoal.ISIAN_SINGKAT) is False

    def test_isian_mengabaikan_spasi_tepi_dan_kapital(self) -> None:
        assert cocokkan_jawaban("BENAR", " benar ", TipeSoal.ISIAN_SINGKAT) is True
        assert cocokkan_jawaban("Lisa dan Marta", "lisa  dan marta", TipeSoal.ISIAN_SINGKAT) is True
        assert cocokkan_jawaban("OSSNNN", "OSNSNN", TipeSoal.ISIAN_SINGKAT) is False

    def test_isian_angka_dibandingkan_sebagai_bilangan(self) -> None:
        assert cocokkan_jawaban("1260", "1260.0", TipeSoal.ISIAN_SINGKAT) is True
        assert cocokkan_jawaban("0.5", "0,5", TipeSoal.ISIAN_SINGKAT) is True
        assert cocokkan_jawaban("1260", "1261", TipeSoal.ISIAN_SINGKAT) is False

    def test_isian_daftar_mengabaikan_spasi_sekitar_koma(self) -> None:
        assert cocokkan_jawaban("26, 17, 11", "26,17,11", TipeSoal.ISIAN_SINGKAT) is True
        assert cocokkan_jawaban("B, G, C", "b ,g, c", TipeSoal.ISIAN_SINGKAT) is True