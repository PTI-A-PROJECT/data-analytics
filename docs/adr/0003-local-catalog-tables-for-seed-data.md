---
Status: accepted
---

# This service owns a local Kompetensi/Subkompetensi/Soal/TingkatSeleksi/AturanPemetaan schema, seeded for dev/test bootstrap

Tiket 09 (scaffold proyek) needs seed data — soal pilihan ganda tagged with
Kompetensi/Subkompetensi, sample Aturan Pemetaan — so Peta Kompetensi and
Rekomendasi Materi logic can be developed and tested before real pilot data
exists. That requires somewhere to put this data.

ADR 0002 already established that this service doesn't mirror Materi — it's
"a computation engine over caller-supplied facts, not a mirror of the content
catalog", and the same reasoning was extended by convention (not a separate
ADR) to `siswa_id`, `sekolah_id`, `simulasi_id`: all stored as plain ints on
`HasilTes`/`ProgressMateri`/etc. without a SQLAlchemy `ForeignKey()`, because
those entities are owned and CRUD'd by the fullstack team (map.md "Out of
scope" explicitly excludes Soal/Kompetensi/Tingkat Seleksi management from
this service too).

We're deviating from that pattern for **Kompetensi, Subkompetensi, Soal,
TingkatSeleksi, and AturanPemetaan only**: these are now real tables, owned
and migrated by this service (Alembic revision `0001`), not caller-supplied
per-request facts. Reasoning: unlike a `hasil_tes` row (created per real
submission, always accompanied by fresh caller-supplied ids), there is no
request that would ever hand this service a full soal bank or competency
syllabus — something has to hold that data locally for the mapping/scoring
logic to run against at all, whether that's real pilot content or synthetic
seed content. We chose to model it as owned tables rather than, say,
in-memory fixtures constructed ad hoc per test, so the same schema can be
seeded once (`python -m data_analytics.scripts.seed`) and reused across
local development, tests, and — until a real content-sync mechanism exists
from the fullstack side — pilot bootstrap.

**What this does not change:** `HasilTes`, `HasilTesSubkompetensi`,
`AturanPredikat`, and `ProgressMateri` still store `tingkat_seleksi_id`,
`subkompetensi_id`, `siswa_id`, `sekolah_id`, `simulasi_id`, and `materi_id`
as plain ints with no `ForeignKey()` to these new tables. A submitted test
result is still trusted as-is, exactly per the resolution of tiket 01/08 —
this service doesn't validate that a `subkompetensi_id` on an incoming
`HasilTes` actually exists in its local `subkompetensi` table. Materi
remains entirely un-mirrored (ADR 0002 stands unchanged).

**Known gap, deliberately left open:** there is currently no mechanism to
keep this local catalog in sync with the fullstack team's authoritative
content once real pilot Soal/Kompetensi data exists — the seed script is a
bootstrap/dev-test convenience, not a sync pipeline. A future reader who
needs production-authoritative catalog data flowing into this service should
treat that as unsolved, not assume the seed data is ever replaced
automatically.
