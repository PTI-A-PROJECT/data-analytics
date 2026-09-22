# Task: Scaffold Proyek FastAPI + PostgreSQL & Data Uji

Type: task
Status: resolved
Blocked by: none

## Question

Siapkan skeleton proyek Python/FastAPI + PostgreSQL (struktur folder, dependency
management, koneksi database, migrasi skema dasar) sesuai stack yang sudah disepakati
di sesi charting. Sertakan data uji/seed (siswa, soal pilihan ganda bertag
Kompetensi/Subkompetensi, Aturan Pemetaan contoh) supaya perhitungan Peta Kompetensi &
Rekomendasi Materi bisa dikembangkan dan diuji sebelum data pilot nyata tersedia.

## Resolution

Rancangan arsitektur dan scaffolding proyek telah disepakati melalui sesi grilling:

1. **Model Eksekusi Database & Dependensi**:
   - Python `>=3.11`, FastAPI, SQLAlchemy 2.0 dengan **Synchronous Session** (`Session`, `create_engine`) dan driver `psycopg2-binary`.
   - Menggunakan pool koneksi terukur bawaan SQLAlchemy yang stabil untuk beban konkurensi pilot (50 siswa serentak) tanpa kompleksitas async context management.
   - Pydantic v2 dan `pydantic-settings` untuk konfigurasi type-safe.

2. **Pola Arsitektur Folder (Clean Seam Architecture)**:
   - `src/domain/`: Logika analitik murni (algoritma skor, pemetaan status kompetensi, filter rekomendasi materi) berbasis pure Python / Pydantic models—**terisolasi 100% dari database/FastAPI**. Ini membuat unit testing instan (sub-milidetik) dan kode sangat mudah dirawat.
   - `src/models/`: Definisi tabel SQLAlchemy ORM dan metadata declarative base.
   - `src/schemas/`: DTO Pydantic untuk request/response API.
   - `src/api/`: Endpoint FastAPI (routers) dan dependency injection (DB session, security token).
   - `src/core/`: Inisialisasi engine DB, `BaseSettings` konfigurasi environment, dan middleware.
   - `src/scripts/`: Script operasional seperti `seed.py`.
   - `tests/`: Unit test (domain) dan integrasi test (API) menggunakan pytest.

3. **Skema Database Awal (Alembic Migration 0001)**:
   - **Konfigurasi**:
     - `tingkat_seleksi` (`id`, `nama`, `urutan`)
     - `aturan_predikat` (`id`, `tingkat_seleksi_id`, `label`, `batas_bawah` — default 90/80/70/<70 dari Tiket 01)
     - `aturan_pemetaan` (`id`, `tingkat_seleksi_id`, `ambang_cukup_persen`, `ambang_representasi_persen`)
   - **Silabus & Soal Uji**:
     - `kompetensi` (`id`, `nama`, `deskripsi`)
     - `subkompetensi` (`id`, `kompetensi_id`, `nama`, `deskripsi`)
     - `soal` (`id`, `subkompetensi_id`, `tingkat_seleksi_id`, `nomor`, `pertanyaan`, `pilihan_jawaban`, `kunci_jawaban`)
   - **Hasil & Penilaian (Tiket 01 & 08)**:
     - `hasil_tes` (`id`, `siswa_id`, `sekolah_id`, `tingkat_seleksi_id`, `jenis_tes`, `total_soal`, `jumlah_benar`, `jumlah_salah`, `skor`, `predikat_label`, `diselesaikan_pada`, `dibuat_pada`)
     - `hasil_tes_subkompetensi` (`id`, `hasil_tes_id`, `subkompetensi_id`, `jumlah_soal`, `jumlah_benar`)

4. **Data Uji (Seed Strategy)**:
   - Dijalankan via script CLI mandiri yang idempotent: `python -m src.scripts.seed`.
   - Dataset seed awal:
     - 3 Tingkat Seleksi (Kabupaten, Provinsi, Nasional).
     - Aturan predikat bawaan per tingkat (Sangat Baik, Baik, Cukup, Perlu Latihan).
     - Aturan pemetaan bawaan (ambang cukup 70%, representasi 20%).
     - 2 Kompetensi: "Dasar Pemrograman" dan "Struktur Data".
     - 4 Subkompetensi: "Percabangan", "Perulangan", "Graph", "Linked List".
     - 15 Soal pilihan ganda berimbang antar-subkompetensi untuk simulasi pengerjaan.
     - 2 Dummy siswa uji dan 1 dummy sekolah uji untuk memverifikasi agregasi analitik.

5. **Test Harness & Healthcheck**:
   - `pytest` dikonfigurasi dengan fixture SQLite in-memory (`sqlite:///:memory:`) di `tests/conftest.py` untuk feedback loop TDD instan tanpa perlu menjalankan container Docker PostgreSQL.
   - Endpoint:
     - `GET /health`: Liveness probe cepat.
     - `GET /api/v1/health`: Readiness probe yang melakukan query ping aktif ke database.

## Implementation

Diimplementasikan dan **diverifikasi jalan** (bukan sekadar dicatat — lihat catatan
verifikasi di tiket 10 untuk kontras dengan klaim yang tidak terverifikasi):
`uv run pytest` (64 test lulus), `uv run mypy src tests` (bersih), migrasi
`alembic upgrade head` dan `python -m data_analytics.scripts.seed` dijalankan
end-to-end terhadap file SQLite sungguhan (bukan cuma di test).

Tiga penyesuaian sengaja menyimpang dari resolusi di atas, disepakati bersama user
sebelum coding (lihat percakapan sesi ini untuk konteks lengkap):

1. **Struktur folder**: kode tetap di paket datar `src/data_analytics/` yang sudah
   ada dan teruji (tiket 01/02/08), BUKAN direstrukturisasi ke layout
   `src/domain/`, `src/models/`, `src/schemas/`, `src/api/`, `src/core/`,
   `src/scripts/` yang diusulkan poin 2. Alasan: restrukturisasi akan mengubah
   import path 48 test yang sudah ada tanpa manfaat fungsional, murni risiko
   regresi.
2. **Kepemilikan tabel katalog**: `tingkat_seleksi`, `aturan_pemetaan`,
   `kompetensi`, `subkompetensi`, `soal` awalnya bertentangan dengan pola
   "tanpa FK, caller-supplied" yang sudah mapan (diperluas dari ADR 0002). User
   memilih tetap membuatnya sebagai tabel produksi sungguhan (bukan cuma
   fixture test) — didokumentasikan formal di **`docs/adr/0003`**, termasuk
   penjelasan bahwa `HasilTes`/`ProgressMateri`/dst. tetap TIDAK di-FK ke
   tabel-tabel baru ini.
3. **Driver Postgres**: tetap `psycopg[binary]` (psycopg3, sudah terpasang
   sejak tiket 01) alih-alih `psycopg2-binary` yang disebut poin 1 — tidak ada
   alasan untuk migrasi driver mundur.

### File yang dibuat/diubah

| File | Fungsi |
|---|---|
| `src/data_analytics/models.py` | + `TingkatSeleksi`, `AturanPemetaan`, `Kompetensi`, `Subkompetensi`, `Soal` |
| `src/data_analytics/config.py` | `Settings` (pydantic-settings) — baca `DATABASE_URL` dari env/`.env` |
| `src/data_analytics/db.py` | Engine + `SessionLocal` + `get_db` dependency |
| `src/data_analytics/api.py` | FastAPI app: `GET /health`, `GET /api/v1/health` |
| `src/data_analytics/scripts/seed.py` | Seed idempotent: 3 Tingkat Seleksi, aturan predikat+pemetaan bawaan, 2 Kompetensi/4 Subkompetensi, 15 soal seimbang, 2 dummy siswa + 1 dummy sekolah |
| `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_skema_awal.py` | Migrasi awal — seluruh 9 tabel (autogenerate dari `Base.metadata`, diverifikasi lewat `tests/test_migrations.py`) |
| `docs/adr/0003-local-catalog-tables-for-seed-data.md` | Dokumentasi keputusan poin 2 di atas |
| `.env.example`, `README.md`, `.gitignore` (+`.env`, `*.db`) | Onboarding dev |
| `tests/test_catalog_models.py`, `tests/test_api.py`, `tests/test_seed.py`, `tests/test_migrations.py` | Test baru (TDD) untuk seluruh poin di atas |
| `tests/conftest.py` | Fixture `session` ditambah `StaticPool`/`check_same_thread=False` supaya bisa dipakai lintas-thread oleh FastAPI `TestClient` |

### Cara menjalankan

```bash
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run python -m data_analytics.scripts.seed
uv run uvicorn data_analytics.api:app --reload
```
