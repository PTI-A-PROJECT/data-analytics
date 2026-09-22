from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import HasilTes
from data_analytics.repository import anonimkan_hasil_tes_kedaluwarsa

RETENSI_BULAN = 24


class TestAnonimkanHasilTesKedaluwarsa:
    def test_hasil_tes_lama_dianonimkan(
        self, session: Session, buat_hasil_tes: Callable[..., HasilTes]
    ) -> None:
        sekarang = datetime(2026, 9, 22, tzinfo=timezone.utc)
        lama = sekarang - timedelta(days=RETENSI_BULAN * 31 + 10)  # jelas lewat retensi
        hasil = buat_hasil_tes(dibuat_pada=lama)

        jumlah = anonimkan_hasil_tes_kedaluwarsa(
            session, retention_months=RETENSI_BULAN, sekarang=sekarang
        )

        session.refresh(hasil)
        assert jumlah == 1
        assert hasil.siswa_id is None
        assert hasil.is_anonymized is True

    def test_data_agregat_tetap_utuh(
        self, session: Session, buat_hasil_tes: Callable[..., HasilTes]
    ) -> None:
        sekarang = datetime(2026, 9, 22, tzinfo=timezone.utc)
        lama = sekarang - timedelta(days=RETENSI_BULAN * 31 + 10)
        hasil = buat_hasil_tes(dibuat_pada=lama)

        anonimkan_hasil_tes_kedaluwarsa(session, retention_months=RETENSI_BULAN, sekarang=sekarang)

        session.refresh(hasil)
        assert hasil.sekolah_id == "7"  # tetap - dipakai agregasi Dashboard Admin
        assert hasil.skor == 80.0
        assert hasil.predikat_label == "Baik"
        assert hasil.tingkat_seleksi_id == "1"

    def test_hasil_tes_baru_tidak_disentuh(
        self, session: Session, buat_hasil_tes: Callable[..., HasilTes]
    ) -> None:
        sekarang = datetime(2026, 9, 22, tzinfo=timezone.utc)
        baru = sekarang - timedelta(days=10)
        hasil = buat_hasil_tes(dibuat_pada=baru)

        jumlah = anonimkan_hasil_tes_kedaluwarsa(
            session, retention_months=RETENSI_BULAN, sekarang=sekarang
        )

        session.refresh(hasil)
        assert jumlah == 0
        assert hasil.siswa_id == "1"
        assert hasil.is_anonymized is False

    def test_dry_run_tidak_mengubah_data(
        self, session: Session, buat_hasil_tes: Callable[..., HasilTes]
    ) -> None:
        sekarang = datetime(2026, 9, 22, tzinfo=timezone.utc)
        lama = sekarang - timedelta(days=RETENSI_BULAN * 31 + 10)
        hasil = buat_hasil_tes(dibuat_pada=lama)

        jumlah = anonimkan_hasil_tes_kedaluwarsa(
            session, retention_months=RETENSI_BULAN, sekarang=sekarang, dry_run=True
        )

        session.refresh(hasil)
        assert jumlah == 1  # tetap melaporkan berapa yang AKAN terdampak
        assert hasil.siswa_id == "1"  # tapi tidak benar-benar diubah
        assert hasil.is_anonymized is False

    def test_idempoten_baris_yang_sudah_dianonimkan_tidak_dihitung_ulang(
        self, session: Session, buat_hasil_tes: Callable[..., HasilTes]
    ) -> None:
        sekarang = datetime(2026, 9, 22, tzinfo=timezone.utc)
        lama = sekarang - timedelta(days=RETENSI_BULAN * 31 + 10)
        buat_hasil_tes(dibuat_pada=lama)

        anonimkan_hasil_tes_kedaluwarsa(session, retention_months=RETENSI_BULAN, sekarang=sekarang)
        jumlah_kedua = anonimkan_hasil_tes_kedaluwarsa(
            session, retention_months=RETENSI_BULAN, sekarang=sekarang
        )

        assert jumlah_kedua == 0

    def test_hanya_baris_kedaluwarsa_yang_terdampak(
        self, session: Session, buat_hasil_tes: Callable[..., HasilTes]
    ) -> None:
        sekarang = datetime(2026, 9, 22, tzinfo=timezone.utc)
        lama = sekarang - timedelta(days=RETENSI_BULAN * 31 + 10)
        baru = sekarang - timedelta(days=10)
        hasil_lama = buat_hasil_tes(dibuat_pada=lama, siswa_id="1")
        hasil_baru = buat_hasil_tes(dibuat_pada=baru, siswa_id="2")

        anonimkan_hasil_tes_kedaluwarsa(session, retention_months=RETENSI_BULAN, sekarang=sekarang)

        semua = session.scalars(select(HasilTes)).all()
        assert {h.id: h.siswa_id for h in semua} == {
            hasil_lama.id: None,
            hasil_baru.id: "2",
        }
