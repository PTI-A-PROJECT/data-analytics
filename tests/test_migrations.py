"""Test migrasi Alembic (tiket 09) — pastikan revisi 0001 benar-benar membuat
semua tabel yang didefinisikan di data_analytics.models, dan aman dijalankan
berulang (idempoten di posisi head).
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from data_analytics.models import Base

REPO_ROOT = Path(__file__).resolve().parent.parent


def _alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


class TestMigrasiAwal:
    def test_upgrade_head_membuat_semua_tabel(self, tmp_path: Path) -> None:
        database_url = f"sqlite:///{tmp_path / 'migrasi_test.db'}"
        config = _alembic_config(database_url)

        command.upgrade(config, "head")

        engine = create_engine(database_url)
        try:
            tabel_dibuat = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

        tabel_diharapkan = set(Base.metadata.tables.keys())
        assert tabel_diharapkan <= tabel_dibuat

    def test_upgrade_head_idempoten(self, tmp_path: Path) -> None:
        database_url = f"sqlite:///{tmp_path / 'migrasi_test.db'}"
        config = _alembic_config(database_url)

        command.upgrade(config, "head")
        command.upgrade(config, "head")  # sudah di head, tidak boleh error
