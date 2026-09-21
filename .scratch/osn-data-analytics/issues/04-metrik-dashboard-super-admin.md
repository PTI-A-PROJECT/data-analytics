# Metrik Dashboard Super Admin

Type: grilling
Status: open
Blocked by: 01, 02, 03, 08

## Question

FR-24 (Dashboard Super Admin) menyebut "jumlah siswa, aktivitas pengerjaan, distribusi
tingkat, serta data hasil pembelajaran dan simulasi" secara umum — statistik konkret
apa saja yang perlu ditampilkan? Apakah agregasi perlu dipecah per sekolah (butuh
model identitas sekolah — lihat tiket "Kumpulkan fakta dari tim fullstack")? Apakah
ada perbandingan antar-sekolah, atau tiap Super Admin hanya melihat data sekolahnya
sendiri? Bagaimana granularitas waktu (real-time vs snapshot harian)? Resolusi tiket
ini harus mencakup rancangan API/skema untuk endpoint dashboard admin.

Ditunggu sampai tiket Skor, Progress Belajar, Kenaikan Tingkat, dan pengumpulan fakta
dari tim fullstack (model identitas sekolah) selesai, karena dashboard mengagregasi
data dari semuanya.
