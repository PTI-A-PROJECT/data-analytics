---
Status: accepted
Supersedes: 0002; extends 0003
---

# This service owns the content bank (Materi, Halaman Materi, Soal) and assembles test packets

Phase 1 treated this service as "a computation engine over caller-supplied facts":
the fullstack side owned Soal and Materi, assembled every Pre-Test/Simulasi, and
sent us per-Subkompetensi answer counts to score (ADR 0002). Local Soal/Kompetensi
tables existed only as seed data for dev/test (ADR 0003).

Phase 2 changes who owns the content. Soal (~900 per tingkat) and Materi are now
prepared by this project directly, not authored through a Super Admin UI, and test
assembly has become adaptive: which Soal a student sees next depends on their
history, per-Materi Level Soal, and vector similarity to Soal they answered
wrong. That selection logic needs the Soal bank — text, level, and embedding — in
the same database as the student history, so fetching it from the fullstack side
per request is not viable.

Decision:

- This service **owns** `materi`, `halaman_materi`, and `soal` as production
  tables, populated by an offline ingest (`data_analytics.ingest`) from source
  files in the repo. The seed script and the phase-1 `kompetensi`/`subkompetensi`/
  `soal` seed tables are removed (migration `0005`).
- **Materi is the unit of evaluation**, replacing Subkompetensi. Each Soal is tagged
  to exactly one Materi. Materi has no difficulty; only Soal has a Level Soal
  (mudah/menengah/sulit), taken from the source data (questions come already grouped
  per Materi and difficulty) and never recalibrated from answer data. (An earlier plan
  to label difficulty with a local LLM was dropped: the data already carries it, and
  VPS memory is 4-8 GB shared with other apps.)
- Soal and Materi carry a 384-dim embedding (`paraphrase-multilingual-MiniLM-L12-v2`,
  int8 ONNX, no PyTorch, computed offline at ingest; chosen over multilingual-e5-small/
  -base by `scripts/benchmark_embedding.py`) in PostgreSQL via **pgvector**. The API never loads a model at
  runtime; similarity search uses stored vectors only.
- Content tables use real foreign keys and source-file string ids. `siswa_id`/
  `sekolah_id` stay caller-supplied without FKs — student identity is still owned by
  the fullstack side.
- PostgreSQL + pgvector is now required everywhere, including tests. SQLite is no
  longer supported.

Consequences: ADR 0002 no longer holds — a future reader looking for "why is there a
`materi` table when ADR 0002 says we don't mirror Materi" should read this ADR. The
phase-1 tables that still reference content by caller-supplied id (`jawaban_siswa`,
`progress_materi`, `hasil_tes_subkompetensi`) are migrated to local FKs alongside the
endpoints that use them (phase 2 issues 02–04), not in the same change.
