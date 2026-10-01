import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import AturanPredikat
from data_analytics.repository import (
    get_or_create_aturan_predikat,
    set_aturan_predikat,
)

TINGKAT_KABUPATEN = "1"
TINGKAT_PROVINSI = "2"


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
