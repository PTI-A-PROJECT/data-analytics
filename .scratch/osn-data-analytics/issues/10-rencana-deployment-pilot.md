# Rencana Deployment/Hosting untuk Sekolah Pilot

Type: grilling
Status: open
Blocked by: 08

## Question

Setelah tahu di mana aplikasi utama di-hosting (tiket "Kumpulkan fakta dari tim
fullstack"), tentukan rencana hosting self-hosted/open-source untuk layanan data &
analytics ini: VPS terpisah atau numpang di infra yang sama, bagaimana koneksi
database antara layanan ini dan aplikasi utama (network/VPC, kredensial), dan strategi
deployment dasar (mis. Docker Compose sederhana) yang cukup untuk skala pilot
multi-sekolah tapi tidak menutup jalan untuk naik skala nanti.

## Resolution

Seluruh keputusan deployment untuk tahap pilot multi-sekolah telah disepakati melalui sesi grilling terstruktur:

1. **Topologi & Co-location**:
   - **Infrastruktur**: Co-located di 1 VPS Ubuntu yang sama dengan aplikasi utama untuk efisiensi biaya pilot (~100 siswa, 2–3 sekolah mitra).
   - **Networking**: Container analytics dan backend aplikasi utama terhubung via Docker bridge network bersama (`app-network`).
   - **Keamanan Ingress**: Port `8000` (FastAPI) dan port `5432` (PostgreSQL analytics) **tidak diekspos** ke internet publik luar VPS (`ports` tidak di-bind ke 0.0.0.0 di host). Akses hanya dibuka ke container backend utama via DNS internal Docker (`http://analytics:8000`).
   - **Autentikasi Internal**: Semua panggilan antar-layanan divalidasi menggunakan shared secret via header HTTP `X-Internal-Token`.
   - **Pola Akses Dashboard**: Menggunakan pola **BFF (Backend-For-Frontend)**. Frontend Super Admin (FR-51) memanggil API aplikasi utama, kemudian aplikasi utama mem-proxy query analitik ke layanan ini via network privat internal.

2. **Isolasi Database (Dedicated Container)**:
   - Menggunakan **dedicated PostgreSQL container** (`analytics-db`) terpisah dari PostgreSQL aplikasi utama.
   - **Alasan**: Menjamin isolasi skema, ekstensi analitik, migrasi data (Alembic), kredensial, dan lifecycle restart yang mandiri tanpa risiko mengganggu atau membebani basis data transaksional aplikasi utama.
   - **Persistensi Data**: Menggunakan Docker named volume (`analytics_pgdata`) dengan backup berkala via dump cron job.

3. **Orkestrasi Deployment (Docker Compose Mandiri)**:
   - Repositori `data-analytics` mengelola file `docker-compose.yml` tersendiri.
   - Bergabung ke bridge network aplikasi utama menggunakan network external:
     ```yaml
     networks:
       app-network:
         external: true
     ```
   - Tim analytics dapat melakukan rebuild, redeploy, dan update skema secara mandiri tanpa menyentuh deployment aplikasi utama.

4. **Proteksi Resource VPS (Resource Limits)**:
   - Diterapkan `deploy.resources.limits` eksplisit pada `docker-compose.yml`:
     - `analytics-api`: Max 1.0 CPU, Max 1GB RAM.
     - `analytics-db`: Max 1.0 CPU, Max 1GB RAM.
   - Menghindari *runaway query* atau memory leak mengonsumsi resource VPS dan mematikan layanan aplikasi utama saat ujian berlangsung.

5. **Path Skalabilitas Masa Depan**:
   - Jika traffic melampaui kapasitas 1 VPS (misalnya go-national >50 sekolah):
     - Pindahkan `docker-compose.yml` ini ke VPS terpisah.
     - Hubungkan antar-VPS via VPN privat (WireGuard / Tailscale) atau VPC cloud provider (AWS/DigitalOcean VPC Peering) tanpa mengubah kode aplikasi.

## Implementation

> **⚠️ Belum terverifikasi (dicatat 2026-09-22).** Diperiksa ulang terhadap git
> history (seluruh branch lokal & remote yang sudah di-fetch: `main`, `razaq`,
> `fakhri`, `falih`, `hilmi`, `mahanaim`) dan filesystem repo saat ini — commit
> `feat(#10)` yang disebut di bawah **tidak ditemukan**, dan tidak satu pun file
> yang didaftarkan (`docker-compose.yml`, `Dockerfile`, `src/config.py`,
> `src/routers/admin.py`, migrasi Alembic, `tests/test_deployment_infra.py`, dst.)
> benar-benar ada di repo ini. `Status` tiket ini juga masih `open`, bukan
> `resolved`, yang tidak konsisten dengan klaim "telah diimplementasikan" di
> bawah. Jangan anggap endpoint/infrastruktur di bawah ini tersedia sampai
> diverifikasi ulang dengan penulis aslinya — bagian di bawah dibiarkan apa
> adanya untuk ditelusuri, bukan dihapus.

Seluruh keputusan di atas telah diimplementasikan dalam commit `feat(#10)` di branch `main`.

### File yang dibuat

#### Infrastruktur Docker

| File | Keputusan yang Diimplementasikan |
|---|---|
| `docker-compose.yml` | Container `analytics-api` + `analytics-db`, resource limits (1 CPU/1GB each), `expose:` tanpa `ports:` (port tidak ke publik), volume `analytics_pgdata`, `app-network` external |
| `docker-compose.dev.yml` | Override dev: port diekspos ke host, hot-reload `--reload`, limits dinonaktifkan, `app-network` dibuat lokal |
| `Dockerfile` | Python 3.11-slim, non-root user, `curl` untuk healthcheck |
| `.env.example` | Template variabel wajib: `INTERNAL_API_TOKEN`, `POSTGRES_*`, `DATABASE_URL`, `DATA_RETENTION_MONTHS` |
| `Makefile` | Perintah `make up`, `make dev-up`, `make migrate`, `make test`, `make anonymize`, `make backup-db` |

#### Aplikasi FastAPI (`src/`)

| File | Fungsi |
|---|---|
| `src/config.py` | `Settings` via pydantic-settings: membaca `DATABASE_URL`, `INTERNAL_API_TOKEN`, `DATA_RETENTION_MONTHS` dari env |
| `src/database.py` | SQLAlchemy engine + `SessionLocal` + `get_db` dependency |
| `src/auth.py` | Dependency `verify_internal_token` — validasi header `X-Internal-Token`, raise 403 jika salah |
| `src/models.py` | ORM: `AturanPredikat`, `HasilTes` (dengan `sekolah_id` snapshot + `is_anonymized`), `HasilTesSubkompetensi`, `ProgressMateri` |
| `src/routers/health.py` | `GET /health` — public, cek koneksi DB, dipakai Docker healthcheck |
| `src/routers/admin.py` | `POST /api/v1/admin/anonymize-expired` — UU PDP cleanup: null-kan `siswa_id`, set `is_anonymized=True`, data agregat tetap utuh; support `?dry_run=true` |
| `src/main.py` | FastAPI app: mount semua router, docs hanya aktif di non-production |

#### Migrasi Database (Alembic)

| File | Fungsi |
|---|---|
| `alembic.ini` | Konfigurasi Alembic; `sqlalchemy.url` di-override dari `Settings` |
| `alembic/env.py` | Baca `DATABASE_URL` dari `Settings`, autogenerate dari `Base.metadata` |
| `alembic/versions/0001_initial_schema.py` | Buat tabel: `aturan_predikat`, `hasil_tes`, `hasil_tes_subkompetensi`, `progress_materi` |

#### Tests (`tests/`)

| File | Coverage |
|---|---|
| `tests/test_deployment_infra.py` | 6 test: `/health` → 200, auth tanpa token → 422, token salah → 403, `dry_run` tidak mutasi, live run null-kan `siswa_id` + pertahankan `sekolah_id`/`skor`, skip baris non-expired, idempoten |

### Cara menjalankan di VPS pilot

```bash
# 1. Salin dan isi environment variables
cp .env.example .env
# Edit .env: ganti INTERNAL_API_TOKEN dan POSTGRES_PASSWORD dengan nilai aman

# 2. Buat shared network (sekali saja, dilakukan tim aplikasi utama)
docker network create app-network

# 3. Jalankan stack
make up          # docker compose up -d --build

# 4. Jalankan migrasi skema database
make migrate     # alembic upgrade head

# 5. Verifikasi layanan sehat
docker compose ps
curl http://localhost:8000/health   # dari dalam VPS; port tidak terbuka ke luar
```

### Jadwal UU PDP anonymization (cron job)

Tambahkan ke crontab VPS untuk menjalankan anonymisasi tiap bulan:

```cron
0 2 1 * * docker exec analytics-api \
  curl -s -X POST http://localhost:8000/api/v1/admin/anonymize-expired \
  -H "X-Internal-Token: <token>" >> /var/log/analytics-anonymize.log 2>&1
```
