# Spesifikasi Visualisasi Funnel di Dashboard Super Admin (FR-24)

Type: grilling
Status: resolved
Blocked by: none

## Question

Fitur ini akan dimasukkan ke dalam website (Dashboard Super Admin FR-24). Kita perlu menetapkan spesifikasi tampilan dan kontrak JSON API-nya:
1. **Bentuk Visualisasi**: Apakah ditampilkan sebagai Horizontal/Vertical Funnel Bar Chart (menunjukkan jumlah pengunjung unik, % konversi bertahap, % konversi total, dan % drop-off di tiap transisi)?
2. **Metrik Pendukung**: Apakah perlu menampilkan **Median & P90 Waktu Konversi (Time-to-Convert)** dari kunjungan ke akun jadi, serta **Breakdown Error Validasi**?
3. **Segmentasi & Halaman Demo Website**: Dimensi filter apa saja yang dibutuhkan di UI website (misal: Perangkat `Desktop vs Mobile`, Sumber Trafik `utm_source`, dan Rentang Tanggal `7d`/`30d`/`90d`/`all`), dan apakah kita akan langsung membangun halaman web interaktif (simulasi form registrasi FR-01 + live Dashboard Super Admin FR-24) di workspace ini?

## Resolution

Spesifikasi kontrak endpoint agregasi dan antarmuka website Dashboard Super Admin (FR-24) ditetapkan sebagai berikut:

1. **Kontrak Endpoint Agregasi Funnel**:
   - `GET /api/v1/admin/funnel`
   - **Query Parameters**:
     - `rentang_waktu`: `7d` | `30d` | `90d` | `all` (default: `30d`)
     - `device_type`: `desktop` | `mobile` | `tablet` | `None` (opsional)
     - `utm_source`: `str` | `None` (opsional)
   - **Struktur Respons JSON**:
     ```json
     {
       "rentang_waktu": "30d",
       "filter": {
         "device_type": null,
         "utm_source": null
       },
       "kpi": {
         "total_visitors": 200,
         "total_accounts_created": 72,
         "overall_conversion_rate": 36.0,
         "median_time_to_convert_seconds": 64.5,
         "p90_time_to_convert_seconds": 142.0
       },
       "stages": [
         {
           "step": 1,
           "stage": "page_visit",
           "label": "Kunjungan Halaman",
           "unique_users": 200,
           "step_conversion_rate": 100.0,
           "overall_conversion_rate": 100.0,
           "drop_off_users": 0,
           "drop_off_rate": 0.0
         },
         {
           "step": 2,
           "stage": "click_register",
           "label": "Klik Pendaftaran",
           "unique_users": 140,
           "step_conversion_rate": 70.0,
           "overall_conversion_rate": 70.0,
           "drop_off_users": 60,
           "drop_off_rate": 30.0
         },
         {
           "step": 3,
           "stage": "start_registration",
           "label": "Memulai Registrasi",
           "unique_users": 110,
           "step_conversion_rate": 78.6,
           "overall_conversion_rate": 55.0,
           "drop_off_users": 30,
           "drop_off_rate": 21.4
         },
         {
           "step": 4,
           "stage": "account_created",
           "label": "Akun Berhasil Dibuat",
           "unique_users": 72,
           "step_conversion_rate": 65.5,
           "overall_conversion_rate": 36.0,
           "drop_off_users": 38,
           "drop_off_rate": 34.5
         }
       ],
       "drop_off_attribution": {
         "total_step3_drop_off": 38,
         "form_abandonment_users": 22,
         "validation_error_users": 16,
         "error_breakdown": {
           "duplicate_email": 11,
           "validation_failed": 5
         }
       },
       "segment_by_device": [
         {
           "device_type": "desktop",
           "visitors": 120,
           "accounts_created": 51,
           "overall_conversion_rate": 42.5
         },
         {
           "device_type": "mobile",
           "visitors": 80,
           "accounts_created": 21,
           "overall_conversion_rate": 26.3
         }
       ]
     }
     ```

2. **Paket Deliverable untuk Website SIAP OSN**:
   - **Backend FastAPI + SQLAlchemy (`src/funnel_analytics/`)**: Model `UserAccount` (merepresentasikan tabel `users` FR-01) dan `FunnelEvent` (`funnel_events`), layanan kalkulasi funnel monotonik ketat, endpoint registrasi FR-01 (`POST /api/v1/auth/register`), endpoint ingest (`POST /api/v1/analytics/events/funnel`), dan endpoint agregasi (`GET /api/v1/admin/funnel`).
   - **Script Tracker Frontend (`static/siap-osn-funnel-tracker.js`)**: Modul JavaScript mandiri yang mengatur `anonymous_id` (`localStorage`), `session_id` (`sessionStorage`), auto-backfill `/register`, serta pengiriman event 4 tahap.
   - **Antarmuka Website Interaktif (`static/index.html`)**: Menampilkan dua tampilan terintegrasi:
     1. **Simulasi Portal Registrasi Siswa (FR-01)**: Landing page, tombol daftar, dan form registrasi nyata untuk menguji setiap tahap funnel secara langsung.
     2. **Dashboard Super Admin (FR-24) Conversion Funnel**: Kartu KPI, grafik batang berjenjang 4 tahap dengan indikator drop-off, panel atribusi kegagalan Tahap 3 ke Tahap 4, tabel komparasi perangkat, dan filter interaktif.
