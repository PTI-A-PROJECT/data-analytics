# Task: Selaraskan Instrumentasi Timestamp Per Soal dengan Tim Fullstack

Type: task
Status: open
Blocked by: none

## Question

Kecepatan Pengerjaan (lihat `CONTEXT.md`) butuh timestamp dibuka & dijawab per soal
saat Pre-Test (FR-06) dan Simulasi (FR-11) — data ini belum ada di brief saat ini
(brief hanya punya jawaban final per soal + durasi total simulasi). Selesaikan tiket
ini dengan mengonfirmasi ke tim fullstack bahwa instrumentasi ini akan ditambahkan,
menyepakati bentuk datanya (mis. field `dibuka_at`/`dijawab_at` per jawaban), dan
mencatat kesepakatan tersebut sebagai jawaban.

## Answer

Hasil penyelarasan dengan tim fullstack terkait penambahan field Subkompetensi pada entitas Materi disepakati sebagai berikut:

### 1. Aturan Relasi & Kardinalitas
- **Kardinalitas 1:1**: Tepat **1 Subkompetensi per Materi** (`materi.subkompetensi_id` sebagai Foreign Key tunggal, non-array).
- **Desain Modular**: Setiap materi disusun secara modular berfokus pada 1 unit subkompetensi spesifik (misal: "Graph Traversal BFS/DFS", bukan satu modul raksasa "Struktur Data"). Ini menjamin engine Rekomendasi Materi (kelemahan terendah duluan) dan metrik Progress Belajar per subkompetensi dapat bekerja secara deterministik tanpa bias multi-topik.

### 2. Format Data & Tipe Identifier
- Seluruh identifier (`materi_id`, `subkompetensi_id`, `kompetensi_id`, `tingkat_seleksi_id`, `siswa_id`) disepakati menggunakan standar **UUID string (v4)** (contoh: `c1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c`).
- Menjamin decoupling penuh antara database internal Fullstack dan Data & Analytics, serta mencegah enumerasi sekuensial numerik di API publik.

### 3. Integritas Skema & Skrip Migrasi Database (Sisi Fullstack)
- Field `subkompetensi_id` bersifat **Wajib (`NOT NULL`)** pada tabel materi di database fullstack.
- **DDL / Skrip Migrasi PostgreSQL (Fullstack)**:
  ```sql
  -- 1. Tambahkan kolom subkompetensi_id (UUID) ke tabel materi
  ALTER TABLE materi
    ADD COLUMN subkompetensi_id UUID NOT NULL,
    ADD CONSTRAINT fk_materi_subkompetensi
      FOREIGN KEY (subkompetensi_id)
      REFERENCES subkompetensi(id)
      ON DELETE RESTRICT;

  -- 2. Buat index untuk mempercepat filter materi berdasarkan subkompetensi
  CREATE INDEX idx_materi_subkompetensi_id ON materi(subkompetensi_id);
  ```
- Aturan `ON DELETE RESTRICT` diberlakukan agar data referensi Subkompetensi tidak dapat dihapus jika masih ada Materi yang terikat padanya.

### 4. Spesifikasi UI Admin Manajemen Materi (FR-19)
- **Cascading Dropdown**: Pada antarmuka Super Admin untuk CRUD Materi (FR-19), input kategori dibuat berjenjang 3 level:
  1. **Tingkat Seleksi** (Kabupaten / Kota, Provinsi, Nasional)
  2. **Kompetensi** (otomatis terfilter berdasarkan Tingkat Seleksi terpilih)
  3. **Subkompetensi** (otomatis terfilter berdasarkan Kompetensi terpilih)
- **Validasi Form**: Form tidak dapat disubmit (`Save` disabled) jika `subkompetensi_id` belum dipilih.

### 5. Struktur Kontrak Payload Antar-Layanan
Sesuai ADR 0002 (Data & Analytics tidak menyimpan tabel katalog Materi sendiri), tim fullstack menyuplai metadata Materi pada dua skenario panggilan API:

#### A. Event Pelaporan Halaman Materi Terbaca (Progress Belajar)
Dipanggil saat siswa membaca halaman materi (sinkron atau via webhook internal backend):
```json
{
  "siswa_id": "8f3b2c14-52d3-4a11-9a7e-4b2a8d3e1101",
  "materi_id": "c1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
  "subkompetensi_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "tingkat_seleksi_id": "b5a4c3d2-e1f0-4a9b-8c7d-6e5f4a3b2c1d",
  "total_halaman": 12,
  "halaman_dibuka": 5,
  "timestamp": "2026-09-22T06:30:00Z"
}
```

#### B. Request Rekomendasi Materi & Evaluasi Progress Belajar
Dipanggil oleh backend fullstack untuk mendapatkan daftar rekomendasi materi beserta progres siswa per subkompetensi:
```json
{
  "siswa_id": "8f3b2c14-52d3-4a11-9a7e-4b2a8d3e1101",
  "tingkat_seleksi_id": "b5a4c3d2-e1f0-4a9b-8c7d-6e5f4a3b2c1d",
  "katalog_materi": [
    {
      "materi_id": "c1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
      "subkompetensi_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "judul": "Representasi Graf & Matriks Keterhubungan",
      "total_halaman": 12,
      "urutan": 1
    },
    {
      "materi_id": "d2e3f4a5-b6c7-4d8e-9f0a-1b2c3d4e5f6a",
      "subkompetensi_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "judul": "Penelusuran Graf: BFS dan DFS",
      "total_halaman": 15,
      "urutan": 2
    }
  ]
}
```

### 6. Pydantic DTO (Layanan Data & Analytics)
Model validasi Pydantic v2 yang diimplementasikan di layanan Data & Analytics:
```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

class MateriMetadataDTO(BaseModel):
    materi_id: UUID
    subkompetensi_id: UUID
    judul: str
    total_halaman: int = Field(..., gt=0, description="Total halaman materi, minimal 1")
    urutan: int = Field(default=1, ge=1, description="Urutan penyajian materi dalam subkompetensi")

class HalamanMateriEventDTO(BaseModel):
    siswa_id: UUID
    materi_id: UUID
    subkompetensi_id: UUID
    tingkat_seleksi_id: UUID
    total_halaman: int = Field(..., gt=0)
    halaman_dibuka: int = Field(..., ge=1)
    timestamp: datetime
```

### 7. Penanganan Kasus Khusus (Edge Cases)
- **Subkompetensi Tanpa Materi**: Jika Subkompetensi berstatus *Belum Cukup* namun belum ada materi di-tag ke sana oleh admin, engine rekomendasi menghasilkan entri subkompetensi dengan `rekomendasi_materi: []` dan flag `materi_tersedia: false`.
- **Perubahan Tag Subkompetensi pada Materi**: Jika admin mengubah tag `subkompetensi_id` suatu materi, record `progress_materi` siswa yang tersimpan akan di-update merujuk ke subkompetensi baru saat event pembacaan berikutnya diterima (ADR 0002).
- **Batas Nilai Halaman**: `halaman_dibuka` tidak boleh melebihi `total_halaman`; jika melebihi akibat inkonsistensi klien, backend mem-bound ke nilai `total_halaman`.

### 8. Pembagian Tanggung Jawab & Timeline
- **Tim Fullstack**: Mengimplementasikan migrasi DDL database, cascading dropdown di form admin FR-19, dan penyediaan payload katalog/event.
- **Tim Data & Analytics**: Menyediakan skema DTO Pydantic dan logika ranking rekomendasi materi di Tiket 11.
- **Target Ketersediaan**: Siap di environment development bersamaan dengan penyelesaian **Tiket 11 (Kontrak API Pemetaan & Rekomendasi)** sebelum fase integrasi pilot multi-sekolah dimulai.
