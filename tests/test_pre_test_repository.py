"""Test repository dan database logic Pre-Test berjenjang (tiket 15)."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import (
    AksesTingkatSiswa,
    AturanPreTest,
    HasilTes,
    JenisTes,
    RiwayatEvaluasiPreTest,
    TingkatSeleksi,
)
from data_analytics.repository import (
    BreakdownSubkompetensi,
    catat_hasil_tes,
    evaluasi_dan_catat_pre_test,
    get_or_create_aturan_pre_test,
    get_semua_aturan_pre_test,
    inisialisasi_akses_siswa,
    update_aturan_pre_test,
)


def _buat_tingkat(session: Session) -> tuple[TingkatSeleksi, TingkatSeleksi, TingkatSeleksi]:
    kab = TingkatSeleksi(nama="Kabupaten", urutan=1)
    prov = TingkatSeleksi(nama="Provinsi", urutan=2)
    nas = TingkatSeleksi(nama="Nasional", urutan=3)
    session.add_all([kab, prov, nas])
    session.flush()
    return kab, prov, nas


def _buat_hasil_tes(session: Session, *, siswa_id: str = "siswa-1") -> HasilTes:
    return catat_hasil_tes(
        session,
        siswa_id=siswa_id,
        tingkat_seleksi_id="tk-1",
        jenis_tes=JenisTes.PRE_TEST,
        total_soal=10,
        jumlah_benar=8,
        breakdown_subkompetensi=[
            BreakdownSubkompetensi(subkompetensi_id="sk-1", jumlah_soal=10, jumlah_benar=8)
        ],
        diselesaikan_pada=datetime.now(timezone.utc),
    )


class TestAturanPreTestRepository:
    def test_get_or_create_aturan_seeding_otomatis(self, session: Session) -> None:
        kab, prov, nas = _buat_tingkat(session)

        aturan = get_or_create_aturan_pre_test(session)
        assert len(aturan) == 3

        by_tingkat = {a.tingkat_seleksi_id: a for a in aturan}
        assert by_tingkat[kab.id].skor_min == 70.0
        assert by_tingkat[prov.id].skor_min == 75.0
        assert by_tingkat[nas.id].skor_min == 80.0

    def test_get_or_create_aturan_idempoten(self, session: Session) -> None:
        _buat_tingkat(session)

        pertama = get_or_create_aturan_pre_test(session)
        kedua = get_or_create_aturan_pre_test(session)

        assert len(pertama) == 3
        assert len(kedua) == 3
        total_rows = session.scalars(select(AturanPreTest)).all()
        assert len(total_rows) == 3

    def test_update_aturan_pre_test(self, session: Session) -> None:
        kab, _, _ = _buat_tingkat(session)
        get_or_create_aturan_pre_test(session)

        aturan_kab = session.scalars(
            select(AturanPreTest).where(AturanPreTest.tingkat_seleksi_id == kab.id)
        ).one()

        updated = update_aturan_pre_test(session, aturan_id=aturan_kab.id, skor_min=72.5)
        assert updated is not None
        assert updated.skor_min == 72.5

    def test_update_aturan_pre_test_tidak_ditemukan(self, session: Session) -> None:
        assert update_aturan_pre_test(session, aturan_id=9999, skor_min=80.0) is None


class TestEvaluasiDanCatatPreTest:
    def test_lulus_pre_test_buka_simulasi_dan_tingkat_berikutnya(self, session: Session) -> None:
        kab, prov, nas = _buat_tingkat(session)
        get_or_create_aturan_pre_test(session)
        hasil_tes = _buat_hasil_tes(session)

        riwayat, simulasi_terbuka, tingkat_berikutnya_terbuka = evaluasi_dan_catat_pre_test(
            session,
            siswa_id="siswa-1",
            hasil_tes_id=hasil_tes.id,
            tingkat_seleksi_id=kab.id,
            skor=75.0,
        )

        assert riwayat is not None
        assert riwayat.lulus is True
        assert simulasi_terbuka is True
        assert tingkat_berikutnya_terbuka is True

        # Cek database: simulasi Kabupaten terbuka
        akses_kab = session.scalars(
            select(AksesTingkatSiswa).where(
                AksesTingkatSiswa.siswa_id == "siswa-1",
                AksesTingkatSiswa.tingkat_seleksi_id == kab.id,
            )
        ).one()
        assert akses_kab.simulasi_terbuka is True

        # Cek database: akses Provinsi terbuka karena lulus pre-test
        akses_prov = session.scalars(
            select(AksesTingkatSiswa).where(
                AksesTingkatSiswa.siswa_id == "siswa-1",
                AksesTingkatSiswa.tingkat_seleksi_id == prov.id,
            )
        ).one()
        assert akses_prov.status == "terbuka"
        assert akses_prov.dibuka_karena == "lulus_pre_test"

        # Cek database: Nasional masih terkunci
        akses_nas = session.scalars(
            select(AksesTingkatSiswa).where(
                AksesTingkatSiswa.siswa_id == "siswa-1",
                AksesTingkatSiswa.tingkat_seleksi_id == nas.id,
            )
        ).one()
        assert akses_nas.status == "terkunci"

    def test_gagal_pre_test_simulasi_dan_tingkat_berikutnya_tetap_terkunci(
        self, session: Session
    ) -> None:
        kab, prov, _ = _buat_tingkat(session)
        get_or_create_aturan_pre_test(session)
        hasil_tes = _buat_hasil_tes(session)

        riwayat, simulasi_terbuka, tingkat_berikutnya_terbuka = evaluasi_dan_catat_pre_test(
            session,
            siswa_id="siswa-1",
            hasil_tes_id=hasil_tes.id,
            tingkat_seleksi_id=kab.id,
            skor=65.0,
        )

        assert riwayat is not None
        assert riwayat.lulus is False
        assert simulasi_terbuka is False
        assert tingkat_berikutnya_terbuka is False

        akses_kab = session.scalars(
            select(AksesTingkatSiswa).where(
                AksesTingkatSiswa.siswa_id == "siswa-1",
                AksesTingkatSiswa.tingkat_seleksi_id == kab.id,
            )
        ).one()
        assert akses_kab.simulasi_terbuka is False

        akses_prov = session.scalars(
            select(AksesTingkatSiswa).where(
                AksesTingkatSiswa.siswa_id == "siswa-1",
                AksesTingkatSiswa.tingkat_seleksi_id == prov.id,
            )
        ).one()
        assert akses_prov.status == "terkunci"

    def test_unidirectional_akses_yang_sudah_terbuka_tidak_dicabut(
        self, session: Session
    ) -> None:
        kab, prov, _ = _buat_tingkat(session)
        get_or_create_aturan_pre_test(session)
        hasil_tes = _buat_hasil_tes(session)

        # Pertama: Lulus
        evaluasi_dan_catat_pre_test(
            session,
            siswa_id="siswa-1",
            hasil_tes_id=hasil_tes.id,
            tingkat_seleksi_id=kab.id,
            skor=80.0,
        )

        # Kedua: Mencoba lagi dengan nilai di bawah KKM
        riwayat2, simulasi_terbuka, tingkat_berikutnya_terbuka = evaluasi_dan_catat_pre_test(
            session,
            siswa_id="siswa-1",
            hasil_tes_id=hasil_tes.id,
            tingkat_seleksi_id=kab.id,
            skor=50.0,
        )

        assert riwayat2.lulus is False
        # Hak akses simulasi dan jenjang berikutnya tetap bertahan (unidirectional)
        assert simulasi_terbuka is True
        assert tingkat_berikutnya_terbuka is True

        akses_kab = session.scalars(
            select(AksesTingkatSiswa).where(
                AksesTingkatSiswa.siswa_id == "siswa-1",
                AksesTingkatSiswa.tingkat_seleksi_id == kab.id,
            )
        ).one()
        assert akses_kab.simulasi_terbuka is True

        akses_prov = session.scalars(
            select(AksesTingkatSiswa).where(
                AksesTingkatSiswa.siswa_id == "siswa-1",
                AksesTingkatSiswa.tingkat_seleksi_id == prov.id,
            )
        ).one()
        assert akses_prov.status == "terbuka"

    def test_lulus_pre_test_tingkat_tertinggi(self, session: Session) -> None:
        _, _, nas = _buat_tingkat(session)
        get_or_create_aturan_pre_test(session)
        hasil_tes = _buat_hasil_tes(session)

        riwayat, simulasi_terbuka, tingkat_berikutnya_terbuka = evaluasi_dan_catat_pre_test(
            session,
            siswa_id="siswa-1",
            hasil_tes_id=hasil_tes.id,
            tingkat_seleksi_id=nas.id,
            skor=85.0,
        )

        assert riwayat is not None
        assert riwayat.lulus is True
        assert simulasi_terbuka is True
        assert tingkat_berikutnya_terbuka is False  # Tidak ada tingkat lanjutan setelah Nasional

