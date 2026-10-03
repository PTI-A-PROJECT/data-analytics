# Distribusi Bank Soal OSN

Kondisi per 30 September 2026: soal aktif di vector database (pgvector) hasil ingest folder `soal_osn/`.

## Ringkasan

| Jenjang | Soal aktif | Pilihan ganda | Isian singkat | Tahun soal |
|---|--:|--:|--:|---|
| Kabupaten | 929 | 764 (82,2%) | 165 (17,8%) | 2006–2026 |
| Provinsi | 790 | 254 (32,2%) | 536 (67,8%) | 2006–2026 |
| **Total** | **1.719** | **1.018** | **701** | |

Materi mengikuti kelompok materi osn.toki.id per jenjang. Level Soal: mudah, sedang, sulit.

## Kabupaten (929 soal)

| Materi | Mudah | Sedang | Sulit | Total | Porsi |
|---|--:|--:|--:|--:|--:|
| Aljabar Boolean & Teori Himpunan | 33 | 31 | 9 | **73** | 7,9% |
| Graf & Geometri | 23 | 56 | 12 | **91** | 9,8% |
| Kombinatorika, Model Matematis & Deret | 88 | 100 | 47 | **235** | 25,3% |
| Simulasi, Optimisasi, Logika & Berpikir Komputasional | 82 | 109 | 57 | **248** | 26,7% |
| Membaca Algoritma & Pemrograman | 100 | 108 | 74 | **282** | 30,4% |
| **Total** | **326** | **404** | **199** | **929** | 100% |
| Porsi per level | 35,1% | 43,5% | 21,4% | | |

## Provinsi (790 soal)

| Materi | Mudah | Sedang | Sulit | Total | Porsi |
|---|--:|--:|--:|--:|--:|
| Dasar-dasar Pemrograman | 78 | 24 | 14 | **116** | 14,7% |
| Operasi Logika dan Bitwise | 57 | 28 | 12 | **97** | 12,3% |
| Aritmetika | 74 | 45 | 7 | **126** | 15,9% |
| Aturan Berhitung | 28 | 46 | 10 | **84** | 10,6% |
| Rekursi | 39 | 33 | 16 | **88** | 11,1% |
| Pencarian dan Pengurutan | 11 | 18 | 6 | **35** | 4,4% |
| Strategi Pemecahan Masalah | 18 | 68 | 37 | **123** | 15,6% |
| Struktur Data | 10 | 24 | 5 | **39** | 4,9% |
| Graf dan Tree | 14 | 32 | 17 | **63** | 8,0% |
| Geometri Dasar | 4 | 13 | 2 | **19** | 2,4% |
| **Total** | **333** | **331** | **126** | **790** | 100% |
| Porsi per level | 42,2% | 41,9% | 15,9% | | |

## Sebaran per tahun

| Tahun | Kabupaten | Provinsi |
|---|--:|--:|
| 2006 | 60 | 50 |
| 2007 | 50 | 60 |
| 2008 | 44 | 60 |
| 2009 | 50 | 61 |
| 2010 | 50 | 38 |
| 2011 | 49 | 40 |
| 2012 | 50 | 47 |
| 2013 | 50 | 49 |
| 2014 | 50 | 47 |
| 2015 | 50 | 50 |
| 2016 | 50 | 42 |
| 2017 | 39 | 44 |
| 2018 | 36 | 43 |
| 2019 | 36 | 34 |
| 2020 | 40 | 28 |
| 2021 | 35 | –¹ |
| 2022 | 35 | 25 |
| 2023 | 35 | 19 |
| 2024 | 40 | 18 |
| 2025 | 40 | 18 |
| 2026 | 40 | 17 |
| **Total** | **929** | **790** |

¹ Soal Provinsi 2021 di sumber identik dengan 2020, jadi dihitung sekali di 2020.

## Catatan untuk penyusunan Paket Tes

- **Stok paling tipis:** Geometri Dasar sulit di Provinsi, 2 soal, tepat di batas stok minimum (2). Berikutnya Struktur Data sulit (5) dan Pencarian dan Pengurutan sulit (6). Untuk kombinasi ini mesin adaptif lebih cepat mengulang soal atau jatuh ke fallback level terdekat.
- **Komposisi berbeda antarjenjang:**
  - Kabupaten didominasi pilihan ganda (82,2%) dan level sedang (43,5%).
  - Provinsi didominasi isian singkat (67,8%), dengan porsi mudah dan sedang hampir seimbang.
- **Soal dengan gambar atau potongan kode** perlu dirender oleh frontend:
  - Kabupaten: 106 soal bergambar, 180 berkode.
  - Provinsi: 27 soal bergambar, 158 berkode.
- **Butuh verifikasi tim konten:** kunci dan pembahasan 85 soal yang diselesaikan manual, yaitu 44 soal Kabupaten 2008 dan 41 soal Provinsi yang ditulis ulang. Daftarnya ada di `soal_osn/kunci_tambahan.json`.
