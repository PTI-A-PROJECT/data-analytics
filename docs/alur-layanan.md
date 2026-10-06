> **Catatan (6 Oktober 2026).** Dokumen ini menjelaskan desain lengkap
> repo ini, termasuk jalur `/api/v1/*` dengan bank soal sendiri. Dalam
> aplikasi yang berjalan, **Laravel tidak memanggil jalur itu**. Yang hidup
> hanya dua endpoint `/hitung/*` — `/hitung/penilaian` dan `/hitung/pretest` —
> yang dipakai Laravel lewat `PerhitunganClient` dan
> `PerhitunganClientInterface`. Kontrak yang benar-benar dipegang kedua sisi
> ada di [`kontrak-laravel.md`](kontrak-laravel.md), bukan di bagian 2
> dokumen ini. Bagian 8 sudah menandai kode mati; catatan ini mencakup
> pemanggilnya.

# Alur Layanan Data & Analytics

Dokumen ini menjelaskan cara kerja `data-analytics` dari request masuk sampai angka
keluar, disusun dari pembacaan kode pada commit `58b5212`. Karena ada beberapa
bagian yang **tertulis di kode tapi tidak dipanggil** dan beberapa tempat
kode bertentangan dengan docstring-nya, dokumen ini menandai hal itu secara
eksplisit di bagian [8. Yang kodanya mati](#8-kode-yang-mati--bertentangan-dengan-docstring).

Istilah domain (Materi, Level Soal Siswa, Materi Wajib, Gerbang Simulasi, dll.)
mengikuti `CONTEXT.md` — dokumen ini tidak mengulang definisinya.

---

## 1. Gambaran Besar

```
                    OFFLINE (tidak ada di jalur request)
  soal_osn/*.json ─┐
  label_materi_   │
  level.json      ├─► baca_bank_soal ─► ingest_bank_konten ─► EmbedderMiniLM
  materi.json     │   (sumber_osn)     (ingest.py)             (ONNX, 384-d)
  Materi/*.docx ──┘                            │
                                              ▼
                                    PostgreSQL 16 + pgvector
                                    materi / halaman_materi / soal
                                    (embedding vector(384))

                    ONLINE — semua lewat FastAPI, semua butuh X-Internal-Token
  backend aplikasi utama ─► /api/v1/... ─► repository.py ─► DB
                            ▲                    │
                            │                    ├─► modul fungsi murni:
                            │                    │     pemetaan · adaptif
                            │                    │     scoring · kenaikan
                            │                    │     materi_wajib · progress
                            │                    │     paket · leaderboard
                            └────────────────────┘
```

Dua jalur yang tidak boleh dicampur:

- **Offline** — ingest bank konten. Jalankan manual lewat CLI. Butuh
  `uv sync --group ingest` karena memuat model ML.
- **Online** — API FastAPI. **Tidak pernah** memuat model ML; vector search
  memakai embedding yang sudah tersimpan di DB.

---

## 2. Ingest Bank Konten (offline)

CLI: `uv run python -m data_analytics.scripts.ingest`

### 2.1 Membaca sumber

`sumber_osn.baca_bank_soal(folder_soal, folder_materi)` membaca `soal_osn/`:

| Sumber | Isi | Peran |
|---|---|---|
| `soal_<tingkat>_pembahasan/soal_<kab\|prov>_<tahun>.json` | soal, pilihan, kunci, pembahasan, gambar | daftar soal |
| `materi.json` | daftar Materi per tingkat (silabus osn.toki.id) | **sumber kebenaran** Materi |
| `label_materi_level.json` | Materi + Level per soal, dan `dikecualikan` | **sumber kebenaran** Level |
| `gambar_<tingkat>/` | file gambar | disajikan via endpoint konten |
| `Materi/<Tingkat>/Topik N_*.docx` | dokumen materi | sumber halaman Materi |

Penting: data sumber **tidak membawa** penugasan Materi maupun Level soal.
Keduanya datang dari `label_materi_level.json` yang dilabeli manual. Ingest tidak
menebaknya; `Level Soal` berasal dari data sumber, tidak dikalibrasi ulang.

Id soal = `<kab|prov>-<tahun>-<urutan>`, stabil selama urutan file sumber tidak
berubah. Nomor topik di nama file `.docx` dicocokkan ke field `topik` di
`materi.json`; tiap judul bagian tebal membuka satu halaman Materi.

### 2.2 Menghitung embedding

`embedding.EmbedderMiniLM` — `paraphrase-multilingual-MiniLM-L12-v2`, varian
int8 lewat ONNX Runtime. Tanpa PyTorch.

- Teks yang di-embed untuk soal: `deskripsi + "\n\n" + pertanyaan` saja.
  Pilihan jawaban **sengaja tidak** ikut — isinya angka/opsi pendek menambah
  noise ke makna. Konsekuensinya (dipakai untuk efisiensi): perubahan
  level/pilihan/kunci **tidak** memicu embedding ulang.
- Teks model dilatih ≤128 token dan **tidak dipotong**. Teks panjang dipecah jadi
  jendela 128 token tumpang-tindih 32 token, tiap jendela di-embed, lalu
  dirata-rata berbobot jumlah token.
- Mean pooling di atas token non-padding, lalu normalisasi L2 — jadi cosine
  = dot product.
- Dimensi 384, harus cocok dengan `DIMENSI_EMBEDDING`; embedder memverifikasi
  dan melempar error kalau tidak cocok.

### 2.3 Upsert idempoten

`ingest.ingest_bank_konten` bertransaksi per Tingkat Seleksi:

1. Tolak id Materi/Soal kembar.
2. Upsert Materi + Halaman Materi. Embedding hanya dihitung untuk entri baru
   atau yang `sha256` teks ter-embed-nya berubah. Pergantian tingkat tidak
   mengubah hash, jadi diterapkan terpisah dari hitung ulang embedding.
3. Upsert Soal dengan logika sama.
4. Soal yang tag Materi-nya kosong/tidak dikenal **tidak disimpan** — hanya
   masuk `LaporanIngest.soal_tanpa_materi`, dan untuk proposes Materi terdekat
   lewat vector search (`_materi_terdekat`) supaya bisa ditinjau manual.
   Versi lama soal yang sudah tersimpan tetap utuh.
5. Soal tingkat ini yang **tidak ada lagi** di masukan → `aktif = False`, bukan
   dihapus, karena Paket Tes lama mungkin masih mereferensikannya.
6. Hitung laporan stok per `(Materi, Level)`; yang di bawah `stok_minimum`
   (default 2) ditandai `stok_tipis` — ini yang akan memaksa mesin adaptif
   jatuh ke fallback.

Ringkasan dicetak ke stdout. `--recompute` memaksa hitung ulang semua embedding.

---

## 3. Kontrak Akses

Semua endpoint `/api/v1/*` dilindungi `Depends(verify_internal_token)`:

- Header `X-Internal-Token` wajib ada → FastAPI membalas **422** kalau tidak.
- Nilainya harus cocok dengan `INTERNAL_API_TOKEN` → **403** kalau salah.

Tidak ada autentikasi siswa per individu. Layanan ini tidak mengekspos user
end-user secara langsung — backend aplikasi utama yang menerjemahkan
sesi siswa menjadi `siswa_id`, lalu memanggil layanan ini di network Docker
privat. Konsekuensinya: `siswa_id` di tabel ini **dipercaya dari pemanggil**,
bukan diverifikasi.

`GET /health` = liveness (tanpa sentuh DB). `GET /api/v1/health` = readiness
(`SELECT 1`).

---

## 4. Siklus Belajar Siswa

### 4.1 Inisialisasi akses

`inisialisasi_akses_siswa` dipanggil hampir di setiap endpoint siswa. Siswa baru
otomatis dapat satu baris akses per Tingkat Seleksi: Kabupaten
`pretest_terbuka`, tingkat di atasnya `terkunci`.

### 4.2 Pre-Test

```
POST /api/v1/pretest/paket
  └─ susun_paket_pretest (repository.py)
       ├─ cek Tingkat ada                      → 404 TingkatTidakDitemukan
       ├─ paket lama yang sudah disubmit?
       │    ├─ gagal simulasi < 3x             → 409 KonflikPaket
       │    └─ sudah ≥ 3x → HAPUS paket lama, buat baru (reset kuota)
       ├─ akses == pretest_terbuka?            → 403 AksesDitolak
       ├─ paket belum disubmit                 → kembalikan yang sama (idempoten)
       ├─ total = aturan.jumlah_soal_pretest (default 30)
       ├─ bagi 50% Mudah / 30% Menengah / 20% Sulit   (DISTRIBUSI_PRETEST)
       ├─ tiap level: stok per Materi → bagi_kuota_rata → pilih acak (ORDER BY random)
       └─ acak urutan → simpan PaketTes + PaketTesSoal (alasan = ACAK)
```

Sisip soal: `with session.begin_nested()` di sekitar `session.add(paket)`.
Kalau dua request bersamaan untuk siswa+tingkat yang sama, yang kalah menabrak
partial unique index, menangkap `IntegrityError`, lalu memakai paket pemenang
(idempoten) — bukan 500.

Submit:

```
POST /api/v1/paket/{paket_id}/submit
  └─ submit_paket
       ├─ SELECT ... FOR UPDATE pada baris paket → submitravat bergiliran,
       │    yang kedua melihat disubmit_pada terisi → 409, bukan 500
       ├─ cocokkan jawaban per soal (scoring.cocokkan_jawaban)
       │    soal tidak dijawab = salah
       ├─ hitung (jumlah_soal, jumlah_benar) per Materi
       │    → SEMUA Materi tingkat itu ikut, yang 0 soal = Belum Teruji
       ├─ Peta Kompetensi: pemetaan.petakan_per_materi(ambang_lemah)
       ├─ skor = Σbobot·benar / Σbobot × 100   (scoring.hitung_skor)
       ├─ predikat = tentukan_predikat (batas bawah tertinggi ≤ skor)
       ├─ simpan HasilTes + HasilTesMateri (breakdown per Materi)
       ├─ _catat_materi_wajib  ← selalu, untuk pre-test maupun simulasi
       └─ _setelah_pretest:
            ├─ buat LevelSoalSiswa = Mudah untuk semua Materi
            ├─ isi akurasi_terakhir & flag lemah dari peta
            └─ buka akses tingkat ini jadi TERBUKA
```

`_setelah_pretest` **tidak** mengevaluasi jalur cepat ke notwithstanding
`kenaikan.evaluasi_jalur_cepat` ada di kode — lihat [bagian 8](#8-kode-yang-mati--bertentangan-dengan-docstring).

### 4.3 Materi Wajib & Gerbang Simulasi

Setiap submit — pre-test maupun simulasi — memanggil `_catat_materi_wajib`.
Materi Wajib = setiap Materi berstatus **Belum Cukup**, diurutkan akurasi
terendah dulu. Baris dibuat dengan `selesai_pada` langsung terisi kalau Materi
itu **0 halaman** (tidak ada yang bisa dibaca, jadi dianggap selesai).

Siswa dibaca lewat:

```
GET /api/v1/siswa/{siswa_id}/remedial
  └─ status_gerbang_simulasi
       ├─ akses == TERBUKA?
       ├─ attempt TERAKHIR saja (Materi Wajib attempt lama tidak lagi menahan)
       ├─ hitung halaman unik dibuka per Materi Wajib
       └─ boleh_simulasi = terbuka AND semua materi selesai AND
                            semua materi punya >= 1 latihan lulus (nilai >= 50)
```

Dua syarat "selesai", keduanya harus terpenuhi:

1. **Semua halaman** Materi itu sudah dibuka minimal sekali **sejak diwajibkan**
   (`materi_wajib.selesai_dipelajari` — himpunan nomor halaman katalog ⊆ himpunan
   yang dibuka; navigasi bebas, urutan & duplikat tidak berpengaruh,
   melompat ke halaman terakhir saja tidak cukup).
2. **Latihan lulus** — ada ≥ 1 `Latihan` dengan `nilai >= 50` untuk Materi itu
   di tingkat tersebut. Syarat ini tidak ada di `CONTEXT.md` (lihat bagian 8).

Progres dibaca *saat request*, tidak disimpan: `jumlah_selesai / len(materi_wajib)`.

Pencatatan halaman:

```
POST /api/v1/analytics/events/materi-progress
  └─ catat_baca_halaman
       ├─ upsert RiwayatBacaHalaman (ON CONFLICT → update terakhir_dibuka_pada)
       ├─ untuk tiap Materi Wajib AKTIF (belum selesai) siswa+Materi ini:
       │    ├─ insert MateriWajibHalaman (ON CONFLICT DO NOTHING → idempoten per halaman)
       │    └─ kalau semua halaman sudah tercatat → selesai_pada = waktu server
       │         (bukan timestamp klien, jadi tidak pernah mendahului dibuat_pada)
       └─ kembalikan jumlah halaman unik ever-opened / total_halaman
```

`RiwayatBacaHalaman` (permanen, semua Materi) dipisahkan dari
`MateriWajibHalaman` (per Relevan Materi Wajib aktif) — sengaja, karena
"Materi ini belum pernah dibuka" ≠ "belum dibuka sejak diwajibkan".

Baris `MateriWajib` yang belum selesai dikunci `WITH FOR UPDATE`, jadi event
bersamaan untuk halaman berbeda dari Materi yang sama diproses bergiliran dan
pengecekan selesai selalu melihat semua halaman yang sudah tercatat.

### 4.4 Simulasi

```
POST /api/v1/simulasi/paket
  └─ susun_paket_simulasi
       ├─ akses == TERBUKA                          → 403 AksesDitolak
       ├─ sudah submit ≥ 3x                          → 409 KonflikPaket (kuota habis)
       ├─ ada paket simulasi belum disubmit?          → kembalikan yang sama
       ├─ status_gerbang_simulasi.boleh_simulasi?
       │    tidak → 409 dengan body GerbangSimulasiResponse
       └─ STATIS v1: 30% Mudah / 40% Menengah / 30% Sulit, bagi rata per Materi,
          soal acak (seed tersimpan di PaketTes.seed)
```

Submit simulasi = `submit_paket` yang sama, PLUS:

```
  ├─ _perbarui_level_soal_siswa
  │    └─ adaptif.perbarui_level per Materi:
  │         jumlah_soal < kuota_min  → TIDAK diubah (data terlalu sedikit)
  │         akurasi >= ambang_naik   → naik 1 level (mentok Sulit), tidak lemah
  │         akurasi <  ambang_lemah  → tetap, TIDAK PERNAH turun, flag lemah
  │         selain itu               → tetap, tidak lemah
  └─ _evaluasi_jalur_simulasi_dan_catat
       ├─ tidak ada AturanKenaikanTingkat aktif → None
       ├─ lulus = (skor >= passing grade tingkat) AND
       │           (semua materi inti akurasi >= 50%)
       └─ lulus → buka akses tingkat tujuan jadi PRETEST_TERBUKA
```

Catat: level siswa **naik atau tetap, tidak pernah turun** — ini koreksi level,
bukan downgrade saat siswa gagal.

---

## 5. Modul Fungsi Murni

Pola yang konsisten di codebase: logika bisnis berada di modul kecil tanpa
database, diuji terpisah; `repository.py` hanyaquery, Orkestrasi, dan penyimpanan.

| Modul | Tanggung jawab |
|---|---|
| `scoring.py` | skor berbobot (Mudah=1/Menengah=2/Sulit=3), predikat, pencocokan jawaban |
| `pemetaan.py` | Status Pemetaan per Materi (Cukup/Belum Cukup/Belum Teruji) |
| `adaptif.py` | perubahan Level Soal Siswa, alokasi kuota, urutan level fallback |
| `kenaikan.py` | evaluasi syarat kenaikan tingkat |
| `materi_wajib.py` | kriteria "sudah dipelajari" |
| `progress.py` | persentase halaman terbaca |
| `paket.py` | pembagian kuota rata, terbatas stok |
| `leaderboard.py` | peringkat gabungan skor + kecepatan |

Detail menarik:

- **`scoring.cocokkan_jawaban`** — pilihan ganda: huruf, abaikan kapital. Isian
  singkat: normalisasi spasi/koma, `casefold`; kalau keduanya bilangan
  (`Fraction`, koma desimal diterima) dibandingkan **nilainya** (1260 = 1260.0).
  Tidak dijawab/kosong selalu salah.
- **`scoring.tentukan_predikat`** — wajib ada predikat berambang `batas_bawah=0`
  supaya setiap skor 0–100 pasti tertampung.
- **`adaptif.bagi_proporsional`** — *largest remainder* dengan `Fraction`
  (bukan float) supaya total selalu tepat dan sisa pembulatan tidak ambigu.
- **`adaptif.urutan_level_fallback`** — target dulu, lalu yang terdekat; jarak
  sama → **lebih mudah dulu**.

---

## 6. Endpoint Lain

### Latihan (formatif)

```
POST /api/v1/latihan/paket     — 10–15 soal acak satu Materi + pembahasan
POST /api/v1/latihan/submit    — skor berbobot, lulus >= 50%, pengulangan unlimited
```

Latihan sengaja **tidak** memakai `PaketTes`: formatif, bukan bagian dari
riwayat attempt, dan tidak memengaruhi paket maupun kuotanya. Pembahasan
disertakan langsung di respons karena latihan formatif — berbeda dari simulasi.

### Leaderboard

`GET /api/v1/siswa/{siswa_id}/leaderboard` — 5 teratas di jenjang yang diikuti
siswa (Tingkat tertinggi yang sudah `TERBUKA`), dari skor gabungan 50% skor +
50% kecepatan. Dihitung saat dibaca dari seluruh attempt simulasi yang punya
waktu pengerjaan — jadi selalu mengikuti submit terbaru. Nama & sekolah =
snapshot terbaru yang tidak terisi.

### Dashboard Admin

`GET /api/v1/admin/dashboard` — metrik agregat Super Admin, opsional
`sekolah_id` & `rentang_waktu`. Data agregat tetap utuh setelah anonimisasi.

### Anonimisasi UU PDP

`POST /api/v1/admin/anonymize-expired` — cron bulanan, meng-`NULL`-kan `siswa_id`
pada `HasilTes` yang lewat `DATA_RETENTION_MONTHS` (default 24). Skor, predikat,
dan breakdown tetap utuh untuk Dashboard. `?dry_run=true` mengecek dulu tanpa
mengubah. `make anonymize-dry-run`.

### Katalog Materi

```
GET /api/v1/materi                          — daftar, urut tingkat & nomor topik
GET /api/v1/materi/{id}?siswa_id=           — + daftar isi (sudah_dibaca)
GET /api/v1/materi/{id}/halaman/{nomor}     — konten + prev/next (READ-ONLY)
```

Endpoint halaman **tidak** mencatat progres — itu harus dilakukan eksplisit
lewat `POST /api/v1/analytics/events/materi-progress`. Konten disimpan sebagai
Markdown dengan rumus LaTeX (`$...$`, `$$...$$`) dan blok kode; render di
frontend dengan Markdown + KaTeX.

`GET /api/v1/konten/gambar/{tingkat}/{file}` menyajikan gambar soal. Path
divalidasi: `tingkat` harus `kabupaten|provinsi`, dan file harus langsung di
folder itu — `path.parent != folder` → 404, jadi tidak ada path traversal.

---

## 7. Database

PostgreSQL 16 + pgvector 0.8.6. **SQLite tidak didukung** sejak fase 2.

Tabel inti:

| Tabel | Isi |
|---|---|
| `tingkat_seleksi` | Kabupaten (urutan 1), Provinsi (urutan 2) — diisi migrasi 0005 |
| `materi`, `halaman_materi` | Katalog + isi dokumen `.docx` |
| `soal` | Bank soal, satu `materi_id`, satu `level`, `embedding vector(384)` |
| `paket_tes`, `paket_tes_soal` | Paket yang disusun, disimpan untuk diaudit |
| `hasil_tes`, `hasil_tes_materi` | Skor, predikat, breakdown per Materi |
| `level_soal_siswa` | Level Soal Siswa per (siswa, Materi) |
| `materi_wajib`, `materi_wajib_halaman` | Syarat Gerbang Simulasi |
| `riwayat_baca_halaman` | Riwayat baca unik permanen |
| `latihan`, `latihan_jawaban` | Latihan formatif |
| `aturan_adaptif`, `aturan_predikat`, `aturan_kenaikan_tingkat` | Parameter, di-Super-Admin-kan |
| `akses_tingkat_siswa`, `riwayat_evaluasi_kenaikan` | Status akses + jejak evaluasi |

Semua aturan default dibuat **otomatis** saat pertama dibutuhkan
(`get_or_create_*`), lalu di-commit oleh endpoint yang memanggilnya — supaya
konfigurasi selalu ada tanpa langkah migrasi manual.

### Kenapa tidak ada index HNSW

Migrasi `0007_pencarian_eksak_tanpa_hnsw.py` secara eksplisit menghapus index
HNSW yang dibuat migrasi 0005. Alasan (dari docstring `Soal`): HNSW bersifat
*approximate* dan menyaring **setelah** mengambil kandidat global, sehingga soal
paling mirip bisa terlewat — padahal Paket Tes harus deterministik supaya bisa
diaudit. Pada ~1.800 soal planner sudah memilih B-tree; menghapus HNSW
menjamin itu tetap begitu.

Konsekuensi: pencarian "soal mirip" = filter B-tree di `(tingkat, materi, level)`
lalu jarak cosine **eksak** ke kandidat yang tersisa (puluhan soal, ~2 ms).
Ini aman untuk ribuan soal, tapi akan melambat kalau bank soal tumbuh ke ratusan
ribu. Keputusan yang perlu ditinjau ulang nanti — bukan masalah sekarang.

---

## 8. Kode yang Mati & Bertentangan dengan Docstring

Bagian ini hasil verifikasi kode, bukan asumsi. Empat temuan; semuanya pada
commit `58b5212` dengan working tree bersih.

### 8.1 Mesin soal adaptif tidak pernah dipanggil — simulasi benar-benar statis

Docstring `susun_paket_simulasi` sendiri jujur: *"Paket simulasi STATIS v1:
30% Mudah, 40% Menengah, 30% Sulit. Distribusi dibagi rata per Materi.
Adaptive di-hold untuk fase 2."*

Tapi migrate `0008_mesin_soal_adaptif_simulasi.py` dan docstring `adaptif.py`
("*Langkah 3 (pilih soal via vector search) ada di
repository.susun_paket_simulasi*") menyatakan sebaliknya. Yang benar: **yang
live adalah yang statis.** Terverifikasi:

- `_PemilihSoal` didefinisikan di `repository.py:841` dan **tidak pernah
  diinstansiasi** di mana pun.
- `alokasi_kuota` di-`import` (`repository.py:23`) tapi **tidak pernah dipanggil**.
- `_level_soal_siswa_per_materi`, `_riwayat_muncul`, `_soal_acuan` — ketiganya
  hanya dipakai oleh `_PemilihSoal`, jadi mati bersama.
- Satu-satunya `cosine_distance` di jalur penyusunan paket ada di
  `_PemilihSoal._tetangga_bergiliran` (line 924) — mati. Yang hidup cuma
  `_materi_terdekat` di `ingest.py:304`, untuk proposes, bukan pemilihan soal.

Dampaknya: `level_soal_siswa` **disimpan dan diperbarui** tapi tidak pernah
mempengaruhi soal mana yang disajikan. `ambang_naik`, `ambang_lemah`,
`bobot_lemah`, `kuota_min` tidak berpengaruh pada komposisi paket. Yang
membedakan hanya `ambang_lemah` lewat pemetaan & Gerbang Simulasi, dan
`ambang_naik`/`bobot_lemah`/`kuota_min` praktis tak terpakai.

Yang **tidak** terpengaruh: penulisan `level_soal_siswa`, `materi_lemah`,
`Materi Wajib`, Gerbang Simulasi, dan kenaikan tingkat tetap berjalan.

Perbaikan adalah menyambungkan `alokasi_kuota` + `_PemilihSoal` di
`susun_paket_simulasi` — kodenya sudah lengkap dan teruji (`tests/test_adaptif.py`,
`test_simulasi_adaptif.py`), hanya tidak tersambung.

### 8.2 Docstring pre-test tidak cocok dengan kodenya

Docstring `susun_paket_pretest`: *"semua soal Mudah"*. Kodenya: 50% Mudah,
30% Menengah, 20% Sulit (`DISTRIBUSI_PRETEST`, lines 534–537). Docstring yang
benar ada di `api.py:405`. Test yang ada (`test_api_pretest.py`) menguji kode,
jadi docstringnya yang usang.

### 8.3 `evaluasi_jalur_simulasi` di `kenaikan.py` tidak dipakai

`_evaluasi_jalur_simulasi_dan_catat` (`repository.py:1276`) **tidak** memanggil
`kenaikan.evaluasi_jalur_simulasi`; ia menghitung sendiri dengan semantik
berbeda: passing grade + akurasi materi inti ≥ 50%, dan mengabaikan syarat
level sama sekali.

 manifested sebagai dua error mypy di `repository.py`:

- `1295`: `tingkat.urutan` — `tingkat` bisa `None` (`session.get` tanpa cek).
- `1320`: `rata_level_aktual=None` dikirim ke `HasilEvaluasiJalurSimulasi`
  yang deklarasinya `float`.

`RiwayatEvaluasiKenaikan` juga menyimpan `rata_level_aktual=None` dan
`rata_level_target=None` — dua kolom jadi tidak pernah terisi. `tingkat_seleksi_id`
di `HasilTes` masih `str` ("fase 1") sementara tabel lain `int`, dengan
konversi di `repository.py:1065`.

### 8.4 Syarat "latihan lulus" di Gerbang Simulasi tidak ada di dokumentasi

`status_gerbang_simulasi` (lines 1492–1508) menambahkan syarat kedua:
setiap Materi Wajib harus punya minimal satu `Latihan` dengan `nilai >= 50`.

`CONTEXT.md` mendefinisikan Gerbang Simulasi sebagai *"semua Materi Wajib dari
attempt terakhir sudah selesai dipelajari"* — tidak menyebut latihan. Keduanya
saling diperiksa dengan `and`, jadi syarat ini **mengunci** gerbang.

Ini kemungkinan besar penyebab 31 dari 37 test gagal: fixture test tidak
pernah membuat `Latihan`, jadi `boleh_simulasi` selalu `False` dan
`GerbangSimulasiTertutup` terpicu. Test yang gagal tidak pernah menguji
perilaku adaptif yang sedang di-hold — semuanya gagal **sebelum** ke sana.

### 8.5 Status test suite saat ini

```
37 failed, 192 passed
```

- **6 gagal** `tests/test_scoring.py` — memanggil `hitung_skor(jumlah_benar=,
  total_soal=)`, tapi signature sekarang `hitung_skor(*, bobot_benar: float,
  bobot_total: float)`. Test tidak diupdate saat skor jadi berbobot.
- **31 gagal** `test_simulasi_adaptif.py` + `test_api_simulasi.py` — semua
  `GerbangSimulasiTertutup` — penyebabnya lihat 8.4.

Pola yang sama: **test tidak mengikuti rewrite fase 1 → fase 2**. Plus 14 error
mypy (12 di test, 2 di `repository.py`).

---

## 9. Menjalankan

```bash
uv sync --group ingest                          # sekali
cp .env.example .env

make test-db-up        # pgvector/pgvector:pg16 di port 5433, untuk pytest
uv run pytest
uv run mypy src tests

make dev-up            # stack dev: API :8000, DB :5432
make migrate           # atau: uv run alembic upgrade head

uv run python -m data_analytics.scripts.ingest           # ingest bank konten
uv run python -m data_analytics.scripts.ingest --recompute
```

Dua DB berbeda, jangan tertukar:

| | Test | Dev |
|---|---|---|
| Container | `analytics-test-db` | `analytics-db` |
| Port host | 5433 | 5432 |
| DB | `analytics_test` | `analytics` |
| Dipakai oleh | `pytest` (`TEST_DATABASE_URL`) | API, alembic, ingest |

Di produksi (`docker-compose.yml` tanpa override) port **tidak** di-bind ke
host — hanya `expose:`, supaya tidak bisa diakses publik; hanya lewat network
Docker privat `app-network`.

---

## 10. Ringkasan Alur End-to-End

```
1. OFFLINE  ingest: JSON + DOCX + label → embedding MiniLM 384-d → PostgreSQL
             (idempoten, soal hilang di-nonaktifkan bukan dihapus)

2. SISWA    GET  /siswa/{id}/akses
            → akses diinisialisasi otomatis (Kabupaten terbuka, atasnya terkunci)

3. PRE-TEST POST /pretest/paket → paket statis 50/30/20, kuotanya rata per Materi
            POST /paket/{id}/submit
                 → skor berbobot + predikat + Peta Kompetensi per Materi
                 → Level Soal Siswa = Mudah untuk semua Materi
                 → akses tingkat ini jadi TERBUKA
                 → Materi Wajib = Materi Belum Cukup

4. BELAJAR  GET  /materi, /materi/{id}, /materi/{id}/halaman/{n}   (READ-ONLY)
            POST /analytics/events/materi-progress                  (catat)
            POST /latihan/paket + /latihan/submit                   (formatif, >= 50%)

5. GERBANG  GET /siswa/{id}/remedial → boleh_simulasi?
                 perlu: akses TERBUKA
                      DAN semua halaman tiap Materi Wajib dibuka sejak diwajibkan
                      DAN tiap Materi Wajib punya >= 1 latihan lulus  ← tak terdokumentasi

6. SIMULASI POST /simulasi/paket → 409 (GerbangSimulasiResponse) kalau gerbang tertutup
                                  → paket statis 30/40/30, kuotanya rata per Materi
            POST /paket/{id}/submit
                 → skor + peta + predikat
                 → Level Soal Siswa: naik atau tetap, tidak pernah turun
                 → evaluasi kenaikan: skor >= passing AND materi inti >= 50%
                 → lulus → buka pre-test tingkat berikutnya

7. KONSUMEN Dashboard Admin · Leaderboard · Anonimisasi UU PDP (cron bulanan)
```

Semua langkah online berada di belakang `X-Internal-Token`; tidak ada satu pun
endpoint yang menyentuh model ML.