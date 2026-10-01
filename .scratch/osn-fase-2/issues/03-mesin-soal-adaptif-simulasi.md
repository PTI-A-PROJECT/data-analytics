# Mesin Pemilihan Soal Adaptif untuk Simulasi

Type: design
Status: implemented (409 Gerbang Simulasi menyusul di issue 04)
Blocked by: 01 (bank konten + embedding), 02 (paket_tes, endpoint submit bersama)

## Question

Kemunculan soal simulasi harus dinamis, bergantung pada kemampuan dan riwayat siswa:
simulasi pertama semua soal Mudah; soal dari materi yang lemah muncul lebih banyak;
materi yang sudah dikuasai disajikan dengan soal yang lebih sulit pada simulasi
berikutnya; semakin bagus performa, semakin tinggi tingkat kesulitan soal. Bagaimana
algoritmanya — dengan vector search sebagai inti pemilihan soal?

## Resolution

### Istilah

- **Materi** baku dan sama untuk semua siswa — **tidak punya tingkat kesulitan**.
- **Level Soal** (`mudah`/`menengah`/`sulit`) hanya melekat pada Soal (issue 01).
- **Level Soal Siswa**: level soal yang *disajikan kepada siswa ini untuk Materi ini*
  pada simulasi berikutnya. Disimpan di `level_soal_siswa` (`siswa_id`, `materi_id`,
  `level`, `akurasi_terakhir`, `lemah` bool, `diperbarui_pada`); unik
  (`siswa_id`, `materi_id`). Diinisialisasi Mudah untuk semua Materi saat pre-test
  tingkat itu disubmit (issue 02).

### Algoritma loop adaptif

Setiap simulasi menjalankan siklus: **submit → perbarui Level Soal Siswa → alokasi
kuota → pilih soal via vector search → paket berikutnya.** Langkah 1 & 2 fungsi murni
(`adaptif.py`), langkah 3 query Postgres/pgvector (`repository.py`).

**Langkah 1 — Perbarui Level Soal Siswa** (saat simulasi disubmit, per Materi yang
diuji):

| Akurasi siswa di Materi itu | Efek |
|---|---|
| ≥ `ambang_naik` (default 80%) | level naik satu (Mudah→Menengah→Sulit, mentok Sulit); `lemah = false` |
| `ambang_lemah` ≤ akurasi < `ambang_naik` | level tetap; `lemah = false` |
| < `ambang_lemah` (default 50%) | **level tetap (tidak pernah turun)**; `lemah = true` |

- Materi yang tampil < `kuota_min` soal di attempt itu tidak diubah (data terlalu
  sedikit).
- Pre-test tidak menaikkan level; hanya mengisi `akurasi_terakhir` & `lemah`.
- **Satu definisi "lemah"**: Status Pemetaan per Materi di Peta Kompetensi memakai
  ambang yang sama — Belum Cukup ≡ `lemah` ≡ akurasi < `ambang_lemah`; Belum Teruji =
  Materi tanpa soal di attempt itu (tidak lemah, tidak wajib). `aturan_pemetaan`
  (`ambang_cukup_persen`/`ambang_representasi_persen`) dipensiunkan.

**Langkah 2 — Alokasi kuota per Materi** (total `jumlah_soal_simulasi` = N):

1. Setiap Materi di tingkat itu mendapat `kuota_min` (default 2) → **semua Materi
   selalu tercakup**.
2. Sisa `N − kuota_min × jumlah_materi` dibagi **proporsional terhadap bobot**:
   Materi `lemah` berbobot `bobot_lemah` (default 3), lainnya 1. Pembulatan metode
   *largest remainder* → total selalu tepat N.
3. Materi lemah di level Menengah/Sulit tetap di level itu — perbaikannya lewat porsi
   yang lebih besar, bukan penurunan level.

**Langkah 3 — Pilih soal per Materi via vector search**, pada level = Level Soal Siswa
untuk Materi itu, selalu mengecualikan soal yang pernah muncul di paket siswa itu pada
tingkat itu:

- **Materi lemah** — kumpulan *soal acuan* = soal Materi itu yang dijawab salah pada
  attempt terakhir. Untuk tiap soal acuan secara bergiliran (round-robin), ambil
  tetangga terdekat yang belum dipakai:
  ```sql
  SELECT id FROM soal
  WHERE materi_id = :m AND level = :lvl AND id <> ALL(:sudah_muncul)
  ORDER BY embedding <=> :embedding_soal_acuan
  LIMIT :k
  ```
  → siswa berlatih pada konsep yang *mirip secara makna* dengan yang ia salahkan,
  naik ke level yang sedang disajikan. Sisa kuota (kalau acuan habis) diisi acak.
- **Materi tidak lemah** — acak dari soal yang belum pernah muncul.
- **Fallback stok habis** (distribusi soal tidak merata), berurutan:
  1. belum pernah muncul, level terdekat — lebih mudah dulu, lalu lebih sulit;
     untuk Materi lemah tetap diurutkan dengan vector search terhadap soal acuan;
  2. pernah muncul, yang paling lama tidak muncul;
  3. sisa kuota dialihkan ke Materi lain sesuai bobot.
  Setiap soal di `paket_tes_soal` menyimpan `level_target`, `level_aktual`, dan
  `alasan` (`vektor_mirip` / `acak` / `fallback_level` / `fallback_ulang`) — auditable
  & bahan test.
- Urutan soal dalam paket diacak; acak memakai seed yang disimpan di `paket_tes`
  (reproducible untuk test/debug).

### Konfigurasi

`aturan_adaptif` (satu baris per tingkat): `jumlah_soal_pretest`,
`jumlah_soal_simulasi`, `kuota_min`, `bobot_lemah`, `ambang_naik`, `ambang_lemah`.
Validasi: `kuota_min × jumlah_materi ≤ jumlah_soal_simulasi`,
`0 ≤ ambang_lemah < ambang_naik ≤ 100`, `bobot_lemah ≥ 1`. Di-seed default.

### Endpoint

- `POST /api/v1/simulasi/paket` `{siswa_id, tingkat_seleksi_id}` → paket soal (tanpa
  kunci/pembahasan). 403 kalau akses tingkat belum `terbuka`; **409** kalau Gerbang
  Simulasi (issue 04) belum terpenuhi, dengan daftar Materi yang wajib dipelajari.
  Paket belum disubmit → dikembalikan ulang (idempoten).
- Submit memakai `POST /api/v1/paket/{paket_id}/submit` (issue 02); untuk simulasi,
  response ditambah perubahan Level Soal Siswa per Materi dan hasil evaluasi jalur
  simulasi → pre-test Provinsi.
- Endpoint fase 1 `POST /api/v1/analytics/assessment/submit` (soal disusun fullstack)
  dipensiunkan — semua submit lewat `paket_tes`.

### Test

- Unit `perbarui_level`: batas tepat 80/50, mentok Sulit, tidak pernah turun, materi
  di bawah `kuota_min` tidak berubah.
- Unit `alokasi_kuota`: total selalu N, setiap Materi ≥ `kuota_min`, rasio lemah:biasa
  mengikuti bobot, kasus sisa nol.
- Integrasi (Postgres + pgvector, embedding sintetis berdimensi kecil yang dikontrol):
  soal lemah memilih tetangga terdekat yang benar; soal yang sudah muncul tidak
  terulang; tiap tahap fallback; simulasi pertama setelah pre-test semuanya Mudah;
  performa bagus berulang menaikkan level hingga Sulit.

## Implementation

- Migrasi `0008_mesin_soal_adaptif_simulasi`: `aturan_adaptif` + `jumlah_soal_simulasi`
  (30), `kuota_min` (2), `bobot_lemah` (3), `ambang_naik` (80) dengan check
  `kuota_min ≥ 1`, `bobot_lemah ≥ 1`, `ambang_lemah < ambang_naik ≤ 100`
  (`kuota_min × jumlah_materi ≤ jumlah_soal_simulasi` dicek saat paket disusun —
  `alokasi_kuota` → ValueError). `paket_tes.seed` (bigint) + partial unique index satu
  simulasi belum-disubmit per (siswa, tingkat). `paket_tes_soal.level` →
  `level_aktual`, + `level_target` & `alasan` (baris pre-test lama: `mudah`/`acak`).
- Fungsi murni `adaptif.py`: `perbarui_level`, `alokasi_kuota` (+ `bagi_proporsional`
  largest remainder, eksak dengan `Fraction`), `urutan_level_fallback`,
  `gabung_bergiliran` (round-robin soal acuan).
- `repository.susun_paket_simulasi` + `_PemilihSoal` (langkah 3 & fallback);
  `submit_paket` untuk simulasi memperbarui `level_soal_siswa` (baris dikunci
  `FOR UPDATE`) lalu mengevaluasi & mencatat jalur simulasi
  (`riwayat_evaluasi_kenaikan.jalur = jalur_simulasi`). Response submit ditambah
  `perubahan_level` & `evaluasi_jalur_simulasi`.
- `POST /api/v1/simulasi/paket` (404/403, idempoten). `POST /api/v1/analytics/assessment/
  submit` dihapus beserta `catat_submission_tes`/`JawabanInput`; `catat_hasil_tes` &
  tabel `aturan_pemetaan`/`jawaban_siswa` tetap untuk data fase 1.
- Keputusan detail:
  - "Attempt terakhir" (soal acuan) = paket terakhir yang sudah disubmit siswa di
    tingkat itu (pre-test atau simulasi).
  - "Paling lama tidak muncul" diurutkan menurut id paket terakhir tempat soal muncul
    (monoton; `dibuat_pada` bisa seri dalam satu transaksi), seri → level terdekat.
  - Acak memakai `random.Random(seed)` atas kandidat terurut id (bukan
    `ORDER BY random()`), jadi paket reproducible dari seed + isi bank.
  - Materi tanpa baris `level_soal_siswa` (Materi baru / akses dibuka admin) → Mudah,
    tidak lemah; barisnya dibuat saat simulasi disubmit.
  - `PaketPretestRequest` → `PaketRequest` (dipakai kedua endpoint).
- Belum: 409 Gerbang Simulasi (issue 04).
- Catatan code review — diselesaikan (commit lanjutan):
  - Konfigurasi divalidasi di depan: `GET /api/v1/analytics/aturan-adaptif` &
    `PUT /api/v1/analytics/aturan-adaptif/{tingkat_seleksi_id}` (422 kalau
    `kuota_min × jumlah_materi > jumlah_soal_simulasi`, `ambang_lemah ≥ ambang_naik`,
    dst. — `adaptif.validasi_aturan_adaptif`). Kalau Materi bertambah setelah
    divalidasi, paket diperbesar ke `kuota_min × jumlah_materi` (tidak pernah 500);
    `jumlah_soal_diminta` mencatat ukuran efektif.
  - `aturan_pemetaan` dihapus (migrasi `0009`) beserta `catat_hasil_tes`,
    `tentukan_status_pemetaan`, `tentukan_butuh_optimasi`. Tabel riwayat fase 1
    `hasil_tes_subkompetensi` & `jawaban_siswa` tetap.
  - Soal acuan per Materi diambil dari attempt terakhir yang memuat jawaban salah di
    Materi itu — Materi yang tetap `lemah` karena tampil < `kuota_min` soal tetap
    mendapat soal lewat vector search.
