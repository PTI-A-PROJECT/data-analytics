# Map: User Analytics & Registration Conversion Funnel SIAP OSN

## Destination

Rancang dan integrasikan sistem pelacakan User Analytics & Conversion Funnel 4 tahap (`page_visit` -> `click_register` -> `start_registration` -> `account_created`) ke dalam website SIAP OSN (mengacu pada FR-01 Registrasi, Gambar 12, Gambar 18) serta tampilkan visualisasi konversi, drop-off, dan durasi pendaftaran pada Dashboard Super Admin (FR-24). Lihat `CONTEXT.md` untuk glosarium domain dan `analysis_plan.md` untuk rencana analisis lengkap.

## Notes

- **Domain**: Akuisisi & registrasi calon siswa pada platform persiapan OSN Informatika (SIAP OSN).
- **Acuan Utama**: `SIAP_OSN_System_Analyst_Document.docx.pdf` (FR-01, FR-24, ERD/PDM `users`, Activity Diagram Gambar 12, Sequence Diagram Gambar 18).
- **Skills**: `/grilling` dan `/domain-modeling` untuk menyelesaikan setiap tiket keputusan; `/funnel-analysis` untuk aturan kalkulasi konversi; `/stop-slop` untuk penulisan dokumentasi.
- **Prinsip Privasi (UU PDP)**: Jangan menyimpan PII (`nama`, `email`, `password`) pada event pra-registrasi (`page_visit`, `click_register`, `start_registration`). Gunakan `anonymous_id` (UUID v4) hingga akun resmi terbuat di tabel `users`.

## Decisions so far

- [Definisi Trigger & Identitas Anonim 4 Tahap Funnel](issues/01-definisi-trigger-dan-identitas-funnel.md): 4 tahap dikunci (`page_visit` di `/` atau `/login`, `click_register` di tombol/tab Daftar dengan auto-backfill bila masuk langsung ke `/register`, `start_registration` saat ketikan pertama di field form, `account_created` saat `simpanAkunBaru` berhasil di `Controller Auth`), ditambah sub-event `registration_error` (`duplicate_email`, `validation_failed`); identitas memakai `anonymous_id` (UUID v4 di `localStorage`) + `session_id` (`sessionStorage`) yang di-stitch ke `siswa_id` (`users.id`) saat akun terbuat.
- [Lokasi Penyimpanan & Kontrak Endpoint Ingest Funnel](issues/02-arsitektur-penyimpanan-dan-endpoint-ingest.md): disimpan di tabel `funnel_events` pada layanan `data-analytics` (FastAPI + PostgreSQL/SQLite) melalui endpoint `POST /api/v1/analytics/events/funnel` (dengan proxy first-party `/api/v1/onboarding/step` di web utama untuk menghindari AdBlocker), menyaring User-Agent bot/crawler secara otomatis, dan mematuhi UU PDP (tanpa menyimpan nama/email/password mentah di tabel event).
- [Aturan Kalkulasi Konversi, Jendela Waktu & Atribusi Drop-Off](issues/03-aturan-kalkulasi-dan-jendela-konversi.md): deduplikasi berbasis `COUNT(DISTINCT anonymous_id)` dengan syarat urutan monotonik ketat ($S_1 \rightarrow S_2 \rightarrow S_3 \rightarrow S_4$); drop-off Tahap 3 ke Tahap 4 dipecah menjadi `form_abandonment_users` vs `validation_error_users` (`duplicate_email`, `validation_failed`); `Time-to-Convert` dihitung dalam detik menggunakan kuantil Median (P50) dan P90 dengan filter `rentang_waktu` (`7d`, `30d`, `90d`, `all`).
- [Spesifikasi Visualisasi Funnel di Dashboard Super Admin (FR-24)](issues/04-spesifikasi-widget-dashboard-super-admin.md): endpoint `GET /api/v1/admin/funnel` menyuplai KPI, 4 tahap funnel, atribusi drop-off, dan komparasi perangkat; diwujudkan sebagai paket lengkap modul backend FastAPI + unit test `pytest`, script tracker frontend `siap-osn-funnel-tracker.js`, dan halaman website interaktif (Simulasi Registrasi Siswa FR-01 + Dashboard Super Admin FR-24).

## Issues (Frontier & Blocked)

<!-- Seluruh tiket keputusan telah diselesaikan (Frontier kosong). -->

## Not yet specified

- Integrasi funnel pra-registrasi dengan aktivasi pasca-registrasi (misal: apakah funnel nantinya perlu diperluas ke Tahap 5 "Pilih Tingkat Seleksi" FR-05 dan Tahap 6 "Selesai Pre-Test Pertama" FR-06 setelah metrik registrasi dasar berjalan stabil).
- Mekanisme retensi/pembersihan otomatis baris `funnel_events` untuk pengunjung anonim yang tidak pernah mendaftar setelah $N$ bulan.

## Out of scope

- Pelacakan perilaku di luar alur akuisisi/registrasi (seperti rekaman layar penuh, klik menu latihan, atau navigasi halaman materi yang sudah dicakup `riwayat_baca_halaman`).
- Penggunaan layanan analitik berbayar pihak ketiga (Mixpanel/Amplitude Cloud) karena platform SIAP OSN berjalan self-hosted di VPS sekolah pilot.
