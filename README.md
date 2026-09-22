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

## Deployment (VPS pilot)

Lihat resolusi lengkap di
`.scratch/osn-data-analytics/issues/10-rencana-deployment-pilot.md`. Ringkasan:
co-located di VPS yang sama dengan aplikasi utama, container `analytics-api`
+ `analytics-db` terpisah dari stack aplikasi utama, port **tidak** diekspos
ke publik — hanya bisa diakses lewat network Docker privat (`app-network`).

```bash
# 1. Salin & isi environment variables — WAJIB ganti INTERNAL_API_TOKEN dan
#    POSTGRES_PASSWORD dengan nilai rahasia asli.
cp .env.example .env

# 2. Buat shared network (sekali saja — biasanya sudah dibuat tim aplikasi utama)
docker network create app-network

# 3. Jalankan stack & migrasi
make up
make migrate

# 4. Verifikasi
docker compose ps
docker compose exec analytics-api curl -sf http://localhost:8000/health
```

Untuk dev lokal (port diekspos ke host, hot-reload): `make dev-up`.

### Anonymisasi UU PDP (cron bulanan)

Endpoint `POST /api/v1/admin/anonymize-expired` (dilindungi header
`X-Internal-Token`, lihat `src/data_analytics/auth.py`) meng-null-kan
`siswa_id` pada `HasilTes` yang sudah lewat `DATA_RETENTION_MONTHS` — lihat
riset di `.scratch/osn-data-analytics/issues/12-riset-uu-pdp-data-siswa.md`.
Data agregat (skor, predikat, breakdown Subkompetensi) tetap utuh untuk
Dashboard Admin. `make anonymize-dry-run` untuk mengecek dulu tanpa mengubah
data.

Tambahkan ke crontab VPS:

```cron
0 2 1 * * cd /path/ke/repo && INTERNAL_API_TOKEN=<token> make anonymize >> /var/log/analytics-anonymize.log 2>&1
```

### Backup database

`make backup-db` men-dump `analytics-db` ke `./backups/` (buat direktori itu
dulu). Jadwalkan berkala lewat cron VPS dengan pola yang sama seperti di atas.

### Jalur skalabilitas

Kalau traffic melampaui kapasitas satu VPS (mis. ekspansi lintas provinsi):
pindahkan `docker-compose.yml` ini ke VPS terpisah, hubungkan ke VPS aplikasi
utama lewat VPN privat (WireGuard/Tailscale) atau VPC peering, tanpa perlu
mengubah kode aplikasi — `analytics-api`/`analytics-db` sudah terisolasi
sebagai stack mandiri sejak awal.
