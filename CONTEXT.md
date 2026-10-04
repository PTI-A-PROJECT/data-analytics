# Data & Analytics — OSN Informatika Test-Prep Platform

Domain model for the data & analytics scope of a web app that prepares students for
Indonesia's OSN (Olimpiade Sains Nasional) informatics olympiad selection. This context
owns test-result processing, competency mapping, material recommendation, progress
tracking, scoring, tier-advancement evaluation, and admin analytics — exposed as
synchronous APIs the fullstack backend calls. Question authoring, content management,
and the student-facing UI belong to other teams/contexts.

## Language

**Kompetensi**:
A top-level competency area (e.g. "Struktur Data") used to organize the syllabus. Groups
one or more Subkompetensi.
_Avoid_: Topic, category, subject

**Subkompetensi**:
The finest-grained competency unit (e.g. "Graph", "Linked List") that a Soal is tagged
with, and the unit the mapping algorithm evaluates directly. Belongs to exactly one
Kompetensi.
_Avoid_: Sub-topic, skill

**Aturan Pemetaan** _(fase 1 — dipensiunkan di fase 2; lihat "Status Pemetaan (fase 2)")_:
The Super-Admin-configured parameters the mapping algorithm applies: a correctness
threshold (minimum % correct within a Subkompetensi to be classified Cukup) and a
minimum representation threshold (minimum % of a test's questions that must belong to
a Subkompetensi for its result to be considered valid).
_Avoid_: Mapping rule, threshold config

**Status Pemetaan**:
The three-value classification a Subkompetensi (or Kompetensi) receives from the
mapping algorithm: **Cukup** (correctness threshold met), **Belum Cukup** (threshold
not met), or **Belum Teruji** (representation threshold not met — too few questions
answered for this Subkompetensi to classify it validly).
_Avoid_: Mapping result, competency level

**Peta Kompetensi**:
The mapping algorithm's output for one student's one test attempt: a Status Pemetaan
per Kompetensi, each carrying its own correctness stats plus the full breakdown of
Status Pemetaan (and stats) for every child Subkompetensi — never collapsed away, since
Subkompetensi-level detail is what tells a student/pembina exactly which specific area
needs work. A Kompetensi's status is Cukup when the proportion of its *valid* (non-Belum
Teruji) Subkompetensi that are Cukup meets the Kompetensi-level threshold; a Kompetensi
is itself Belum Teruji only if every one of its Subkompetensi is Belum Teruji.
_Avoid_: Competency map, mapping result

**Rekomendasi Materi** _(fase 1; di fase 2 digantikan Materi Wajib)_:
An ordered list of Materi for one student, produced from their latest Peta Kompetensi.
Built from Subkompetensi in Status Pemetaan Belum Cukup (ranked weakest-first by
correctness %) followed by Belum Teruji (lower priority — recommended so the student
generates enough attempts to be validly mapped next time). Subkompetensi at Cukup are
excluded. Requires Materi to be taggable at Subkompetensi granularity, not just
Kompetensi as FR-19 currently states — see ADR on Materi tagging granularity.
_Avoid_: Study recommendation, suggested materials

**Progress Belajar** _(fase 1; definisi fase 2 di bawah)_:
A per-Subkompetensi snapshot of how far a student has consumed the Materi currently
in their Rekomendasi Materi — never a mastery signal. Mastery is Status Pemetaan's job
(earned only by retesting); Progress Belajar can rise and fall as recommendations
change, and that's fine because it isn't credit. Computed on read from Progress
Halaman Materi rows for whatever Materi the current recommendation includes.
_Avoid_: Learning progress, completion rate

**Halaman Materi** _(fase 1; fase 2: navigasi bebas, lihat Materi Wajib)_:
A Materi is divided into sequential pages a student must reach in order (no skipping
ahead), though they may move freely back and forth among pages already reached. What's
tracked per student per Materi is a single high-water mark: the furthest Halaman
Materi reached. A Materi is complete when that mark reaches its last page.
_Avoid_: Material section, chapter

**Kecepatan Pengerjaan**:
Per-question response time — the interval between a Soal being opened and being
answered/submitted. Requires the fullstack team to capture per-question open/answer
timestamps during Pre-Test (FR-06) and Simulasi (FR-11), which the brief does not
currently specify (it only has a per-Soal answer, and an overall test duration at the
Simulasi-config level). This is a coordination dependency, not yet a settled data
contract.
_Avoid_: Response time, speed

## Fase 2 — bank konten & simulasi adaptif

Lihat `docs/adr/0004` dan `.scratch/osn-fase-2/`. Sejak fase 2, **Materi** menggantikan
Subkompetensi sebagai unit evaluasi; istilah Subkompetensi di atas berlaku untuk
alur fase 1 yang belum ditulis ulang.

**Materi**:
Unit belajar sekaligus unit evaluasi fase 2 di satu Tingkat Seleksi, terdiri dari
beberapa Halaman Materi. Baku dan sama untuk semua siswa — Materi tidak punya tingkat
kesulitan.
_Avoid_: Topik, bab, level materi

**Level Soal**:
Tingkat kesulitan satu Soal: Mudah, Sedang, atau Sulit. Berasal dari data sumber
(soal sudah dikelompokkan per Materi dan per tingkat kesulitan), tidak dikalibrasi ulang
dari data jawaban.
_Avoid_: Level materi, bobot soal

**Level Soal Siswa**:
Level Soal yang disajikan kepada satu siswa untuk satu Materi pada simulasi berikutnya.
Mulai dari Mudah, naik satu tingkat saat akurasi siswa di Materi itu memenuhi ambang,
tidak pernah turun.
_Avoid_: Level siswa, kemampuan siswa

**Paket Tes**:
Susunan Soal yang disusun layanan ini untuk satu attempt Pre-Test atau Simulasi satu
siswa, disimpan supaya bisa diaudit.
_Avoid_: Sesi, lembar soal

**Materi Wajib**:
Materi berstatus lemah pada attempt terakhir siswa, yang harus dibuka ulang semua
halamannya (urutan bebas) sebelum simulasi berikutnya.
_Avoid_: Remedial, rekomendasi wajib

**Progress Belajar (fase 2)**:
Untuk attempt terakhir siswa di satu tingkat: jumlah Materi Wajib selesai dibanding
total Materi Wajib, plus per Materi halaman yang dibuka sejak diwajibkan dibanding
total halaman. Sinyal konsumsi, bukan mastery — mastery dibuktikan lewat Level Soal
Siswa di simulasi.
_Avoid_: Progres materi, completion rate

**Halaman Materi (fase 2)**:
Halaman boleh dibuka dalam urutan apa pun dan bolak-balik. Materi Wajib selesai saat
setiap halamannya sudah dibuka minimal sekali sejak diwajibkan; melompat ke halaman
terakhir tidak menyelesaikannya. Riwayat baca umum mencatat halaman unik yang pernah
dibuka.

**Gerbang Simulasi**:
Syarat pembuatan Paket Tes simulasi baru: semua Materi Wajib dari attempt terakhir
sudah selesai dipelajari.
_Avoid_: Kunci simulasi

**Status Pemetaan (fase 2)**:
Untuk attempt lewat Paket Tes, Status Pemetaan dihitung per Materi dengan satu ambang
(`ambang_lemah`): **Cukup** kalau akurasi ≥ ambang, **Belum Cukup** (= lemah) kalau di
bawahnya, **Belum Teruji** kalau Materi itu tidak punya soal di attempt tersebut.
Ambang representasi fase 1 tidak dipakai.
