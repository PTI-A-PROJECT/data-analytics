"""Test migrasi Alembic — pastikan rantai revisi sampai head benar-benar membuat
semua tabel yang didefinisikan di data_analytics.models di PostgreSQL + pgvector,
dan aman dijalankan berulang (idempoten di posisi head).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from data_analytics.models import Base
from tests.conftest import TEST_DATABASE_URL

REPO_ROOT = Path(__file__).resolve().parent.parent
NAMA_DB_MIGRASI = "analytics_migrasi_test"


def _alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def database_url_kosong() -> Iterator[str]:
    """Database Postgres baru yang kosong (tanpa tabel & extension) — terpisah
    dari database fixture `engine`, yang skemanya dibuat lewat create_all.
    """
    admin = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {NAMA_DB_MIGRASI} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {NAMA_DB_MIGRASI}"))
    try:
        yield make_url(TEST_DATABASE_URL).set(database=NAMA_DB_MIGRASI).render_as_string(
            hide_password=False
        )
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {NAMA_DB_MIGRASI} WITH (FORCE)"))
        admin.dispose()


class TestMigrasi:
    def test_upgrade_head_membuat_semua_tabel(self, database_url_kosong: str) -> None:
        command.upgrade(_alembic_config(database_url_kosong), "head")

        engine = create_engine(database_url_kosong)
        try:
            tabel_dibuat = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

        tabel_diharapkan = set(Base.metadata.tables.keys())
        assert tabel_diharapkan <= tabel_dibuat

    def test_upgrade_head_menyediakan_tingkat_kabupaten_dan_provinsi(
        self, database_url_kosong: str
    ) -> None:
        command.upgrade(_alembic_config(database_url_kosong), "head")

        engine = create_engine(database_url_kosong)
        try:
            with engine.connect() as conn:
                tingkat = conn.execute(
                    text("SELECT urutan, nama FROM tingkat_seleksi ORDER BY urutan")
                ).all()
        finally:
            engine.dispose()

        assert [tuple(t) for t in tingkat] == [(1, "Kabupaten"), (2, "Provinsi")]

    def test_upgrade_head_menyediakan_aturan_default(self, database_url_kosong: str) -> None:
        command.upgrade(_alembic_config(database_url_kosong), "head")

        engine = create_engine(database_url_kosong)
        try:
            with engine.connect() as conn:
                aturan_kenaikan = conn.execute(
                    text(
                        "SELECT skor_simulasi_min, skor_pretest_jalur_cepat, rata_level_min "
                        "FROM aturan_kenaikan_tingkat"
                    )
                ).all()
                aturan_adaptif = conn.execute(
                    text(
                        "SELECT jumlah_soal_pretest, ambang_lemah, jumlah_soal_simulasi, "
                        "kuota_min, bobot_lemah, ambang_naik FROM aturan_adaptif"
                    )
                ).all()
        finally:
            engine.dispose()

        assert [tuple(a) for a in aturan_kenaikan] == [(75, 90, 2.0)]
        assert [tuple(a) for a in aturan_adaptif] == [(30, 50, 30, 2, 3, 80)] * 2

    def test_upgrade_head_idempoten(self, database_url_kosong: str) -> None:
        config = _alembic_config(database_url_kosong)

        command.upgrade(config, "head")
        command.upgrade(config, "head")  # sudah di head, tidak boleh error
