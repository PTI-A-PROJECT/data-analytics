"""Test script seed data uji (tiket 09)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data_analytics.models import (
    AturanPemetaan,
    AturanPredikat,
    HasilTes,
    Kompetensi,
    Soal,
    Subkompetensi,
    TingkatSeleksi,
)
from data_analytics.scripts.seed import seed


def _hitung(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


class TestSeed:
    def test_membuat_dataset_sesuai_spesifikasi(self, session: Session) -> None:
        seed(session)

        assert _hitung(session, TingkatSeleksi) == 3
        assert _hitung(session, AturanPredikat) == 12  # 4 predikat x 3 tingkat
        assert _hitung(session, AturanPemetaan) == 3  # 1 per tingkat
        assert _hitung(session, Kompetensi) == 2
        assert _hitung(session, Subkompetensi) == 4
        assert _hitung(session, Soal) == 15
        assert _hitung(session, HasilTes) == 2  # 2 dummy siswa

    def test_idempoten_tidak_menduplikasi_saat_dijalankan_dua_kali(
        self, session: Session
    ) -> None:
        seed(session)
        seed(session)

        assert _hitung(session, TingkatSeleksi) == 3
        assert _hitung(session, Soal) == 15
        assert _hitung(session, HasilTes) == 2

    def test_soal_seimbang_antar_subkompetensi(self, session: Session) -> None:
        seed(session)

        jumlah_per_sub = session.scalars(
            select(func.count()).select_from(Soal).group_by(Soal.subkompetensi_id)
        ).all()

        assert sum(jumlah_per_sub) == 15
        assert max(jumlah_per_sub) - min(jumlah_per_sub) <= 1

    def test_dummy_sekolah_konsisten_di_semua_hasil_tes(self, session: Session) -> None:
        seed(session)

        hasil = session.scalars(select(HasilTes)).all()
        assert {h.sekolah_id for h in hasil} == {1}
        assert {h.siswa_id for h in hasil} == {1, 2}
