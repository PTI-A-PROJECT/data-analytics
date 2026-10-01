---
Status: superseded by 0004
---

# Data & analytics does not own a Materi catalog — callers supply Materi metadata per event

Tracking Progress Belajar (per-page completion of a Materi) needs each Materi's
Subkompetensi tag and total page count. The alternative was to sync/cache a Materi
catalog from the fullstack side (via a periodic pull or a sync endpoint), keeping this
service's copy consistent with the authoritative one. We rejected that: it reintroduces
the kind of sync/consistency machinery the earlier decision to drop event-streaming was
meant to avoid, for a context (Materi authoring) this service doesn't own and shouldn't
need to mirror.

Instead, whoever calls this service (the fullstack backend, reporting a page-view or
asking for Progress Belajar) passes the Materi's `subkompetensi_id` and `total_halaman`
in that same request. This service stores/uses them as given — it trusts the caller as
the source of truth for Materi metadata, the same way Hasil Tes (see tiket 01) stores
per-Subkompetensi answer counts without storing Soal identity or content. A future
reader who expects a `materi` table with foreign-key integrity here should know this
was deliberate: this service is a computation engine over caller-supplied facts, not a
mirror of the content catalog.
