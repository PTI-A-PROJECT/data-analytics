from collections.abc import Callable, Iterator
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_analytics.models import Base, HasilTes, JenisTes


@pytest.fixture
def session() -> Iterator[Session]:
    # StaticPool + check_same_thread=False: satu koneksi in-memory yang sama
    # dipakai di semua thread, supaya fixture ini juga bisa dipakai lewat
    # FastAPI TestClient (jalan di thread terpisah via anyio portal).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


@pytest.fixture
def buat_hasil_tes(session: Session) -> Callable[..., HasilTes]:
    """Factory HasilTes pilihan-default untuk test yang tidak peduli detail
    skor/breakdown-nya (mis. test anonymisasi) — dipakai lintas test file.
    """

    def _buat(
        *, dibuat_pada: datetime, siswa_id: int = 1, sekolah_id: int | None = 7
    ) -> HasilTes:
        hasil = HasilTes(
            siswa_id=siswa_id,
            sekolah_id=sekolah_id,
            tingkat_seleksi_id=1,
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
