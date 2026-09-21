# Riset: Kepatuhan UU PDP untuk Data Siswa

Type: research
Status: resolved
Blocked by: none

## Question

Siswa pengguna platform ini kemungkinan besar di bawah umur. Teliti kewajiban UU
Pelindungan Data Pribadi (UU PDP) Indonesia yang relevan untuk sistem yang menyimpan
data performa/hasil tes siswa minor: syarat consent (dari siapa — siswa, orang tua,
atau institusi sekolah cukup sebagai pengendali data), batasan retensi data, kewajiban
keamanan data pribadi, dan apakah ada ketentuan khusus untuk data pendidikan anak.
Rangkum temuan sebagai implikasi konkret untuk desain retensi & penyimpanan data di
layanan data & analytics ini (bukan nasihat hukum lengkap — cukup untuk menginformasikan
keputusan desain teknis).

## Answer

Temuan lengkap (dengan kutipan pasal & sumber) ada di
[`research/uu-pdp-data-siswa.md`](./../research/uu-pdp-data-siswa.md). Ringkasan:

1. **Consent**: Consent sekolah saja **tidak cukup**. UU PDP Pasal 4(2) mengklasifikasikan
   data anak sebagai data pribadi spesifik (sensitif), dan Pasal 25(2) mewajibkan consent
   eksplisit **terpisah dari orang tua/wali** untuk pemrosesan data anak — kewajiban
   lex specialis, bukan sekadar salah satu dari 6 dasar hukum umum di Pasal 20. Tidak ada
   pengecualian model "school official" seperti FERPA di hukum Indonesia. "Anak" mengacu ke
   definisi di bawah 18 tahun (UU 35/2014), jadi hampir semua peserta OSN (siswa SMA) masuk
   kategori ini.
2. **Retensi**: UU PDP menetapkan prinsip pembatasan penyimpanan (Pasal 16(2)(g) — data
   harus dihapus setelah masa retensi berakhir) tapi **tidak menetapkan durasi retensi
   baku**. Pengendali data wajib menetapkan & mengungkapkan sendiri periode retensinya
   (Pasal 21(1)(d)), mendokumentasikannya, dan menghapus otomatis saat masa berlaku habis,
   consent dicabut, atau tujuan tercapai.
3. **Keamanan**: Pasal 35/39 mewajibkan kontrol teknis/organisasi berbasis risiko (bukan
   preskriptif), diperberat karena data siswa sensitif (Pasal 34 — wajib DPIA). Pasal 46
   mewajibkan notifikasi pelanggaran data dalam 3×24 jam. Pasal 53 berpotensi mewajibkan
   penunjukan PPDP (petugas pelindungan data pribadi) mengingat skala & sensitivitas data.
   Belum ada standar teknis mengikat (mis. algoritma enkripsi spesifik) di level UU — ini
   didelegasikan ke Peraturan Lembaga dari otoritas PDP Indonesia yang per September 2026
   belum terbentuk.
4. **Ketentuan khusus data anak**: Pasal 4(2), 25, 26 secara eksplisit memberi perlakuan
   khusus untuk data anak (dan disabilitas); tidak ada kategori "data pendidikan" terpisah
   seperti FERPA.

**Catatan sumber penting**: PP No. 33/2026 (peraturan pelaksana, berlaku efektif 15 Jan
2027) ditemukan dan dikonfirmasi keberadaannya, tapi teks lengkapnya tidak bisa diekstrak
oleh tooling yang tersedia — semua detail PP 33/2026 di file riset ditandai eksplisit
sebagai bersumber sekunder (situs analisis hukum/compliance), dengan rekomendasi
verifikasi ulang nomor pasal terhadap teks resmi (jdih.setneg.go.id / peraturan.bpk.go.id
/ Hukumonline Pro) sebelum dipakai untuk keputusan kepatuhan final. Teks UU No. 27/2022
sendiri sudah diverifikasi lewat pasal.id (dicek silang dengan ringkasan berita
Kompas/Hukumonline).

File riset ditutup dengan checklist teknik konkret ("## Implikasi untuk desain teknis"):
skema record consent (termasuk consent orang tua/wali terpisah dari siswa), kolom
retention-expiry + job penghapusan terjadwal, anonimisasi untuk analytics jangka panjang,
kontrol keamanan spesifik PostgreSQL (enkripsi at-rest/in-transit, RBAC/row-level
security, audit log), runbook notifikasi pelanggaran data, trigger DPIA/PPDP, dan
rekomendasi dokumentasi RoPA (Record of Processing Activities).
