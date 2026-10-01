"""Test algoritma Pemetaan Kompetensi murni per Materi (fase 2)."""

from data_analytics.models import StatusPemetaan
from data_analytics.pemetaan import (
    materi_lemah,
    petakan_per_materi,
)


class TestPetakanPerMateri:
    """Peta Kompetensi fase 2 — unit Materi, satu definisi lemah: akurasi <
    ambang_lemah (issue fase 2 #03)."""

    def test_status_per_materi_mengikuti_ambang_lemah_inklusif(self) -> None:
        peta = petakan_per_materi(
            {"a": (4, 2), "b": (4, 1), "c": (0, 0)}, ambang_lemah=50
        )

        assert [(p.materi_id, p.status, p.akurasi) for p in peta] == [
            ("a", StatusPemetaan.CUKUP, 50.0),
            ("b", StatusPemetaan.BELUM_CUKUP, 25.0),
            ("c", StatusPemetaan.BELUM_TERUJI, None),
        ]

    def test_materi_lemah_diurutkan_dari_akurasi_terendah(self) -> None:
        peta = petakan_per_materi(
            {"x": (4, 1), "y": (5, 0), "z": (4, 4), "w": (4, 1)}, ambang_lemah=50
        )

        assert materi_lemah(peta) == ["y", "w", "x"]
