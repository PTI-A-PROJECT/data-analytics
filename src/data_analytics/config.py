"""Konfigurasi environment type-safe (tiket 09) — dibaca dari env var/.env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # File SQLite lokal, bukan ":memory:" — supaya `alembic upgrade head` dan
    # `seed` yang dijalankan sebagai proses terpisah tetap memakai DB yang
    # sama kalau developer belum sempat `cp .env.example .env` (tanpa ini,
    # tiap proses diam-diam dapat DB in-memory kosong sendiri-sendiri).
    database_url: str = "sqlite:///./dev.db"

    # Shared secret untuk endpoint internal (tiket 10) — dipanggil backend
    # aplikasi utama lewat network Docker privat, bukan publik. Default ini
    # HANYA untuk dev lokal; .env.example mewajibkan nilai asli di VPS pilot.
    internal_api_token: str = "dev-only-insecure-token-ganti-di-produksi"

    # UU PDP mewajibkan pengendali data menetapkan & mendisclose periode
    # retensinya sendiri (tidak ada angka baku di UU) — lihat riset tiket 12.
    # 24 bulan dipilih sebagai default kerja (mencakup >1 siklus OSN
    # tahunan penuh); Super Admin/sekolah bisa override lewat env.
    data_retention_months: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()
