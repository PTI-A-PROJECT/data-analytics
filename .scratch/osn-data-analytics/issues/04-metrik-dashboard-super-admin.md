# Metrik Dashboard Super Admin

Type: grilling
Status: resolved
Blocked by: none

## Question

FR-24 (Dashboard Super Admin) menyebut "jumlah siswa, aktivitas pengerjaan, distribusi
tingkat, serta data hasil pembelajaran dan simulasi" secara umum — statistik konkret
apa saja yang perlu ditampilkan? Apakah agregasi perlu dipecah per sekolah (butuh
model identitas sekolah — lihat tiket "Kumpulkan fakta dari tim fullstack")? Apakah
ada perbandingan antar-sekolah, atau tiap Super Admin hanya melihat data sekolahnya
sendiri? Bagaimana granularitas waktu (real-time vs snapshot harian)? Resolusi tiket
ini harus mencakup rancangan API/skema untuk endpoint dashboard admin.

Ditunggu sampai tiket Skor, Progress Belajar, Kenaikan Tingkat, dan pengumpulan fakta
dari tim fullstack (model identitas sekolah) selesai, karena dashboard mengagregasi
data dari semuanya.

## Resolution

Dashboard Super Admin (FR-24) berfungsi sebagai pusat pemantauan performa platform OSN
secara holistik lintas sekolah pilot, menyajikan metrik operasional dan akademik secara real-time.

### 1. Cakupan Data & Multi-Tenancy (Sekolah)
- **Cakupan Global**: Super Admin melihat agregat tingkat platform (seluruh sekolah mitra) secara default.
- **Filter Sekolah**: Tersedia parameter filter opsional `sekolah_id` untuk membedah data satu sekolah tertentu.
- **Tabel Komparasi Antar-Sekolah**: Menampilkan ringkasan komparatif per sekolah (`sekolah_id`, `total_siswa_aktif`, `total_attempt_simulasi`, `rata_rata_skor`, `rasio_kelulusan_tingkat`). Metadata nama sekolah di-resolve oleh tim fullstack atau dikirim sebagai lookup.

### 2. Katalog Metrik & Widget Konkret
Dashboard dibagi menjadi 5 komponen widget visual:

1. **Ringkasan KPI Utama (Metric Cards)**:
   - `total_siswa_aktif`: `COUNT(DISTINCT siswa_id)` dari siswa yang memiliki aktivitas pengerjaan tes atau konsumsi materi (mandiri, tanpa dependensi CRUD akun siswa di fullstack).
   - `total_tes_selesai`: akumulasi tes yang diselesaikan (breakdown: Pre-Test vs Simulasi).
   - `rata_rata_skor_simulasi`: rata-rata nilai skor simulasi (`hasil_tes.skor`) pada periode terpilih.
   - `rasio_kelulusan_tingkat`: persentase kelulusan kenaikan tingkat (`total evaluasi lulus / total evaluasi dilakukan × 100%`) dari `riwayat_evaluasi_kenaikan`.
2. **Distribusi Tingkat Siswa (Tier Distribution)**:
   - Menghitung jumlah dan persentase siswa aktif berdasarkan tingkat akses tertinggi yang sedang terbuka (`Kabupaten`, `Provinsi`, `Nasional`) dari `akses_tingkat_siswa`.
   - Disajikan sebagai pie/donut chart.
   - *Semantik*: Selalu menampilkan posisi status terkini (lifetime snapshot), tidak terpotong rentang waktu tanggal.
3. **Tren Aktivitas Pengerjaan (Activity Trends)**:
   - Grafik garis/batang harian yang memperlihatkan volume submission Pre-Test vs Simulasi dalam rentang waktu yang dipilih.
4. **Distribusi Predikat Simulasi (Performance Breakdown)**:
   - Sebaran persentase predikat pengerjaan simulasi berdasarkan snapshot `hasil_tes.predikat_label` ("Sangat Baik", "Baik", "Cukup", "Perlu Latihan").
5. **Analisis Penguasaan Kompetensi (Curriculum Health)**:
   - **Top 3 Kompetensi Terkuat**: Kompetensi dengan rata-rata persentase skor/keberhasilan tertinggi.
   - **Top 3 Kompetensi Terlemah**: Kompetensi dengan rata-rata persentase skor/keberhasilan terendah (indikator fokus pembinaan guru/pembina).

### 3. Strategi Komputasi & Granularitas Waktu
- **Real-time Query Terindeks**: Semua metrik dihitung langsung secara real-time dari tabel data analytics (`hasil_tes`, `hasil_tes_subkompetensi`, `akses_tingkat_siswa`, `riwayat_evaluasi_kenaikan`).
- Pada skala pilot (~100 siswa, ribuan baris data), query agregasi SQL dengan indeks majemuk (`sekolah_id, diselesaikan_pada`, `tingkat_seleksi_id`) berjalan sangat cepat (<100ms), menjamin data langsung akurat seketika tanpa overhead pengelolaan cron job rollup harian.
- **Pemisahan Semantik Rentang Waktu**:
  - Filter `rentang_waktu` (`7d`, `30d`, `90d`, `all`; default `30d`) memfilter data transaksional (KPI pengerjaan, tren pengerjaan, skor simulasi, predikat, dan kompetensi).
  - Status distribusi tingkat siswa (`akses_tingkat_siswa`) tetap mencerminkan posisi siswa saat ini (*current state*).

### 4. Kontrak Endpoint API

Layanan menyediakan endpoint terpadu untuk meminimalkan latensi round-trip frontend:

`GET /api/v1/admin/dashboard`

**Query Parameters**:
- `sekolah_id` (UUID/string, opsional): filter untuk sekolah tertentu.
- `tingkat_seleksi_id` (integer, opsional): filter untuk tingkat seleksi tertentu.
- `rentang_waktu` (enum: `7d`, `30d`, `90d`, `all`, default `30d`): jendela waktu evaluasi.

**Struktur Payload Respons**:
```json
{
  "rentang_waktu": "30d",
  "filter": {
    "sekolah_id": null,
    "tingkat_seleksi_id": null
  },
  "kpi": {
    "total_siswa_aktif": 85,
    "total_tes_selesai": 340,
    "total_pre_test": 85,
    "total_simulasi": 255,
    "rata_rata_skor_simulasi": 78.4,
    "rasio_kelulusan_tingkat": 42.5
  },
  "distribusi_tingkat": [
    { "tingkat_id": 1, "nama": "Kabupaten", "jumlah_siswa": 50, "persentase": 58.8 },
    { "tingkat_id": 2, "nama": "Provinsi", "jumlah_siswa": 28, "persentase": 32.9 },
    { "tingkat_id": 3, "nama": "Nasional", "jumlah_siswa": 7, "persentase": 8.2 }
  ],
  "tren_aktivitas": [
    { "tanggal": "2026-09-01", "pre_test": 10, "simulasi": 25 },
    { "tanggal": "2026-09-02", "pre_test": 5, "simulasi": 30 }
  ],
  "distribusi_predikat": [
    { "label": "Sangat Baik", "jumlah": 60, "persentase": 23.5 },
    { "label": "Baik", "jumlah": 110, "persentase": 43.1 },
    { "label": "Cukup", "jumlah": 55, "persentase": 21.6 },
    { "label": "Perlu Latihan", "jumlah": 30, "persentase": 11.8 }
  ],
  "analisis_kompetensi": {
    "terkuat": [
      { "kompetensi_id": 1, "nama": "Dasar Pemrograman", "rata_rata_skor": 88.5 },
      { "kompetensi_id": 2, "nama": "Aritmatika & Aljabar", "rata_rata_skor": 82.0 }
    ],
    "terlemah": [
      { "kompetensi_id": 5, "nama": "Graf & Pohon", "rata_rata_skor": 54.2 },
      { "kompetensi_id": 4, "nama": "Pemrograman Dinamis", "rata_rata_skor": 58.0 }
    ]
  },
  "komparasi_sekolah": [
    {
      "sekolah_id": "sch-01",
      "total_siswa_aktif": 40,
      "total_simulasi": 130,
      "rata_rata_skor": 81.2,
      "rasio_kelulusan_tingkat": 50.0
    }
  ]
}
```

### 5. Skema & Indeks Basis Data yang Dibutuhkan

Tidak memerlukan tabel agregasi terpisah. Kueri agregasi dioptimalkan menggunakan indeks pada tabel-tabel yang sudah ada:

```sql
-- Indeks penunjang query analitik dashboard
CREATE INDEX idx_hasil_tes_dashboard ON hasil_tes (sekolah_id, tingkat_seleksi_id, jenis_tes, diselesaikan_pada);
CREATE INDEX idx_hasil_tes_subkomp_aggr ON hasil_tes_subkompetensi (subkompetensi_id, hasil_tes_id);
CREATE INDEX idx_akses_tingkat_dashboard ON akses_tingkat_siswa (status, tingkat_seleksi_id);
CREATE INDEX idx_riwayat_eval_dashboard ON riwayat_evaluasi_kenaikan (hasil_evaluasi, dievaluasi_pada);
```

### Dependensi turunan yang diselesaikan

- Tiket 11 (Kontrak API: Pemetaan Kompetensi & Rekomendasi Materi): spesifikasi rute `GET /api/v1/admin/dashboard` siap dimasukkan ke kontrak OpenAPI platform.

## Implementation

**Diimplementasikan** di `src/data_analytics/dashboard.py` +
`GET /api/v1/admin/dashboard` (`api.py`, dilindungi `X-Internal-Token`) —
KPI Utama, Tren Aktivitas, Distribusi Predikat, dan Komparasi Sekolah persis
sesuai resolusi di atas, dihitung real-time dari `hasil_tes` +
`riwayat_evaluasi_kenaikan` (tiket 03), tanpa tabel rollup terpisah. Filter
`sekolah_id` dan `rentang_waktu` (`7d`/`30d`/`90d`/`all`) diimplementasikan;
`distribusi_tingkat` memakai `akses_tingkat_siswa`+`tingkat_seleksi` (tiket
03) — snapshot lifetime, tidak terpotong `rentang_waktu`, sesuai resolusi.

**Scope dipersempit dari resolusi di atas — dua bagian SENGAJA belum
diimplementasikan**, keduanya karena gap yang sama yang sudah dicatat tiket
11 ("progress_materi dan PK katalog seed lokal belum diselaraskan ke UUID"):

1. **"Analisis Penguasaan Kompetensi" (top/bottom 3 Kompetensi)**: butuh
   join `hasil_tes_subkompetensi.subkompetensi_id` (str, UUID caller-supplied
   sejak tiket 11) ke katalog `subkompetensi`/`kompetensi` LOKAL (int,
   tiket 09) untuk resolve `nama` — dua ruang id berbeda, tidak bisa di-join
   langsung. Ditinggalkan kosong daripada menampilkan grouping yang
   menyesatkan (mis. label = UUID mentah).
2. **Filter `tingkat_seleksi_id`**: KPI transaksional (`hasil_tes`) pakai
   UUID caller-supplied, sedangkan `distribusi_tingkat` pakai id katalog
   lokal (tiket 03) — satu parameter filter tidak bisa menyaring keduanya
   secara konsisten.

Kedua gap ini menunggu penyelarasan skema id yang sama dengan `progress_materi`
(tiket 02) — item terbuka yang sama, bukan kegagalan baru dari tiket ini.

### File yang dibuat/diubah

| File | Fungsi |
|---|---|
| `src/data_analytics/dashboard.py` | Agregasi metrik (baru) |
| `src/data_analytics/schemas.py` | DTO Pydantic response dashboard |
| `src/data_analytics/api.py` | Endpoint `GET /api/v1/admin/dashboard` |
| `tests/test_api_kenaikan_dashboard.py` | Test baru (KPI, filter sekolah, komparasi sekolah) |

Diverifikasi: full test suite (129 test) dan `mypy` bersih.

### Latar belakang: konsolidasi dari `app/` (PR #7)

Sama seperti tiket 03 — lihat catatan konsolidasi di tiket itu dan di
`map.md`.
