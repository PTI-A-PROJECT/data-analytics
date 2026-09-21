---
Status: accepted
---

# Materi is tagged at Subkompetensi granularity, not just Kompetensi

The brief's FR-19 (Manajemen Materi) says Materi links to "tingkat dan kompetensi" —
Kompetensi granularity only. But Rekomendasi Materi needs to rank weakest-first using
Peta Kompetensi, which is computed at Subkompetensi granularity. Tagging Materi at
Kompetensi only would force recommending an entire Kompetensi's materials whenever any
one Subkompetensi under it is weak, drowning out the specific gap (e.g. recommending
all of "Struktur Data" when only "Graph" is weak). We're deviating from the brief:
Materi must carry a Subkompetensi tag. This needs coordination with the fullstack team,
since it adds a field to the Materi schema/admin CRUD (FR-19) beyond what's currently
specced.
