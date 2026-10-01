# data-analytics

Layanan Data & Analytics untuk platform OSN Informatika. Lihat `CONTEXT.md`
(glosarium domain) dan `.scratch/osn-data-analytics/map.md` (peta scope &
keputusan) sebelum mengerjakan tiket apa pun.

## Setup

```bash
uv sync
cp .env.example .env   # DATABASE_URL harus PostgreSQL + pgvector (SQLite tidak didukung)
```

## Menjalankan migrasi

```bash
uv run alembic upgrade head
```

Migrasi `0005` memasang extension `vector` dan mengisi tingkat seleksi
Kabupaten & Provinsi. Tidak ada lagi seed data uji: bank soal & materi diisi
lewat ingest offline (lihat di bawah).

## Bank konten (fase 2)

Soal & materi disimpan di katalog lokal dengan embedding pgvector — lihat
`docs/adr/0004-layanan-memiliki-bank-konten.md` dan
`.scratch/osn-fase-2/issues/01-bank-konten-soal-materi.md`. Inti ingest ada di
`data_analytics.ingest.ingest_bank_konten`. Sumber data ada di `soal_osn/`:
JSON soal per tahun (Kabupaten & Provinsi 2006–2026), gambar, `materi.json`
(kelompok Materi mengikuti silabus osn.toki.id), dan `label_materi_level.json`
(Materi & Level per soal, dilabeli manual — data sumber tidak membawanya).
Embedder (`embedding.EmbedderMiniLM`,
`paraphrase-multilingual-MiniLM-L12-v2` int8 lewat ONNX Runtime, tanpa PyTorch,
~555 MB RAM puncak, ~35 detik / 1.800 soal) hanya dipakai saat ingest dan butuh
dependency group `ingest`:

```bash
uv sync --group ingest
```

Ingest (idempoten; embedding hanya dihitung untuk soal baru/berubah):

```bash
uv run python -m data_analytics.scripts.ingest            # --recompute untuk hitung ulang semua
```

Soal tanpa kunci, soal pemrograman, jawaban isian yang tidak bisa dinilai
otomatis, dan entri di `dikecualikan` dilewati; ringkasannya dicetak. Gambar soal
disajikan `GET /api/v1/konten/gambar/{tingkat}/{file}` dari folder yang sama
(`FOLDER_SOAL`, default `soal_osn`). Perbandingan model & kualitas: `uv run --group ingest python -m
data_analytics.scripts.benchmark_embedding`.

### Dokumen Materi

Halaman Materi diambil dari `Materi/<Kabupaten|Provinsi>/Topik N_*.docx`
(`FOLDER_MATERI`, default `Materi`; parser `data_analytics.materi_docx`) oleh
ingest yang sama. Nomor topik di nama file dicocokkan ke field `topik` di
`soal_osn/materi.json`; setiap judul bagian tebal ("1. ...", "Studi Kasus ...",
"Bagian A: ...") membuka satu halaman. Konten disimpan sebagai Markdown dengan
rumus LaTeX (`$...$`, `$$...$$`) dan blok kode — render di frontend dengan
Markdown + KaTeX. Menambah/mengganti dokumen: taruh file-nya, sesuaikan
`materi.json` kalau topiknya baru, lalu jalankan ingest ulang.

Endpoint (header `X-Internal-Token`):

- `GET /api/v1/materi?tingkat_seleksi_id=&siswa_id=` — daftar Materi urut
  tingkat & topik; dengan `siswa_id` ikut `halaman_dibaca`/`persentase_dibaca`.
- `GET /api/v1/materi/{materi_id}?siswa_id=` — detail + daftar isi (nomor &
  judul halaman, `sudah_dibaca` kalau `siswa_id` dikirim).
- `GET /api/v1/materi/{materi_id}/halaman/{nomor}` — konten satu halaman +
  `nomor_sebelumnya`/`nomor_berikutnya`. Hanya membaca; catat progres lewat
  `POST /api/v1/analytics/events/materi-progress`.

## Menjalankan server dev

```bash
uv run uvicorn data_analytics.api:app --reload
```

`GET /health` — liveness probe. `GET /api/v1/health` — readiness probe (ping
database).

## Test & typecheck

Test berjalan di PostgreSQL + pgvector sungguhan (container Docker, port
5433 — override lewat env `TEST_DATABASE_URL`):

```bash
make test-db-up        # sekali saja; `make test-db-down` untuk membuang
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
