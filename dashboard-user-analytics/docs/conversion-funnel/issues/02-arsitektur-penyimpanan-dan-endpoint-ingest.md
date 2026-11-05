# Lokasi Penyimpanan & Kontrak Endpoint Ingest Funnel

Type: grilling
Status: resolved
Blocked by: none

## Question

Pada ekosistem SIAP OSN, terdapat aplikasi web utama (Fullstack/Laravel yang mengelola autentikasi `users` sesuai FR-01) dan layanan `data-analytics` (FastAPI + PostgreSQL yang melayani analitik dan Dashboard Super Admin FR-24).

Keputusan arsitektur mana yang dipilih untuk menampung event conversion funnel:
1. **Opsi A (Langsung di Backend Fullstack/Laravel)**: Frontend mengirim event ke endpoint Laravel (`POST /api/telemetry/funnel`), disimpan di database aplikasi utama (satu transaksi dengan tabel `users` saat registrasi berhasil), lalu diekspos ke Dashboard Super Admin.
2. **Opsi B (Terpusat di Layanan `data-analytics` FastAPI)**: Backend Laravel meneruskan (atau melakukan batch/sinkron forward) event funnel ke layanan `data-analytics` (`POST /api/v1/analytics/events/funnel`) sehingga seluruh metrik Dashboard Super Admin (FR-24) tetap berada di satu layanan analitik.
3. Bagaimana perlindungan endpoint publik pra-login ini terhadap spam/bot (filter User-Agent crawler, rate limit per IP)?

## Resolution

Penyimpanan dan pemrosesan metrik Conversion Funnel ditempatkan di layanan **`data-analytics` (FastAPI + PostgreSQL)**, dilengkapi script tracker frontend dan komponen visual UI siap pasang untuk website SIAP OSN:

1. **Topologi Aliran Data**:
   - Event pra-registrasi (`page_visit`, `click_register`, `start_registration`) dikirim secara non-blocking (`keepalive: true`) dari frontend menuju backend, lalu dicatat ke tabel `funnel_events` melalui endpoint `POST /api/v1/analytics/events/funnel`.
   - Event pasca-submit (`registration_error` dan `account_created`) dikirim oleh `Controller Auth` saat memproses `submitRegistrasi(data)` (Gambar 18).
   - Untuk mencegah pemblokiran oleh ekstensi AdBlocker di browser siswa, rute proxy di sisi website utama menggunakan path netral first-party (`/api/v1/onboarding/step`) yang meneruskan payload ke layanan `data-analytics`.

2. **Perlindungan Privasi (UU PDP) & Penyaringan Bot**:
   - Tabel `funnel_events` dilarang menyimpan data pribadi mentah (`nama`, `email`, `password`) pada kolom `metadata`.
   - Endpoint ingest otomatis mengabaikan (return `202 Accepted` tanpa menyimpan baris) apabila header `User-Agent` cocok dengan pola bot/crawler (`bot`, `crawler`, `spider`, `headless`, `curl`, `python-requests`, `lighthouse`).

3. **Skema Penyimpanan (`funnel_events`)**:

| Kolom | Tipe | Constraint | Keterangan |
|---|---|---|---|
| `id` | `BIGSERIAL` / `INTEGER` | `PRIMARY KEY` | ID baris event |
| `anonymous_id` | `VARCHAR(36)` | `NOT NULL`, Indexed | UUID v4 dari `localStorage` calon pengguna |
| `session_id` | `VARCHAR(36)` | `NOT NULL`, Indexed | UUID v4 dari `sessionStorage` sesi kunjungan |
| `siswa_id` | `VARCHAR(36)` | `NULLABLE`, Indexed | UUID dari `users.id` (terisi saat `account_created`) |
| `sekolah_id` | `VARCHAR(36)` | `NULLABLE`, Indexed | Opsional jika pendaftaran melalui tautan afiliasi sekolah |
| `stage` | `VARCHAR(30)` | `NOT NULL`, Indexed | Enum: `page_visit`, `click_register`, `start_registration`, `registration_error`, `account_created` |
| `page_path` | `VARCHAR(255)` | `NOT NULL` | Path halaman tempat event terjadi (misal `/`, `/login`, `/register`) |
| `device_type` | `VARCHAR(20)` | `NOT NULL` | `desktop`, `mobile`, `tablet` |
| `utm_source` | `VARCHAR(100)` | `NULLABLE` | Sumber akuisisi/kampanye (misal `organik`, `grup_sekolah`, `instagram`) |
| `referrer` | `VARCHAR(255)` | `NULLABLE` | URL perujuk |
| `error_type` | `VARCHAR(50)` | `NULLABLE` | Diisi khusus saat `stage = 'registration_error'` (`duplicate_email`, `validation_failed`) |
| `occurred_at` | `TIMESTAMPTZ` | `NOT NULL` | Waktu kejadian event |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT NOW()` | Waktu pencatatan di server |

4. **Kontrak Endpoint Ingest**:
   - `POST /api/v1/analytics/events/funnel` (dilindungi `X-Internal-Token` untuk panggilan antar-layanan):
     ```json
     {
       "anonymous_id": "550e8400-e29b-41d4-a716-446655440000",
       "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
       "siswa_id": null,
       "stage": "click_register",
       "page_path": "/login",
       "device_type": "mobile",
       "utm_source": "grup_pembina_osn",
       "referrer": "https://osn.toki.id",
       "error_type": null,
       "occurred_at": "2026-10-27T20:30:00Z"
     }
     ```

### Dependensi turunan yang terbuka

- Tiket [04-spesifikasi-widget-dashboard-super-admin.md](04-spesifikasi-widget-dashboard-super-admin.md) kini telah memiliki kontrak penyimpanan dasar dan siap diselesaikan bersama Tiket 03 pada Putaran 2.
