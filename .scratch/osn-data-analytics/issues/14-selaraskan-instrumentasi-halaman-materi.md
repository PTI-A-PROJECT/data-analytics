# Task: Selaraskan Instrumentasi Halaman Materi dengan Tim Fullstack

Type: task
Status: open
Blocked by: none

## Question

Tiket "Definisi & Formula Progress Belajar" memutuskan bahwa Materi terbagi jadi
Halaman Materi sekuensial, dan progress dilacak sebagai halaman tertinggi yang
dicapai siswa. Brief belum punya konsep ini sama sekali (FR-19 Manajemen Materi
hanya "judul, isi materi"). Selesaikan tiket ini dengan mengonfirmasi ke tim
fullstack bahwa: (1) Materi akan distrukturkan jadi halaman-halaman sekuensial,
(2) UI Layanan Belajar (FR-09) akan mengirim event ke layanan data & analytics saat
siswa mencapai suatu halaman (payload: siswa_id, materi_id, subkompetensi_id,
tingkat_seleksi_id, total_halaman, halaman_dicapai), dan mencatat kesepakatan
tersebut sebagai jawaban.
