import pytest
from sqlalchemy.orm import Session

from data_analytics.repository import (
    MateriRelevan,
    ProgressSubkompetensi,
    catat_progress_halaman,
    hitung_progress_belajar,
)

SISWA = 1
SUBKOMPETENSI_GRAPH = 10
SUBKOMPETENSI_TREE = 11
TINGKAT_KABUPATEN = 1


def _catat(
    session: Session,
    *,
    materi_id: int,
    subkompetensi_id: int = SUBKOMPETENSI_GRAPH,
    total_halaman: int = 5,
    halaman_dicapai: int,
) -> None:
    catat_progress_halaman(
        session,
        siswa_id=SISWA,
        materi_id=materi_id,
        subkompetensi_id=subkompetensi_id,
        tingkat_seleksi_id=TINGKAT_KABUPATEN,
        total_halaman=total_halaman,
        halaman_dicapai=halaman_dicapai,
    )


class TestCatatProgressHalaman:
    def test_baris_baru_saat_pertama_dibuka(self, session: Session) -> None:
        hasil = catat_progress_halaman(
            session,
            siswa_id=SISWA,
            materi_id=100,
            subkompetensi_id=SUBKOMPETENSI_GRAPH,
            tingkat_seleksi_id=TINGKAT_KABUPATEN,
            total_halaman=5,
            halaman_dicapai=1,
        )

        assert hasil.halaman_tertinggi_dicapai == 1
        assert hasil.total_halaman == 5

    def test_high_water_mark_naik(self, session: Session) -> None:
        _catat(session, materi_id=100, halaman_dicapai=2)
        hasil = catat_progress_halaman(
            session,
            siswa_id=SISWA,
            materi_id=100,
            subkompetensi_id=SUBKOMPETENSI_GRAPH,
            tingkat_seleksi_id=TINGKAT_KABUPATEN,
            total_halaman=5,
            halaman_dicapai=4,
        )

        assert hasil.halaman_tertinggi_dicapai == 4

    def test_navigasi_mundur_tidak_menurunkan_mark(self, session: Session) -> None:
        _catat(session, materi_id=100, halaman_dicapai=4)
        hasil = catat_progress_halaman(
            session,
            siswa_id=SISWA,
            materi_id=100,
            subkompetensi_id=SUBKOMPETENSI_GRAPH,
            tingkat_seleksi_id=TINGKAT_KABUPATEN,
            total_halaman=5,
            halaman_dicapai=2,  # siswa mundur ke halaman 2
        )

        assert hasil.halaman_tertinggi_dicapai == 4

    def test_total_halaman_diperbarui_ke_snapshot_terakhir(self, session: Session) -> None:
        _catat(session, materi_id=100, total_halaman=5, halaman_dicapai=3)
        hasil = catat_progress_halaman(
            session,
            siswa_id=SISWA,
            materi_id=100,
            subkompetensi_id=SUBKOMPETENSI_GRAPH,
            tingkat_seleksi_id=TINGKAT_KABUPATEN,
            total_halaman=7,  # admin menambah 2 halaman baru
            halaman_dicapai=3,
        )

        assert hasil.total_halaman == 7

    def test_total_halaman_tidak_valid_menaikkan_error(self, session: Session) -> None:
        with pytest.raises(ValueError, match="total_halaman"):
            catat_progress_halaman(
                session,
                siswa_id=SISWA,
                materi_id=100,
                subkompetensi_id=SUBKOMPETENSI_GRAPH,
                tingkat_seleksi_id=TINGKAT_KABUPATEN,
                total_halaman=0,
                halaman_dicapai=1,
            )

    def test_halaman_dicapai_di_luar_rentang_menaikkan_error(self, session: Session) -> None:
        with pytest.raises(ValueError, match="halaman_dicapai"):
            catat_progress_halaman(
                session,
                siswa_id=SISWA,
                materi_id=100,
                subkompetensi_id=SUBKOMPETENSI_GRAPH,
                tingkat_seleksi_id=TINGKAT_KABUPATEN,
                total_halaman=5,
                halaman_dicapai=6,
            )

    def test_total_halaman_menyusut_di_bawah_mark_lama_menaikkan_error(
        self, session: Session
    ) -> None:
        _catat(session, materi_id=100, total_halaman=10, halaman_dicapai=8)

        with pytest.raises(ValueError, match="lebih kecil dari halaman yang sudah"):
            catat_progress_halaman(
                session,
                siswa_id=SISWA,
                materi_id=100,
                subkompetensi_id=SUBKOMPETENSI_GRAPH,
                tingkat_seleksi_id=TINGKAT_KABUPATEN,
                total_halaman=5,  # menyusut, di bawah mark lama (8)
                halaman_dicapai=3,
            )

    def test_halaman_dicapai_nol_menaikkan_error(self, session: Session) -> None:
        with pytest.raises(ValueError, match="halaman_dicapai"):
            catat_progress_halaman(
                session,
                siswa_id=SISWA,
                materi_id=100,
                subkompetensi_id=SUBKOMPETENSI_GRAPH,
                tingkat_seleksi_id=TINGKAT_KABUPATEN,
                total_halaman=5,
                halaman_dicapai=0,
            )


class TestHitungProgressBelajar:
    def test_materi_belum_dibuka_dianggap_nol(self, session: Session) -> None:
        breakdown = hitung_progress_belajar(
            session,
            siswa_id=SISWA,
            materi_relevan=[
                MateriRelevan(materi_id=100, subkompetensi_id=SUBKOMPETENSI_GRAPH)
            ],
        )

        assert breakdown == [
            _progress_subkompetensi(SUBKOMPETENSI_GRAPH, jumlah_materi=1, rata_rata=0.0)
        ]

    def test_breakdown_per_subkompetensi(self, session: Session) -> None:
        # Graph: 3 materi, semua sudah selesai dibaca penuh
        _catat(session, materi_id=1, subkompetensi_id=SUBKOMPETENSI_GRAPH, total_halaman=5, halaman_dicapai=5)
        _catat(session, materi_id=2, subkompetensi_id=SUBKOMPETENSI_GRAPH, total_halaman=4, halaman_dicapai=4)
        _catat(session, materi_id=3, subkompetensi_id=SUBKOMPETENSI_GRAPH, total_halaman=2, halaman_dicapai=2)
        # Tree: 2 materi, belum disentuh sama sekali (tidak ada baris progress_materi)

        breakdown = hitung_progress_belajar(
            session,
            siswa_id=SISWA,
            materi_relevan=[
                MateriRelevan(materi_id=1, subkompetensi_id=SUBKOMPETENSI_GRAPH),
                MateriRelevan(materi_id=2, subkompetensi_id=SUBKOMPETENSI_GRAPH),
                MateriRelevan(materi_id=3, subkompetensi_id=SUBKOMPETENSI_GRAPH),
                MateriRelevan(materi_id=4, subkompetensi_id=SUBKOMPETENSI_TREE),
                MateriRelevan(materi_id=5, subkompetensi_id=SUBKOMPETENSI_TREE),
            ],
        )

        assert breakdown == [
            _progress_subkompetensi(SUBKOMPETENSI_GRAPH, jumlah_materi=3, rata_rata=100.0),
            _progress_subkompetensi(SUBKOMPETENSI_TREE, jumlah_materi=2, rata_rata=0.0),
        ]

    def test_hanya_materi_relevan_yang_dihitung(self, session: Session) -> None:
        # materi 999 punya progress tapi TIDAK ada di materi_relevan (mis. Subkompetensi
        # sudah Cukup, sudah tidak direkomendasikan lagi) - tidak boleh ikut dihitung.
        _catat(session, materi_id=999, subkompetensi_id=SUBKOMPETENSI_GRAPH, total_halaman=5, halaman_dicapai=5)
        _catat(session, materi_id=1, subkompetensi_id=SUBKOMPETENSI_GRAPH, total_halaman=4, halaman_dicapai=2)

        breakdown = hitung_progress_belajar(
            session,
            siswa_id=SISWA,
            materi_relevan=[
                MateriRelevan(materi_id=1, subkompetensi_id=SUBKOMPETENSI_GRAPH)
            ],
        )

        assert breakdown == [
            _progress_subkompetensi(SUBKOMPETENSI_GRAPH, jumlah_materi=1, rata_rata=50.0)
        ]

    def test_materi_relevan_kosong_menghasilkan_breakdown_kosong(self, session: Session) -> None:
        assert hitung_progress_belajar(session, siswa_id=SISWA, materi_relevan=[]) == []


def _progress_subkompetensi(
    subkompetensi_id: int, *, jumlah_materi: int, rata_rata: float
) -> ProgressSubkompetensi:
    return ProgressSubkompetensi(
        subkompetensi_id=subkompetensi_id,
        jumlah_materi=jumlah_materi,
        rata_rata_persentase=rata_rata,
    )
