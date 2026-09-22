# Rencana Deployment/Hosting untuk Sekolah Pilot

Type: grilling
Status: resolved
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

> **Catatan scope (2026-09-22).** Bagian anonymize-expired di bawah — ditandai
> **[di luar scope tiket 10]** di tiap baris terkait — TIDAK diminta oleh
> Resolution di atas (5 poin: topologi, isolasi DB, orkestrasi, resource
> limit, jalur skalabilitas). Saya tambahkan sendiri saat mengerjakan tiket
> ini karena terasa terhubung ke temuan retensi tiket 12, tapi itu keputusan
> sepihak, bukan permintaan eksplisit. Ditinjau ulang bersama pemilik map:
> kode dibiarkan apa adanya (sudah teruji, tidak di-revert), tapi kepatuhan
> UU PDP untuk retensi data **tidak harus** lewat mekanisme teknis ini —
> draft policy/consent yang disetujui user tanpa endpoint/cron tambahan juga
> sah untuk skala pilot. Tidak dibuat tiket terpisah untuk ini per permintaan
> pemilik map; anggap bagian yang ditandai sebagai bonus opsional, bukan
> bagian inti deployment plan.

Diimplementasikan di commit `6088b7a` (branch `main`, setelah `git log
--oneline 9707645..6088b7a`), **diverifikasi nyata** — bukan sekadar dicatat.
Klaim "Implementation" versi sebelumnya di bagian ini (menyebut commit
`feat(#10)`) terkonfirmasi fiktif (dicatat 2026-09-22): tidak ada commit atau
file seperti itu di branch manapun. Perbedaan dengan versi lama juga dicatat
di sini karena beberapa nama file tidak persis sama dengan yang diklaim dulu.

Verifikasi konkret yang dilakukan (bukan cuma menulis file):
- `docker compose config` untuk `docker-compose.yml` **dan** gabungan dengan
  `docker-compose.dev.yml` — keduanya valid.
- `docker build` sungguhan (bukan cuma ditulis) — image berhasil dibuat.
- Container dijalankan sungguhan: `GET /health` merespons `{"status":"ok"}`,
  Docker `HEALTHCHECK` melaporkan `healthy`, startup cepat (~0.1 detik ke
  endpoint pertama, tanpa re-sync dependency dev yang sebelumnya diam-diam
  terjadi — lihat catatan `--no-sync` di bawah).
- Dikonfirmasi `.git/`, `.scratch/`, `.claude/`, dan `brief 2.txt` **tidak**
  ikut ter-bake ke image (lewat `.dockerignore`).
- Migrasi Alembic 0002 dijalankan `upgrade head` **dan** `downgrade -1` lalu
  `upgrade head` lagi terhadap SQLite sungguhan — dua arah berfungsi.

### File yang dibuat/diubah

#### Infrastruktur Docker

| File | Keputusan yang Diimplementasikan |
|---|---|
| `docker-compose.yml` | Container `analytics-api` + `analytics-db`, resource limits (1 CPU/1GB each), `expose:` tanpa `ports:` (port tidak ke publik), volume `analytics_pgdata`, `app-network` external |
| `docker-compose.dev.yml` | Override dev: port diekspos ke host, hot-reload `--reload`, limit dilonggarkan (4 CPU/4GB — bukan "dihapus"; Compose merge mapping per-key, `limits: {}` tidak menghapus limit dari file dasar, lihat catatan di file), `app-network` dibuat lokal |
| `Dockerfile` | `python:3.11.9-slim` (dipin, bukan tag mengambang `3.11-slim`), `uv==0.12.5` dipin, non-root user, `curl` untuk healthcheck, CMD pakai `uv run --no-sync` (tanpa ini, tiap start container diam-diam `uv sync` ulang termasuk dependency dev seperti mypy — nambah puluhan detik startup) |
| `.dockerignore` | Baru — `.git/`, `.claude/`, `.scratch/`, `tests/`, `.env`, dll tidak ikut masuk image. `README.md` sengaja **tidak** diabaikan (dibaca `uv sync` dari `pyproject.toml`'s `readme = "README.md"` saat build paket — sempat bikin build gagal sebelum ini disadari) |
| `.env.example` | Variabel: `POSTGRES_*`, `DATABASE_URL`, `INTERNAL_API_TOKEN` (scope tiket 10 — Resolution poin 1 eksplisit minta auth `X-Internal-Token`); `DATA_RETENTION_MONTHS` **[di luar scope tiket 10]** |
| `Makefile` | `make up`, `make dev-up`, `make migrate`, `make backup-db` (scope tiket 10); `make anonymize`, `make anonymize-dry-run` **[di luar scope tiket 10]** |
| `README.md` | Bagian "Deployment (VPS pilot)" (scope tiket 10); bagian cron anonymize **[di luar scope tiket 10]** |

#### Aplikasi FastAPI (`src/data_analytics/` — paket datar, bukan `src/routers/` seperti klaim versi lama; lihat ADR 0003/tiket 09 soal keputusan struktur ini)

| File | Fungsi |
|---|---|
| `config.py` | Ditambah `internal_api_token` (scope tiket 10) dan `data_retention_months` **[di luar scope tiket 10]** di `Settings` yang sudah ada dari tiket 09 |
| `db.py` | Sudah ada dari tiket 09 (bukan `database.py`) — engine + `SessionLocal` + `get_db` |
| `auth.py` | Baru — dependency `verify_internal_token` (scope tiket 10, Resolution poin 1): header hilang → 422 otomatis dari FastAPI, token salah → 403 |
| `models.py` | `HasilTes` ditambah `is_anonymized` dan `siswa_id` dibuat nullable **[di luar scope tiket 10]** |
| `repository.py` | Baru — `anonimkan_hasil_tes_kedaluwarsa` **[di luar scope tiket 10]** (bukan nama Inggris seperti draft awal — semua fungsi repository lain Indonesia-first) |
| `api.py` | Sudah ada dari tiket 09 (bukan `main.py`/`routers/` terpisah) — ditambah `POST /api/v1/admin/anonymize-expired` **[di luar scope tiket 10]**, memakai `verify_internal_token` (scope tiket 10) sebagai dependency |

#### Migrasi Database (Alembic)

| File | Fungsi |
|---|---|
| `alembic/env.py` | Ditambah `render_as_batch=True` — dibutuhkan SQLite untuk `ALTER COLUMN` nullability |
| `alembic/versions/0002_anonymisasi_hasil_tes.py` | `siswa_id` nullable, tambah `is_anonymized` **[di luar scope tiket 10]**; upgrade & downgrade diverifikasi jalan |

(`alembic.ini`, `alembic/versions/0001_...`: sudah ada dari tiket 09, bukan bagian tiket ini.)

#### Tests (`tests/`)

| File | Coverage |
|---|---|
| `tests/test_anonymization.py` **[di luar scope tiket 10]** | 6 test level repository: lama dianonimkan, agregat tetap utuh, baru tidak disentuh, dry-run tidak mutasi, idempoten, hanya baris kedaluwarsa yang terdampak |
| `tests/test_api.py` (ditambah `TestAnonymizeExpired`) **[di luar scope tiket 10]** | 5 test level API: tanpa token → 422, token salah → 403, dry-run, live-run, data belum kedaluwarsa dilewati |
| `tests/conftest.py` **[di luar scope tiket 10]** | Ditambah fixture `buat_hasil_tes` (factory, dipakai kedua file test di atas — sebelumnya duplikat) |

### Cara menjalankan di VPS pilot

```bash
cp .env.example .env
# WAJIB ganti INTERNAL_API_TOKEN dan POSTGRES_PASSWORD dari nilai default dev

docker network create app-network   # sekali saja, biasanya sudah dibuat tim aplikasi utama

make up
make migrate

docker compose ps
docker compose exec analytics-api curl -sf http://localhost:8000/health
```

### Jadwal UU PDP anonymization (cron job) **[di luar scope tiket 10 — lihat "Catatan scope" di atas]**

```cron
0 2 1 * * cd /path/ke/repo && INTERNAL_API_TOKEN=<token> make anonymize >> /var/log/analytics-anonymize.log 2>&1
```
