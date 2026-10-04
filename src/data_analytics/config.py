"""Konfigurasi environment type-safe (tiket 09) — dibaca dari env var/.env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL + pgvector wajib sejak fase 2 (kolom vector, migrasi 0005) —
    # SQLite tidak lagi didukung. Default ini cocok dengan analytics-db dari
    # `make dev-up` memakai kredensial .env.example.
    database_url: str = (
        "postgresql+psycopg://analytics:changeme-generate-a-real-secret@localhost:5432/analytics"
    )

    # Shared secret untuk endpoint internal (tiket 10) — dipanggil backend
    # aplikasi utama lewat network Docker privat, bukan publik. Default ini
    # HANYA untuk dev lokal; .env.example mewajibkan nilai asli di VPS pilot.
    internal_api_token: str = "dev-only-insecure-token-ganti-di-produksi"

    # UU PDP mewajibkan pengendali data menetapkan & mendisclose periode
    # retensinya sendiri (tidak ada angka baku di UU) — lihat riset tiket 12.
    # 24 bulan dipilih sebagai default kerja (mencakup >1 siklus OSN
    # tahunan penuh); Super Admin/sekolah bisa override lewat env.
    data_retention_months: int = 24

    # Folder bank soal sumber (JSON, label, gambar) — relatif ke direktori
    # kerja; gambar soal disajikan dari <folder_soal>/gambar_<tingkat>/.
    folder_soal: str = "soal_osn"

    # Folder dokumen Materi (<Tingkat>/Topik N_*.docx) untuk ingest halaman
    # Materi — lihat data_analytics.materi_docx.
    folder_materi: str = "Materi"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# =============================================================================
# KONSTANTA ATURAN FINAL v1
# =============================================================================

# Ambang lemah pemetaan kompetensi.
# Akurasi < 60% → Lemah (remedial wajib)
# Akurasi 60-79% → Cukup
# Akurasi >= 80% → Kuat
DEFAULT_AMBANG_LEMAH: float = 60.0

# Passing grade simulasi per tingkat.
# Harus lulus BAIK nilai >= passing grade, DAN tidak ada materi inti < 50%.
PASSING_GRADE: dict[str, float] = {
    "kabupaten": 70.0,
    "provinsi": 80.0,
}

# Materi inti per tingkat — wajib >= 50% akurasi untuk lulus.
# Materi inti = fundamental, tidak boleh di-skip.
MATERI_INTI: dict[str, list[str]] = {
    "kabupaten": [
        "algoritma-pemrograman",
        "berpikir-komputasional",
        "logika-himpunan",
    ],
    "provinsi": [
        "rekursi",
        "struktur-data",
        "graf-tree",
        "dp",
    ],
}

# Kuota maksimum percobaan simulasi per tingkat.
# Setelah gagal 3x → wajib pre-test ulang untuk reset kuota.
MAX_PERCOBAAN_SIMULASI: int = 3

# Distribusi level soal untuk pre-test (50% Mudah, 30% Sedang, 20% Sulit).
# Catatan: enum di models.py = SEDANG, konsisten dengan DB Laravel.
DISTRIBUSI_PRETEST: dict[str, float] = {
    "mudah": 0.50,
    "sedang": 0.30,
    "sulit": 0.20,
}

# Distribusi level soal untuk simulasi (30% Mudah, 40% Sedang, 30% Sulit).
DISTRIBUSI_SIMULASI: dict[str, float] = {
    "mudah": 0.30,
    "sedang": 0.40,
    "sulit": 0.30,
}