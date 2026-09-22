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


@lru_cache
def get_settings() -> Settings:
    return Settings()
