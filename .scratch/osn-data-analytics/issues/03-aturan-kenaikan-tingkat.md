# Aturan Kenaikan Tingkat

Type: grilling
Status: resolved
Blocked by: none

## Question

FR-15 (Kenaikan Tingkat) memeriksa "pencapaian siswa terhadap ketentuan tingkat" untuk
membuka akses ke Tingkat seleksi berikutnya (Kabupaten → Provinsi → Nasional). Apa
persisnya syarat kenaikan itu — nilai minimum di Hasil Simulasi (tiket 01), status
Peta Kompetensi tertentu (mis. semua/sebagian besar Kompetensi harus Cukup), progress
belajar minimum (tiket 02), atau kombinasi beberapa syarat? Apakah syarat ini
dikonfigurasi Super Admin per Tingkat (mirip Aturan Pemetaan)? Resolusi tiket ini
harus mencakup rancangan skema penyimpanan untuk aturan & status kenaikan tingkat per
siswa.

Ditunggu sampai tiket "Aturan Skor & Hasil Simulasi" dan "Definisi & Formula Progress
Belajar" selesai karena aturan kenaikan tingkat kemungkinan bergantung pada keduanya.

## Resolution

Kenaikan Tingkat (FR-15) mengatur pembukaan akses siswa ke Tingkat Seleksi berikutnya
(Kabupaten → Provinsi → Nasional) secara bertahap dan objektif berdasarkan performa ujian.

- **Kriteria Kelayakan**: Kombinasi dua syarat mutlak:
  1. **Skor Simulasi minimum**: nilai total pengerjaan simulasi resmi mencapai ambang batas tertentu.
  2. **Penguasaan Peta Kompetensi**: persentase Kompetensi berstatus **Cukup** pada tingkat tersebut mencapai ambang batas tertentu.
  - *Progress Belajar (tiket 02) tidak dijadikan syarat kenaikan*: progress murni sinyal konsumsi materi/keterlibatan, bukan bukti mastery. Penguasaan materi dibuktikan melalui hasil tes (tiket 01).
- **Ruang Lingkup Evaluasi (Single Attempt)**: Dievaluasi per satu sesi pengerjaan Simulasi Seleksi OSN (FR-11/FR-12). Siswa dinyatakan lulus kenaikan tingkat jika dalam **satu attempt simulasi resmi**, kedua syarat (skor dan % kompetensi Cukup) terpenuhi sekaligus. Bersifat self-contained, auditable, dan tidak bergantung pada status ambigu sesi-sesi terpisah.
- **Formula Persentase Kompetensi Cukup**:
  $$\text{persentase\_cukup} = \frac{\text{jumlah Kompetensi berstatus Cukup pada attempt ini}}{\text{total seluruh Kompetensi yang terdaftar pada Tingkat Seleksi tersebut}} \times 100\%$$
  Denominator dihitung terhadap total silabus kompetensi pada tingkat tersebut untuk memastikan simulasi yang dikerjakan benar-benar komprehensif.
- **Sifat Pembukaan Akses (Permanent & Unidirectional)**:
  - Sekali terbuka (*unlocked*), akses ke tingkat berikutnya bersifat **permanen** — jika siswa mencoba simulasi lain di kemudian hari dan mendapat skor rendah, hak akses tingkat yang sudah terbuka **tidak akan dicabut/terkunci kembali**.
  - Siswa tetap bebas mengakses dan berlatih pada tingkat-tingkat sebelumnya yang sudah diselesaikan (akses tidak pernah ditutup ke belakang).
- **Progresi & Akses Awal**:
  - Siswa baru terdaftar otomatis memiliki akses terbuka ke **Tingkat Kabupaten** (`status = 'terbuka'`, `dibuka_karena = 'default_awal'`), sedangkan Provinsi dan Nasional terkunci (`status = 'terkunci'`).
  - Mendukung **manual override** oleh Super Admin (FR-17) untuk memberikan akses langsung ke tingkat tertentu (mis. bagi siswa yang sudah terbukti lolos seleksi OSN-K di sekolah) dengan mencatat alasan override.
- **Konfigurasi Super Admin & Default Seed**:
  - Dikonfigurasi Super Admin per transisi tingkat (`tingkat_asal_id` → `tingkat_tujuan_id`).
  - Tingkat Nasional merupakan jenjang puncak (tidak memiliki tingkat tujuan berikutnya).
  - **Default bawaan** (di-seed otomatis pada sistem):
    - **Kabupaten → Provinsi**: Skor Simulasi Min = 75.0, Persentase Kompetensi Cukup Min = 80.0%
    - **Provinsi → Nasional**: Skor Simulasi Min = 85.0, Persentase Kompetensi Cukup Min = 85.0%

### Skema penyimpanan

**`aturan_kenaikan_tingkat`** (konfigurasi Super Admin per transisi tingkat)

| kolom | tipe | keterangan |
|---|---|---|
| id | PK | |
| tingkat_asal_id | FK | tingkat seleksi prasyarat (Kabupaten / Provinsi) |
| tingkat_tujuan_id | FK | tingkat seleksi yang akan dibuka (Provinsi / Nasional) |
| skor_simulasi_min | numeric | skor simulasi minimal (0–100), default 75/85 |
| persentase_kompetensi_cukup_min | numeric | persentase minimum kompetensi Cukup (0–100), default 80/85 |
| aktif | boolean | default true |
| dibuat_pada / diperbarui_pada | timestamp | |

Unique: (tingkat_asal_id, tingkat_tujuan_id).

**`akses_tingkat_siswa`** (state akses aktif per siswa per tingkat seleksi)

| kolom | tipe | keterangan |
|---|---|---|
| id | PK | |
| siswa_id | FK (eksternal) | referensi siswa |
| tingkat_seleksi_id | FK | referensi tingkat (Kabupaten, Provinsi, Nasional) |
| status | enum('terbuka','terkunci') | status akses siswa ke tingkat ini |
| dibuka_karena | enum('default_awal','lulus_evaluasi','manual_admin') | alasan tingkat terbuka |
| hasil_tes_id | FK nullable → hasil_tes | pemicu kelulusan (jika dibuka_karena='lulus_evaluasi') |
| dibuka_pada | timestamp nullable | waktu saat akses dibuka |
| catatan | text nullable | alasan override admin (jika manual_admin) |
| dibuat_pada / diperbarui_pada | timestamp | |

Unique: (siswa_id, tingkat_seleksi_id).

**`riwayat_evaluasi_kenaikan`** (audit log setiap evaluasi saat submit simulasi)

| kolom | tipe | keterangan |
|---|---|---|
| id | PK | |
| siswa_id | FK (eksternal) | |
| hasil_tes_id | FK → hasil_tes | attempt simulasi yang dievaluasi |
| aturan_kenaikan_id | FK → aturan_kenaikan_tingkat | aturan yang dipakai saat evaluasi |
| skor_aktual | numeric | skor yang diperoleh di hasil_tes |
| skor_target | numeric | snapshot skor_simulasi_min saat evaluasi |
| syarat_skor_lulus | boolean | apakah skor_aktual >= skor_target |
| persentase_cukup_aktual | numeric | persentase kompetensi Cukup aktual |
| persentase_cukup_target | numeric | snapshot persentase_kompetensi_cukup_min saat evaluasi |
| syarat_kompetensi_lulus | boolean | apakah persentase_cukup_aktual >= persentase_cukup_target |
| hasil_evaluasi | enum('lulus','tidak_lulus') | lulus jika kedua syarat bernilai true |
| dievaluasi_pada | timestamp | default now |

### Dependensi turunan

- Tiket 04 (Metrik Dashboard Super Admin): dapat mengagregasi laju kelulusan/distribusi siswa per tingkat dari `akses_tingkat_siswa` dan tingkat kesulitan dari `riwayat_evaluasi_kenaikan`.
- Tiket 11 (Kontrak API: Pemetaan Kompetensi & Rekomendasi Materi): respons `submit_simulasi` menyertakan objek hasil evaluasi kenaikan tingkat (`kenaikan_tingkat`), dan menyediakan endpoint query status akses tingkat siswa.
