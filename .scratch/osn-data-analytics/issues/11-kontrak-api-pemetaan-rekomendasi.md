# Kontrak API: Pemetaan Kompetensi & Rekomendasi Materi

Type: prototype
Status: open
Blocked by: 05, 06

## Question

Rancang & sketsakan kontrak API konkret (request/response JSON, endpoint, status
code) untuk dua endpoint inti: (1) submit hasil Pre-Test/Simulasi → hitung & kembalikan
Peta Kompetensi, (2) ambil Rekomendasi Materi untuk siswa berdasar Peta Kompetensi
terakhirnya. Buat contoh payload konkret (termasuk representasi Kecepatan Pengerjaan
dan Materi bertag Subkompetensi) yang bisa langsung didiskusikan/direaksi oleh tim
fullstack sebagai kontrak data. Ditunggu sampai tiket "Peran Kecepatan Pengerjaan" dan
"Selaraskan Field Subkompetensi di Materi" selesai karena bentuk payload bergantung
pada keduanya.

Berikut adalah rumusan final **Resolusi dan Implementasi untuk Issue #11** yang sudah diselaraskan sepenuhnya dengan keputusan dari Issue 5 (Kecepatan & flag `butuh_optimasi`) dan Issue 6 (Materi ber-tag Subkompetensi dengan format UUID).

Kamu bisa langsung *copy-paste* teks di bawah ini ke kolom komentar **Issue #11** di GitHub kamu!

---

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

