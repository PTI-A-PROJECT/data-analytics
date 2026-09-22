from collections.abc import Sequence
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import AturanPredikat, HasilTes, JawabanSiswa, JenisTes, StatusPemetaan
from data_analytics.repository import (
    BreakdownSubkompetensi,
    JawabanInput,
    catat_hasil_tes,
    catat_submission_tes,
    get_or_create_aturan_predikat,
    set_aturan_predikat,
)

TINGKAT_KABUPATEN = "1"
TINGKAT_PROVINSI = "2"


def _breakdown(*triples: tuple[str, int, int]) -> list[BreakdownSubkompetensi]:
    return [
        BreakdownSubkompetensi(subkompetensi_id=s, jumlah_soal=js, jumlah_benar=jb)
        for s, js, jb in triples
    ]


def _catat_hasil_tes_default(
    session: Session,
    *,
    jenis_tes: JenisTes = JenisTes.PRE_TEST,
    simulasi_id: str | None = None,
    total_soal: int = 10,
    jumlah_benar: int = 8,
    breakdown_subkompetensi: Sequence[BreakdownSubkompetensi] | None = None,
    sekolah_id: str | None = None,
) -> HasilTes:
    return catat_hasil_tes(
        session,
        siswa_id="1",
        tingkat_seleksi_id=TINGKAT_KABUPATEN,
        jenis_tes=jenis_tes,
        simulasi_id=simulasi_id,
        total_soal=total_soal,
        jumlah_benar=jumlah_benar,
        breakdown_subkompetensi=breakdown_subkompetensi or _breakdown(("1", total_soal, jumlah_benar)),
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
            breakdown_subkompetensi=_breakdown(("1", 6, 5), ("2", 4, 3)),
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
            _catat_hasil_tes_default(session, jenis_tes=JenisTes.PRE_TEST, simulasi_id="99")

    def test_simulasi_dengan_simulasi_id_valid(self, session: Session) -> None:
        hasil = _catat_hasil_tes_default(
            session, jenis_tes=JenisTes.SIMULASI, simulasi_id="42"
        )

        assert hasil.simulasi_id == "42"

    def test_breakdown_tidak_sama_dengan_total_soal_menaikkan_error(
        self, session: Session
    ) -> None:
        with pytest.raises(ValueError, match="total_soal"):
            _catat_hasil_tes_default(
                session,
                total_soal=10,
                jumlah_benar=8,
                breakdown_subkompetensi=_breakdown(("1", 5, 4)),  # cuma 5, bukan 10
            )

    def test_sekolah_id_disimpan_sebagai_snapshot(self, session: Session) -> None:
        hasil = _catat_hasil_tes_default(session, sekolah_id="7")

        assert hasil.sekolah_id == "7"

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

    def test_breakdown_membawa_status_pemetaan_dan_butuh_optimasi(
        self, session: Session
    ) -> None:
        # representasi 100% (valid), korektnes 100% >= ambang cukup default 70%.
        hasil = _catat_hasil_tes_default(
            session,
            total_soal=4,
            jumlah_benar=4,
            breakdown_subkompetensi=_breakdown(("1", 4, 4)),
        )

        breakdown = hasil.breakdown_subkompetensi[0]
        assert breakdown.status_pemetaan == StatusPemetaan.CUKUP
        assert breakdown.butuh_optimasi is False  # jumlah_benar_lambat default 0


def _jawaban(
    *,
    soal_id: str = "soal-1",
    subkompetensi_id: str = "1",
    jawaban_dipilih: str = "A",
    is_benar: bool = True,
    durasi_detik: int = 30,
    batas_waktu_detik: int = 60,
) -> JawabanInput:
    return JawabanInput(
        soal_id=soal_id,
        subkompetensi_id=subkompetensi_id,
        jawaban_dipilih=jawaban_dipilih,
        is_benar=is_benar,
        durasi_detik=durasi_detik,
        batas_waktu_detik=batas_waktu_detik,
    )


class TestCatatSubmissionTes:
    def test_menyimpan_hasil_tes_dan_log_jawaban(self, session: Session) -> None:
        jawaban = [
            _jawaban(soal_id="s1", subkompetensi_id="1"),
            _jawaban(soal_id="s2", subkompetensi_id="1"),
            _jawaban(soal_id="s3", subkompetensi_id="1"),
            _jawaban(soal_id="s4", subkompetensi_id="1", is_benar=False),
        ]

        hasil = catat_submission_tes(
            session,
            siswa_id="siswa-1",
            sekolah_id="sekolah-1",
            tingkat_seleksi_id=TINGKAT_KABUPATEN,
            jenis_tes=JenisTes.PRE_TEST,
            jawaban_siswa=jawaban,
            diselesaikan_pada=datetime.now(timezone.utc),
        )

        assert hasil.total_soal == 4
        assert hasil.jumlah_benar == 3
        assert hasil.skor == 75.0
        assert len(hasil.breakdown_subkompetensi) == 1
        assert hasil.breakdown_subkompetensi[0].jumlah_soal == 4
        assert hasil.breakdown_subkompetensi[0].jumlah_benar == 3

        log = session.scalars(
            select(JawabanSiswa).where(JawabanSiswa.hasil_tes_id == hasil.id)
        ).all()
        assert len(log) == 4
        assert {j.soal_id for j in log} == {"s1", "s2", "s3", "s4"}

    def test_mengelompokkan_per_subkompetensi(self, session: Session) -> None:
        jawaban = [
            _jawaban(soal_id="s1", subkompetensi_id="1", is_benar=True),
            _jawaban(soal_id="s2", subkompetensi_id="1", is_benar=False),
            _jawaban(soal_id="s3", subkompetensi_id="2", is_benar=True),
        ]

        hasil = catat_submission_tes(
            session,
            siswa_id="siswa-1",
            tingkat_seleksi_id=TINGKAT_KABUPATEN,
            jenis_tes=JenisTes.PRE_TEST,
            jawaban_siswa=jawaban,
            diselesaikan_pada=datetime.now(timezone.utc),
        )

        breakdown_by_sub = {b.subkompetensi_id: b for b in hasil.breakdown_subkompetensi}
        assert breakdown_by_sub["1"].jumlah_soal == 2
        assert breakdown_by_sub["1"].jumlah_benar == 1
        assert breakdown_by_sub["2"].jumlah_soal == 1
        assert breakdown_by_sub["2"].jumlah_benar == 1

    def test_is_lambat_dihitung_dari_durasi_vs_batas_waktu(self, session: Session) -> None:
        jawaban = [
            _jawaban(soal_id="s1", durasi_detik=85, batas_waktu_detik=60),  # lambat
            _jawaban(soal_id="s2", durasi_detik=30, batas_waktu_detik=60),  # tidak
        ]

        catat_submission_tes(
            session,
            siswa_id="siswa-1",
            tingkat_seleksi_id=TINGKAT_KABUPATEN,
            jenis_tes=JenisTes.PRE_TEST,
            jawaban_siswa=jawaban,
            diselesaikan_pada=datetime.now(timezone.utc),
        )

        log = {j.soal_id: j.is_lambat for j in session.scalars(select(JawabanSiswa)).all()}
        assert log == {"s1": True, "s2": False}

    def test_butuh_optimasi_true_saat_mayoritas_benar_lambat(self, session: Session) -> None:
        # 4 soal representasi 100% (valid), 4/4 benar (Cukup), 3/4 benar juga
        # lambat = 75% > 50% -> butuh_optimasi.
        jawaban = [
            _jawaban(soal_id="s1", is_benar=True, durasi_detik=90, batas_waktu_detik=60),
            _jawaban(soal_id="s2", is_benar=True, durasi_detik=90, batas_waktu_detik=60),
            _jawaban(soal_id="s3", is_benar=True, durasi_detik=90, batas_waktu_detik=60),
            _jawaban(soal_id="s4", is_benar=True, durasi_detik=30, batas_waktu_detik=60),
        ]

        hasil = catat_submission_tes(
            session,
            siswa_id="siswa-1",
            tingkat_seleksi_id=TINGKAT_KABUPATEN,
            jenis_tes=JenisTes.PRE_TEST,
            jawaban_siswa=jawaban,
            diselesaikan_pada=datetime.now(timezone.utc),
        )

        breakdown = hasil.breakdown_subkompetensi[0]
        assert breakdown.status_pemetaan == StatusPemetaan.CUKUP
        assert breakdown.butuh_optimasi is True

    def test_jawaban_siswa_kosong_menaikkan_error(self, session: Session) -> None:
        with pytest.raises(ValueError, match="jawaban_siswa"):
            catat_submission_tes(
                session,
                siswa_id="siswa-1",
                tingkat_seleksi_id=TINGKAT_KABUPATEN,
                jenis_tes=JenisTes.PRE_TEST,
                jawaban_siswa=[],
                diselesaikan_pada=datetime.now(timezone.utc),
            )
