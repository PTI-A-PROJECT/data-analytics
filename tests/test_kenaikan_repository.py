"""Test akses tingkat & aturan kenaikan (tiket 03, fase 2 issue 02):
AksesTingkatSiswa, AturanKenaikanTingkat. Evaluasi jalur cepat dites lewat alur
HTTP di test_api_pretest.py.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import (
    AksesTingkatSiswa,
    AturanKenaikanTingkat,
    StatusAkses,
    TingkatSeleksi,
)
from data_analytics.repository import (
    get_akses_siswa,
    get_semua_aturan_kenaikan,
    inisialisasi_akses_siswa,
    override_akses_admin,
    update_aturan_kenaikan,
)


def _buat_tingkat(session: Session) -> tuple[TingkatSeleksi, TingkatSeleksi]:
    kab = TingkatSeleksi(nama="Kabupaten", urutan=1)
    prov = TingkatSeleksi(nama="Provinsi", urutan=2)
    session.add_all([kab, prov])
    session.flush()
    return kab, prov


def _buat_aturan(
    session: Session, tingkat_asal: TingkatSeleksi, tingkat_tujuan: TingkatSeleksi
) -> AturanKenaikanTingkat:
    aturan = AturanKenaikanTingkat(
        tingkat_asal_id=tingkat_asal.id,
        tingkat_tujuan_id=tingkat_tujuan.id,
        skor_simulasi_min=75.0,
        skor_pretest_jalur_cepat=90.0,
        rata_level_min=2.0,
    )
    session.add(aturan)
    session.flush()
    return aturan


class TestInisialisasiAksesSiswa:
    def test_tingkat_pertama_pretest_terbuka_sisanya_terkunci(self, session: Session) -> None:
        kab, prov = _buat_tingkat(session)

        akses = inisialisasi_akses_siswa(session, "siswa-1")

        by_tingkat = {a.tingkat_seleksi_id: a for a in akses}
        assert by_tingkat[kab.id].status == StatusAkses.PRETEST_TERBUKA
        assert by_tingkat[kab.id].dibuka_karena == "default_awal"
        assert by_tingkat[prov.id].status == StatusAkses.TERKUNCI

    def test_idempoten_tidak_duplikat_baris(self, session: Session) -> None:
        _buat_tingkat(session)

        inisialisasi_akses_siswa(session, "siswa-1")
        akses_kedua = inisialisasi_akses_siswa(session, "siswa-1")

        assert len(akses_kedua) == 2
        total_rows = session.scalars(
            select(AksesTingkatSiswa).where(AksesTingkatSiswa.siswa_id == "siswa-1")
        ).all()
        assert len(total_rows) == 2


class TestGetAksesSiswa:
    def test_menginisialisasi_otomatis_kalau_belum_pernah_ada(self, session: Session) -> None:
        kab, _ = _buat_tingkat(session)

        akses = get_akses_siswa(session, "siswa-baru")

        assert len(akses) == 2
        assert {a.tingkat_seleksi_id: a.status for a in akses}[kab.id] == StatusAkses.PRETEST_TERBUKA


class TestOverrideAksesAdmin:
    def test_buka_akses_tingkat_belum_ada_baris(self, session: Session) -> None:
        _, prov = _buat_tingkat(session)

        akses = override_akses_admin(
            session, siswa_id="siswa-1", tingkat_seleksi_id=prov.id, status=StatusAkses.TERBUKA
        )

        assert akses.status == StatusAkses.TERBUKA
        assert akses.dibuka_karena == "override_admin"
        assert akses.dibuka_pada is not None

    def test_override_bisa_menurunkan_status(self, session: Session) -> None:
        kab, _ = _buat_tingkat(session)
        inisialisasi_akses_siswa(session, "siswa-1")

        akses = override_akses_admin(
            session,
            siswa_id="siswa-1",
            tingkat_seleksi_id=kab.id,
            status=StatusAkses.TERKUNCI,
            catatan="Dikunci ulang manual",
        )

        assert akses.status == StatusAkses.TERKUNCI
        assert akses.catatan == "Dikunci ulang manual"


class TestAturanKenaikanCrud:
    def test_get_semua_aturan_terurut_by_id(self, session: Session) -> None:
        kab, prov = _buat_tingkat(session)
        _buat_aturan(session, kab, prov)
        _buat_aturan(session, prov, kab)

        semua = get_semua_aturan_kenaikan(session)

        assert [a.tingkat_asal_id for a in semua] == [kab.id, prov.id]

    def test_update_aturan_mengubah_field_yang_diberikan_saja(self, session: Session) -> None:
        kab, prov = _buat_tingkat(session)
        aturan = _buat_aturan(session, kab, prov)

        updated = update_aturan_kenaikan(session, aturan_id=aturan.id, rata_level_min=2.5)

        assert updated is not None
        assert updated.rata_level_min == 2.5
        assert updated.skor_pretest_jalur_cepat == 90.0
        assert updated.skor_simulasi_min == 75.0

    def test_update_aturan_tidak_ditemukan_mengembalikan_none(self, session: Session) -> None:
        assert update_aturan_kenaikan(session, aturan_id=999, aktif=False) is None
