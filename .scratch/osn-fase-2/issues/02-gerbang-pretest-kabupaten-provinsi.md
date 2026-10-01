# Gerbang Pre-Test: Kabupaten → Provinsi

Type: design
Status: implemented (jalur simulasi: fungsi murni siap, disambungkan di issue 03)
Blocked by: 01 (bank konten — butuh `soal.level`, `materi`, `paket_tes`)

## Question

Fase 2 hanya punya dua Tingkat Seleksi: **Kabupaten** dan **Provinsi** (Nasional
dihapus). Setiap siswa memulai dengan pre-test untuk menilai kemampuan awal lewat skor.
Siswa wajib memenuhi kriteria Kabupaten sebelum boleh ikut pre-test Provinsi. Kapan
persisnya pre-test Provinsi terbuka, bagaimana pre-test disusun, dan apa yang terjadi
setelah pre-test dikerjakan?

## Resolution

### Tingkat Seleksi

- Hanya **Kabupaten** (urutan 1) dan **Provinsi** (urutan 2). Baris Nasional dihapus dari
  seed/katalog beserta `aturan_kenaikan_tingkat` Provinsi → Nasional (migrasi `0005`).

### Status akses per siswa per tingkat

`akses_tingkat_siswa` yang sudah ada dipakai ulang dengan status diperluas:

| Status | Arti | Kabupaten | Provinsi |
|---|---|---|---|
| `terkunci` | belum boleh apa-apa | — | awal |
| `pretest_terbuka` | boleh mengerjakan pre-test | awal (siswa baru) | setelah syarat Kabupaten terpenuhi |
| `terbuka` | pre-test selesai → materi & simulasi terbuka | setelah pre-test dikerjakan | setelah pre-test dikerjakan |

- Materi & simulasi suatu tingkat terbuka setelah pre-test tingkat itu **dikerjakan,
  berapa pun skornya** — pre-test memetakan kelemahan, bukan menyaring.
- ~~Akses yang sudah terbuka permanen, tidak pernah dicabut~~ — **aturan ini dihapus**
  (keputusan user setelah implementasi): akses boleh diturunkan/dicabut lewat override
  Super Admin (dan migrasi data fase 1). Alur otomatis hanya membuka akses dan tidak
  menimpa status yang sudah lebih tinggi.

### Pre-test

- **Sekali per tingkat** — baseline. Kemajuan berikutnya diukur lewat simulasi; siswa
  yang tidak lolos jalur cepat naik lewat jalur simulasi, bukan mengulang pre-test.
- **Tidak adaptif**: semua soal level **Mudah**, kuota dibagi **rata per Materi** di
  tingkat itu. Kalau stok Mudah suatu Materi kurang, sisa kuota dialihkan ke Materi lain
  (dicatat di `paket_tes`). Soal dipilih acak; susunan disimpan sebagai `paket_tes` +
  `paket_tes_soal` (auditable).
- Jumlah soal pre-test dikonfigurasi per tingkat (`aturan_adaptif.jumlah_soal_pretest`,
  lihat issue 03).

### Setelah pre-test di-submit

1. Skor & predikat (`scoring.py`), Peta Kompetensi **per Materi** (`pemetaan.py`
   dengan unit Materi).
2. `level_soal_siswa` diinisialisasi **Mudah** untuk *semua* Materi di tingkat itu →
   simulasi pertama pasti mudah semua.
3. Materi lemah diteruskan ke Gerbang Simulasi (issue 04).
4. Status akses tingkat itu → `terbuka`.
5. **Jalur cepat**: pre-test Kabupaten dengan skor ≥ `skor_pretest_jalur_cepat`
   (default **90**) → Provinsi → `pretest_terbuka`.

### Jalur simulasi (Kabupaten → pre-test Provinsi)

Dievaluasi setiap kali simulasi Kabupaten di-submit. Pre-test Provinsi terbuka jika
**dalam satu attempt simulasi**:

- skor simulasi ≥ `skor_simulasi_min`, **dan**
- rata-rata Level Soal siswa atas **semua** Materi Kabupaten ≥ `rata_level_min`
  (default **2.0**), dengan Mudah=1, Menengah=2, Sulit=3, memakai level *setelah*
  diperbarui oleh simulasi tersebut (issue 03).

### Skema

`aturan_kenaikan_tingkat` (sudah ada) disesuaikan:

| Perubahan | Kolom |
|---|---|
| tambah | `skor_pretest_jalur_cepat` numeric, default 90 |
| tambah | `rata_level_min` numeric, default 2.0 |
| tetap | `skor_simulasi_min` (default Kabupaten→Provinsi 75) |
| hapus | `persentase_kompetensi_cukup_min` (digantikan rata-rata level) |

`riwayat_evaluasi_kenaikan` mencatat jalur yang membuka akses (`jalur_cepat_pretest` /
`jalur_simulasi` / `override_admin`).

### Endpoint (semua `X-Internal-Token`)

- `POST /api/v1/pretest/paket` `{siswa_id, tingkat_seleksi_id}` → paket soal **tanpa
  kunci jawaban & pembahasan**. 403 kalau status bukan `pretest_terbuka`; 409 kalau
  pre-test tingkat itu sudah selesai; kalau paket belum disubmit, paket yang sama
  dikembalikan (idempoten).
- `POST /api/v1/paket/{paket_id}/submit` `{jawaban: [{soal_id, jawaban_dipilih,
  dibuka_pada, dijawab_pada}]}` → skor, predikat, peta per Materi, materi lemah, status
  akses terbaru. Dipakai bersama oleh simulasi (issue 03). Soal di luar paket → 422;
  paket sudah disubmit → 409.
- `GET /api/v1/siswa/{siswa_id}/akses` → status akses per tingkat.

### Test

- Unit (tanpa DB): evaluasi jalur cepat & jalur simulasi (batas tepat 90 / rata 2.0),
  pembagian kuota rata dengan pengalihan stok kurang.
- Integrasi (Postgres): alur siswa baru → pre-test Kabupaten → akses; 403/409; skor 90
  membuka Provinsi; skor 89 tidak.

## Implementation

- Migrasi `0006_gerbang_pretest_paket_tes` (bukan `0005` — sudah dipakai issue 01):
  hapus Nasional (akses & aturan ikut via cascade), status akses `default_awal`
  `terbuka` → `pretest_terbuka`, `manual_admin` → `override_admin`,
  `lulus_evaluasi` → `jalur_simulasi`; `aturan_kenaikan_tingkat` + kolom jalur cepat &
  rata level (default Kabupaten→Provinsi 75/90/2.0 diisi — fase 1 tidak pernah
  mengisinya); `riwayat_evaluasi_kenaikan.jalur` + kolom rata level; tabel baru
  `aturan_adaptif` (hanya `jumlah_soal_pretest` default 30 & `ambang_lemah` default 50 —
  kolom simulasi menyusul di issue 03), `level_soal_siswa`, `paket_tes`,
  `paket_tes_soal`, `hasil_tes_materi`; `hasil_tes.paket_tes_id`.
- **Deviasi**: jawaban disimpan di `paket_tes_soal` (`jawaban_dipilih`, `is_benar`,
  `dibuka_pada`, `dijawab_pada`), bukan `jawaban_siswa` fase 1. Pre-test unik per
  (siswa, tingkat) ditegakkan partial unique index. `POST /paket/{id}/submit` menerima
  `sekolah_id` opsional (snapshot untuk Dashboard, resolusi tiket 08).
- Fungsi murni: `paket.bagi_kuota_rata`, `pemetaan.petakan_per_materi`/`materi_lemah`,
  `kenaikan.evaluasi_jalur_cepat`/`evaluasi_jalur_simulasi`. Alur: `repository.
  susun_paket_pretest`/`submit_paket`. Endpoint: `POST /api/v1/pretest/paket`,
  `POST /api/v1/paket/{paket_id}/submit`, `GET /api/v1/siswa/{siswa_id}/akses`.
- Dihapus (fase 1, digantikan): `POST /api/v1/analytics/tingkat/evaluasi` +
  `evaluasi_dan_catat_kenaikan` (syarat % kompetensi cukup kiriman fullstack),
  `GET /api/v1/analytics/tingkat/{siswa_id}/akses` (→ `/api/v1/siswa/{id}/akses`).
- Jalur simulasi: `evaluasi_jalur_simulasi` siap & dites; pemanggilan dari submit
  simulasi + pencatatan riwayatnya dikerjakan di issue 03 (simulasi belum ada).
- Perbaikan dari code review:
  - Race condition: submit mengunci baris paket (`FOR UPDATE`) → submit bersamaan = satu
    200 + satu 409; susun paket bersamaan → paket yang sama (savepoint + tangkap unique);
    `inisialisasi_akses_siswa` memakai `ON CONFLICT DO NOTHING` (race lama fase 1).
    Diverifikasi dengan skrip dua-thread sekali pakai, bukan test otomatis.
  - Migrasi: akses tingkat > Kabupaten yang `terbuka` di fase 1 (tanpa pre-test) →
    `pretest_terbuka`, konsisten dengan arti `terbuka` fase 2.
  - Akses dicek sebelum mengembalikan paket yang belum disubmit (admin yang mengunci
    akses → 403). Aturan aktif ganda dari tingkat asal yang sama tidak crash (yang tertua).
- Migrasi mengubah Kabupaten `terbuka` (default fase 1) → `pretest_terbuka`; sah sejak
  aturan "akses permanen" dihapus. Catatan terbuka: `hasil_tes.tingkat_seleksi_id` masih
  str (id lokal sebagai string).
