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

**Aturan Pemetaan**:
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

**Rekomendasi Materi**:
An ordered list of Materi for one student, produced from their latest Peta Kompetensi.
Built from Subkompetensi in Status Pemetaan Belum Cukup (ranked weakest-first by
correctness %) followed by Belum Teruji (lower priority — recommended so the student
generates enough attempts to be validly mapped next time). Subkompetensi at Cukup are
excluded. Requires Materi to be taggable at Subkompetensi granularity, not just
Kompetensi as FR-19 currently states — see ADR on Materi tagging granularity.
_Avoid_: Study recommendation, suggested materials

**Progress Belajar**:
A per-Subkompetensi snapshot of how far a student has consumed the Materi currently
in their Rekomendasi Materi — never a mastery signal. Mastery is Status Pemetaan's job
(earned only by retesting); Progress Belajar can rise and fall as recommendations
change, and that's fine because it isn't credit. Computed on read from Progress
Halaman Materi rows for whatever Materi the current recommendation includes.
_Avoid_: Learning progress, completion rate

**Halaman Materi**:
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
