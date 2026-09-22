# Task: Selaraskan Instrumentasi Timestamp Per Soal dengan Tim Fullstack

Type: task
Status: resolved
Blocked by: none

## Question

Kecepatan Pengerjaan (lihat `CONTEXT.md`) butuh timestamp dibuka & dijawab per soal
saat Pre-Test (FR-06) dan Simulasi (FR-11) — data ini belum ada di brief saat ini
(brief hanya punya jawaban final per soal + durasi total simulasi). Selesaikan tiket
ini dengan mengonfirmasi ke tim fullstack bahwa instrumentasi ini akan ditambahkan,
menyepakati bentuk datanya (mis. field `dibuka_at`/`dijawab_at` per jawaban), dan
mencatat kesepakatan tersebut sebagai jawaban.

## Answer

Hasil penyelarasan dengan tim fullstack terkait instrumentasi timestamp per soal
(Kecepatan Pengerjaan, `CONTEXT.md`) untuk Pre-Test (FR-06) dan Simulasi (FR-11)
disepakati sebagai berikut:

### 1. Apa yang Diinstrumentasi di Sisi Fullstack
- UI Pre-Test/Simulasi mencatat **`dibuka_at`** (timestamp pertama kali soal
  ditampilkan ke siswa) dan **`dijawab_at`** (timestamp saat jawaban untuk soal
  itu final — siswa pindah ke soal lain atau submit tes) untuk **setiap soal**,
  bukan cuma durasi total tes.
- **Navigasi maju-mundur**: siswa boleh berpindah bebas antar soal sebelum submit
  akhir (tidak ada penguncian sekuensial seperti Halaman Materi — tiket 14). Jika
  siswa membuka ulang soal yang sama, fullstack mengakumulasikan tiap interval
  buka→tinggalkan sebagai durasi terpisah dan menjumlahkannya, bukan hanya
  memakai interval pembukaan terakhir. Ini mencegah siswa membuat `durasi_detik`
  tampak singkat dengan cara sengaja meninggalkan lalu kembali ke soal tepat
  sebelum submit.

### 2. Field yang Dikirim ke Data & Analytics: `durasi_detik`, Bukan Timestamp Mentah
- Fullstack **tidak** mengirim `dibuka_at`/`dijawab_at` mentah ke layanan Data &
  Analytics. Sebagai gantinya, fullstack menghitung `durasi_detik` (total detik
  aktif di soal tsb, hasil akumulasi §1) di sisi fullstack dan mengirim nilai itu
  saja — field ini **sudah ada** di kontrak `POST
  /api/v1/analytics/assessment/submit` (`JawabanSiswaRequest.durasi_detik`,
  tiket 11), yang mengadopsi definisi durasi dari tiket 05 ("selisih waktu mulai
  & kirim").
- Alasan: sesuai ADR 0002 (Data & Analytics stateless, tidak menyimpan
  master Soal), layanan ini hanya butuh *durasi*, bukan *kapan persisnya* — payload
  tetap ramping dan tidak membawa jejak timestamp granular siswa yang tidak
  punya konsumen di sisi analytics. Timestamp mentah (`dibuka_at`/`dijawab_at`)
  tetap tersimpan di database fullstack untuk kebutuhan audit/anti-kecurangan
  mereka sendiri, di luar scope layanan ini.

### 3. Status Implementasi
- **Sudah diimplementasikan** — kebutuhan tiket ini (data per-soal open/answer
  yang menghasilkan durasi) sudah terpenuhi lewat kontrak tiket 11 yang berjalan
  di `POST /api/v1/analytics/assessment/submit`: `JawabanSiswaRequest.durasi_detik`
  (`src/data_analytics/schemas.py`) dan pemakaiannya di `catat_submission_tes`
  (`src/data_analytics/repository.py`) untuk menghitung `is_lambat`/`butuh_optimasi`
  (`src/data_analytics/pemetaan.py`).
- **Tidak ada perubahan skema/kode** yang dibutuhkan dari tiket ini — kesepakatan
  di atas mengonfirmasi bahwa bentuk data yang sudah dibangun tiket 11 memang
  hasil instrumentasi timestamp per soal, bukan angka yang caller bebas
  karang-karang. Ini menutup catatan "coordination dependency, not yet a settled
  data contract" di glosarium `CONTEXT.md` (Kecepatan Pengerjaan).

### 4. Dipertimbangkan tapi Ditolak
- **Kirim `dibuka_at`/`dijawab_at` mentah ke Data & Analytics, hitung
  `durasi_detik` di sisi kami**: ditolak — akan mengubah kontrak tiket 11 yang
  sudah diimplementasikan & di-merge (`durasi_detik` caller-supplied), menambah
  blast radius tanpa manfaat fungsional (hasil akhirnya identik), dan
  bertentangan dengan prinsip stateless ADR 0002.

### 5. Pembagian Tanggung Jawab & Timeline
- **Tim Fullstack**: Instrumentasi `dibuka_at`/`dijawab_at` per soal di UI
  Pre-Test/Simulasi, akumulasi durasi saat navigasi maju-mundur, hitung &
  kirim `durasi_detik` sesuai kontrak tiket 11 yang sudah berjalan.
- **Tim Data & Analytics**: Tidak ada pekerjaan tambahan — kontrak penerima
  (`durasi_detik`, `batas_waktu_detik`) sudah live sejak tiket 11.
- **Status**: Selesai — tidak memblokir tiket lain.

### Dependensi turunan yang terbuka
- Tidak ada. Tiket 05 dan 11 tetap final/settled seperti sebelumnya; tiket ini
  hanya mengonfirmasi provenance datanya.
