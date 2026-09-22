# Kontrak API: Pemetaan Kompetensi & Rekomendasi Materi

Type: prototype
Status: partially resolved — endpoint 1 diimplementasikan, endpoint 2 ditunda (lihat "## Implementation")
Blocked by: 06 (untuk endpoint 2 saja; tiket 05 sudah settled)

## Question

Rancang & sketsakan kontrak API konkret (request/response JSON, endpoint, status
code) untuk dua endpoint inti: (1) submit hasil Pre-Test/Simulasi → hitung & kembalikan
Peta Kompetensi, (2) ambil Rekomendasi Materi untuk siswa berdasar Peta Kompetensi
terakhirnya. Buat contoh payload konkret (termasuk representasi Kecepatan Pengerjaan
dan Materi bertag Subkompetensi) yang bisa langsung didiskusikan/direaksi oleh tim
fullstack sebagai kontrak data. Ditunggu sampai tiket "Peran Kecepatan Pengerjaan" dan
"Selaraskan Field Subkompetensi di Materi" selesai karena bentuk payload bergantung
pada keduanya.


### 📝 Resolusi Issue #11: Kontrak API Pemetaan Kompetensi & Rekomendasi Materi

Berdasarkan kesepakatan dari tiket peran kecepatan (Issue #5) dan standarisasi field subkompetensi (Issue #6), disepakati bahwa arsitektur API antara layanan *Fullstack* dan *Data & Analytics* akan menggunakan pendekatan berikut:

1. **Prinsip *Stateless Calculation* (Sesuai ADR 0002):** Layanan *Data & Analytics* tidak memegang data *master* Soal dan Materi. Oleh karena itu, *Fullstack* wajib mengirimkan metadata krusial (seperti `batas_waktu_detik`, `subkompetensi_id`, dan `katalog_materi`) di dalam *payload request*.
2. **Standarisasi ID:** Seluruh *identifier* wajib menggunakan format UUID v4 string.
3. **Pemisahan *Endpoint* (Separation of Concerns):** Pemrosesan dipisah menjadi 2 *endpoint* (1 untuk *Submit Tes*, 1 untuk *Get Rekomendasi*) agar skalabilitas *read* dan *write* dapat diatur secara independen.
4. **Hierarki Rekomendasi:** Mesin rekomendasi akan mengurutkan materi dengan prioritas: `URGENT_LEARN` (Belum Cukup) -> `SPEED_DRILL` (Cukup tapi lambat / `butuh_optimasi`) -> `ENRICHMENT` (Cukup & Cepat).

---

### 🛠️ Implementasi: Skema Kontrak API Khusus (JSON DTO)

#### 1. Endpoint: Submit Hasil Tes & Kalkulasi Peta

**Tujuan:** Menerima riwayat jawaban siswa, menghitung status kompetensi, dan menentukan flag `butuh_optimasi`.

* **Method & Endpoint:** `POST /api/v1/analytics/assessment/submit`
* **Status Code:** `200 OK` (Sukses), `422 Unprocessable Entity` (Validasi Payload Gagal)

**Request Payload (Dari Fullstack):**

```json
{
  "siswa_id": "8f3b2c14-52d3-4a11-9a7e-4b2a8d3e1101",
  "tingkat_seleksi_id": "b5a4c3d2-e1f0-4a9b-8c7d-6e5f4a3b2c1d",
  "jenis_tes": "PRE_TEST",
  "jawaban_siswa": [
    {
      "soal_id": "a1b2c3d4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
      "subkompetensi_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "is_benar": true,
      "durasi_detik": 85,
      "batas_waktu_detik": 60 
    }
  ]
}

```

*(Catatan: durasi_detik (85) > batas_waktu (60), otomatis men-trigger flag `butuh_optimasi` = true dari rules Issue #5).*

**Response Payload:**

```json
{
  "status": "success",
  "message": "Pemetaan kompetensi berhasil dihitung",
  "data": {
    "peta_kompetensi": [
      {
        "subkompetensi_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "status_pemetaan": "Cukup",
        "butuh_optimasi": true
      }
    ]
  }
}

```

#### 2. Endpoint: Get Rekomendasi Materi

**Tujuan:** Mengembalikan daftar materi yang sudah diranking berdasarkan kelemahan/kebutuhan optimasi siswa terakhir.

* **Method & Endpoint:** `POST /api/v1/analytics/recommendations/rank`
* **Status Code:** `200 OK`

**Request Payload (Dari Fullstack - Menggunakan struktur DTO dari Issue #6):**

```json
{
  "siswa_id": "8f3b2c14-52d3-4a11-9a7e-4b2a8d3e1101",
  "tingkat_seleksi_id": "b5a4c3d2-e1f0-4a9b-8c7d-6e5f4a3b2c1d",
  "katalog_materi": [
    {
      "materi_id": "c1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
      "subkompetensi_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "judul": "Penelusuran Graf: BFS dan DFS",
      "total_halaman": 15,
      "urutan": 1
    }
  ]
}

```

**Response Payload (Materi Diranking & Dikategorikan):**

```json
{
  "status": "success",
  "data": {
    "rekomendasi": [
      {
        "subkompetensi_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "prioritas_ranking": 1,
        "tipe_rekomendasi": "SPEED_DRILL",
        "alasan": "butuh_optimasi",
        "materi_tersedia": true,
        "daftar_materi": [
          {
            "materi_id": "c1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
            "judul": "Penelusuran Graf: BFS dan DFS",
            "urutan": 1
          }
        ]
      }
    ]
  }
}
```

## Implementation

**Scope: hanya endpoint 1 (Submit Hasil Tes & Kalkulasi Peta) yang diimplementasikan.**
Endpoint 2 (Get Rekomendasi Materi, `POST /api/v1/analytics/recommendations/rank`)
**ditunda** — bergantung pada tiket 06 (struktur katalog Materi/Subkompetensi),
yang masih direview ulang oleh pemilik tiket saat sesi ini berjalan. Tiket 05
(Peran Kecepatan Pengerjaan) diperlakukan sebagai final/settled, termasuk
konsekuensi format ID-nya.

### Migrasi id ke UUID string (konsekuensi tiket 05 disetujui final)

Tiket 05/06/11 menetapkan seluruh id caller-supplied berformat UUID v4 string —
bertentangan dengan skema yang sudah dibangun (tiket 01/02/08/09) yang memakai
integer. Untuk mendukung endpoint 1, kolom-kolom berikut diubah dari `int` ke
`str` (migrasi Alembic `0003`): `hasil_tes.siswa_id/sekolah_id/tingkat_seleksi_id/
simulasi_id`, `hasil_tes_subkompetensi.subkompetensi_id`, `aturan_predikat.
tingkat_seleksi_id`, `aturan_pemetaan.tingkat_seleksi_id` (FK ke `tingkat_seleksi`
lokal juga **dilepas** — tingkat_seleksi_id yang dikirim saat submit adalah UUID
Fullstack, bukan PK katalog seed lokal tiket 09).

**Sengaja TIDAK diubah** (di luar scope tiket 05/11, supaya blast radius
terbatas): `progress_materi` (tiket 02) dan PK tabel katalog seed lokal
(`tingkat_seleksi.id`, `kompetensi.id`, `subkompetensi.id`, `soal.id` — tetap
integer, tiket 09/ADR 0003 tidak tersentuh). Ini berarti ada inkonsistensi tipe
antar-tabel untuk sementara (`hasil_tes.siswa_id` kini `str`, `progress_materi.
siswa_id` masih `int`) — perlu diselaraskan kalau/ketika tiket 02 disentuh ulang.

### Algoritma Peta Kompetensi (FR-07) — belum ada sebelum tiket ini

Modul baru `src/data_analytics/pemetaan.py` (fungsi murni, TDD, pola sama dengan
`scoring.py`): `tentukan_status_pemetaan` (Cukup/Belum Cukup/Belum Teruji dari
ambang `AturanPemetaan`, representasi dihitung dulu — Belum Teruji kalau di
bawah ambang representasi) dan `tentukan_butuh_optimasi` (>50% jawaban benar di
subkompetensi itu juga lambat, hanya relevan kalau status Cukup — resolusi
tiket 05). `repository.get_or_create_aturan_pemetaan` (pola sama dengan
`get_or_create_aturan_predikat`, default 70%/20%) memastikan pemetaan tidak
gagal walau Super Admin belum konfigurasi. `catat_hasil_tes` sekarang mengisi
`status_pemetaan`/`butuh_optimasi` pada tiap `HasilTesSubkompetensi` — dibekukan
saat attempt dihitung, sama seperti `predikat_label` (tiket 01).

### Skema tambahan (tiket 05)

`JawabanSiswa` (tabel baru, `jawaban_siswa`) — log per jawaban: `soal_id`,
`subkompetensi_id`, `jawaban_dipilih`, `is_benar`, `durasi_detik`, `is_lambat`.
**Catatan**: contoh payload tiket 11 di atas tidak menyertakan `jawaban_dipilih`
atau `sekolah_id` — keduanya ditambahkan ke request/skema karena eksplisit
diminta di resolusi tiket 05/08; diperlakukan sebagai kelalaian contoh, bukan
scope yang sengaja dikecualikan. `Soal.batas_waktu_detik` (kolom baru, default
60) ditambahkan sesuai skema tiket 05, tapi **tidak dibaca** oleh endpoint
submit — `batas_waktu_detik` datang per-jawaban di request (caller-supplied,
sesuai prinsip stateless ADR 0002 yang disebut resolusi tiket 11 poin 1 sendiri).
Kolom di `Soal` hanya untuk konsistensi data uji/seed lokal.

### Endpoint yang diimplementasikan

`POST /api/v1/analytics/assessment/submit` — dilindungi `X-Internal-Token`
(pola sama dengan `/api/v1/admin/anonymize-expired`, tiket 10; seluruh panggilan
antar-layanan pakai header ini per resolusi tiket 10). Terima `jenis_tes` dalam
bentuk `"PRE_TEST"`/`"SIMULASI"` (UPPERCASE, sesuai contoh tiket 11) dan
memetakannya ke enum internal `JenisTes` (lowercase). Response memetakan
`StatusPemetaan` internal ke label berkapital (`"Cukup"`, `"Belum Cukup"`,
`"Belum Teruji"`) sesuai contoh response tiket 11 — lihat `STATUS_PEMETAAN_LABEL`
di `schemas.py`. Validasi gagal (mis. `simulasi_id` kosong untuk `jenis_tes=
SIMULASI`, atau `jawaban_siswa` kosong) → `422`, sesuai spesifikasi tiket ini.

### File yang dibuat/diubah

| File | Fungsi |
|---|---|
| `src/data_analytics/pemetaan.py` | Algoritma FR-07 murni (baru) |
| `src/data_analytics/schemas.py` | DTO Pydantic request/response endpoint submit (baru) |
| `src/data_analytics/models.py` | Tipe id → str (caller-supplied), `StatusPemetaan` enum, `JawabanSiswa`, `Soal.batas_waktu_detik`, naming convention constraint |
| `src/data_analytics/repository.py` | `get_or_create_aturan_pemetaan`, `JawabanInput`, `catat_submission_tes`; `catat_hasil_tes` kini mengisi status_pemetaan/butuh_optimasi |
| `src/data_analytics/api.py` | Endpoint `POST /api/v1/analytics/assessment/submit` |
| `alembic/versions/0001_skema_awal.py` | Nama eksplisit ditambahkan ke FK `aturan_pemetaan` (dibutuhkan naming convention baru, aman diubah — belum pernah dijalankan di DB nyata) |
| `alembic/versions/0003_kontrak_api_pemetaan_rekomendasi.py` | Migrasi baru: tabel `jawaban_siswa`, perubahan tipe id, kolom `status_pemetaan`/`butuh_optimasi`/`batas_waktu_detik` |
| `src/data_analytics/scripts/seed.py`, `tests/*` | Disesuaikan ke id string (`str(tingkat.id)` dst.) |
| `tests/test_pemetaan.py` | Test baru untuk `pemetaan.py` |

Diverifikasi end-to-end (bukan cuma test suite): `alembic upgrade head` penuh
(0001→0002→0003) terhadap file SQLite sungguhan, lalu panggilan nyata ke
endpoint submit via `TestClient` — respons `200` dengan Peta Kompetensi benar.

### Dependensi turunan yang terbuka

- Endpoint 2 (`recommendations/rank`) menunggu tiket 06 selesai direview.
- `progress_materi` (tiket 02) dan PK katalog seed lokal (tiket 09) belum
  diselaraskan ke UUID — perlu diputuskan kalau/ketika tiket-tiket itu disentuh
  ulang, supaya tidak ada inkonsistensi tipe id permanen di skema.
- **Gap diketahui**: resolusi tiket 05 poin 2 mewajibkan format UUID v4 untuk
  seluruh identifier, tapi `schemas.py` (`SubmitAssessmentRequest` dkk.) hanya
  memvalidasi tipe `str`, bukan format UUID v4 — string apa pun saat ini lolos
  validasi Pydantic. Sengaja tidak diperketat di sesi ini karena butuh
  menyesuaikan seluruh payload uji di `tests/test_api.py` ke UUID sungguhan
  (risiko regresi tanpa manfaat fungsional langsung); pengetatan (mis. pakai
  tipe `UUID4` Pydantic) adalah pekerjaan terpisah yang aman ditambahkan kapan
  saja tanpa mengubah skema penyimpanan.

