from collections.abc import Sequence
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import AturanPredikat, HasilTes, JenisTes
from data_analytics.repository import (
    BreakdownSubkompetensi,
    catat_hasil_tes,
    get_or_create_aturan_predikat,
    set_aturan_predikat,
)

TINGKAT_KABUPATEN = 1
TINGKAT_PROVINSI = 2


def _breakdown(*triples: tuple[int, int, int]) -> list[BreakdownSubkompetensi]:
    return [
        BreakdownSubkompetensi(subkompetensi_id=s, jumlah_soal=js, jumlah_benar=jb)
        for s, js, jb in triples
    ]


def _catat_hasil_tes_default(
    session: Session,
    *,
    jenis_tes: JenisTes = JenisTes.PRE_TEST,
    simulasi_id: int | None = None,
    total_soal: int = 10,
    jumlah_benar: int = 8,
    breakdown_subkompetensi: Sequence[BreakdownSubkompetensi] | None = None,
    sekolah_id: int | None = None,
) -> HasilTes:
    return catat_hasil_tes(
        session,
        siswa_id=1,
        tingkat_seleksi_id=TINGKAT_KABUPATEN,
        jenis_tes=jenis_tes,
        simulasi_id=simulasi_id,
        total_soal=total_soal,
        jumlah_benar=jumlah_benar,
        breakdown_subkompetensi=breakdown_subkompetensi or _breakdown((1, total_soal, jumlah_benar)),
        diselesaikan_pada=datetime.now(timezone.utc),
        sekolah_id=sekolah_id,
    )


class TestGetOrCreateAturanPredikat:
    def test_seed_default_saat_belum_ada_aturan(self, session: Session) -> None:
        aturan = get_or_create_aturan_predikat(session, TINGKAT_KABUPATEN)

        labels = {a.label: a.batas_bawah for a in aturan}
        assert labels == {
            "Sangat Baik": 90,
            "Baik": 80,
            "Cukup": 70,
            "Perlu Latihan": 0,
        }

    def test_idempoten_tidak_membuat_duplikat(self, session: Session) -> None:
        get_or_create_aturan_predikat(session, TINGKAT_KABUPATEN)
        get_or_create_aturan_predikat(session, TINGKAT_KABUPATEN)

        semua = session.scalars(
            select(AturanPredikat).where(
                AturanPredikat.tingkat_seleksi_id == TINGKAT_KABUPATEN
            )
        ).all()
        assert len(semua) == 4

    def test_tidak_menimpa_aturan_kustom_yang_sudah_ada(self, session: Session) -> None:
        set_aturan_predikat(
            session, TINGKAT_KABUPATEN, [("Lulus", 60), ("Tidak Lulus", 0)]
        )

        aturan = get_or_create_aturan_predikat(session, TINGKAT_KABUPATEN)

        assert {a.label for a in aturan} == {"Lulus", "Tidak Lulus"}

    def test_tiap_tingkat_seleksi_punya_aturan_independen(self, session: Session) -> None:
        get_or_create_aturan_predikat(session, TINGKAT_KABUPATEN)
        set_aturan_predikat(session, TINGKAT_PROVINSI, [("Lulus", 95), ("Gagal", 0)])

        aturan_provinsi = get_or_create_aturan_predikat(session, TINGKAT_PROVINSI)

        assert {a.label for a in aturan_provinsi} == {"Lulus", "Gagal"}


class TestSetAturanPredikat:
    def test_mengganti_seluruh_aturan_lama(self, session: Session) -> None:
        get_or_create_aturan_predikat(session, TINGKAT_KABUPATEN)  # seed default dulu

        set_aturan_predikat(session, TINGKAT_KABUPATEN, [("Lulus", 60), ("Gagal", 0)])

        aturan = session.scalars(
            select(AturanPredikat).where(
                AturanPredikat.tingkat_seleksi_id == TINGKAT_KABUPATEN
            )
        ).all()
        assert {a.label for a in aturan} == {"Lulus", "Gagal"}

    def test_menolak_batas_bawah_di_luar_rentang(self, session: Session) -> None:
        with pytest.raises(ValueError, match="0 dan 100"):
            set_aturan_predikat(session, TINGKAT_KABUPATEN, [("Lulus", 150), ("Gagal", 0)])

    def test_menolak_batas_bawah_negatif(self, session: Session) -> None:
        with pytest.raises(ValueError, match="0 dan 100"):
            set_aturan_predikat(session, TINGKAT_KABUPATEN, [("Lulus", 60), ("Gagal", -5)])

    def test_menolak_tanpa_predikat_dasar(self, session: Session) -> None:
        with pytest.raises(ValueError, match="batas_bawah=0"):
            set_aturan_predikat(session, TINGKAT_KABUPATEN, [("Lulus", 60)])

    def test_menolak_aturan_kosong(self, session: Session) -> None:
        with pytest.raises(ValueError, match="tidak boleh kosong"):
            set_aturan_predikat(session, TINGKAT_KABUPATEN, [])


class TestCatatHasilTes:
    def test_pre_test_dasar(self, session: Session) -> None:
        hasil = _catat_hasil_tes_default(
            session,
            total_soal=10,
            jumlah_benar=8,
            breakdown_subkompetensi=_breakdown((1, 6, 5), (2, 4, 3)),
        )

        assert hasil.jumlah_salah == 2
        assert hasil.skor == 80.0
        assert hasil.predikat_label == "Baik"
        assert hasil.simulasi_id is None
        assert len(hasil.breakdown_subkompetensi) == 2

    def test_simulasi_wajib_simulasi_id(self, session: Session) -> None:
        with pytest.raises(ValueError, match="simulasi_id"):
            _catat_hasil_tes_default(session, jenis_tes=JenisTes.SIMULASI)

    def test_pre_test_menolak_simulasi_id(self, session: Session) -> None:
        with pytest.raises(ValueError, match="simulasi_id"):
            _catat_hasil_tes_default(session, jenis_tes=JenisTes.PRE_TEST, simulasi_id=99)

    def test_simulasi_dengan_simulasi_id_valid(self, session: Session) -> None:
        hasil = _catat_hasil_tes_default(
            session, jenis_tes=JenisTes.SIMULASI, simulasi_id=42
        )

        assert hasil.simulasi_id == 42

    def test_breakdown_tidak_sama_dengan_total_soal_menaikkan_error(
        self, session: Session
    ) -> None:
        with pytest.raises(ValueError, match="total_soal"):
            _catat_hasil_tes_default(
                session,
                total_soal=10,
                jumlah_benar=8,
                breakdown_subkompetensi=_breakdown((1, 5, 4)),  # cuma 5, bukan 10
            )

    def test_sekolah_id_disimpan_sebagai_snapshot(self, session: Session) -> None:
        hasil = _catat_hasil_tes_default(session, sekolah_id=7)

        assert hasil.sekolah_id == 7

    def test_sekolah_id_opsional_default_none(self, session: Session) -> None:
        hasil = _catat_hasil_tes_default(session)

        assert hasil.sekolah_id is None

    def test_predikat_dibekukan_tidak_berubah_saat_aturan_diubah_admin(
        self, session: Session
    ) -> None:
        hasil = _catat_hasil_tes_default(session, total_soal=10, jumlah_benar=8)
        assert hasil.predikat_label == "Baik"  # skor 80 -> default threshold

        # Super Admin mengubah ambang batas "Sangat Baik" jadi 75 setelah tes ini dibuat
        aturan_sangat_baik = session.scalars(
            select(AturanPredikat).where(
                AturanPredikat.tingkat_seleksi_id == TINGKAT_KABUPATEN,
                AturanPredikat.label == "Sangat Baik",
            )
        ).one()
        aturan_sangat_baik.batas_bawah = 75
        session.flush()

        session.refresh(hasil)
        assert hasil.predikat_label == "Baik"  # tetap, snapshot tidak dihitung ulang
