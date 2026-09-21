# Definisi & Formula Progress Belajar

Type: grilling
Status: resolved
Blocked by: none

## Question

FR-10 (Progress Belajar) bilang sistem "menghitung perkembangan pembelajaran siswa"
dari "data materi, latihan, aktivitas siswa" — tapi apa persisnya yang dihitung?
Apakah progress = proporsi Materi yang sudah dibuka/dibaca dari Rekomendasi Materi
yang diberikan? Apakah latihan soal (bukan hanya pre-test/simulasi resmi) masuk
hitungan? Apakah progress dihitung per Tingkat, per Kompetensi, atau keseluruhan?
Bagaimana hubungannya dengan Peta Kompetensi — apakah progress "menutup" saat status
Subkompetensi berubah dari Belum Cukup/Belum Teruji menjadi Cukup? Resolusi tiket ini
harus mencakup rancangan skema penyimpanan untuk data progress.

## Resolution

- **Yang diukur**: konsumsi Materi saja (proporsi halaman dibuka), **bukan** gabungan
  dengan Hasil Tes — Hasil Tes (tiket 01) sudah punya tracking sendiri.
- **Cara deteksi selesai**: otomatis dari akses. Materi terbagi jadi **Halaman Materi**
  sekuensial (siswa wajib urut untuk *maju* pertama kali, tapi bebas mundur/maju di
  antara halaman yang sudah pernah dicapai). Disimpan sebagai satu angka:
  **halaman tertinggi yang pernah dicapai** (high-water mark) per siswa per Materi.
  100% selesai begitu mark mencapai halaman terakhir.
- **Denominator**: **rekomendasi Materi terkini** (snapshot, bukan histori kumulatif).
  Progress boleh naik-turun seiring rekomendasi berubah — ini bukan bug, karena
  **penguasaan sebenarnya adalah tanggung jawab Peta Kompetensi/Status Pemetaan**
  (hanya "didapat" lewat uji ulang), bukan Progress Belajar. Progress Belajar murni
  sinyal keterlibatan belajar saat ini terhadap apa yang *sedang* direkomendasikan.
- **Granularitas laporan**: dipecah **per Subkompetensi** (paralel dengan struktur
  Peta Kompetensi) — bukan satu angka overall. Angka overall/per-Kompetensi bisa
  dihitung sebagai rata-rata dari breakdown ini saat dibutuhkan (mis. Dashboard Admin),
  tidak perlu tabel terpisah.
- **Kepemilikan katalog Materi**: layanan ini **tidak** menyimpan katalog Materi
  sendiri (judul, total halaman, tag Subkompetensi) — data tersebut dikirim oleh
  pemanggil (tim fullstack) di setiap event/permintaan. Lihat
  [ADR 0002](../../../docs/adr/0002-no-materi-catalog-ownership.md).

### Skema penyimpanan

**`progress_materi`** (satu baris per siswa per Materi — snapshot kumulatif akses;
metadata Materi didenormalisasi dari payload event terakhir, bukan di-join dari tabel
Materi milik tim fullstack — lihat ADR 0002)

| kolom | tipe | keterangan |
|---|---|---|
| id | PK | |
| siswa_id | FK (referensi eksternal) | |
| materi_id | FK (referensi eksternal, dikelola tim fullstack) | |
| subkompetensi_id | FK | dikirim tim fullstack di payload event (Materi wajib bertag Subkompetensi — ADR 0001) |
| tingkat_seleksi_id | FK | |
| total_halaman | int | snapshot dari payload event terakhir |
| halaman_tertinggi_dicapai | int | high-water mark |
| pertama_dibuka_pada | timestamp | |
| diperbarui_pada | timestamp | |

Unique: (siswa_id, materi_id). `persentase_selesai` dihitung saat baca
(`halaman_tertinggi_dicapai / total_halaman × 100`), tidak disimpan sebagai kolom
terpisah — menghindari nilai basi kalau `total_halaman` berubah di event berikutnya
(mis. admin menambah halaman ke Materi yang sudah ada).

Breakdown Progress Belajar per Subkompetensi dihitung saat baca: rata-rata
`persentase_selesai` dari baris `progress_materi` untuk Materi yang **saat ini** masuk
Rekomendasi Materi siswa tersebut pada Subkompetensi itu (Materi yang belum pernah
dibuka dianggap 0%). Ini butuh layanan ini menerima daftar Materi yang relevan
(id, subkompetensi_id) dari pemanggil saat menghitung, bukan dari katalog sendiri —
detail kontrak permintaan/tanggapannya akan dirancang konkret di tiket "Kontrak API:
Pemetaan Kompetensi & Rekomendasi Materi".

### Dependensi turunan

- Tiket "Kontrak API: Pemetaan Kompetensi & Rekomendasi Materi" perlu menyertakan
  bentuk payload event "halaman dibuka" (siswa_id, materi_id, subkompetensi_id,
  tingkat_seleksi_id, total_halaman, halaman_dicapai) dan cara pemanggil menyertakan
  daftar Materi relevan saat meminta breakdown Progress Belajar.
- Tiket "Metrik Dashboard Super Admin" dapat memakai `progress_materi` untuk agregasi
  keterlibatan belajar lintas siswa/sekolah.
