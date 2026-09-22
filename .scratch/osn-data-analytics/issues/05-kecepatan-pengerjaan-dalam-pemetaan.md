# Peran Kecepatan Pengerjaan dalam Peta Kompetensi & Rekomendasi Materi

Type: grilling
Status: resolved
Blocked by: none

## Question

Sudah dipastikan (sesi charting) bahwa Kecepatan Pengerjaan (timestamp per soal) wajib
dilacak. Tapi bagaimana persisnya dipakai? Apakah: (a) murni ditampilkan sebagai metrik
terpisah di samping Status Pemetaan (tidak memengaruhi Cukup/Belum Cukup), (b) ikut
memengaruhi Aturan Pemetaan — mis. jawaban benar tapi sangat lambat tetap dianggap
"kurang cukup" karena indikasi pemahaman belum solid, atau (c) hanya dipakai di
Rekomendasi Materi untuk memprioritaskan Subkompetensi yang benar tapi lambat? Perlu
juga ditentukan threshold "lambat" itu relatif terhadap apa (rata-rata waktu soal
sejenis, alokasi waktu per soal, dll).

## Resolution

Keputusan yang diambil adalah pendekatan **ramah motivasi berbasis flag `butuh_optimasi`** dengan integrasi langsung ke mesin rekomendasi materi dan latihan soal.

- **Pengaruh pada Peta Kompetensi (Ramah Motivasi)**:
  - Jawaban yang benar tetapi melebihi alokasi waktu (lambat) **tidak menggagalkan** status kompetensi. Jika syarat ambang ketercapaian benar sudah terpenuhi, status siswa tetap berhak naik menjadi **"Cukup"**.
  - Namun, sistem menyematkan status sekunder berupa flag **`butuh_optimasi`** pada subkompetensi terkait jika rasio jawaban benar-tetapi-lambat melebihi batas toleransi ($> 50\%$).
- **Pengaruh pada Rekomendasi Materi**:
  - Subkompetensi dengan flag `butuh_optimasi` **diprioritaskan untuk latihan penajaman/drilling kecepatan**.
  - Alur rekomendasi: Siswa akan diberikan latihan berbatas waktu (speed drill) untuk subkompetensi yang sudah "Cukup tetapi lambat" sebelum melangkah ke materi pengayaan tingkat lanjut.
- **Definisi Threshold "Lambat"**:
  - Menggunakan **alokasi batas waktu statis per soal (`batas_waktu_detik`)** yang ditetapkan pada master soal (default 60–90 detik jika tidak diisi secara spesifik).
  - Menghindari perbandingan waktu rata-rata dinamis lintas siswa karena kalkulasi tersebut membebani kueri analitik dan rentan bias akibat sampel kecil.

### Skema Penyimpanan

1. **`soal`** (Penambahan atribut durasi pada tabel master soal)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `batas_waktu_detik` | int | Ambang waktu ideal pengerjaan butir soal (default: 60) |

2. **`jawaban_siswa`** (Tabel log jawaban butir soal per attempt)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | PK | |
| `hasil_tes_id` | FK | Referensi ke attempt di tabel `hasil_tes` |
| `soal_id` | FK | Referensi ke master `soal` |
| `jawaban_dipilih` | varchar | Opsi pilihan jawaban yang dipilih siswa |
| `is_benar` | boolean | `true` jika jawaban siswa benar |
| `durasi_detik` | int | Durasi riil siswa mengerjakan butir soal (selisih waktu mulai & kirim) |
| `is_lambat` | boolean | `true` jika `durasi_detik > soal.batas_waktu_detik` |
| `dibuat_pada` | timestamp | default now() |

3. **`peta_kompetensi_siswa`** (Penambahan flag indikator optimasi)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `butuh_optimasi` | boolean | `true` jika subkompetensi berstatus 'Cukup' tetapi $\ge 50\%$ jawaban benarnya berstatus `is_lambat = true` |

### Dependensi Turunan

- Mesin Rekomendasi Materi & Latihan membaca flag `butuh_optimasi` untuk menyusun rekomendasi latihan berfokus pada efisiensi waktu.
- Data `jawaban_siswa.durasi_detik` dapat digunakan pada dashboard analitik sebagai indikator kelancaran kognitif siswa.
