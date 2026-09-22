# data-analytics

Layanan Data & Analytics untuk platform OSN Informatika. Lihat `CONTEXT.md`
(glosarium domain) dan `.scratch/osn-data-analytics/map.md` (peta scope &
keputusan) sebelum mengerjakan tiket apa pun.

## Setup

```bash
uv sync
cp .env.example .env   # sesuaikan DATABASE_URL kalau tidak pakai SQLite dev
```

## Menjalankan migrasi & seed data uji

```bash
uv run alembic upgrade head
uv run python -m data_analytics.scripts.seed
```

`seed` idempotent — aman dijalankan berulang, tidak menduplikasi data kalau
`tingkat_seleksi` sudah pernah terisi.

## Menjalankan server dev

```bash
uv run uvicorn data_analytics.api:app --reload
```

`GET /health` — liveness probe. `GET /api/v1/health` — readiness probe (ping
database).

## Test & typecheck

```bash
uv run pytest
uv run mypy src tests
```
