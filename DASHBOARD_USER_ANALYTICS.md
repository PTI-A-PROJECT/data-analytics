# User Analytics & Conversion Funnel (SIAP OSN)

Modul khusus analitik pengguna dan corong konversi registrasi siswa untuk platform SIAP OSN Informatika (FR-01 Registrasi Siswa dan FR-24 Dashboard Super Admin).

Seluruh kode sumber, antarmuka dashboard, skrip pelacak, pengujian, dan dokumentasi mendalam ditempatkan dalam folder mandiri [`dashboard-user-analytics/`](./dashboard-user-analytics/).

---

## 1. Struktur Modul

```text
dashboard-user-analytics/
├── README.md                      # Dokumentasi komprehensif (konsep, alur, formula, diagnosis)
├── DESIGN.md                      # Token desain Apple HIG, tipografi, dan palet warna
├── src/
│   └── funnel_analytics/
│       ├── __init__.py            # Inisialisasi paket
│       ├── models.py              # Model database (FunnelEvent, UserAccount, SQLite/PostgreSQL)
│       ├── schemas.py             # Skema Pydantic request & response
│       ├── service.py             # Logika bisnis (Strict Monotonic Funnel, Attribution, P50/P90)
│       └── api.py                 # Endpoint FastAPI + Server-Sent Events (SSE) broadcast
├── static/
│   ├── index.html                 # Antarmuka web (Dual-view: Simulasi FR-01 & Dashboard FR-24)
│   └── siap-osn-funnel-tracker.js # SDK pelacak otomatis aktivitas dan form peramban siswa
├── tests/
│   └── test_funnel_analytics.py   # Suite pengujian otomatis (7 skenario lolos 100%)
└── docs/
    └── conversion-funnel/         # Catatan arsitektur dan spesifikasi tiket implementasi
```

---

## 2. Fitur Utama

1. **Strict Monotonic Conversion Funnel**:
   Perhitungan 4 tahap konversi:
   - Kunjungan Landing Page (`page_visit`)
   - Klik Tombol Registrasi (`click_register`)
   - Pengisian Formulir (`start_registration`)
   - Akun Berhasil Dibuat (`account_created`)
   Menggunakan validasi sekuensial kronologis sehingga rasio antar-tahap tidak pernah melebihi 100% ($N_1 \ge N_2 \ge N_3 \ge N_4$).

2. **Real-Time Activity Streaming (SSE)**:
   Mencatat dan menyiarkan log aktivitas siswa secara langsung tanpa jeda reload ke antarmuka Super Admin melalui endpoint `/api/v1/funnel/stream`.

3. **Identity Stitching**:
   Menghubungkan identitas anonim peramban (`anonymous_id`) ke identitas siswa terverifikasi (`users.id`) saat pendaftaran berhasil.

4. **Drop-Off Attribution**:
   Membedakan penurunan konversi formulir menjadi dua kategori:
   - Pengabaian formulir (*abandonment*)
   - Penolakan sistem (*duplicate email* atau *validation failed*)

5. **Waktu Konversi**:
   Menghitung durasi pendaftaran menggunakan Median (P50) dan P90.

---

## 3. Cara Menjalankan

### A. Menjalankan Server FastAPI
Jalankan perintah berikut dari direktori root:

```bash
uv run uvicorn funnel_analytics.api:app --reload --port 8000
```

Atau langsung dari dalam folder `dashboard-user-analytics`:

```bash
cd dashboard-user-analytics
python -m uvicorn funnel_analytics.api:app --reload --port 8000
```

### B. Membuka Dashboard Web
Buka peramban dan akses:
```text
http://127.0.0.1:8000/
```
Antarmuka menyajikan dua panel:
- Panel Kiri: Simulasi interaktif registrasi siswa (FR-01).
- Panel Kanan: Dashboard metrik konversi dan log aktivitas real-time (FR-24).

### C. Menjalankan Pengujian Otomatis
Jalankan pengujian menggunakan `pytest`:

```bash
uv run --no-sync pytest dashboard-user-analytics/tests -v
```

Hasil verifikasi:
```text
7 passed in 0.89s (100% lolos)
```

---

## 4. Referensi Lengkap

- Baca penjelasan rinci mengenai konsep, alur langkah, dan formula analitik di [`dashboard-user-analytics/README.md`](./dashboard-user-analytics/README.md).
- Rincian spesifikasi desain antarmuka tersedia di [`dashboard-user-analytics/DESIGN.md`](./dashboard-user-analytics/DESIGN.md).
