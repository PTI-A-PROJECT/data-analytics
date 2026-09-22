from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.models.master import TingkatSeleksi, Kompetensi, Subkompetensi, Soal
from app.models.kenaikan_tingkat import AturanKenaikanTingkat
from app.api.v1 import api_router


def seed_database():
    """Menginisialisasi seed data dasar (Tingkat, Aturan Kenaikan, Kompetensi contoh)."""
    db = SessionLocal()
    try:
        # 1. Seed Tingkat Seleksi
        if db.query(TingkatSeleksi).count() == 0:
            kab = TingkatSeleksi(id=1, kode="KABUPATEN", nama="Tingkat Kabupaten/Kota", urutan=1)
            prov = TingkatSeleksi(id=2, kode="PROVINSI", nama="Tingkat Provinsi", urutan=2)
            nas = TingkatSeleksi(id=3, kode="NASIONAL", nama="Tingkat Nasional", urutan=3)
            db.add_all([kab, prov, nas])
            db.commit()

            # 2. Seed Aturan Kenaikan Tingkat (Tiket 03 default seeds)
            aturan_kab_prov = AturanKenaikanTingkat(
                tingkat_asal_id=kab.id,
                tingkat_tujuan_id=prov.id,
                skor_simulasi_min=75.0,
                persentase_kompetensi_cukup_min=80.0,
                aktif=True,
            )
            aturan_prov_nas = AturanKenaikanTingkat(
                tingkat_asal_id=prov.id,
                tingkat_tujuan_id=nas.id,
                skor_simulasi_min=85.0,
                persentase_kompetensi_cukup_min=85.0,
                aktif=True,
            )
            db.add_all([aturan_kab_prov, aturan_prov_nas])

            # 3. Seed Kurikulum Dasar Kabupaten
            k1 = Kompetensi(id=1, tingkat_seleksi_id=kab.id, kode="K-DASAR", nama="Dasar Pemrograman")
            k2 = Kompetensi(id=2, tingkat_seleksi_id=kab.id, kode="K-MAT", nama="Aritmatika & Logika")
            db.add_all([k1, k2])
            db.commit()

            sk1 = Subkompetensi(id=1, kompetensi_id=k1.id, kode="SK-LOOP", nama="Percabangan & Perulangan")
            sk2 = Subkompetensi(id=2, kompetensi_id=k1.id, kode="SK-ARR", nama="Array & Karakter")
            sk3 = Subkompetensi(id=3, kompetensi_id=k2.id, kode="SK-BIL", nama="Teori Bilangan Dasar")
            db.add_all([sk1, sk2, sk3])
            db.commit()

            # 4. Seed Butir Soal contoh (Tiket 05: batas_waktu_detik)
            # Soal 1: batas waktu 60 detik
            s1 = Soal(id=1, subkompetensi_id=sk1.id, tingkat_seleksi_id=kab.id, kunci_jawaban="A", batas_waktu_detik=60)
            s2 = Soal(id=2, subkompetensi_id=sk1.id, tingkat_seleksi_id=kab.id, kunci_jawaban="B", batas_waktu_detik=60)
            # Soal 3: batas waktu 45 detik
            s3 = Soal(id=3, subkompetensi_id=sk2.id, tingkat_seleksi_id=kab.id, kunci_jawaban="C", batas_waktu_detik=45)
            # Soal 4: batas waktu 90 detik
            s4 = Soal(id=4, subkompetensi_id=sk3.id, tingkat_seleksi_id=kab.id, kunci_jawaban="D", batas_waktu_detik=90)
            db.add_all([s1, s2, s3, s4])
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Buat tabel
    Base.metadata.create_all(bind=engine)
    seed_database()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "status": "healthy",
        "docs_url": "/docs",
    }
