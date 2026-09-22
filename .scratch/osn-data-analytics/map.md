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
