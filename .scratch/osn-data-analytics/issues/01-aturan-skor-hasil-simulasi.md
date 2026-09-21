# Aturan Skor & Hasil Simulasi

Type: grilling
Status: resolved
Blocked by: none

## Question

Bagaimana persisnya Skor/Hasil Simulasi (FR-12) dihitung dari jawaban pilihan ganda
siswa? Apakah sekadar persentase benar (jumlah benar / total soal), atau ada bobot per
soal (mis. berdasar kesulitan/Tingkat)? Apakah ada konsep "pencapaian" (achievement)
terpisah dari nilai mentah — misalnya predikat/level tertentu berdasarkan nilai? Apakah
Aturan-nya dikonfigurasi Super Admin (mirip Aturan Pemetaan) atau tetap (fixed logic)?
Resolusi tiket ini juga harus mencakup rancangan skema penyimpanan (tabel) untuk hasil
skor per siswa per simulasi.

## Resolution

Aturan penilaian yang sama berlaku untuk Pre-Test (FR-06) dan Simulasi (FR-12) — tidak
ada mekanisme terpisah per jenis tes.

- **Formula skor**: persentase sederhana, `jumlah_benar / total_soal × 100`. Semua soal
  berbobot sama — tidak ada bobot per kesulitan/Tingkat, karena brief tidak punya field
  kesulitan pada Soal (FR-20 hanya menghubungkan Soal dengan Tingkat Seleksi dan
  Kompetensi) dan menambahkannya akan jadi deviasi dari brief tanpa kebutuhan yang jelas.
- **Soal tidak dijawab**: dihitung sebagai "salah". Tidak ada kategori terpisah
  "tidak dijawab" — brief FR-12 hanya menyebut output biner benar/salah.
- **Pencapaian**: predikat tunggal berbasis rentang nilai, ditampilkan berdampingan
  dengan skor mentah. Terpisah dari Status Pemetaan (Cukup/Belum Cukup/Belum Teruji) —
  predikat murni soal performa nilai, bukan duplikasi Peta Kompetensi.
- **Konfigurasi**: aturan predikat dikonfigurasi Super Admin, **per Tingkat Seleksi**
  (Kabupaten/Provinsi/Nasional dapat punya ambang batas berbeda), mengikuti pola yang
  sama dengan Aturan Pemetaan (FR-23).
- **Default bawaan** (di-seed otomatis untuk setiap Tingkat Seleksi baru, dipakai sampai
  Super Admin mengubahnya — mencegah proses penilaian gagal/terblokir karena config
  belum diisi):
  - Sangat Baik: ≥ 90
  - Baik: 80–89
  - Cukup: 70–79
  - Perlu Latihan: < 70
- **Histori**: predikat dibekukan (snapshot) pada hasil tes saat dihitung. Perubahan
  ambang batas oleh Super Admin di kemudian hari tidak mengubah predikat pada hasil tes
  yang sudah tersimpan — Riwayat Hasil (FR-14) harus mencerminkan apa yang dilihat siswa
  saat itu, dan data untuk evaluasi Kenaikan Tingkat (tiket 03) perlu stabil/auditable.

### Skema penyimpanan

**`aturan_predikat`** (config Super Admin, per Tingkat Seleksi)

| kolom | tipe | keterangan |
|---|---|---|
| id | PK | |
| tingkat_seleksi_id | FK | |
| label | varchar | "Sangat Baik", "Baik", dst |
| batas_bawah | numeric | ambang skor minimum (inklusif), 0–100 |
| created_at / updated_at | timestamp | |

Unique: (tingkat_seleksi_id, label). Di-seed otomatis dengan 4 default di atas saat
Tingkat Seleksi baru dibuat.

**`hasil_tes`** (satu baris per attempt — Pre-Test atau Simulasi)

| kolom | tipe | keterangan |
|---|---|---|
| id | PK | |
| siswa_id | FK (referensi eksternal) | |
| tingkat_seleksi_id | FK | |
| jenis_tes | enum('pre_test','simulasi') | |
| simulasi_id | FK nullable | diisi hanya jika jenis_tes='simulasi' |
| total_soal | int | |
| jumlah_benar | int | |
| jumlah_salah | int | = total_soal − jumlah_benar |
| skor | numeric | persentase, 0–100 |
| predikat_label | varchar | snapshot label dari aturan_predikat saat itu |
| diselesaikan_pada | timestamp | |
| dibuat_pada | timestamp | default now |

**`hasil_tes_subkompetensi`** (breakdown per Subkompetensi dalam satu attempt — input
untuk Peta Kompetensi; tidak menyimpan identitas soal atau isi jawaban)

| kolom | tipe | keterangan |
|---|---|---|
| id | PK | |
| hasil_tes_id | FK → hasil_tes, cascade delete | |
| subkompetensi_id | FK | |
| jumlah_soal | int | jumlah soal dari subkompetensi ini di attempt tsb |
| jumlah_benar | int | |

Unique: (hasil_tes_id, subkompetensi_id).

### Dependensi turunan

- Tiket 03 (Aturan Kenaikan Tingkat) dapat memakai `hasil_tes.skor` /
  `hasil_tes.predikat_label` sebagai salah satu kandidat syarat kenaikan tingkat.
- Tiket 04 (Metrik Dashboard Super Admin) dapat memakai `hasil_tes` dan
  `hasil_tes_subkompetensi` untuk agregasi lintas siswa/sekolah.
