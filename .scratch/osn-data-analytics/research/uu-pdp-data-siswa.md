# Kewajiban UU PDP untuk Data Performa Tes Siswa (Platform OSN Informatika)

Riset ini meneliti sumber primer: teks **UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi (UU PDP)** dan peraturan pelaksananya, **PP No. 33 Tahun 2026 tentang Peraturan Pelaksanaan UU No. 27/2022**, untuk kebutuhan desain layanan data & analytics platform latihan OSN Informatika yang menyimpan data performa tes siswa (mayoritas kemungkinan besar berstatus anak/di bawah umur).

**Status hukum per 21 September 2026 (tanggal riset ini dibuat):**
- UU PDP disahkan dan diundangkan 17 Oktober 2022; mengikat penuh (masa transisi 2 tahun berakhir) sejak **17 Oktober 2024**.
- Peraturan pelaksana (PP) baru **ditetapkan 16 Juli 2026** sebagai **PP No. 33 Tahun 2026** (LN 2026 No. 88, TLN No. 7190; 225 pasal dalam 12 bab), dan **baru mulai berlaku 15/16 Januari 2027**. Artinya pada tanggal riset ini PP tersebut sudah diundangkan tetapi *belum berlaku efektif*.
- **Lembaga Pelindungan Data Pribadi** (otoritas pengawas independen yang diamanatkan UU PDP) **belum terbentuk** per September 2026 — sejumlah pihak bahkan membawa kekosongan ini ke Mahkamah Konstitusi. Konsekuensinya: banyak "aturan turunan dari Lembaga" (misalnya standar teknis keamanan yang rinci) belum punya rujukan resmi.

> Catatan metodologi: Teks pasal UU PDP di bawah ini diverifikasi lewat situs pengutip pasal-per-pasal (pasal.id) yang mengutip teks resmi, disilangkan dengan ringkasan berita hukum (Kompas, Hukumonline). Teks resmi PDF hasil pindai (peraturan.bpk.go.id, JDIH Kemkomdigi) tidak bisa diekstraksi otomatis oleh tooling riset ini (PDF berbasis gambar/scan). Untuk **PP No. 33/2026**, karena PP ini belum tersedia sebagai teks yang bisa diekstraksi penuh, sebagian besar rincian pasal dalam riset ini berasal dari **artikel analisis hukum sekunder** (veritask.ai, kres.id, edulawproject.id, paralegal.id, meridianhukum.com) — ini ditandai eksplisit di setiap klaim terkait, dan sebaiknya **diverifikasi ulang terhadap teks resmi PP 33/2026** (via jdih.setneg.go.id atau peraturan.bpk.go.id) sebelum dijadikan dasar kepatuhan final, karena beberapa sumber sekunder saling tidak konsisten soal nomor pasal persis.

---

## 1. Persyaratan Consent — apakah izin sekolah cukup, atau perlu consent eksplisit orang tua/wali?

**Jawaban singkat: consent sekolah sebagai pengendali data TIDAK cukup. UU PDP mewajibkan consent eksplisit dari orang tua dan/atau wali anak secara terpisah, karena data anak diperlakukan sebagai kategori data pribadi yang bersifat spesifik (sensitif).**

Dasar hukum (primer, UU No. 27/2022):

- **Pasal 4 ayat (1)–(2)**: UU PDP membagi data pribadi menjadi "Data Pribadi yang bersifat spesifik" dan "Data Pribadi yang bersifat umum". Ayat (2) secara eksplisit memasukkan **"data anak"** ke dalam daftar data pribadi spesifik, sejajar dengan data kesehatan, data biometrik, data genetika, catatan kejahatan, dan data keuangan pribadi. Artinya seluruh data yang terkait siswa (termasuk data performa tes, karena melekat pada identitas anak) berpotensi tunduk pada rezim perlindungan data sensitif, bukan data umum.
- **Pasal 20 ayat (1)–(2)**: Pengendali data wajib memiliki dasar hukum pemrosesan. Salah satu dasar yang sah adalah "persetujuan yang sah secara eksplisit dari Subjek Data Pribadi" (huruf a); dasar lain termasuk pelaksanaan kontrak, kewajiban hukum, kepentingan vital, **"pelaksanaan tugas dalam rangka kepentingan umum, pelayanan publik"** (huruf e), atau kepentingan sah lain dengan mempertimbangkan proporsionalitas.
- **Pasal 25 ayat (1)–(2)** (ketentuan lex specialis untuk anak): *"Pemrosesan Data Pribadi anak diselenggarakan secara khusus."* (ayat 1) dan *"Pemrosesan Data Pribadi anak sebagaimana dimaksud pada ayat (1) wajib mendapat persetujuan dari orang tua anak dan/atau wali anak sesuai dengan ketentuan peraturan perundang-undangan."* (ayat 2).
- **Pasal 26** memuat ketentuan paralel untuk data penyandang disabilitas (persetujuan wajib dari penyandang disabilitas dan/atau walinya) — pola yang sama diterapkan UU PDP untuk kelompok rentan.
- **Pasal 57 ayat (1)** menegaskan pelanggaran terhadap Pasal 25 ayat (2) (antara lain) dikenai **sanksi administratif**.

**Implikasi kunci untuk platform ini:** Karena Pasal 25 berdiri sebagai ketentuan khusus (bukan hanya salah satu dari enam opsi dasar hukum di Pasal 20), interpretasi paling aman adalah: *walaupun sekolah, sebagai institusi, mungkin punya dasar hukum lain untuk memproses data siswa (mis. "pelayanan publik" di Pasal 20(2)(e) untuk sekolah negeri), platform tetap wajib memperoleh persetujuan eksplisit dari orang tua/wali secara terpisah* ketika data yang diproses adalah data pribadi anak. UU PDP tidak menyediakan pengecualian setara "school official exception" (seperti FERPA di AS) yang membolehkan sekolah bertindak mewakili wali murid tanpa consent terpisah — ini adalah **gap penting** dibanding kerangka hukum data pendidikan di yurisdiksi lain, dan tim rekayasa sebaiknya tidak berasumsi consent institusional (MoU sekolah–platform) otomatis mencakup consent data pribadi anak secara hukum.

**Definisi "anak":** UU PDP sendiri tidak mendefinisikan batas usia anak dan merujuk pada *"ketentuan peraturan perundang-undangan"* lain. Definisi umum yang berlaku adalah **Pasal 1 angka 1 UU No. 23/2002 jo. UU No. 35/2014 tentang Perlindungan Anak**: *"Anak adalah seseorang yang belum berusia 18 (delapan belas) tahun, termasuk anak yang masih dalam kandungan."* Karena peserta OSN Informatika (tingkat SMA, umumnya kelas 10–12) besar kemungkinan berusia 15–18 tahun, hampir seluruh basis pengguna berpotensi berstatus anak di bawah UU ini — termasuk yang mendekati usia 18 tahun.

Catatan tambahan dari sumber sekunder (belum terverifikasi lewat teks resmi): beberapa artikel menyebut PP 33/2026 mengatur *"persetujuan orang tua/wali yang terverifikasi"* (disebut sebagai Pasal 38 oleh satu sumber sekunder, namun nomor ini tidak bisa dikonfirmasi silang dari sumber kedua) — jika benar, ini akan menambah kewajiban **mekanisme verifikasi identitas/hubungan orang tua-anak**, bukan sekadar centang consent. **Ini perlu diverifikasi ulang begitu teks resmi PP 33/2026 tersedia.**

---

## 2. Retensi Data — apa kata undang-undang (langsung atau via peraturan pelaksana) soal batas/kewajiban retensi?

**UU PDP menganut prinsip *storage limitation* (pembatasan penyimpanan), tetapi TIDAK menetapkan angka/jangka waktu retensi yang pasti secara langsung dalam teks UU** — jangka waktu retensi justru wajib **ditentukan dan diumumkan sendiri oleh pengendali data**, lalu didokumentasikan/diaudit.

Dasar hukum (primer, UU No. 27/2022):

- **Pasal 16 ayat (2) huruf g**: *"Data Pribadi dimusnahkan dan/atau dihapus setelah masa retensi berakhir atau berdasarkan permintaan Subjek Data Pribadi, kecuali ditentukan lain oleh peraturan perundang-undangan."* — ini adalah kewajiban pemusnahan/penghapusan, bukan penetapan durasi retensi itu sendiri.
- **Pasal 16 ayat (3)**: ketentuan lebih lanjut mengenai pelaksanaan pemrosesan data pribadi (termasuk soal retensi) *"diatur dalam Peraturan Pemerintah"* — mandat inilah yang baru dipenuhi lewat PP 33/2026 (belum berlaku efektif).
- **Pasal 21 ayat (1) huruf d**: ketika dasar pemrosesan adalah persetujuan (Pasal 20(2)(a)), pengendali data **wajib menyampaikan informasi** kepada subjek data pribadi mengenai *"jangka waktu retensi dokumen yang memuat Data Pribadi"* — jadi kewajibannya bersifat **transparansi/disclosure**, bukan batas waktu tetap yang ditentukan UU.
- **Pasal 21 ayat (2)**: jika informasi tersebut (termasuk jangka waktu retensi) berubah, pengendali wajib memberi tahu subjek data **sebelum** perubahan terjadi.
- **Pasal 34 ayat (1)–(2)**: pengendali wajib melakukan **Penilaian Dampak Pelindungan Data Pribadi (DPIA)** untuk pemrosesan berisiko tinggi — termasuk pemrosesan data pribadi spesifik (data anak termasuk kategori ini per Pasal 4(2)) dan pemrosesan skala besar. DPIA semestinya mencakup evaluasi kebutuhan/proporsionalitas retensi.

Dari **PP No. 33/2026** (sumber sekunder, belum terverifikasi penuh terhadap teks resmi):
- Beberapa sumber sekunder (veritask.ai) menyebut kewajiban pengendali untuk mampu menjelaskan *"jangka waktu penyimpanan, mekanisme penghapusan"* sebagai bagian dari *record of processing* (disebut Pasal 74, dengan kewajiban dokumentasi retensi disebut Pasal 75 oleh sumber lain — nomor pasal antar-sumber tidak sepenuhnya konsisten).
- Tidak ditemukan angka retensi baku (mis. "maksimal 5 tahun") dalam PP ini menurut ringkasan yang berhasil diakses — retensi tetap **ditentukan oleh pengendali berdasarkan tujuan pemrosesan**, didokumentasikan, dan bisa diaudit oleh Lembaga PDP (setelah lembaga ini terbentuk).
- Ada rujukan pada *"jadwal retensi arsip"* di beberapa ringkasan berita — ini berpotensi bersinggungan dengan **UU No. 43/2009 tentang Kearsipan** jika data siswa dianggap bagian dari arsip institusi pendidikan formal. Ini di luar cakupan UU PDP itu sendiri dan perlu dicek terpisah bila platform ini terintegrasi resmi dengan sistem sekolah/Kemdikbud.

**Kesimpulan bagian ini:** UU PDP tidak memberi angka retensi siap pakai. Kewajiban intinya adalah (a) pengendali **menentukan sendiri** jangka waktu retensi berdasarkan tujuan pemrosesan yang jelas dan proporsional, (b) **mengumumkan/mendokumentasikan** jangka waktu itu kepada subjek data (orang tua/wali untuk data anak), dan (c) **memusnahkan/menghapus secara otomatis** begitu masa retensi berakhir, consent dicabut, atau tujuan tercapai.

---

## 3. Kewajiban Keamanan — persyaratan keamanan apa yang berlaku untuk penyimpanan data pribadi (relevan untuk PostgreSQL self-hosted)?

Dasar hukum (primer, UU No. 27/2022):

- **Pasal 35**: *"Pengendali Data Pribadi wajib melindungi dan memastikan keamanan Data Pribadi yang diprosesnya, dengan melakukan: a. penyusunan dan penerapan langkah teknis operasional untuk melindungi Data Pribadi dari gangguan pemrosesan Data Pribadi yang bertentangan dengan ketentuan peraturan perundang-undangan; dan b. penentuan tingkat keamanan Data Pribadi dengan memperhatikan sifat dan risiko dari Data Pribadi yang harus dilindungi dalam pemrosesan Data Pribadi."* — Ini adalah kewajiban **berbasis risiko** (risk-based), bukan standar teknis spesifik (tidak disebutkan algoritma enkripsi tertentu dsb. dalam UU itu sendiri). Karena data anak = data pribadi spesifik (Pasal 4(2)), platform ini wajib menerapkan **tingkat keamanan yang lebih tinggi** dibanding data umum, sesuai amanat huruf b.
- **Pasal 39 ayat (1)–(3)**: *"Pengendali Data Pribadi wajib mencegah Data Pribadi diakses secara tidak sah"* (ayat 1), dilakukan dengan *"menggunakan sistem keamanan terhadap Data Pribadi yang diproses dan/atau memproses Data Pribadi menggunakan sistem elektronik secara andal, aman, dan bertanggung jawab"* (ayat 2), sesuai ketentuan peraturan perundang-undangan lain (ayat 3, mis. UU ITE dan turunannya soal Penyelenggara Sistem Elektronik).
- **Pasal 34 ayat (1)–(2)**: DPIA wajib untuk pemrosesan berisiko tinggi, termasuk pemrosesan data pribadi spesifik (data anak) dan pemrosesan skala besar — relevan karena database performa tes seluruh peserta OSN kemungkinan besar tergolong "skala besar" dan berisi data spesifik.
- **Pasal 46 ayat (1)–(3)** (kewajiban notifikasi kegagalan pelindungan data / *data breach*): dalam hal terjadi kegagalan pelindungan data pribadi, pengendali data **wajib menyampaikan pemberitahuan tertulis paling lambat 3×24 (tiga kali dua puluh empat) jam** kepada subjek data pribadi *dan* kepada Lembaga (Lembaga PDP), memuat minimal: data pribadi yang terungkap, kapan dan bagaimana kebocoran terjadi, serta upaya penanganan/pemulihan. Dalam keadaan tertentu (dampak signifikan pada layanan publik/kepentingan umum), wajib pula pemberitahuan kepada masyarakat.
- **Pasal 53 ayat (1)–(3)**: kewajiban **menunjuk Pejabat/Petugas Pelindungan Data Pribadi (PPDP/DPO)** berlaku untuk tiga skenario, salah satunya *"pemrosesan Data Pribadi untuk kepentingan pelayanan publik"* dan **pemrosesan skala besar atas data pribadi spesifik/terkait kejahatan**. Sebuah platform yang menyimpan data performa tes seluruh peserta OSN (data anak = data spesifik, dalam skala besar) berpotensi wajib menunjuk PPDP, walau bukan lembaga pemerintah.
- **Pasal 57**: pelanggaran atas kewajiban keamanan (termasuk Pasal 35, 39, 46) dikenai sanksi administratif berupa peringatan tertulis, penghentian sementara pemrosesan, penghapusan/pemusnahan data, dan/atau **denda administratif hingga maksimum 2% dari pendapatan tahunan** (Pasal 57 ayat 3), tergantung berat pelanggaran.

Dari **PP No. 33/2026** (sumber sekunder, belum terverifikasi penuh):
- Beberapa ringkasan menyebut kewajiban dokumentasi *"record of processing"* dengan 13 komponen wajib termasuk pemetaan alur data, kebijakan penanganan insiden (disebut Pasal 116–117 oleh satu sumber), dan kewajiban DPIA lebih rinci (Pasal 120–122 menurut dua sumber independen — cukup konsisten), serta kriteria penunjukan PPDP (Pasal 142–147 menurut dua sumber independen — juga cukup konsisten).
- **PENTING — perlu kehati-hatian**: satu sumber sekunder (bitlionai.com, sebuah blog kepatuhan swasta, bukan sumber pemerintah) mengklaim standar minimum enkripsi adalah **AES-256**. **Klaim ini TIDAK ditemukan di teks resmi UU PDP maupun ringkasan PP 33/2026 yang berhasil diverifikasi** — ini adalah **opini/rekomendasi praktik terbaik dari pihak swasta**, bukan mandat hukum yang mengikat. Sumber-sumber yang lebih dapat dipercaya justru secara eksplisit menyatakan bahwa **standar teknis keamanan rinci (algoritma enkripsi, kontrol akses, dsb.) didelegasikan ke "Peraturan Lembaga"** — yaitu peraturan yang akan diterbitkan oleh Lembaga Pelindungan Data Pribadi, **yang sampai catatan riset ini dibuat (September 2026) belum terbentuk**. Artinya: **belum ada standar teknis keamanan yang mengikat secara hukum di Indonesia untuk cara spesifik menyimpan/mengenkripsi data pribadi** — tim rekayasa sebaiknya mengikuti praktik industri baik (enkripsi at-rest & in-transit, least-privilege access, audit log) sebagai *praktik yang berhati-hati (prudent)*, bukan karena ada pasal spesifik yang mewajibkan algoritma tertentu.

---

## 4. Ketentuan Khusus untuk Data Anak / Data Pendidikan

- **Pasal 4 ayat (2) UU PDP** secara eksplisit memasukkan **"data anak"** ke dalam kategori "Data Pribadi yang bersifat spesifik" (setara data kesehatan, biometrik, genetika, catatan kejahatan, keuangan pribadi) — ini konsekuensinya berantai ke banyak kewajiban lain (consent eksplisit wajib per Pasal 20(2)(a) jo. Pasal 25(2), DPIA wajib per Pasal 34(2), potensi kewajiban PPDP per Pasal 53).
- **Pasal 25 ayat (1)–(2)**: pemrosesan data anak "diselenggarakan secara khusus" dan wajib persetujuan orang tua/wali (dibahas rinci di Bagian 1 di atas).
- **Pasal 26**: ketentuan paralel untuk data penyandang disabilitas — menunjukkan pola umum UU PDP: kelompok rentan (anak, disabilitas) mendapat lapisan perlindungan tambahan berupa consent oleh wali/pendamping.
- **Tidak ditemukan** ketentuan khusus "data pendidikan" (*education records*) sebagai kategori tersendiri di UU PDP — berbeda dari kerangka seperti FERPA (AS) yang punya kategori "education records" dan pengecualian "school official" tersendiri. Di Indonesia, data performa tes siswa yang disimpan platform ini **tunduk pada rezim umum data pribadi (dan rezim data anak sebagai data spesifik)**, tanpa pengecualian institusional khusus untuk konteks sekolah.
- Sumber sekunder menyebut PP 33/2026 mensyaratkan *"persetujuan orang tua/wali yang terverifikasi"* untuk data anak (kemungkinan Pasal 38, belum terkonfirmasi silang) — jika benar, ini menaikkan standar dari sekadar "consent tercatat" menjadi consent dengan **mekanisme verifikasi identitas/hubungan keluarga**.
- **Lembaga PDP belum terbentuk** (per September 2026) berarti belum ada **panduan resmi (regulatory guidance)** khusus dari otoritas pengawas Indonesia soal data anak di sektor pendidikan/edtech — berbeda dengan, misalnya, ICO (Inggris) yang sudah punya "Age Appropriate Design Code". Tim proyek sebaiknya memantau terbitnya "Peraturan Lembaga" pasca-lembaga terbentuk (diperkirakan sejumlah sumber baru efektif sekitar 2028) karena kemungkinan besar akan ada aturan turunan lebih spesifik soal data anak di layanan digital.

---

## Ringkasan Sumber

**Sumber primer (dikutip langsung / dekat-primer):**
- UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi — teks pasal dikutip via https://pasal.id/peraturan/uu/uu-no-27-tahun-2022/ (pasal 3, 4, 7, 16, 20, 21, 25, 26, 34, 35, 39, 46, 53, 57), disilangkan dengan ringkasan berita Kompas (https://nasional.kompas.com/read/2022/09/20/13013871/uu-pdp-pemrosesan-data-anak-dan-penyandang-disabilitas-diatur-khusus) dan Hukumonline.
- Metadata resmi UU No. 27/2022 dari JDIH Kemkomdigi: https://jdih.komdigi.go.id/produk_hukum/view/id/832/t/undangundang+nomor+27+tahun+2022
- UU No. 23/2002 jo. UU No. 35/2014 tentang Perlindungan Anak (definisi "anak").

**Sumber sekunder (ditandai eksplisit di teks, digunakan karena teks resmi PP 33/2026 tidak dapat diekstraksi tooling ini):**
- https://veritask.ai/id/artikel/pengaturan-teknis-pelindungan-data-pribadi-dan-kewajiban-pengendali-serta-prosesor-akhirnya-terbit-lewat-pp-33-2026
- https://www.kres.id/pp-33-2026-aturan-pelaksana-uu-pdp
- https://edulawproject.id/insight/pp-no-33-tahun-2026-dan-penguatan-rezim-pelindungan-data-pribadi-di-indonesia-dari-persetujuan-formal-menuju-tata-kelola-data-yang-akuntabel
- https://paralegal.id/peraturan/peraturan-pemerintah-nomor-33-tahun-2026/
- https://meridianhukum.com/peraturan/pp-no-33-tahun-2026
- https://bitlionai.com/framework/uu-perlindungan-data-pribadi/ (klaim AES-256 — perlakukan sebagai opini praktik terbaik, bukan mandat hukum)
- https://www.cnbcindonesia.com/tech/20260916115609-37-768328/lembaga-perlindungan-data-belum-ada-di-ri-padahal-aturannya-sudah-ada (status Lembaga PDP belum terbentuk)

**Rekomendasi tindak lanjut:** sebelum finalisasi desain kepatuhan, sebaiknya seorang konsultan hukum atau tim yang punya akses ke teks resmi PP 33/2026 (misalnya lewat langganan Hukumonline Pro atau jdih.setneg.go.id) memverifikasi ulang nomor pasal persis terkait consent anak terverifikasi dan detail teknis keamanan.

---

## Implikasi untuk desain teknis

Checklist praktis untuk desain skema retensi dan penyimpanan data siswa di layanan data & analytics ini (PostgreSQL self-hosted). Ini bukan nasihat hukum lengkap — hanya terjemahan temuan di atas menjadi keputusan desain konkret.

**Consent & identitas subjek data**
- [ ] Jangan mengandalkan MoU/izin sekolah sebagai satu-satunya dasar hukum pemrosesan data siswa. Rancang alur onboarding yang mengumpulkan **consent eksplisit dan tercatat dari orang tua/wali** per siswa (bukan consent kolektif via sekolah), dengan timestamp, versi kebijakan privasi yang disetujui, dan (idealnya) mekanisme verifikasi identitas wali — bukan sekadar checkbox anonim.
- [ ] Simpan record consent sebagai entitas terpisah dan queryable (`consent_records` — subject_id, guardian_id, granted_at, policy_version, method, revoked_at nullable), bukan sekadar boolean flag di tabel siswa, karena Pasal 21(2) mewajibkan sistem bisa menunjukkan riwayat informasi/consent dan perubahannya.
- [ ] Sediakan mekanisme pencabutan consent (revoke) yang **memicu proses hapus/anonimisasi data**, bukan hanya menonaktifkan akun.
- [ ] Tandai kolom/tabel yang berisi data anak (hampir semua data siswa) sebagai kategori "data pribadi spesifik" secara internal (mis. lewat data classification tag), karena ini memicu kewajiban tambahan (DPIA, keamanan lebih tinggi) yang berbeda dari data non-sensitif seperti metadata soal ujian.

**Retensi**
- [ ] Karena UU tidak memberi angka retensi baku, **tetapkan kebijakan retensi eksplisit per jenis data** (mis. "data performa tes disimpan 3 tahun setelah siswa terakhir aktif, lalu diagregasi/dianonimkan"), dokumentasikan tujuannya, dan **cantumkan jangka waktu itu di kebijakan privasi yang disodorkan ke orang tua/wali** (kewajiban disclosure Pasal 21(1)(d)).
- [ ] Implementasikan penghapusan/pemusnahan **otomatis** (job terjadwal, bukan proses manual) begitu retensi berakhir, consent dicabut, atau akun dihapus — sesuai Pasal 16(2)(g). Desain skema dengan kolom `retention_expires_at` / `scheduled_deletion_at` per record atau per subject, plus job cleanup yang idempotent dan ter-audit.
- [ ] Pertimbangkan **anonimisasi/agregasi** sebagai alternatif hapus total untuk data analitik jangka panjang (misalnya statistik performa OSN antar-tahun) — data yang sudah dianonimkan penuh (tidak bisa dikaitkan kembali ke individu) keluar dari cakupan "data pribadi" dan lebih aman disimpan lebih lama untuk riset/tren.
- [ ] Sediakan endpoint/prosedur internal untuk memenuhi permintaan penghapusan oleh subjek data (orang tua/wali) sesuai Pasal 16(2)(g) — idealnya soft-delete dengan grace period lalu hard-delete permanen, dan hapus juga dari backup sesuai jadwal retensi backup.

**Keamanan (khusus untuk PostgreSQL self-hosted)**
- [ ] Karena data anak = data spesifik (Pasal 4(2)), terapkan tingkat keamanan yang **lebih tinggi dari baseline** (Pasal 35(b)): enkripsi at-rest untuk seluruh volume database, TLS wajib untuk koneksi (in-transit), dan pertimbangkan enkripsi kolom-level untuk field paling sensitif (skor tes yang terkait langsung dengan identitas, PII seperti NIK/nomor identitas sekolah jika disimpan).
- [ ] Terapkan **kontrol akses berbasis peran (RBAC)** di level aplikasi maupun `GRANT`/row-level security PostgreSQL, dengan prinsip least-privilege — batasi siapa (staf internal, guru, sekolah mitra) yang bisa melihat data performa siswa individual vs. agregat.
- [ ] Aktifkan **audit logging** (siapa mengakses/mengubah data siswa kapan) — mendukung kewajiban Pasal 39 (pemrosesan "andal, aman, dan bertanggung jawab") dan mempermudah investigasi bila terjadi insiden.
- [ ] Siapkan **runbook insiden kebocoran data** yang bisa dieksekusi dalam **kurang dari 3×24 jam** (Pasal 46(1)): siapa yang harus diberi tahu (subjek data/orang tau-wali, dan nantinya Lembaga PDP begitu terbentuk), template notifikasi (apa yang bocor, kapan, bagaimana, langkah pemulihan), dan proses eskalasi ke publik bila dampaknya signifikan.
- [ ] Evaluasi apakah skala pemrosesan (jumlah siswa, jangkauan sekolah mitra) membuat platform ini wajib menunjuk **Pejabat/Petugas Pelindungan Data Pribadi (PPDP)** per Pasal 53 — jika platform akan dipakai lintas banyak sekolah/skala nasional, sebaiknya siapkan peran ini sejak awal (internal atau eksternal/konsultan), bukan ditambahkan belakangan.
- [ ] Jalankan **DPIA (Penilaian Dampak Pelindungan Data Pribadi)** sebelum go-live fitur analitik baru yang memproses data performa siswa secara agregat/otomatis (mis. profiling kemampuan siswa, rekomendasi materi otomatis) — Pasal 34(2) mewajibkan ini untuk pemrosesan skala besar/data spesifik/pengambilan keputusan otomatis, yang kemungkinan mencakup fitur inti platform ini.
- [ ] Jangan menganggap AES-256 atau standar teknis spesifik lain sebagai "kewajiban hukum yang pasti" — belum ada aturan Lembaga yang mengikat. Tetap gunakan sebagai praktik baik, tapi jangan salah kutip di dokumen kepatuhan internal sebagai "diwajibkan UU PDP".

**Tata kelola & dokumentasi**
- [ ] Buat **Record of Processing Activities (RoPA)** internal per tabel/dataset yang berisi data siswa: asal data, dasar hukum pemrosesan, tujuan, siapa yang punya akses, jangka waktu simpan, mekanisme hapus, pihak ketiga yang menerima data (jika ada) — ini sejalan dengan arah PP 33/2026 (per sumber sekunder) dan akan memudahkan audit begitu Lembaga PDP aktif.
- [ ] Pantau terbitnya **Peraturan Lembaga** pasca-pembentukan Lembaga PDP (diperkirakan bertahap mulai ~2027-2028) — kemungkinan besar akan memuat standar teknis keamanan yang lebih rinci dan mungkin ketentuan spesifik untuk sektor pendidikan/edtech yang belum ada saat ini.
