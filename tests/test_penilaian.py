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


# --- Contoh dari Rangkuman Lengkap SIAP OSN (aturan final v1) -----------------


def _kab_10_soal(benar_mudah, benar_sedang, benar_sulit, materi="m1"):
    soal = []
    for lvl, n, benar in ((M, 5, benar_mudah), (S, 3, benar_sedang), (X, 2, benar_sulit)):
        for i in range(n):
            soal.append(_s(f"{lvl}-{i}", lvl, "A", "A" if i < benar else "B", materi))
    return soal


def test_contoh_simulasi_kabupaten_64_71_tidak_lulus():
    from data_analytics.penilaian import nilai_simulasi

    h = nilai_simulasi(
        _kab_10_soal(4, 2, 1),
        tingkat="kabupaten",
        ambang_lemah=60.0,
        ambang_kuat=80.0,
    )
    assert (h.penilaian.bobot_benar, h.penilaian.bobot_total) == (11, 17)
    assert h.penilaian.skor == 64.71
    assert h.passing_grade == 70.0
    assert not h.lulus


def test_akurasi_materi_berbobot_contoh_rangkuman():
    # Rekursi bobot 6, benar 2 (hanya soal sedang) -> 33.3% Lemah
    # Array bobot 5 semua benar -> 100% Kuat
    soal = [
        _s("r1", M, "A", "B", "rekursi"), _s("r2", S, "A", "A", "rekursi"), _s("r3", X, "A", "B", "rekursi"),
        _s("a1", S, "A", "A", "array"), _s("a2", X, "A", "A", "array"),
        _s("l1", M, "A", "B", "loop"), _s("l2", S, "A", "A", "loop"), _s("l3", X, "A", "B", "loop"),
    ]
    peta, lemah = hitung_pemetaan(soal, ambang_lemah=60.0, ambang_kuat=80.0)
    p = {x.materi_id: x for x in peta}
    assert (p["rekursi"].bobot_total, p["rekursi"].bobot_benar, p["rekursi"].akurasi) == (6, 2, 33.33)
    assert p["array"].akurasi == 100.0 and p["array"].status is StatusPemetaan.KUAT
    assert p["loop"].status is StatusPemetaan.BELUM_CUKUP
    assert lemah == ["loop", "rekursi"]


def test_batas_ambang_inklusif():
    from data_analytics.pemetaan import status_dari_akurasi as st

    kw = dict(ambang_lemah=60.0, ambang_kuat=80.0)
    assert st(59.99, **kw) is StatusPemetaan.BELUM_CUKUP
    assert st(60.0, **kw) is StatusPemetaan.CUKUP
    assert st(79.99, **kw) is StatusPemetaan.CUKUP
    assert st(80.0, **kw) is StatusPemetaan.KUAT


def test_lulus_hanya_ditentukan_nilai_vs_passing_grade():
    from data_analytics.penilaian import nilai_simulasi

    kw = dict(ambang_lemah=60.0, ambang_kuat=80.0)
    # 7 dari 10 soal mudah benar = 70 -> lulus Kabupaten (inklusif), tidak lulus Provinsi
    soal = [_s(f"x{i}", M, "A", "A" if i < 7 else "B", "m1") for i in range(10)]
    assert nilai_simulasi(soal, tingkat="kabupaten", **kw).lulus
    assert not nilai_simulasi(soal, tingkat="provinsi", **kw).lulus


def test_materi_lemah_tetap_dikembalikan_untuk_remap():
    from data_analytics.penilaian import nilai_simulasi

    soal = [_s("a", M, "A", "A", "m1"), _s("b", M, "A", "B", "m2")]
    h = nilai_simulasi(soal, tingkat="kabupaten", ambang_lemah=60.0, ambang_kuat=80.0)
    assert h.materi_lemah == ["m2"]


# --- Latihan (threshold 50, inklusif) -----------------------------------------


def test_latihan_skor_tepat_50_lulus():
    from data_analytics.penilaian import nilai_latihan

    h = nilai_latihan([_s("a", M, "A", "A"), _s("b", M, "A", "B")])
    assert h.skor == 50.0
    assert h.lulus is True


def test_latihan_skor_49_99_tidak_lulus():
    from data_analytics.penilaian import nilai_latihan

    # 1666 sulit benar... disusun agar bobot benar 4999 dari 10000 = 49.99
    soal = (
        [_s(f"s{i}", X, "A", "A" if i < 1666 else "B") for i in range(3333)]
        + [_s("m", M, "A", "A")]
    )
    h = nilai_latihan(soal)
    assert h.skor == 49.99
    assert h.lulus is False


def test_latihan_threshold_kustom():
    from data_analytics.penilaian import nilai_latihan

    soal = [_s("a", M, "A", "A"), _s("b", M, "A", "B")]
    assert nilai_latihan(soal, threshold=50.01).lulus is False
    assert nilai_latihan(soal, threshold=0.0).lulus is True
    with pytest.raises(ValueError):
        nilai_latihan(soal, threshold=101)


def test_latihan_akurasi_per_materi_berbobot_dan_lulus_per_materi():
    from data_analytics.penilaian import nilai_latihan

    soal = [
        # rekursi: bobot 1+3=4, benar sulit saja = 3 -> 75% lulus
        _s("r1", M, "A", "B", "rekursi"), _s("r2", X, "A", "A", "rekursi"),
        # dp: bobot 1+3=4, benar mudah saja = 1 -> 25% gagal
        _s("d1", M, "A", "A", "dp"), _s("d2", X, "A", "B", "dp"),
        # graf: tepat 50% (mudah benar, mudah salah) -> lulus (inklusif)
        _s("g1", M, "A", "A", "graf"), _s("g2", M, "A", "B", "graf"),
    ]
    h = nilai_latihan(soal)
    hasil = {a.materi_id: (a.akurasi, a.lulus) for a in h.akurasi_per_materi}
    assert hasil == {"rekursi": (75.0, True), "dp": (25.0, False), "graf": (50.0, True)}


def test_latihan_wajib_materi_id():
    from data_analytics.penilaian import nilai_latihan

    with pytest.raises(ValueError):
        nilai_latihan([_s("a", M, "A", "A", None)])
