# Task: Kumpulkan Fakta dari Tim Fullstack

Type: task
Status: resolved
Blocked by: none

## Question

Beberapa fakta arsitektural belum diketahui dan perlu ditanyakan langsung ke tim
fullstack (bukan keputusan yang bisa diambil sendiri): (1) model identitas siswa ↔
sekolah — apakah ada entitas Sekolah eksplisit, atau siswa mendaftar individual tanpa
afiliasi sekolah formal dalam skema data; (2) di mana aplikasi utama saat ini/akan
di-hosting (menentukan opsi hosting termudah untuk layanan data & analytics); (3)
kebijakan kepatuhan data siswa (lihat juga tiket riset UU PDP) — apakah ada batasan
retensi/consent yang sudah ditetapkan; (4) timeline realistis sekolah pilot mulai
memakai sistem. Selesaikan tiket ini dengan mencatat jawaban dari tim fullstack untuk
tiap poin.

## Resolution

Seluruh 4 fakta arsitektural telah diselaraskan melalui sesi grilling terstruktur:

1. **Model Identitas Siswa ↔ Sekolah**:
   - Terdapat entitas `Sekolah` eksplisit di skema database aplikasi utama. Siswa terafiliasi ke sekolah tertentu.
   - Backend fullstack selalu menyertakan `sekolah_id` bersama `siswa_id` dalam setiap payload submission tes (`POST /api/v1/hasil-tes` dan endpoint pemetaan).
   - Layanan Data & Analytics membekukan `sekolah_id` sebagai snapshot pada tabel `hasil_tes` (nullable) saat attempt diselesaikan. Ini memungkinkan agregasi dan filter performa per sekolah di Dashboard Super Admin (FR-51) tanpa layanan analytics perlu mengelola CRUD data sekolah.
   - **Diimplementasikan**: kolom `sekolah_id` sudah ada di `HasilTes` (`src/data_analytics/models.py`) dan parameter `sekolah_id` di `catat_hasil_tes` (`src/data_analytics/repository.py`).

2. **Lokasi & Topologi Hosting**:
   - Layanan Data & Analytics akan **co-located** di 1 VPS (Ubuntu) yang sama dengan aplikasi utama menggunakan Docker Compose untuk fase pilot multi-sekolah.
   - Komunikasi antar-layanan berjalan privat di dalam Docker bridge network (`http://analytics:8000`), port 8000 tidak diekspos ke internet publik luar VPS.
   - Autentikasi panggilan antar-service diamankan dengan static shared secret pada header HTTP (`X-Internal-Token`).
   - Database PostgreSQL terpisah (dedicated container di Docker Compose atau database `analytics_db` terpisah) agar isolasi data dan eksekusi migrasi skema analytics mandiri dari skema aplikasi utama.
   - **Belum diimplementasikan di sini** — fakta ini adalah input untuk tiket [10-rencana-deployment-pilot.md](10-rencana-deployment-pilot.md) (Docker Compose, topologi VPS, database terpisah). Lihat catatan verifikasi di tiket 10 — bagian "## Implementation"-nya belum terkonfirmasi ada di repo.

3. **Kebijakan Consent Orang Tua & Retensi Data (UU PDP)**:
   - Backend fullstack bertindak sebagai *gatekeeper* kepatuhan UU PDP Pasal 25(2) (menangani verifikasi dan pencatatan consent eksplisit orang tua/wali untuk siswa minor sebelum mengizinkan pengerjaan tes).
   - Durasi retensi data performa/hasil tes siswa ditetapkan **1 siklus tahun ajaran OSN** (12 bulan).
   - Mekanisme pembersihan: Layanan Data & Analytics menyediakan endpoint internal pembersihan terjadwal (`POST /api/v1/admin/anonymize-expired`). Saat retensi kedaluwarsa, baris data tidak di-hard delete melainkan di-**anonimkan** (`siswa_id` di-set `NULL` / di-hash searah) agar data statistik agregat sekolah dan nasional tetap utuh untuk historis platform.
   - **Belum diimplementasikan di sini** — kebijakan consent gatekeeper adalah scope tiket [13-selaraskan-consent-orang-tua.md](13-selaraskan-consent-orang-tua.md); mekanisme pembersihan/anonymize-expired disebut sudah dibuat di tiket 10 (lihat catatan verifikasi di sana — belum terkonfirmasi ada di repo, jangan dianggap tersedia sampai diverifikasi).

4. **Timeline & Pola Beban Konkurensi Pilot**:
   - Timeline: Target go-live pilot dijadwalkan dalam **1–2 bulan ke depan** untuk 2–3 sekolah mitra (total ~100 siswa aktif).
   - Pola Beban: Simulasi dikerjakan secara **serentak di lab komputer sekolah**, menghasilkan lonjakan beban puncak (peak burst) ~50 request submission dalam jendela 5–10 menit saat waktu tes habis.
   - Performa: Pemrosesan skor dan pemetaan kompetensi tetap diproses secara **sinkron instan (<500ms)**. Komputasi matriks pilihan ganda sangat ringan di CPU Python; FastAPI (Gunicorn/Uvicorn workers + connection pool PostgreSQL) mampu menangani konkurensi ini tanpa membutuhkan antrean pesan asinkron (Kafka/Celery) yang berlebihan.
   - **Belum diimplementasikan di sini** — murni input kapasitas/perencanaan, tidak ada tiket kode spesifik yang menjadi tujuannya. Relevan sebagai konteks kapasitas untuk tiket 10 (topologi hosting) saat menentukan resource limits VPS.

### Dependensi turunan yang terbuka

- Tiket [10-rencana-deployment-pilot.md](10-rencana-deployment-pilot.md) kini **unblocked** (spesifikasi Docker Compose, co-located VPS, database terpisah, dan jaringan bridge siap dirumuskan).
- Tiket [11-kontrak-api-pemetaan-rekomendasi.md](11-kontrak-api-pemetaan-rekomendasi.md) dapat menyertakan `sekolah_id` pada payload submission tes.
- Tiket [13-selaraskan-consent-orang-tua.md](13-selaraskan-consent-orang-tua.md) selaras dengan peran fullstack sebagai gatekeeper consent orang tua.
