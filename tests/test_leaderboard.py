"""Leaderboard per Tingkat Seleksi — fungsi murni: skor gabungan 50% skor + 50%
kecepatan, satu attempt terbaik per siswa, 5 teratas.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from data_analytics.leaderboard import AttemptSimulasi, durasi_pengerjaan, susun_leaderboard

T0 = datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc)


def _attempt(siswa_id: str, skor: float, detik_per_soal: float, total_soal: int = 10) -> AttemptSimulasi:
    return AttemptSimulasi(
        siswa_id=siswa_id, skor=skor, durasi_detik=detik_per_soal * total_soal, total_soal=total_soal
    )


class TestDurasiPengerjaan:
    def test_dari_soal_pertama_dibuka_sampai_soal_terakhir_dijawab(self) -> None:
        waktu = [
            (T0 + timedelta(seconds=30), T0 + timedelta(seconds=90)),
            (T0, T0 + timedelta(seconds=20)),
            (None, None),  # dilewati
        ]

        assert durasi_pengerjaan(waktu) == 90.0

    def test_tanpa_timestamp_tidak_bisa_diukur(self) -> None:
        assert durasi_pengerjaan([(None, None), (T0, None)]) is None


class TestSusunLeaderboard:
    def test_skor_gabungan_setengah_skor_setengah_kecepatan(self) -> None:
        peringkat = susun_leaderboard(
            [_attempt("cepat", skor=80, detik_per_soal=30), _attempt("lambat", skor=100, detik_per_soal=60)]
        )

        # cepat: 0.5*80 + 0.5*100 = 90; lambat: 0.5*100 + 0.5*(30/60*100) = 75.
        assert [(p.siswa_id, p.skor_kecepatan, p.skor_gabungan) for p in peringkat] == [
            ("cepat", 100.0, 90.0),
            ("lambat", 50.0, 75.0),
        ]
        assert [p.peringkat for p in peringkat] == [1, 2]

    def test_satu_attempt_terbaik_per_siswa(self) -> None:
        peringkat = susun_leaderboard(
            [
                _attempt("a", skor=60, detik_per_soal=30),
                _attempt("a", skor=100, detik_per_soal=30),
                _attempt("b", skor=90, detik_per_soal=30),
            ]
        )

        assert [(p.siswa_id, p.skor) for p in peringkat] == [("a", 100), ("b", 90)]

    def test_kecepatan_dibandingkan_per_soal_bukan_total_durasi(self) -> None:
        peringkat = susun_leaderboard(
            [
                _attempt("paket-besar", skor=80, detik_per_soal=30, total_soal=30),
                _attempt("paket-kecil", skor=80, detik_per_soal=60, total_soal=10),
            ]
        )

        assert [p.siswa_id for p in peringkat] == ["paket-besar", "paket-kecil"]

    def test_hanya_lima_teratas(self) -> None:
        peringkat = susun_leaderboard(
            [_attempt(f"s{i}", skor=50 + i, detik_per_soal=30) for i in range(8)]
        )

        assert [p.siswa_id for p in peringkat] == ["s7", "s6", "s5", "s4", "s3"]

    def test_gabungan_sama_skor_lebih_tinggi_di_atas(self) -> None:
        # x: 0.5*100 + 0.5*50 = 75; y: 0.5*50 + 0.5*100 = 75.
        peringkat = susun_leaderboard(
            [_attempt("x", skor=100, detik_per_soal=60), _attempt("y", skor=50, detik_per_soal=30)]
        )

        assert [p.siswa_id for p in peringkat] == ["x", "y"]

    def test_kosong(self) -> None:
        assert susun_leaderboard([]) == []
