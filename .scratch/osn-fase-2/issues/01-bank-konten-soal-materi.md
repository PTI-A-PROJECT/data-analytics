# Bank Konten: Skema & Ingest Soal (pgvector) dan Materi, plus Tingkat Kesulitan

Type: design
Status: implemented (data soal_osn di-ingest 2026-09-30)
Blocked by: —

## Question

Di fase 2, soal (~900 per tingkat, Kabupaten & Provinsi, JSON, distribusi per materi
tidak merata) dan materi disiapkan sendiri — bukan lagi dari Super Admin/tim fullstack.
Bagaimana layanan ini menyimpan bank konten tersebut sehingga (a) soal bisa diambil per
materi dan tingkat kesulitan, (b) soal yang mirip secara makna dengan soal yang dijawab
salah bisa dicari, dan (c) soal bisa dicocokkan ke materi yang paling relevan — padahal
soal belum punya label tingkat kesulitan?

## Resolution

### Perubahan peran layanan

Fase 1: layanan ini hanya *menilai* tes yang disusun pihak lain (ADR 0002/0003 —
"computation engine over caller-supplied facts"). Fase 2: layanan ini **memiliki bank
konten** (Materi, Halaman Materi, Soal) dan **menyusun paket soal** (pre-test per
tingkat, simulasi adaptif per siswa — lihat issue 02 & 03). Fullstack meminta paket,
menyajikannya ke siswa, lalu mengirim jawaban kembali.

- ADR baru `docs/adr/0004-layanan-memiliki-bank-konten.md` menggantikan ADR 0002 dan
  memperluas ADR 0003 (katalog lokal bukan lagi sekadar seed dev/test, tapi sumber
  kebenaran produksi).
- **Materi menjadi unit evaluasi** (menggantikan Subkompetensi): soal di-tag ke tepat
  satu Materi; Peta Kompetensi dan Level Soal dihitung per Materi.
- Materi **tidak** punya tingkat kesulitan. Hanya Soal yang punya `level`.
- Istilah baru di `CONTEXT.md`: **Level Soal**, **Level Soal Siswa** (issue 03),
  **Paket Tes**, **Materi Wajib** & **Gerbang Simulasi** (issue 04).

### Hutang tipe id dilunasi untuk entitas konten

Karena katalog kini milik layanan ini, tabel baru memakai FK sungguhan ke
`tingkat_seleksi`/`materi`/`soal` lokal. Id Materi & Soal diambil dari JSON sumber
(string, stabil antar-ingest). `siswa_id`/`sekolah_id` tetap string caller-supplied
tanpa FK (identitas siswa tetap milik fullstack).

### Skema

| Tabel | Kolom utama |
|---|---|
| `materi` | `id` str PK (dari JSON), `tingkat_seleksi_id` FK, `judul`, `total_halaman`, `embedding vector(384)` |
| `halaman_materi` | `materi_id` FK, `nomor`, `konten`; unik (`materi_id`, `nomor`) |
| `soal` (diganti total) | `id` str PK (dari JSON), `materi_id` FK, `tingkat_seleksi_id` FK, `pertanyaan`, `pilihan_jawaban` JSONB, `kunci_jawaban`, `pembahasan`, `level` enum (`mudah`/`menengah`/`sulit`), `embedding vector(384)` |

- Index: B-tree (`tingkat_seleksi_id`, `materi_id`, `level`). ~~HNSW~~ dihapus di
  migrasi `0007` — lihat "Revisi 2026-09-29".
- `level` berasal dari data sumber (lihat revisi) dan **tidak dikalibrasi ulang** dari data
  jawaban (keputusan eksplisit: job kalibrasi p-value dibuang dari scope).
- Tabel lama yang disesuaikan: `jawaban_siswa.soal_id` jadi FK ke `soal`;
  `progress_materi.materi_id` jadi FK str ke `materi` (sekaligus melunasi utang UUID
  dari tiket 11/14); `hasil_tes_subkompetensi` digantikan `hasil_tes_materi` (breakdown
  per Materi). Tabel `kompetensi`/`subkompetensi` lama dipensiunkan kalau data JSON
  tidak membawa hierarki itu — diputuskan setelah struktur JSON terlihat.

### Pemakaian vector search

Embedding soal dan materi berada di ruang vektor yang sama (model yang sama):

- **(A) Soal mirip dengan yang dijawab salah** — dipakai mesin adaptif (issue 03):
  `ORDER BY embedding <=> :embedding_soal_salah` dalam filter materi+level, tidak
  termasuk soal yang sudah pernah dikerjakan siswa. Hanya memakai embedding yang sudah
  tersimpan — **tidak ada inferensi model saat runtime**.
- **(C) Soal ↔ Materi** — saat ingest, soal tanpa tag materi (atau dengan tag yang
  diragukan) dicocokkan ke Materi terdekat di tingkat yang sama; hasilnya dicatat di
  laporan ingest untuk ditinjau manual, bukan diterapkan diam-diam.

### Ingest offline

`python -m data_analytics.scripts.ingest --tingkat kabupaten data/soal/kabupaten.json ...`

1. Baca & validasi JSON (Pydantic) dari folder data di repo.
2. Hitung embedding dengan `intfloat/multilingual-e5-small` (384 dim, lokal,
   prefix `passage: `).
3. Labeli `level` via LLM lokal (Ollama) dengan prompt berisi rubrik Mudah/Menengah/Sulit
   OSN; output divalidasi ke enum, gagal-parse → retry lalu default `menengah` +
   dicatat di laporan.
4. Upsert idempoten per `id`; label & embedding yang sudah ada tidak dihitung ulang
   kecuali `--recompute` atau teks soal berubah (hash konten).
5. Tulis laporan ringkas: jumlah soal per (materi, level), soal yang gagal label,
   usulan pencocokan materi (C), dan **peringatan stok tipis** (materi+level dengan
   soal < kuota minimum simulasi — relevan karena distribusi tidak merata).

Model embedding & klien Ollama dipasang sebagai optional dependency group `ingest` —
image Docker API tidak membawanya.

### Infrastruktur & test

- Image DB diganti `postgres:16-alpine` → `pgvector/pgvector:pg16`; migrasi Alembic
  `0005` menjalankan `CREATE EXTENSION IF NOT EXISTS vector`.
- Test suite pindah dari SQLite in-memory ke **PostgreSQL + pgvector sungguhan**
  (container Docker, database test per sesi, rollback per test). Logika murni
  (alokasi porsi, tangga level) tetap dites tanpa database.

### Belum diputuskan (menunggu data)

- Struktur JSON final soal & materi (field, apakah ada hierarki Kompetensi, format
  konten halaman materi) — skema Pydantic ingest dikunci setelah file masuk repo.

## Implementation (bagian yang tidak menunggu data)

Selesai:

- Migrasi `0005_bank_konten_pgvector`: extension `vector`, tabel `materi`,
  `halaman_materi`, `soal` baru (+ index B-tree & HNSW), baris `tingkat_seleksi`
  Kabupaten & Provinsi (dulu diisi seed). Tabel `kompetensi`/`subkompetensi`/`soal`
  fase 1 dihapus; `scripts/seed.py` dihapus (arahan: bagian fase 1 yang tidak relevan
  dihapus). Kalau JSON ternyata membawa hierarki Kompetensi, tabelnya ditambahkan lagi.
- Model `Materi`/`HalamanMateri`/`Soal`/`LevelSoal` di `models.py`. **Deviasi**:
  `total_halaman` adalah property (jumlah `halaman_materi`), bukan kolom tersimpan —
  tidak ada sumber kebenaran ganda. Kolom `hash_konten` ditambahkan di `materi` & `soal`
  (dibutuhkan langkah 4 ingest).
- `ingest.ingest_bank_konten` — upsert idempoten via `hash_konten`, `recompute`,
  label gagal → `menengah` + `soal_gagal_label`, soal tanpa/dengan tag Materi asing
  tidak disimpan + usulan Materi terdekat (pgvector), tag diragukan dilaporkan, stok
  per (materi, level) + `stok_tipis`. Soal/Materi yang hilang dari masukan **tidak**
  dihapus.
- `pelabel.PelabelLevelOllama` (rubrik, retry, default `menengah`; error HTTP
  menghentikan ingest). `embedding.EmbedderE5` (belum pernah dijalankan dengan model
  sungguhan — tidak dites, butuh group `ingest`).
- Image DB `pgvector/pgvector:pg16`; test suite pindah ke Postgres (`make test-db-up`,
  port 5433). Sekalian ditemukan & diperbaiki: migrasi `0003`/`0004` fase 1 tidak
  pernah bisa jalan di Postgres (ALTER TYPE sebelum DROP FK; default boolean `'0'`/`'1'`).
- ADR 0004 (menggantikan 0002, memperluas 0003), istilah baru di `CONTEXT.md`.

Perbaikan dari code review: Materi yang pindah tingkat tanpa perubahan teks ikut
dipindah; soal tersimpan yang tag-nya menjadi tidak valid tidak diubah dan dicatat di
`soal_tidak_diperbarui`; id kembar dalam satu masukan -> `ValueError`.

Ditunda:

- Parser JSON (Pydantic) + CLI `python -m data_analytics.scripts.ingest` — menunggu
  struktur file data.
- `jawaban_siswa.soal_id` FK, `progress_materi.materi_id` FK, `hasil_tes_materi` —
  dikerjakan bersama penulisan ulang endpoint pemakainya di issue 02–04 supaya endpoint
  fase 1 tidak rusak sebelum penggantinya ada.
- Menulis `LaporanIngest` ke file/terminal (langkah 5) — bagian CLI.

Catatan terbuka (diputuskan setelah data asli terlihat):

- "Tag diragukan" = Materi terdekat != tag, tanpa ambang jarak — dengan ~900 soal bisa
  ramai. Kalau terlalu banyak, tambah ambang selisih jarak (tag vs terdekat).
- Embedding Materi = judul + semua halaman; e5-small memotong di 512 token, jadi materi
  panjang praktis diwakili judul + halaman awal. Alternatif: rata-rata embedding per
  halaman.

## Revisi 2026-09-29 — tanpa LLM, embedding ringan, pencarian eksak

Pemicu: VPS target 4–8 GB RAM dibagi dengan aplikasi lain (hindari model AI berat), dan
**soal sudah dilabeli per Materi dan per tingkat kesulitan di data sumber**.

- **Pelabelan level via LLM (Ollama) dibatalkan**: `level` diambil dari data
  (`SoalMasukan.level`). `pelabel.py`, `test_pelabel.py`, dan `httpx` di group `ingest`
  dihapus; `LaporanIngest.soal_gagal_label` ikut hilang.
- **Embedder**: `embedding.EmbedderMiniLM` — `paraphrase-multilingual-MiniLM-L12-v2`
  int8 lewat ONNX Runtime (tanpa PyTorch/sentence-transformers). Dipilih dengan
  `scripts/benchmark_embedding.py` pada 12 triplet soal OSN (positif = makna sama kata
  beda; jebakan = kata mirip makna beda), recall@1 / MRR: MiniLM 0.38 / 0.53,
  e5-small 0.25 / 0.43, e5-base 0.25 / 0.48, mpnet 0.38 / 0.56 (2x RAM, 3x lebih
  lambat), TF-IDF 0.04 / 0.24. int8 ≈ fp32. Sumber daya: ~555 MB RAM puncak, ~35 detik /
  1.800 soal (2 thread), hanya saat ingest.
- **Soal panjang**: model dilatih ≤128 token; teks lebih panjang dipecah jendela 128
  token tumpang-tindih 32 lalu dirata-rata (`potong_jendela`). Pada soal berpembuka
  cerita ~150 token: dipotong recall@1 0.08 → sliding window 0.25.
- **Yang di-embed hanya pertanyaan** (bukan pilihan jawaban): pilihan = noise makna;
  perubahan level/pilihan/kunci tidak memicu embedding ulang.
- **Laporan "tag diragukan" dihapus**: Materi sudah pasti dari data, dan akurasi model
  ringan (~38% peringkat #1) membuat laporan itu penuh alarm palsu. Pengaman soal dengan
  tag Materi kosong/asing (+ usulan Materi terdekat) tetap ada.
- **Pencarian eksak** (migrasi `0007`, hapus index HNSW): kueri soal mirip selalu
  difilter (tingkat, materi, level) → puluhan kandidat → jarak eksak lewat B-tree
  (~2 ms, diukur pada 1.800 soal). Pada ukuran ini planner sudah memilih B-tree walau
  HNSW ada (hasil identik); penghapusan menjamin perilaku eksak tetap saat data/statistik
  berubah.
- **Makna Materi & tingkat kesulitan dipakai sebagai filter keras**, bukan dicampur ke
  vektor: menambahkan judul Materi ke teks soal hanya menambah komponen yang sama ke
  semua kandidat dalam satu Materi, sehingga mengurangi daya beda antar-soal.
- Batasan: tidak ada model ringan yang sempurna pada jebakan bertopik & berkata sama
  (terbaik 3/12); di dalam satu materi+level hasilnya "lebih baik dari acak", bukan
  jaminan. Ulangi benchmark dengan soal asli setelah data masuk.

## Implementation — data soal_osn (2026-09-30)

- Data masuk lewat PR #9: `soal_osn/soal_{kabupaten,provinsi}_pembahasan/soal_<kab|prov>_<tahun>.json`
  (2.014 entri, 2006–2026) + `gambar_*`. **Tidak membawa Materi, Level, maupun id**
  (asumsi awal issue ini keliru), ~50% isian singkat, sebagian entri hanya konteks.
- Materi: `soal_osn/materi.json` — Kabupaten 5 kelompok (silabus OSN-K osn.toki.id),
  Provinsi 10 kelompok (silabus OSN). Tanpa halaman (konten bacaan belum ada) →
  Materi Wajib langsung selesai.
- Label: `soal_osn/label_materi_level.json` — dilabeli manual per soal (Materi +
  Level), 90 dikecualikan (soal pemrograman, jawaban kode/rumus/daftar, prov-2021 =
  duplikat prov-2020). Kalibrasi: label menengah tahun ≤ 2012 → mudah (stok Mudah per
  Materi harus cukup untuk pre-test/simulasi pertama).
- `sumber_osn.baca_bank_soal`: id `<kab|prov>-<tahun>-<nomor>`, konteks "Deskripsi Untuk
  Soal Nomor A dan B" dipasang ke B-A+1 soal berikutnya, pilihan & kunci dinormalisasi
  huruf kapital, gambar lokal → `<tingkat>/<file>` (fallback URL sumber).
- Skema (migrasi `0012`): `soal.tipe` (pilihan_ganda/isian_singkat), `deskripsi`, `kode`,
  `gambar`, `tahun`. Embedding = deskripsi + pertanyaan. Isian dinilai
  `scoring.cocokkan_jawaban` (spasi/kapital diabaikan, bilangan dibandingkan nilainya).
- CLI `python -m data_analytics.scripts.ingest`; hasil ingest pertama: 885 soal
  Kabupaten + 737 Provinsi (1.622), 208 entri dilewati.
- `PaketResponse.soal[]` ditambah `tipe`, `deskripsi`, `kode`, `gambar`;
  `GET /api/v1/konten/gambar/{tingkat}/{file}`.

