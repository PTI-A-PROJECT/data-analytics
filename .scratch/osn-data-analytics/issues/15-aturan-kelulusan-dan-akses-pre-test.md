# Aturan Kelulusan & Akses Pre-Test Berjenjang

Type: grilling
Status: resolved
Blocked by: none

## Question

Bagaimana sistem dan logika kelulusan Pre-Test berjenjang (Kabupaten → Provinsi → Nasional)? Apa kriteria batas nilai/skor minimal (passing grade) yang harus dicapai siswa pada tiap jenjang pre-test? Bagaimana mekanisme pembukaan akses saat siswa lolos vs gagal (apakah lolos membuka akses ke simulasi pada tingkat tersebut dan/atau membuka pre-test tingkat berikutnya, dan jika gagal apa yang terjadi)? Bagaimana aturan ini dikonfigurasi Super Admin serta skema penyimpanan yang dibutuhkan?

## Resolution

Pre-Test (FR-06) berfungsi sebagai tes diagnostik awal berjenjang sekaligus gerbang pembuka akses menuju simulasi dan jenjang tingkat seleksi berikutnya.

- **Ujian Berjenjang (Kabupaten → Provinsi → Nasional)**:
  - Siswa wajib memulai dari Pre-Test Tingkat Kabupaten sebelum dapat mengakses Pre-Test Tingkat Provinsi.
  - Pre-Test Tingkat Provinsi hanya dapat diakses setelah siswa lulus Pre-Test Tingkat Kabupaten.
  - Pre-Test Tingkat Nasional hanya dapat diakses setelah siswa lulus Pre-Test Tingkat Provinsi.
  - Alur ini menjamin penguasaan materi bertahap dan mencegah siswa langsung melompat ke soal tingkat lanjut tanpa fondasi dasar.

- **Kriteria Kelulusan Minimal (Passing Grade)**:
  - Setiap jenjang Pre-Test memiliki batas skor minimal kelulusan (passing grade).
  - Dikonfigurasi Super Admin per Tingkat Seleksi.
  - Default bawaan (di-seed otomatis pada sistem):
    - Tingkat Kabupaten: Passing Grade = 70.0
    - Tingkat Provinsi: Passing Grade = 75.0
    - Tingkat Nasional: Passing Grade = 80.0

- **Mekanisme Akses (Lolos vs Gagal)**:
  - **Jika Lolos (`skor >= passing_grade`)**:
    1. Membuka akses pengerjaan **Simulasi** pada tingkat seleksi bersangkutan (`simulasi_terbuka = True`).
    2. Membuka akses pengerjaan **Pre-Test pada jenjang berikutnya** (`status = 'terbuka'`, `dibuka_karena = 'lulus_pre_test'`).
  - **Jika Gagal (`skor < passing_grade`)**:
    1. Akses Simulasi pada tingkat tersebut tetap terkunci (`simulasi_terbuka = False`).
    2. Akses ke jenjang berikutnya tetap terkunci (`status = 'terkunci'`).
    3. Siswa diarahkan mempelajari Rekomendasi Materi berdasarkan Subkompetensi yang berstatus `Belum Cukup` dari Peta Kompetensi hasil Pre-Test.
  - **Sifat Akses Permanen (Unidirectional)**:
    - Akses yang sudah terbuka bersifat permanen. Jika siswa mengulang Pre-Test di kemudian hari dan memperoleh nilai di bawah passing grade, hak akses simulasi dan tingkat berikutnya yang sudah terbuka tidak akan dicabut atau terkunci kembali.

### Skema Penyimpanan

1. **`aturan_pre_test`** (Konfigurasi Super Admin per Tingkat Seleksi)

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | PK | Identitas aturan |
| tingkat_seleksi_id | FK → tingkat_seleksi.id | Referensi tingkat seleksi (Kabupaten, Provinsi, Nasional) |
| skor_min | numeric(5,2) | Batas nilai minimal kelulusan pre-test (0-100) |
| aktif | boolean | Status aktif aturan (default true) |
| dibuat_pada / diperbarui_pada | timestamp | Waktu audit pembuatan dan pembaruan |

Unique: `tingkat_seleksi_id`.

2. **Perluasan `akses_tingkat_siswa`**

| Kolom Tambahan | Tipe | Keterangan |
|---|---|---|
| simulasi_terbuka | boolean | Status pembukaan akses simulasi pada tingkat ini (default false) |

3. **`riwayat_evaluasi_pre_test`** (Audit Log Kelulusan Pre-Test)

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | PK | |
| siswa_id | string | Referensi siswa |
| hasil_tes_id | FK → hasil_tes.id | Attempt pre-test yang dievaluasi |
| tingkat_seleksi_id | FK → tingkat_seleksi.id | Tingkat seleksi yang dievaluasi |
| skor_aktual | numeric(5,2) | Skor perolehan siswa |
| passing_grade | numeric(5,2) | Snapshot batas skor minimal saat evaluasi |
| lulus | boolean | True jika skor_aktual >= passing_grade |
| dievaluasi_pada | timestamp | Waktu pencatatan evaluasi |

### Kontrak API

- `GET /api/v1/analytics/pre-test/aturan`: Mengambil daftar konfigurasi passing grade Pre-Test.
- `PUT /api/v1/analytics/pre-test/aturan/{aturan_id}`: Mengubah passing grade atau status aktif aturan.
- `POST /api/v1/analytics/pre-test/evaluasi`: Evaluasi kelulusan hasil submission Pre-Test oleh Fullstack.
- Respons `GET /api/v1/analytics/tingkat/{siswa_id}/akses`: Menyertakan field `simulasi_terbuka` pada setiap item tingkat seleksi.

