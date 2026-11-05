# Definisi Trigger & Identitas Anonim 4 Tahap Funnel

Type: grilling
Status: resolved
Blocked by: none

## Question

Dokumen System Analyst (Gambar 12 & Gambar 18) menggambarkan alur autentikasi dari `Buka Halaman Login/Registrasi` -> `Pilih Registrasi atau Login` -> `Isi Nama, Email, Password` -> `Validasi Data` -> `Simpan Akun Baru`.

Sebelum mengimplementasikan tracker di kode frontend dan backend website, kita perlu mengunci definisi teknis untuk tiap tahap:
1. **Tahap 1 (`page_visit`)**: Halaman mana saja yang dihitung sebagai titik masuk funnel (apakah hanya Landing Page `/` dan halaman `/login` + `/register`, atau semua halaman publik)?
2. **Tahap 2 (`click_register`)**: Apakah halaman Login dan Registrasi berada di satu URL dengan perpindahan tab (sesuai Gambar 12 `Pilih Registrasi atau Login`), atau halaman terpisah (`/register`)?
3. **Tahap 3 (`start_registration`)**: Kapan tepat event ini dikirim? Saat pengguna pertama kali mengetik/fokus pada salah satu input (`nama`/`email`/`password`), atau saat menekan tombol submit (`submitRegistrasi`), atau keduanya dipisah menjadi `form_started` dan `form_submitted`?
4. **Identitas Calon Pengguna**: Apakah kita menggunakan `localStorage` (`anonymous_id` UUID v4) + `sessionStorage` (`session_id`) yang dikirim bersama payload `submitRegistrasi` untuk menyatukan (stitch) riwayat kunjungan dengan `users.id` baru?

## Resolution

Keempat tahap interaksi calon pengguna dan mekanisme penyatuan identitas ditetapkan sebagai berikut:

1. **Definisi & Pemicu 4 Tahap Utama + 1 Sub-Event Validasi**:
   - **Tahap 1 (`page_visit`)**: Dipicu di sisi klien saat calon pengguna membuka halaman Landing (`/`) atau halaman Autentikasi (`/login`, `/register`). Dikirim sekali per sesi kunjungan.
   - **Tahap 2 (`click_register`)**: Dipicu saat calon pengguna menekan tombol CTA "Daftar" di Landing Page atau menekan tab/tautan "Registrasi" pada halaman Autentikasi (`Pilih Registrasi atau Login` pada Gambar 12).
   - **Aturan Auto-Backfill Kunjungan Langsung (`/register`)**: Apabila calon pengguna langsung membuka URL `/register` tanpa melewati halaman `/` atau `/login` pada sesi tersebut, tracker frontend otomatis mengirim `page_visit` dan `click_register` secara berurutan agar urutan sekuensial funnel tetap utuh.
   - **Tahap 3 (`start_registration`)**: Dipicu di sisi klien tepat saat calon pengguna mengetik karakter pertama (`onInput` pertama dalam sesi tersebut) pada salah satu field formulir pendaftaran (`nama`, `email`, atau `password`).
   - **Sub-Event Kegagalan Validasi (`registration_error`)**: Dipicu oleh backend (`Controller Auth`) apabila `submitRegistrasi(data)` gagal melewati `Validasi Data` (Gambar 12 & 18), dengan atribut `error_type` bernilai `duplicate_email` (gagal pada `cekEmailTerdaftar`) atau `validation_failed` (format email/password tidak memenuhi syarat FR-01).
   - **Tahap 4 (`account_created`)**: Dipicu oleh backend tepat setelah `simpanAkunBaru(data)` berhasil menyimpan baris siswa baru di tabel `users` (FR-01).

2. **Identitas Anonim & Penyatuan Identitas (Identity Stitching)**:
   - Browser membuat `anonymous_id` (UUID v4) di `localStorage` (bertahan lintas sesi pada perangkat yang sama) dan `session_id` (UUID v4) di `sessionStorage` (berlaku untuk sesi tab aktif).
   - Mengandalkan alamat IP ditolak karena pada skenario sekolah pilot, puluhan siswa di laboratorium komputer sekolah berbagi satu alamat IP publik yang sama.
   - Saat formulir registrasi dikirim (`submitRegistrasi`), frontend menyertakan `anonymous_id` dan `session_id` di dalam payload. Ketika akun berhasil dibuat, baris `account_created` menyimpan `anonymous_id` beserta `user_id` (UUID dari `users.id`), sehingga seluruh jejak pra-registrasi terhubung ke akun siswa baru.

### Dependensi turunan yang terbuka

- Tiket [03-aturan-kalkulasi-dan-jendela-konversi.md](03-aturan-kalkulasi-dan-jendela-konversi.md) kini tidak lagi terhalang dan siap diselesaikan pada Putaran 2.
