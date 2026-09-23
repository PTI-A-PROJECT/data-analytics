# Map: Data & Analytics — OSN Informatika Test-Prep Platform

## Destination

Bangun & deploy layanan data & analytics (Python/FastAPI + PostgreSQL, API sinkron)
untuk platform OSN Informatika: memproses hasil tes pilihan ganda menjadi Peta
Kompetensi per siswa, menghasilkan Rekomendasi Materi otomatis, plus Skor/Hasil
Simulasi, Progress Belajar, Kenaikan Tingkat, dan Dashboard Super Admin — live nyata
di sekolah-sekolah pilot, arsitektur siap naik skala. Lihat `CONTEXT.md` untuk
glosarium domain lengkap.

## Notes

- **Domain**: platform persiapan OSN Informatika (brief lengkap di `brief 2.txt`).
  Scope effort ini = data & analytics saja; UI/fullstack dan pengelolaan konten
  soal/materi ada di tim lain.
- Baca `CONTEXT.md` (glosarium) dan `docs/adr/` sebelum mengerjakan tiket apa pun
  di map ini.
- Skills: `/grilling` untuk keputusan, `/domain-modeling` untuk istilah baru yang
  muncul saat mengerjakan tiket.
- **Arsitektur**: request/response API sinkron (bukan event-streaming) — backend
  fullstack memanggil endpoint layanan ini setelah siswa submit pre-test/simulasi.
- **Stack**: Python (FastAPI) + PostgreSQL, full open-source/self-hosted.
- **Soal**: pilihan ganda saja (tidak ada code judge/eksekusi kode).
- **Skala**: pilot multi-sekolah, arsitektur harus siap naik skala lebih tinggi.
- Keputusan fondasi (Kompetensi/Subkompetensi, Aturan Pemetaan, Status Pemetaan,
  Peta Kompetensi, Rekomendasi Materi, Kecepatan Pengerjaan) sudah dipatok di sesi
  charting ini — lihat `CONTEXT.md`. ADR 0001 mencatat deviasi dari brief (Materi
  perlu tag Subkompetensi, bukan cuma Kompetensi).

## Decisions so far

- [Riset: Kepatuhan UU PDP untuk Data Siswa](.scratch/osn-data-analytics/issues/12-riset-uu-pdp-data-siswa.md) — consent sekolah saja tidak cukup untuk data anak (butuh consent eksplisit orang tua/wali terpisah, Pasal 25(2)); tidak ada durasi retensi baku (pengendali data wajib menetapkan sendiri & auto-hapus); keamanan wajib berbasis risiko + DPIA karena data sensitif; PP 33/2026 (aturan turunan) baru ditemukan lewat sumber sekunder, perlu verifikasi teks resmi sebelum dipakai final.
- [Aturan Skor & Hasil Simulasi](.scratch/osn-data-analytics/issues/01-aturan-skor-hasil-simulasi.md) — skor = persentase sederhana (tanpa bobot per soal), sama untuk Pre-Test & Simulasi; pencapaian = predikat tunggal berbasis rentang nilai, dikonfigurasi Super Admin per Tingkat Seleksi (default 90/80/70, di-seed otomatis), dibekukan per attempt; skema: `aturan_predikat`, `hasil_tes`, `hasil_tes_subkompetensi`.
- [Definisi & Formula Progress Belajar](.scratch/osn-data-analytics/issues/02-definisi-progress-belajar.md) — progress = konsumsi Materi (halaman tertinggi dicapai), denominator = rekomendasi terkini (snapshot, boleh naik-turun), dipecah per Subkompetensi; bukan sinyal mastery (itu tugas Peta Kompetensi lewat uji ulang); layanan ini tidak menyimpan katalog Materi sendiri (ADR 0002); skema: `progress_materi`.
- [Scaffold Proyek FastAPI + PostgreSQL & Data Uji](.scratch/osn-data-analytics/issues/09-scaffold-proyek.md) — kode tetap di paket datar `src/data_analytics/` (bukan direstrukturisasi ke layout domain/models/schemas/api/core terpisah); `tingkat_seleksi`/`aturan_pemetaan`/`kompetensi`/`subkompetensi`/`soal` dibuat sebagai tabel produksi sungguhan milik layanan ini (deviasi dari pola "tanpa FK, caller-supplied" — didokumentasikan di ADR 0003); Alembic migration `0001` + seed script idempotent (`python -m data_analytics.scripts.seed`) + FastAPI health endpoints, semua diverifikasi jalan end-to-end (bukan cuma dicatat — lihat catatan verifikasi di tiket 10 untuk kontras).
- [Rencana Deployment/Hosting untuk Sekolah Pilot](.scratch/osn-data-analytics/issues/10-rencana-deployment-pilot.md) — co-located di 1 VPS dengan aplikasi utama, `analytics-api`+`analytics-db` sebagai stack Docker Compose mandiri di `app-network` eksternal, port tidak diekspos ke publik, auth internal via `X-Internal-Token`, resource limit 1 CPU/1GB per container. Versi "Implementation" sebelumnya di file tiket ini fiktif (commit tidak pernah ada) — sudah diganti dengan implementasi nyata yang diverifikasi lewat build & run Docker sungguhan, bukan cuma ditulis. Endpoint `anonymize-expired` (kepatuhan retensi UU PDP, tiket 12) ditambahkan di luar scope Resolution tiket ini — dibiarkan (sudah teruji), ditandai eksplisit di file tiket; kepatuhan retensi **tidak harus** lewat mekanisme ini, draft policy/consent tanpa kode tambahan juga sah untuk skala pilot.
- [Kontrak API: Pemetaan Kompetensi & Rekomendasi Materi](.scratch/osn-data-analytics/issues/11-kontrak-api-pemetaan-rekomendasi.md) — **partial**: hanya endpoint 1 (`POST /api/v1/analytics/assessment/submit`) diimplementasikan; endpoint 2 (rekomendasi materi) ditunda, bergantung tiket 06 yang masih direview. Tiket 05 diperlakukan final: id caller-supplied (`siswa_id`/`sekolah_id`/`tingkat_seleksi_id`/`simulasi_id`/`subkompetensi_id`) dimigrasikan dari int ke str (UUID) di `hasil_tes`/`hasil_tes_subkompetensi`/`aturan_predikat`/`aturan_pemetaan` (migrasi `0003`; FK `aturan_pemetaan`→`tingkat_seleksi` lokal dilepas). `progress_materi` (tiket 02) dan PK katalog seed lokal (tiket 09) **sengaja belum** diselaraskan ke UUID — utang teknis terbuka. Algoritma Peta Kompetensi (FR-07, `pemetaan.py`) dan flag `butuh_optimasi` (tiket 05) baru ada sejak tiket ini; tabel `jawaban_siswa` baru (log per-soal, tiket 05). Diverifikasi end-to-end (migrasi + panggilan endpoint nyata terhadap SQLite file).
- [Aturan Kenaikan Tingkat](.scratch/osn-data-analytics/issues/03-aturan-kenaikan-tingkat.md) — syarat = kombinasi skor simulasi minimum DAN persentase kompetensi Cukup minimum (dihitung terhadap total silabus tingkat) dalam satu attempt simulasi; akses bersifat linier (Kabupaten default terbuka, override Super Admin didukung) dan permanen (tidak pernah terkunci kembali); skema: `aturan_kenaikan_tingkat`, `akses_tingkat_siswa`, `riwayat_evaluasi_kenaikan`. **Diimplementasikan** di `src/data_analytics/kenaikan.py` (algoritma murni) + `repository.py`/`api.py` (migrasi `0004`) — bukan sebagai paket terpisah (lihat catatan konsolidasi di bawah): endpoint `GET/POST /api/v1/analytics/tingkat/*`, terpisah dari `/assessment/submit` karena `tingkat_asal_id`/`tingkat_tujuan_id` merujuk katalog `tingkat_seleksi` LOKAL (int), bukan `tingkat_seleksi_id` UUID caller-supplied yang dipakai `hasil_tes` — evaluasi kenaikan karena itu dipanggil terpisah oleh Fullstack, membawa `jumlah_kompetensi_cukup`/`total_kompetensi_silabus` yang sudah mereka agregasikan sendiri (caller-supplied, sesuai ADR 0002), bukan otomatis terintegrasi di endpoint submit.
- [Fakta Arsitektural Tim Fullstack](.scratch/osn-data-analytics/issues/08-kumpulkan-fakta-fullstack.md) — relasi sekolah eksplisit via `sekolah_id` (disnapshot di `hasil_tes`); hosting co-located VPS Ubuntu via Docker Compose & internal bridge network; fullstack bertindak sebagai gatekeeper consent orang tua UU PDP, retensi 12 bulan dengan anonimisasi; beban pilot ~100 siswa (burst ~50 submissions) diproses sinkron <500ms.
- [Metrik Dashboard Super Admin](.scratch/osn-data-analytics/issues/04-metrik-dashboard-super-admin.md) — tampilan agregat platform default dengan filter opsional `sekolah_id` dan tabel komparasi sekolah; komputasi real-time via query SQL terindeks; endpoint `GET /api/v1/admin/dashboard`. **Diimplementasikan** di `src/data_analytics/dashboard.py`, scope dipersempit dari resolusi asli: KPI, distribusi tingkat (dari `akses_tingkat_siswa`), tren aktivitas harian, distribusi predikat, dan komparasi sekolah — semua konsisten tipe id. Section **"Analisis Penguasaan Kompetensi" (top/bottom 3 Kompetensi) SENGAJA belum diimplementasikan**: butuh join `hasil_tes_subkompetensi.subkompetensi_id` (str, UUID caller-supplied sejak tiket 11) ke katalog `kompetensi`/`subkompetensi` LOKAL (int) — gap yang sama dengan "progress_materi dan PK katalog seed lokal belum diselaraskan ke UUID" yang sudah dicatat tiket 11; menunggu penyelarasan skema id itu. Filter `tingkat_seleksi_id` dari resolusi asli juga tidak diimplementasikan (gap id yang sama).
- **Konsolidasi `app/` → `src/data_analytics/` (tiket 03/04, PR #7)**: kode PR #7 awalnya ditulis sebagai paket Python terpisah (`app/models/`, `app/services/`, `app/api/`, FastAPI app sendiri, `requirements.txt`) yang mendupilkasi `TingkatSeleksi`/`Kompetensi`/`Subkompetensi`/`Soal`/`HasilTes` yang sudah ada di `src/data_analytics/models.py`. **Sudah dikonsolidasikan**: `app/` dihapus, business logic (evaluasi kenaikan tingkat, agregasi dashboard) ditulis ulang di `src/data_analytics/kenaikan.py`/`dashboard.py` memakai model & konvensi id yang sudah ada (bukan reimplementasi int-id app/'s), dengan test baru (`test_kenaikan.py`, `test_kenaikan_repository.py`, `test_api_kenaikan_dashboard.py`) memakai fixture `session` yang sama dengan test lain — bukan `db`/`client` terpisah punya `app/`. Konsekuensi penyempitan scope dicatat di bullet tiket 03/04 di atas.
- [Selaraskan Instrumentasi Halaman Materi](.scratch/osn-data-analytics/issues/14-selaraskan-instrumentasi-halaman-materi.md) — event `POST /api/v1/analytics/events/materi-progress` (`X-Internal-Token`) live, memanggil `repository.catat_progress_halaman` (logika high-water-mark sudah ada sejak tiket 02 — gapnya murni endpoint HTTP yang belum pernah dibuat). **Deviasi**: payload id (`siswa_id`/`materi_id`/`subkompetensi_id`/`tingkat_seleksi_id`) tetap `int` mengikuti tabel `progress_materi` yang sudah ada, BUKAN UUID seperti contoh JSON resolusi tiket ini/06 — migrasi `progress_materi` ke UUID tetap utang teknis terbuka (sama seperti dicatat tiket 11), sengaja tidak disentuh di sini. Field `timestamp` divalidasi tapi tidak disimpan (server `diperbarui_pada` sudah menangkap itu).

## Not yet specified

- Strategi migrasi dari arsitektur sinkron ke async/event-driven bila traffic pilot
  berkembang pesat melampaui kapasitas sinkron — belum ada threshold/trigger konkret
  kapan ini perlu dipertimbangkan; akan dipertajam setelah pilot berjalan dan pola
  beban aktual terlihat.

## Out of scope

- Pembuatan & pengelolaan konten soal/materi (FR-16–22: Manajemen Siswa, Tingkat,
  Kompetensi, Materi, Soal, Simulasi, Pembahasan) — implementasi CRUD-nya milik
  tim lain; data & analytics hanya *mengonsumsi* data ini lewat kontrak yang jelas.
- Implementasi UI/fullstack semua fitur siswa (auth, dashboard, pre-test, simulasi,
  layanan belajar, riwayat hasil) — milik tim fullstack.
- Sistem code judge/eksekusi kode — tidak diperlukan (soal pilihan ganda saja).
- Infrastruktur event-streaming (Kafka-class) — diputuskan diganti API sinkron
  (lihat Pertanyaan 9 sesi charting: alur data per-submission, bukan granular
  per-event, jadi request/response lebih sesuai).
