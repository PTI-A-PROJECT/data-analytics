# Task: Selaraskan Instrumentasi Halaman Materi dengan Tim Fullstack

Type: task
Status: open
Blocked by: none

## Question

Tiket "Definisi & Formula Progress Belajar" memutuskan bahwa Materi terbagi jadi
Halaman Materi sekuensial, dan progress dilacak sebagai halaman tertinggi yang
dicapai siswa. Brief belum punya konsep ini sama sekali (FR-19 Manajemen Materi
hanya "judul, isi materi"). Selesaikan tiket ini dengan mengonfirmasi ke tim
fullstack bahwa: (1) Materi akan distrukturkan jadi halaman-halaman sekuensial,
(2) UI Layanan Belajar (FR-09) akan mengirim event ke layanan data & analytics saat
siswa mencapai suatu halaman (payload: siswa_id, materi_id, subkompetensi_id,
tingkat_seleksi_id, total_halaman, halaman_dicapai), dan mencatat kesepakatan
tersebut sebagai jawaban.

## Resolusi Issue #14: Penyelarasan Instrumentasi Halaman Materi

**1. Bentuk UI Halaman (Sekuensial)**
Materi (FR-19) tidak akan ditampilkan sebagai satu halaman panjang (*infinite scroll*). UI/UX akan membagi konten materi menggunakan sistem **Pagination** (tombol *Next/Previous* atau angka halaman). Hal ini wajib dilakukan agar metrik "halaman tertinggi yang dicapai" dapat diukur secara eksak sebagai *integer*.

**2. Mekanisme *Trigger Event* (Anti-Spam)**
Untuk mencegah siswa memanipulasi *progress* 100% dengan cara mengklik tombol *Next* secara cepat, disepakati penerapan *Dwell Time Trigger*.
*Front-end* (UI Layanan Belajar - FR-09) baru akan menembak API *event progress* ke *backend analytics* setelah siswa berada (diam/aktif) di halaman tersebut selama **minimal 3 detik**.

**3. Standarisasi Payload Kontrak Data**
Untuk menjaga konsistensi dengan DTO Pydantic yang sudah disahkan pada **Issue #6**, nama parameter yang disepakati adalah **`halaman_dibuka`** (bukan `halaman_dicapai`).

**Kesepakatan Tindakan (Action Items):**

* **Tim UI/UX:** Mendesain antarmuka materi berbasis *pagination* dan menambahkan logika *timer 3 detik* sebelum memanggil API.
* **Tim Fullstack/Backend:** Menyediakan *endpoint* atau *message broker* untuk menerima *payload* tersebut dari *client*.
* **Tim Data & Analytics:** Menerima dan memproses *payload* berikut untuk memperbarui *high-water mark progress* siswa.

**Format Payload Event yang Disepakati:**

```json
{
  "siswa_id": "8f3b2c14-52d3-4a11-9a7e-4b2a8d3e1101",
  "materi_id": "c1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
  "subkompetensi_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "tingkat_seleksi_id": "b5a4c3d2-e1f0-4a9b-8c7d-6e5f4a3b2c1d",
  "total_halaman": 12,
  "halaman_dibuka": 5,
  "timestamp": "2026-09-22T06:30:00Z"
}
*

## Implementasi: Skema Database & Logika *High-Water Mark*

Untuk memproses *payload event* pembacaan materi dari *front-end*, tim Data & Analytics akan menyiapkan tabel dan logika pemrosesan sebagai berikut:

#### 1. Skema Tabel `progress_materi_siswa`

Tabel ini berfungsi menyimpan "jejak tertinggi" (*high-water mark*) dari materi yang dibaca siswa.

* `id` (PK, UUID)
* `siswa_id` (UUID, terhubung ke data siswa)
* `materi_id` (UUID, terhubung ke data materi)
* `subkompetensi_id` (UUID, terhubung ke data subkompetensi)
* `tingkat_seleksi_id` (UUID, terhubung ke tingkat seleksi)
* `total_halaman` (Integer)
* `halaman_tertinggi_dicapai` (Integer) -> *Menyimpan angka tertinggi dari `halaman_dibuka` yang pernah dikirim oleh frontend.*
* `last_accessed_at` (Timestamp)

#### 2. Logika Pipeline (Event Handler)

Tim Data & Analytics akan membuat *endpoint* internal (misal: `POST /api/v1/analytics/events/materi-progress`) untuk menerima *payload* dari tim Fullstack. Logika pemrosesannya adalah **Upsert (Update or Insert) bersyarat**:

1. **Validasi:** Sistem menerima *payload* dan memvalidasinya menggunakan Pydantic DTO (memastikan `halaman_dibuka` tidak melebihi `total_halaman`).
2. **Cek Data Eksisting:** Sistem melakukan *query* ke tabel `progress_materi_siswa` berdasarkan `siswa_id` dan `materi_id`.
3. **Kondisi Insert (Data Baru):** Jika data belum ada, lakukan `INSERT` data baru dengan `halaman_tertinggi_dicapai` = `payload.halaman_dibuka`.
4. **Kondisi Update (Data Lama):** Jika data sudah ada, sistem hanya akan melakukan `UPDATE` jika angka `payload.halaman_dibuka` **lebih besar** dari `halaman_tertinggi_dicapai` yang tersimpan di *database*.
* *(Contoh: Jika di database tercatat halaman 5, lalu siswa kembali mundur membaca halaman 2 dan frontend mengirim event halaman 2, sistem akan mengabaikan update ini).*
5. **Kalkulasi Progress Subkompetensi:** Data `halaman_tertinggi_dicapai` ini nantinya akan diolah secara agregat oleh mesin rekomendasi untuk menghitung metrik *Progress Belajar* (FR-10) per Subkompetensi.


