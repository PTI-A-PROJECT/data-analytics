# Remedial: Wajib Belajar Materi Lemah sebelum Simulasi Berikutnya

Type: design
Status: implemented
Blocked by: 01 (katalog `materi`/`halaman_materi`), 02 (pre-test → materi lemah),
03 (simulasi → flag `lemah` per Materi)

## Question

Setelah pre-test atau simulasi, siswa diarahkan belajar lagi di Materi yang lemah
sebelum boleh lanjut ke simulasi berikutnya. Materi mana yang wajib, kapan dianggap
selesai dipelajari, dan bagaimana gerbang ini ditegakkan?

## Resolution

### Materi Wajib

- Setiap submit pre-test/simulasi menghasilkan daftar **Materi Wajib** = semua Materi
  berstatus `lemah` pada attempt itu (issue 03, akurasi < `ambang_lemah`), diurutkan
  dari akurasi terendah. Ini adalah **Rekomendasi Materi** fase 2 (menggantikan
  rekomendasi berbasis Subkompetensi Belum Cukup/Belum Teruji).
- Disimpan sebagai snapshot per attempt:
  - `materi_wajib`: `id`, `paket_tes_id` FK, `siswa_id`, `tingkat_seleksi_id`,
    `materi_id` FK, `urutan`, `akurasi`, `dibuat_pada`, `selesai_pada` (null sampai
    selesai).
  - `materi_wajib_halaman`: (`materi_wajib_id`, `nomor_halaman`) unik — halaman yang
    sudah dibuka **sejak Materi itu diwajibkan**.

### Kriteria "selesai dipelajari"

- Materi Wajib **selesai** saat **setiap halaman** Materi itu sudah dibuka minimal
  sekali sejak diwajibkan (`count(materi_wajib_halaman) = materi.total_halaman`) →
  `selesai_pada` diisi.
- **Navigasi bebas**: tidak harus berurutan, boleh bolak-balik ke halaman yang belum
  dipahami. Melompat ke halaman terakhir tidak otomatis menyelesaikan Materi.
- **Wajib dibaca ulang**: Materi yang pernah tamat di putaran sebelumnya tetap harus
  dibuka ulang semua halamannya kalau lemah lagi — progres dilacak per baris
  `materi_wajib`, terpisah dari riwayat baca permanen.
- Ini menggantikan aturan fase 1 "Halaman Materi harus dicapai berurutan, tanpa
  melompat" (`CONTEXT.md` diperbarui).

### Gerbang Simulasi

- `POST /api/v1/simulasi/paket` (issue 03) hanya diizinkan kalau **semua** Materi Wajib
  dari attempt **terakhir** siswa di tingkat itu sudah `selesai_pada IS NOT NULL`.
  Daftar kosong (tidak ada Materi lemah) → langsung boleh.
- Materi Wajib dari attempt yang lebih lama tidak lagi menahan gerbang — hanya
  attempt terakhir yang berlaku.
- Materi & halaman tetap **selalu terbuka** untuk dibaca kapan saja; gerbang hanya
  menahan pembuatan paket simulasi.

### Event baca halaman

`POST /api/v1/analytics/events/materi-progress` (tiket 14) disederhanakan:
payload `{siswa_id, materi_id, halaman, timestamp}` — `total_halaman`,
`subkompetensi_id`, `tingkat_seleksi_id` tidak lagi dikirim fullstack karena dibaca
dari katalog lokal (issue 01). Handler:

1. Validasi `materi_id` ada & `1 ≤ halaman ≤ total_halaman` (422 kalau tidak).
2. Update `progress_materi` (riwayat baca umum; high-water mark diganti menjadi
   jumlah halaman unik yang pernah dibuka, sesuai navigasi bebas).
3. Kalau ada `materi_wajib` aktif (belum selesai) untuk siswa+materi itu → insert
   `materi_wajib_halaman` (idempoten), lalu cek kriteria selesai.

### Progress Belajar

Didefinisikan ulang: untuk attempt terakhir di suatu tingkat, jumlah Materi Wajib
selesai / total Materi Wajib, plus per Materi: halaman dibuka / total halaman. Tetap
sinyal konsumsi, **bukan** mastery — mastery tetap dibuktikan lewat simulasi
(Level Soal Siswa, issue 03).

### Endpoint

- `GET /api/v1/siswa/{siswa_id}/remedial?tingkat_seleksi_id=` →
  `{boleh_simulasi, materi_wajib: [{materi_id, judul, urutan, akurasi,
  halaman_dibuka, total_halaman, selesai}]}`. Body 409 dari `POST /simulasi/paket`
  memakai struktur yang sama.

### Test

- Unit: kriteria selesai (semua halaman, urutan acak, halaman duplikat, lompat ke
  halaman terakhir saja ≠ selesai).
- Integrasi: pre-test dengan 2 Materi lemah → paket simulasi 409 → baca semua halaman
  kedua Materi dalam urutan acak → 200; Materi yang pernah tamat & lemah lagi harus
  dibaca ulang; attempt tanpa Materi lemah → langsung boleh simulasi.

## Implementation

- Migrasi `0010_materi_wajib_gerbang_simulasi`: `materi_wajib`, `materi_wajib_halaman`,
  `riwayat_baca_halaman` (riwayat baca permanen, satu baris per halaman unik).
- **Deviasi**: `progress_materi` fase 1 (high-water mark, id int dari katalog fullstack
  yang tidak bisa dipetakan ke Materi fase 2) tidak ditulis ulang tapi **diarsipkan**
  sebagai `progress_materi_fase1` (data utuh, tanpa model; diabaikan autogenerate
  lewat `alembic/env.py`). Perannya diganti `riwayat_baca_halaman`; jumlah halaman
  unik dihitung saat baca.
- Fungsi murni `materi_wajib.selesai_dipelajari`. Repository: `_catat_materi_wajib`
  (setiap submit pre-test/simulasi; Materi tanpa halaman langsung selesai),
  `catat_baca_halaman` (baris Materi Wajib aktif dikunci `FOR UPDATE` supaya event
  bersamaan tidak melewatkan status selesai), `status_gerbang_simulasi`; gerbang di
  `susun_paket_simulasi` (`GerbangSimulasiTertutup`, setelah pengembalian paket
  aktif yang idempoten).
- Endpoint: `GET /api/v1/siswa/{siswa_id}/remedial?tingkat_seleksi_id=`; 409
  `POST /api/v1/simulasi/paket` dengan body yang sama (bukan dibungkus `detail`);
  `POST /api/v1/analytics/events/materi-progress` payload `{siswa_id, materi_id,
  halaman, timestamp}` → `{halaman_dibuka, total_halaman, persentase_selesai}`.
- Keputusan detail:
  - `boleh_simulasi` = akses tingkat `terbuka` **dan** semua Materi Wajib selesai
    (sebelum pre-test → false, daftar kosong).
  - Response ditambah `jumlah_materi_wajib` & `jumlah_selesai` (Progress Belajar fase 2).
  - `timestamp` event dipakai sebagai `dibuka_pada`/`selesai_pada`.
- Dihapus (fase 1): `catat_progress_halaman`, `hitung_progress_belajar`,
  `ProgressMateri` model.
- Perbaikan dari code review:
  - Penamaan internal memakai istilah glosarium (Materi Wajib / Gerbang Simulasi —
    "Remedial" ada di daftar _Avoid_ CONTEXT.md); path `/remedial` tetap sesuai kontrak.
  - Kriteria selesai & validasi halaman memakai nomor halaman yang benar-benar ada di
    katalog (`halaman_materi.nomor`), bukan asumsi 1..N tanpa celah.
  - `selesai_pada` memakai waktu server (timestamp klien hanya untuk `dibuka_pada`).
  - 409 `POST /simulasi/paket` terdokumentasi di OpenAPI
    (`responses={409: GerbangSimulasiResponse}`).
