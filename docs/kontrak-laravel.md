# Kontrak Laravel untuk `/hitung/penilaian` dan `/hitung/pretest`

Dua endpoint ini ada **khusus untuk backend Osn-Readiness-Web**
(`PerhitunganClient`; sumber truth kontrak: `PerhitunganClientInterface` dan
`tests/Feature/Clients/PerhitunganClientTest.php` di repo Laravel).
`/hitung/simulasi` dan `/hitung/latihan` memakai skema internal lama dan saat
ini tidak dipanggil Laravel — jangan diubah tanpa koordinasi.

## Bentuk wire

### `POST /hitung/penilaian`

Request:

```json
{
  "soal": [
    {"soal_id": 1, "tipe_soal": "pilihan_ganda", "bobot": 1,
     "jawaban_user": "A", "kunci_jawaban": "B"},
    {"soal_id": 2, "tipe_soal": "isian", "bobot": 2,
     "jawaban_user": "4", "kunci_jawaban": "4"}
  ]
}
```

- `tipe_soal`: `pilihan_ganda` | `isian` (nilai enum Laravel; `isian`
  dipetakan ke `isian_singkat` lokal di `laravel.py`). Selain itu → 422.
- `bobot`: bobot eksplisit per soal (otoritatif — **bukan** diturunkan dari
  level; Laravel tidak mengirim level).
- `jawaban_user`: `null`/kosong dihitung salah.

Respons:

```json
{
  "nilai": 66.67,
  "jawaban": [
    {"soal_id": 1, "status_benar": false},
    {"soal_id": 2, "status_benar": true}
  ]
}
```

`nilai` = Σ bobot benar / Σ bobot × 100, dibulatkan 2 desimal
(`scoring.hitung_skor`). Urutan `jawaban` sama seperti permintaan; jumlahnya
harus sama persis (Laravel menolak bila beda → 502 di sisinya).

### `POST /hitung/pretest`

Request = bentuk penilaian per soal **ditambah** `materi_id` tiap soal, plus:

```json
{
  "materi": [{"materi_id": 10, "urutan": 1}],
  "jumlah_materi_wajib": 2
}
```

Respons = bentuk penilaian plus:

```json
{
  "pemetaan": [
    {"materi_id": 10, "jumlah_soal": 2, "jumlah_benar": 1,
     "poin_didapat": 1, "poin_maksimal": 3, "persentase": 33.33, "peringkat": 1}
  ],
  "materi_wajib": [{"materi_id": 10, "prioritas": 1}]
}
```

- Satu baris pemetaan untuk **setiap** materi yang dikirim, termasuk yang
  tanpa soal (`persentase` 0.0). `persentase` berbobot
  (`poin_didapat/poin_maksimal × 100`, aturan final v1).
- `materi_wajib` = `jumlah_materi_wajib` materi pertama sesuai urutan
  permintaan. Bila `jumlah_materi_wajib` melebihi jumlah materi → 422.

## Autentikasi

Semua `/hitung/*` mewajibkan header `X-Internal-Token` sama dengan
`INTERNAL_API_TOKEN` (`.env`). Salah/hilang → 403. Di sisi Laravel ini
dipetakan ke 502 + log kritis (dianggap salah konfigurasi, tidak di-retry).

## Kode terkait

- `src/data_analytics/schemas.py` — model `Laravel*` (kontrak wire).
- `src/data_analytics/laravel.py` — adapter komputasi (mapping tipe, agregasi).
- `src/data_analytics/api.py` — routing + penjagaan token.
- `tests/test_api_hitung.py` — test kontrak (wajib hijau sebelum merge
  perubahan apa pun di endpoint ini).

## Menjalankan lokal (untuk backend Laravel)

```bash
uv run uvicorn data_analytics.api:app --host 127.0.0.1 --port 8001
```

Jangan pakai `docker-compose.dev.yml` apa adanya untuk dev gabungan: ia
mengekspos analytics-api ke port host 8000 (tabrakan dengan
`php artisan serve`). Di `.env` Laravel: `PERHITUNGAN_URL=http://localhost:8001`
dan `PERHITUNGAN_TOKEN` = nilai `INTERNAL_API_TOKEN` yang sama.
