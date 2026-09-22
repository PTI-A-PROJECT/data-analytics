from collections.abc import Iterator
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.core.database import Base as AppBase
from app.api.deps import get_db
from app.models.master import TingkatSeleksi, Kompetensi, Subkompetensi, Soal
from app.models.kenaikan_tingkat import AturanKenaikanTingkat
from app.main import app

from data_analytics.models import Base as PackageBase


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    PackageBase.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


# Gunakan in-memory SQLite dengan StaticPool untuk pengujian FastAPI
TEST_DATABASE_URL = "sqlite:///:memory:"

app_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=app_engine)


@pytest.fixture(scope="function")
def db():
    AppBase.metadata.create_all(bind=app_engine)
    db_session = TestingSessionLocal()

    # Seed data dasar untuk pengujian
    kab = TingkatSeleksi(id=1, kode="KABUPATEN", nama="Tingkat Kabupaten", urutan=1)
    prov = TingkatSeleksi(id=2, kode="PROVINSI", nama="Tingkat Provinsi", urutan=2)
    nas = TingkatSeleksi(id=3, kode="NASIONAL", nama="Tingkat Nasional", urutan=3)
    db_session.add_all([kab, prov, nas])
    db_session.commit()

    # Aturan Kenaikan (Tiket 03 default: Kab->Prov min skor 75, % cukup 80)
    aturan1 = AturanKenaikanTingkat(
        id=1,
        tingkat_asal_id=1,
        tingkat_tujuan_id=2,
        skor_simulasi_min=75.0,
        persentase_kompetensi_cukup_min=80.0,
        aktif=True,
    )
    aturan2 = AturanKenaikanTingkat(
        id=2,
        tingkat_asal_id=2,
        tingkat_tujuan_id=3,
        skor_simulasi_min=85.0,
        persentase_kompetensi_cukup_min=85.0,
        aktif=True,
    )
    db_session.add_all([aturan1, aturan2])

    # 2 Kompetensi di Kabupaten
    k1 = Kompetensi(id=1, tingkat_seleksi_id=1, kode="K1", nama="Logika Pemrograman")
    k2 = Kompetensi(id=2, tingkat_seleksi_id=1, kode="K2", nama="Struktur Data")
    db_session.add_all([k1, k2])
    db_session.commit()

    # 2 Subkompetensi di K1, 1 Subkompetensi di K2
    sk1 = Subkompetensi(id=1, kompetensi_id=1, kode="SK1", nama="Looping")
    sk2 = Subkompetensi(id=2, kompetensi_id=1, kode="SK2", nama="Conditionals")
    sk3 = Subkompetensi(id=3, kompetensi_id=2, kode="SK3", nama="Arrays")
    db_session.add_all([sk1, sk2, sk3])
    db_session.commit()

    # Soal dengan batas_waktu_detik (Tiket 05)
    s1 = Soal(id=1, subkompetensi_id=1, tingkat_seleksi_id=1, kunci_jawaban="A", batas_waktu_detik=60)
    s2 = Soal(id=2, subkompetensi_id=1, tingkat_seleksi_id=1, kunci_jawaban="B", batas_waktu_detik=60)
    s3 = Soal(id=3, subkompetensi_id=2, tingkat_seleksi_id=1, kunci_jawaban="C", batas_waktu_detik=30)
    s4 = Soal(id=4, subkompetensi_id=3, tingkat_seleksi_id=1, kunci_jawaban="D", batas_waktu_detik=45)
    db_session.add_all([s1, s2, s3, s4])
    db_session.commit()

    try:
        yield db_session
    finally:
        db_session.close()
        AppBase.metadata.drop_all(bind=app_engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
