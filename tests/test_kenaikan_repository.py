"""Test orkestrasi Kenaikan Tingkat (tiket 03): AksesTingkatSiswa,
AturanKenaikanTingkat, RiwayatEvaluasiKenaikan.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import (
    AksesTingkatSiswa,
    AturanKenaikanTingkat,
    HasilTes,
    JenisTes,
    TingkatSeleksi,
)
from data_analytics.repository import (
    BreakdownSubkompetensi,
    catat_hasil_tes,
    evaluasi_dan_catat_kenaikan,
    get_akses_siswa,
    get_semua_aturan_kenaikan,
    inisialisasi_akses_siswa,
    override_akses_admin,
    update_aturan_kenaikan,
)


def _buat_tingkat(session: Session) -> tuple[TingkatSeleksi, TingkatSeleksi, TingkatSeleksi]:
    kab = TingkatSeleksi(nama="Kabupaten", urutan=1)
    prov = TingkatSeleksi(nama="Provinsi", urutan=2)
    nas = TingkatSeleksi(nama="Nasional", urutan=3)
    session.add_all([kab, prov, nas])
    session.flush()
    return kab, prov, nas


def _buat_aturan(
    session: Session, tingkat_asal: TingkatSeleksi, tingkat_tujuan: TingkatSeleksi, **kwargs
) -> AturanKenaikanTingkat:
    aturan = AturanKenaikanTingkat(
        tingkat_asal_id=tingkat_asal.id,
        tingkat_tujuan_id=tingkat_tujuan.id,
        skor_simulasi_min=kwargs.get("skor_simulasi_min", 75.0),
        persentase_kompetensi_cukup_min=kwargs.get("persentase_kompetensi_cukup_min", 80.0),
        aktif=kwargs.get("aktif", True),
    )
    session.add(aturan)
    session.flush()
    return aturan


def _buat_hasil_tes(session: Session, *, siswa_id: str = "siswa-1") -> HasilTes:
    return catat_hasil_tes(
        session,
        siswa_id=siswa_id,
        tingkat_seleksi_id="tk-1",
        jenis_tes=JenisTes.SIMULASI,
        simulasi_id="sim-1",
        total_soal=10,
        jumlah_benar=8,
        breakdown_subkompetensi=[
            BreakdownSubkompetensi(subkompetensi_id="sk-1", jumlah_soal=10, jumlah_benar=8)
        ],
        diselesaikan_pada=datetime.now(timezone.utc),
    )


class TestInisialisasiAksesSiswa:
    def test_tingkat_pertama_default_terbuka_sisanya_terkunci(self, session: Session) -> None:
        kab, prov, nas = _buat_tingkat(session)

        akses = inisialisasi_akses_siswa(session, "siswa-1")

        by_tingkat = {a.tingkat_seleksi_id: a for a in akses}
        assert by_tingkat[kab.id].status == "terbuka"
        assert by_tingkat[kab.id].dibuka_karena == "default_awal"
        assert by_tingkat[prov.id].status == "terkunci"
        assert by_tingkat[nas.id].status == "terkunci"

    def test_idempoten_tidak_duplikat_baris(self, session: Session) -> None:
        _buat_tingkat(session)

        inisialisasi_akses_siswa(session, "siswa-1")
        akses_kedua = inisialisasi_akses_siswa(session, "siswa-1")

        assert len(akses_kedua) == 3
        total_rows = session.scalars(
            select(AksesTingkatSiswa).where(AksesTingkatSiswa.siswa_id == "siswa-1")
        ).all()
        assert len(total_rows) == 3


class TestGetAksesSiswa:
    def test_menginisialisasi_otomatis_kalau_belum_pernah_ada(self, session: Session) -> None:
        kab, _, _ = _buat_tingkat(session)

        akses = get_akses_siswa(session, "siswa-baru")

        assert len(akses) == 3
        assert {a.tingkat_seleksi_id: a.status for a in akses}[kab.id] == "terbuka"


class TestOverrideAksesAdmin:
    def test_buka_akses_tingkat_belum_ada_baris(self, session: Session) -> None:
        _, prov, _ = _buat_tingkat(session)

        akses = override_akses_admin(
            session, siswa_id="siswa-1", tingkat_seleksi_id=prov.id, status="terbuka"
        )

        assert akses.status == "terbuka"
        assert akses.dibuka_karena == "manual_admin"
        assert akses.dibuka_pada is not None

    def test_override_baris_yang_sudah_ada(self, session: Session) -> None:
        kab, _, _ = _buat_tingkat(session)
        inisialisasi_akses_siswa(session, "siswa-1")

        akses = override_akses_admin(
            session,
            siswa_id="siswa-1",
            tingkat_seleksi_id=kab.id,
            status="terkunci",
            catatan="Dikunci ulang manual",
        )

        assert akses.status == "terkunci"
        assert akses.catatan == "Dikunci ulang manual"


class TestEvaluasiDanCatatKenaikan:
    def test_lulus_membuka_akses_tingkat_tujuan_permanen(self, session: Session) -> None:
        kab, prov, _ = _buat_tingkat(session)
        _buat_aturan(session, kab, prov, skor_simulasi_min=75.0, persentase_kompetensi_cukup_min=80.0)
        hasil_tes = _buat_hasil_tes(session)

        riwayat = evaluasi_dan_catat_kenaikan(
            session,
            siswa_id="siswa-1",
            hasil_tes_id=hasil_tes.id,
            tingkat_asal_id=kab.id,
            skor=80.0,
            jumlah_kompetensi_cukup=4,
            total_kompetensi_silabus=5,
        )

        assert riwayat is not None
        assert riwayat.hasil_evaluasi == "lulus"

        akses_prov = session.scalars(
            select(AksesTingkatSiswa).where(
                AksesTingkatSiswa.siswa_id == "siswa-1",
                AksesTingkatSiswa.tingkat_seleksi_id == prov.id,
            )
        ).one()
        assert akses_prov.status == "terbuka"
        assert akses_prov.dibuka_karena == "lulus_evaluasi"
        assert akses_prov.hasil_tes_id == hasil_tes.id

    def test_tidak_lulus_tidak_membuka_akses(self, session: Session) -> None:
        kab, prov, _ = _buat_tingkat(session)
        _buat_aturan(session, kab, prov, skor_simulasi_min=75.0, persentase_kompetensi_cukup_min=80.0)
        hasil_tes = _buat_hasil_tes(session)

        riwayat = evaluasi_dan_catat_kenaikan(
            session,
            siswa_id="siswa-1",
            hasil_tes_id=hasil_tes.id,
            tingkat_asal_id=kab.id,
            skor=60.0,
            jumlah_kompetensi_cukup=4,
            total_kompetensi_silabus=5,
        )

        assert riwayat is not None
        assert riwayat.hasil_evaluasi == "tidak_lulus"
        akses_prov = session.scalars(
            select(AksesTingkatSiswa).where(
                AksesTingkatSiswa.siswa_id == "siswa-1",
                AksesTingkatSiswa.tingkat_seleksi_id == prov.id,
            )
        ).one_or_none()
        assert akses_prov is None

    def test_tidak_ada_aturan_aktif_mengembalikan_none(self, session: Session) -> None:
        kab, _, nas = _buat_tingkat(session)
        hasil_tes = _buat_hasil_tes(session)

        riwayat = evaluasi_dan_catat_kenaikan(
            session,
            siswa_id="siswa-1",
            hasil_tes_id=hasil_tes.id,
            tingkat_asal_id=nas.id,
            skor=95.0,
            jumlah_kompetensi_cukup=5,
            total_kompetensi_silabus=5,
        )

        assert riwayat is None

    def test_aturan_nonaktif_diabaikan(self, session: Session) -> None:
        kab, prov, _ = _buat_tingkat(session)
        _buat_aturan(session, kab, prov, aktif=False)
        hasil_tes = _buat_hasil_tes(session)

        riwayat = evaluasi_dan_catat_kenaikan(
            session,
            siswa_id="siswa-1",
            hasil_tes_id=hasil_tes.id,
            tingkat_asal_id=kab.id,
            skor=95.0,
            jumlah_kompetensi_cukup=5,
            total_kompetensi_silabus=5,
        )

        assert riwayat is None


class TestAturanKenaikanCrud:
    def test_get_semua_aturan_terurut_by_id(self, session: Session) -> None:
        kab, prov, nas = _buat_tingkat(session)
        _buat_aturan(session, kab, prov)
        _buat_aturan(session, prov, nas)

        semua = get_semua_aturan_kenaikan(session)

        assert [a.tingkat_asal_id for a in semua] == [kab.id, prov.id]

    def test_update_aturan_mengubah_field_yang_diberikan_saja(self, session: Session) -> None:
        kab, prov, _ = _buat_tingkat(session)
        aturan = _buat_aturan(session, kab, prov, skor_simulasi_min=75.0)

        updated = update_aturan_kenaikan(session, aturan_id=aturan.id, skor_simulasi_min=85.0)

        assert updated is not None
        assert updated.skor_simulasi_min == 85.0
        assert updated.persentase_kompetensi_cukup_min == 80.0

    def test_update_aturan_tidak_ditemukan_mengembalikan_none(self, session: Session) -> None:
        assert update_aturan_kenaikan(session, aturan_id=999, aktif=False) is None
