# Penjelasan Mendalam: Konsep, Alur Langkah, dan Fungsi Halaman
# User Analytics & Conversion Funnel SIAP OSN

> **Panduan Lengkap**: Arsitektur Teknis, Teori Konversi Monotonik, Alur Operasional Pengguna, dan Implementasi Website

| Parameter | Keterangan |
|---|---|
| **Proyek** | Sistem Interaktif Adaptif Persiapan OSN (SIAP OSN) Bidang Informatika |
| **Acuan Dokumen** | `SIAP_OSN_System_Analyst_Document.docx.pdf` (FR-01 Registrasi Siswa, FR-24 Dashboard Super Admin, Gambar 12, Gambar 18, Gambar 24) |
| **Berkas Implementasi** | `static/index.html` (Antarmuka Ganda Portal Siswa & Dashboard Super Admin) |
| **Komponen Backend** | FastAPI + SQLAlchemy (`src/funnel_analytics/`) & Tracker SDK (`static/siap-osn-funnel-tracker.js`) |
| **Status Pengujian** | Terverifikasi Penuh via pytest (7 dari 7 skenario pengujian lolos 100%) |

---

## 1. Latar Belakang dan Urgensi Sistem

Dokumen Analisis Sistem SIAP OSN (`SIAP_OSN_System_Analyst_Document.docx.pdf`) mengatur kebutuhan fungsional registrasi siswa pada **FR-01** dan pemantauan sistem pada Dashboard Super Admin **FR-24**. Pada rancangan awal basis data (Physical Data Model / PDM, hal. 15), sistem hanya mencatat data transaksi saat akun telah berhasil dibuat di tabel `users`. Tidak ada mekanisme untuk merekam jejak calon siswa sebelum akun tersebut terbentuk.

Ketiadaan pencatatan pra-registrasi ini menimbulkan kebutaan informasi bagi pihak sekolah dan pengelola platform. Pengelola tidak dapat mengetahui berapa banyak siswa yang mengunjungi situs web, berapa banyak yang berminat mendaftar, di mana titik kebingungan siswa terjadi, dan berapa siswa yang terhambat oleh validasi formulir (seperti email duplikat atau kata sandi yang tidak memenuhi kriteria).

Halaman `static/index.html` dibangun untuk menyelesaikan masalah tersebut. Halaman ini menghadirkan antarmuka ganda (*Dual-View Interface*): sisi pertama mensimulasikan alur registrasi siswa secara langsung (**FR-01**), sedangkan sisi kedua menyajikan dasbor analitik konversi corong bagi Super Admin (**FR-24**).

---

## 2. Konsep Fundamental Conversion Funnel & User Analytics

### A. Konsep Corong Konversi (Conversion Funnel)
Corong konversi adalah model analitik yang memetakan perjalanan calon pengguna secara bertahap menuju tindakan akhir yang diharapkan (dalam kasus ini: pendaftaran akun siswa). Mengapa disebut corong? Karena pada setiap tahap yang harus dilalui, jumlah calon pengguna secara alamiah akan berkurang (*drop-off*). Corong ini memvisualisasikan di mana kebocoran terbesar terjadi sehingga tim pengembang dapat melakukan perbaikan yang tepat sasaran.

### B. Konsep Corong Monotonik Ketat (Strict Monotonic Funnel)
Banyak sistem pelacakan web mentah hanya menghitung jumlah kemunculan baris event secara terisolasi. Cara tersebut rentan menghasilkan anomali data, misalnya jumlah event klik daftar terlihat lebih banyak daripada jumlah kunjungan halaman karena masalah koneksi atau cache browser. Halaman ini menerapkan prinsip **Strict Monotonic Funnel**:

> **PRINSIP MONOTONIK KETAT:**
> Seorang calon pengguna unik (`anonymous_id`) hanya dihitung berhak masuk ke Tahap N apabila sistem dapat membuktikan bahwa pengguna tersebut telah melewati Tahap 1 sampai Tahap (N-1) secara kronologis dalam jendela waktu yang dipilih. Dengan aturan ini, volume pengguna dijamin selalu mengerucut:
> $$N_1 \ge N_2 \ge N_3 \ge N_4$$
> Rasio konversi antar-tahap tidak akan pernah melebihi 100%.

### C. Konsep Penyatuan Identitas (Identity Stitching)
Sebelum mendaftar, calon siswa berstatus sebagai pengunjung anonim yang belum memiliki `user_id`. Sistem memberikan `anonymous_id` (UUID v4) yang disimpan pada peramban siswa. Saat pendaftaran dinyatakan berhasil oleh sistem (FR-01), server menerbitkan `users.id` baru dan mengaitkannya ke `anonymous_id` tersebut. Seluruh jejak kunjungan, klik, dan durasi pengisian formulir yang semula anonim kini terikat ke riwayat resmi siswa tanpa kehilangan rekam jejak awal.

### D. Konsep Waktu Konversi (Time-to-Convert)
Mengukur kecepatan konversi sangat penting untuk memahami friksi antarmuka. Jika rata-rata waktu pendaftaran mencapai 10 menit untuk formulir sederhana, itu menandakan ada kebingungan pada instruksi halaman. Halaman ini menggunakan ukuran Median (P50) dan P90, bukan rata-rata biasa (*mean*), agar angka durasi tidak bias oleh siswa yang meninggalkan peramban dalam keadaan terbuka.

### E. Konsep Atribusi Drop-Off (Diagnosis Kebocoran)
Ketika calon siswa berhenti di antara Tahap 3 (Memulai Registrasi) dan Tahap 4 (Akun Berhasil Dibuat), sistem tidak sekadar menghitung jumlah orang yang hilang. Sistem membedah penyebabnya menjadi dua akar masalah yang berbeda:
1. **Form Abandonment**: Siswa menutup tab sebelum mengirim formulir.
2. **Gagal Validasi**: Siswa mengirim formulir namun ditolak sistem karena email sudah terdaftar (`duplicate_email`) atau format input/password tidak memenuhi syarat (`validation_failed`).

---

## 3. Langkah Operasional dan Alur Kerja Sistematis (End-to-End)

### A. Alur Langkah dari Sudut Pandang Calon Siswa (Alur Registrasi FR-01)
1. **Langkah 1 (Kunjungan Halaman)**: Calon siswa membuka situs web SIAP OSN (Landing Page). Script tracker di frontend memeriksa `localStorage` peramban. Jika belum ada, script membuat `anonymous_id` baru dan mengirim event `page_visit` secara otomatis.
2. **Langkah 2 (Klik Pendaftaran)**: Calon siswa membaca informasi persiapan seleksi OSN Informatika, lalu menekan tombol *'Daftar Sekarang'*. Aksi ini memicu event `click_register` dan memfokuskan kursor ke kolom formulir pendaftaran.
3. **Langkah 3 (Memulai Pengisian Formulir)**: Calon siswa mengetik karakter pertama pada kolom nama lengkap, email, atau password. Script tracker menangkap interaksi awal ini dan mengirim event `start_registration` tepat satu kali per sesi.
4. **Langkah 4 (Pengiriman Formulir & Validasi)**: Calon siswa menekan tombol *'Submit Registrasi'*. Permintaan dikirim ke Controller Auth (`POST /api/v1/auth/register`). Controller memvalidasi kelengkapan data dan mengecek fungsi `cekEmailTerdaftar(email)`.
5. **Langkah 5A (Jika Validasi Gagal)**: Jika email sudah pernah dipakai atau kata sandi kurang dari 8 karakter, sistem mencatat event `registration_error` dengan rincian penyebab (`duplicate_email` atau `validation_failed`) dan menampilkan pesan kesalahan merah.
6. **Langkah 5B (Jika Validasi Sukses)**: Jika data sah, sistem menyimpan baris baru ke tabel `users`, mencatat event `account_created`, menghubungkan `anonymous_id` dengan `users.id`, dan menampilkan pesan sukses pendaftaran.

### B. Alur Langkah dari Sudut Pandang Super Admin (Alur Analisis FR-24)
1. **Langkah 1 (Membuka Dasbor)**: Super Admin membuka halaman Dasbor Analisis Konversi melalui tab *Dashboard Super Admin*.
2. **Langkah 2 (Menetapkan Parameter Filter)**: Admin memilih rentang waktu evaluasi (misal 30 hari terakhir) dan kategori perangkat (Desktop, Mobile, Tablet) untuk melihat segmen pengguna tertentu.
3. **Langkah 3 (Membaca Kartu Indikator KPI)**: Admin melihat total pengunjung unik, jumlah akun yang terbentuk, rasio konversi keseluruhan, serta median waktu yang dibutuhkan siswa untuk mendaftar.
4. **Langkah 4 (Menganalisis Grafik Corong Visual)**: Admin memeriksa grafik batang bertingkat untuk melihat pada tahap mana penurunan (*drop-off*) paling curam terjadi.
5. **Langkah 5 (Mendiagnosis Rincian Kegagalan)**: Admin meninjau tabel Atribusi Drop-Off. Jika angka `duplicate_email` tinggi, artinya banyak siswa yang lupa bahwa mereka sudah memiliki akun, sehingga tombol *'Lupa Password'* perlu diperjelas.

---

## 4. Penjelasan Rinci Komponen Visual Halaman Web

| Nama Komponen | Letak Tampilan | Fungsi dan Cara Kerjanya |
|---|---|---|
| **Hero Box Landing Page** | Portal Siswa (Atas) | Memperkenalkan platform SIAP OSN dan menyediakan tombol simulasi kunjungan (`page_visit`) serta tombol ajakan daftar (`click_register`). |
| **Formulir Registrasi Siswa** | Portal Siswa (Tengah) | Menyediakan kolom input nama, email, dan kata sandi. Memicu `start_registration` saat pertama kali diketik, dan `submitRegistrasi` saat dikirim. |
| **Inspector Telemetri & Event Stream** | Portal Siswa (Kanan) | Menampilkan kode `anonymous_id` dan `session_id` aktif serta daftar log event yang baru saja dikirimkan ke server secara langsung. |
| **4 Kartu KPI Eksekutif** | Dashboard Admin (Atas) | Menampilkan angka total pengunjung unik, akun terdaftar, persentase konversi total, dan median waktu penyelesaian pendaftaran. |
| **Grafik Batang Corong Konversi** | Dashboard Admin (Tengah Kiri) | Visualisasi batang horizontal proporsional 4 tahap yang dilengkapi persentase konversi bertahap dan lencana merah jumlah siswa yang gugur. |
| **Tabel Atribusi Drop-Off Tahap 3 ke 4** | Dashboard Admin (Tengah Kanan) | Membagi jumlah siswa yang gugur di tahap formulir menjadi: Form Abandonment (tutup tab), Email Duplikat, dan Format Input Salah. |
| **Tabel Log Aktivitas Real-Time** | Dashboard Admin (Bawah) | Menampilkan aliran event aktivitas pengguna secara instan via Server-Sent Events (SSE) lengkap dengan waktu, URL, perangkat, dan status. |

---

## 5. Arsitektur Teknis dan Jaminan Kualitas Data

1. **Pemisahan Jalur Data (Decoupled Ingestion)**: Tracker frontend menggunakan metode fetch non-blocking dengan flag `keepalive` sehingga pengiriman data telemetri tidak pernah memperlambat navigasi peramban siswa.
2. **Aliran Log Real-Time (Server-Sent Events / SSE)**: Server menyediakan endpoint streaming `/api/v1/admin/events/stream` yang menyiarkan setiap interaksi calon pengguna (kunjungan, klik, ketikan form, error, konversi) ke Dashboard Super Admin secara instan tanpa membebani browser dengan polling berulang.
3. **Penyaringan Bot dan Crawler Otomatis**: Permintaan dari robot perayap mesin pencari (seperti Googlebot atau Lighthouse) secara otomatis diabaikan oleh server agar tidak merusak akurasi data kunjungan.
4. **Kepatuhan Undang-Undang Perlindungan Data Pribadi (UU PDP)**: Tabel telemetri analitik tidak menyimpan kata sandi mentah maupun alamat email lengkap siswa, melainkan hanya mencatat identifier teknis anonim dan status validasi.
