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
- [Aturan Kenaikan Tingkat](.scratch/osn-data-analytics/issues/03-aturan-kenaikan-tingkat.md) — syarat = kombinasi skor simulasi minimum DAN persentase kompetensi Cukup minimum (dihitung terhadap total silabus tingkat) dalam satu attempt simulasi; akses bersifat linier (Kabupaten default terbuka, override Super Admin didukung) dan permanen (tidak pernah terkunci kembali); skema: `aturan_kenaikan_tingkat`, `akses_tingkat_siswa`, `riwayat_evaluasi_kenaikan`.
- [Fakta Arsitektural Tim Fullstack](.scratch/osn-data-analytics/issues/08-kumpulkan-fakta-fullstack.md) — relasi sekolah eksplisit via `sekolah_id` (disnapshot di `hasil_tes`); hosting co-located VPS Ubuntu via Docker Compose & internal bridge network; fullstack bertindak sebagai gatekeeper consent orang tua UU PDP, retensi 12 bulan dengan anonimisasi; beban pilot ~100 siswa (burst ~50 submissions) diproses sinkron <500ms.
- [Metrik Dashboard Super Admin](.scratch/osn-data-analytics/issues/04-metrik-dashboard-super-admin.md) — tampilan agregat platform default dengan filter opsional `sekolah_id` dan tabel komparasi sekolah; 5 komponen widget (KPI pengerjaan & kelulusan, distribusi tingkat aktif, tren harian, distribusi predikat, top 3 kompetensi kuat/lemah); komputasi real-time via query SQL terindeks; single endpoint terpadu `GET /api/v1/admin/dashboard`.

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
