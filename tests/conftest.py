from collections.abc import Callable, Iterator
from datetime import datetime
import os

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from data_analytics.models import Base, HasilTes, JenisTes

# Test memakai PostgreSQL + pgvector sungguhan (fase 2, issue 01) — bukan SQLite
# lagi, karena kolom vector(384) dan operator <=> hanya ada di Postgres.
# Jalankan `make test-db-up` sekali untuk menyalakan container-nya.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://analytics:analytics@localhost:5433/analytics_test",
)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    # Satu transaksi luar per test yang selalu di-rollback; commit() di kode
    # yang dites hanya melepas SAVEPOINT (join_transaction_mode) sehingga
    # setiap test mulai dari database kosong. Koneksi yang sama dipakai
    # FastAPI TestClient lewat override get_db.
    with engine.connect() as connection:
        transaksi = connection.begin()
        db_session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield db_session
        finally:
            db_session.close()
            transaksi.rollback()


@pytest.fixture
def buat_hasil_tes(session: Session) -> Callable[..., HasilTes]:
    """Factory HasilTes pilihan-default untuk test yang tidak peduli detail
    skor/breakdown-nya (mis. test anonymisasi) — dipakai lintas test file.
    """

    def _buat(
        *, dibuat_pada: datetime, siswa_id: str = "1", sekolah_id: str | None = "7"
    ) -> HasilTes:
        hasil = HasilTes(
            siswa_id=siswa_id,
            sekolah_id=sekolah_id,
            tingkat_seleksi_id="1",
            jenis_tes=JenisTes.PRE_TEST,
            simulasi_id=None,
            total_soal=10,
            jumlah_benar=8,
            jumlah_salah=2,
            skor=80.0,
            predikat_label="Baik",
            diselesaikan_pada=dibuat_pada,
            dibuat_pada=dibuat_pada,
        )
        session.add(hasil)
        session.flush()
        return hasil

    return _buat
