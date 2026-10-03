import pytest

from data_analytics.models import LevelSoal, StatusPemetaan, TipeSoal
from data_analytics.penilaian import SoalDijawab, hitung_pemetaan, nilai_jawaban

M, S, X = LevelSoal.MUDAH, LevelSoal.SEDANG, LevelSoal.SULIT
PG = TipeSoal.PILIHAN_GANDA


def _s(i, level, kunci, jawaban, materi="m1"):
    return SoalDijawab(i, level, PG, kunci, jawaban, materi)


def test_level_sedang_bernilai_nilai_dan_string_laravel():
    assert LevelSoal.SEDANG.value == "sedang"
    assert not hasattr(LevelSoal, "MENENGAH")


def test_skor_berbobot_mudah_salah_sedang_sulit_benar():
    hasil = nilai_jawaban(
        [_s("a", M, "A", "B"), _s("b", S, "A", "A"), _s("c", X, "A", "a")]
    )
    # bobot benar 2+3=5 dari total 6
    assert (hasil.bobot_benar, hasil.bobot_total, hasil.skor) == (5, 6, 83.33)
    assert (hasil.jumlah_benar, hasil.jumlah_salah) == (2, 1)
    assert hasil.predikat is None


def test_soal_tidak_dijawab_dihitung_salah():
    hasil = nilai_jawaban([_s("a", M, "A", None), _s("b", M, "A", "A")])
    assert hasil.skor == 50.0


def test_predikat_dari_aturan():
    hasil = nilai_jawaban(
        [_s("a", M, "A", "A")], aturan_predikat=[("Dasar", 0), ("Baik", 80)]
    )
    assert hasil.predikat == "Baik"


def test_daftar_kosong_dan_id_ganda_ditolak():
    with pytest.raises(ValueError):
        nilai_jawaban([])
    with pytest.raises(ValueError):
        nilai_jawaban([_s("a", M, "A", "A"), _s("a", M, "A", "A")])


def test_pemetaan_per_materi_dan_materi_lemah():
    soal = [
        _s("1", M, "A", "A", "m1"),
        _s("2", M, "A", "A", "m1"),
        _s("3", M, "A", "B", "m2"),
        _s("4", M, "A", "A", "m2"),
        _s("5", M, "A", "B", "m3"),
    ]
    peta, lemah = hitung_pemetaan(soal, ambang_lemah=60.0, ambang_kuat=80.0)
    status = {p.materi_id: p.status for p in peta}
    assert status == {
        "m1": StatusPemetaan.KUAT,
        "m2": StatusPemetaan.BELUM_CUKUP,
        "m3": StatusPemetaan.BELUM_CUKUP,
    }
    assert lemah == ["m3", "m2"]


def test_pemetaan_wajib_materi_id():
    with pytest.raises(ValueError):
        hitung_pemetaan(
            [_s("1", M, "A", "A", None)], ambang_lemah=60.0, ambang_kuat=80.0
        )
