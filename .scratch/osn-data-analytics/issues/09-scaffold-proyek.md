# Task: Scaffold Proyek FastAPI + PostgreSQL & Data Uji

Type: task
Status: open
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
