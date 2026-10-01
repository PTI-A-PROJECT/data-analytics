# Map: Fase 2 — Bank Konten & Simulasi Adaptif OSN Informatika

## Destination

Layanan ini memiliki bank konten sendiri (Soal di PostgreSQL + pgvector, Materi di
tabel Postgres biasa) dan menyusun paket tes: pre-test bertingkat Kabupaten → Provinsi,
simulasi adaptif berbasis vector search yang menaikkan level soal per Materi sesuai
performa, dan remedial wajib atas Materi lemah sebelum simulasi berikutnya.

## Alur siswa

```
Pre-Test Kabupaten ─► Materi Wajib (lemah) ─► Simulasi adaptif ─► Materi Wajib ─► Simulasi ...
     │ skor ≥ 90                                   │ skor ≥ min & rata Level Soal Siswa ≥ Menengah
     └──────────────► Pre-Test Provinsi ◄──────────┘
                           └─► loop yang sama di Provinsi
```

## Keputusan lintas issue

- Hanya **Kabupaten** dan **Provinsi**; Nasional dihapus.
- **Materi = unit evaluasi** (menggantikan Subkompetensi). Materi baku, tanpa
  kesulitan; hanya Soal yang punya level (Mudah/Menengah/Sulit).
- Level Soal **berasal dari data sumber** (soal sudah dikelompokkan per Materi & tingkat
  kesulitan) — rencana awal pelabelan LLM (Ollama) dibatalkan; **tanpa** kalibrasi
  ulang dari data jawaban.
- Embedding **lokal** (`paraphrase-multilingual-MiniLM-L12-v2` int8 via ONNX Runtime,
  384 dim, tanpa PyTorch, ~555 MB RAM hanya saat ingest), dihitung offline;
  runtime API tidak memuat model.
- Vector search dipakai untuk: memilih soal mirip dengan yang dijawab salah (inti loop
  adaptif) dan mencocokkan soal ↔ Materi saat ingest.
- Adaptif = tangga level berbasis aturan; level **tidak pernah turun** — kelemahan
  ditangani dengan porsi soal proporsional, kuota minimum menjamin semua Materi
  tercakup.
- Test pindah ke PostgreSQL + pgvector sungguhan.

## Issues

1. [Bank Konten: Skema & Ingest Soal (pgvector) dan Materi](issues/01-bank-konten-soal-materi.md)
2. [Gerbang Pre-Test: Kabupaten → Provinsi](issues/02-gerbang-pretest-kabupaten-provinsi.md)
3. [Mesin Pemilihan Soal Adaptif untuk Simulasi](issues/03-mesin-soal-adaptif-simulasi.md)
4. [Remedial: Wajib Belajar Materi Lemah sebelum Simulasi](issues/04-remedial-gerbang-simulasi.md)

Urutan implementasi: 01 → 02 → 03 → 04 (masing-masing bergantung pada sebelumnya).
