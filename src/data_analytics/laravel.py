"""Adapter kontrak Laravel untuk endpoint /hitung/penilaian & /hitung/pretest.

Backend Osn-Readiness-Web (PerhitunganClient) mengirim bobot eksplisit per soal
— bukan level — dan memakai nama field/tipe-nya sendiri
(`jawaban_user`/`kunci_jawaban`, `tipe_soal` = 'pilihan_ganda' | 'isian').
Modul ini memetakan bentuk itu ke fungsi murni scoring yang sudah ada agar satu
sumber kebenaran rumus tetap terjaga.
"""

from __future__ import annotations

from collections.abc import Sequence

from data_analytics.models import TipeSoal
from data_analytics.schemas import (
    LaravelMateriItem,
    LaravelPretestSoalItem,
    LaravelSoalItem,
)
from data_analytics.scoring import cocokkan_jawaban, hitung_skor

# Nilai enum tipe_soal yang dikirim Laravel (App\Enums\TipeSoal) ke TipeSoal
# lokal. 'isian' Laravel = 'isian_singkat' di sini.
TIPE_SOAL_LARAVEL: dict[str, TipeSoal] = {
    "pilihan_ganda": TipeSoal.PILIHAN_GANDA,
    "isian": TipeSoal.ISIAN_SINGKAT,
}


def tipe_dari_laravel(tipe_soal: str) -> TipeSoal:
    """Petakan tipe_soal Laravel ke TipeSoal lokal; tak dikenal → ValueError."""
    try:
        return TIPE_SOAL_LARAVEL[tipe_soal]
    except KeyError:
        raise ValueError(f"tipe_soal tidak dikenal: {tipe_soal}") from None


def _benar(soal: LaravelSoalItem) -> bool:
    return cocokkan_jawaban(
        soal.kunci_jawaban, soal.jawaban_user, tipe_dari_laravel(soal.tipe_soal)
    )


def nilai_paket(
    soal: Sequence[LaravelSoalItem],
) -> tuple[float, list[dict[str, object]]]:
    """Nilai berbobot + status benar per soal, urutan sama seperti permintaan.

    Mengembalikan (nilai, jawaban) dengan jawaban =
    [{'soal_id': int, 'status_benar': bool}].
    """
    if not soal:
        raise ValueError("daftar soal tidak boleh kosong")
    ids = [s.soal_id for s in soal]
    if len(set(ids)) != len(ids):
        raise ValueError("soal_id harus unik")

    jawaban = [{"soal_id": s.soal_id, "status_benar": _benar(s)} for s in soal]
    bobot_benar = sum(s.bobot for s, j in zip(soal, jawaban) if j["status_benar"])
    bobot_total = sum(s.bobot for s in soal)

    return hitung_skor(bobot_benar=bobot_benar, bobot_total=bobot_total), jawaban


def peta_pretest(
    soal: Sequence[LaravelPretestSoalItem],
    materi: Sequence[LaravelMateriItem],
    jumlah_materi_wajib: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Baris pemetaan untuk SETIAP materi yang dikirim (bukan hanya yang punya
    soal — Laravel mewajibkan tiap materi punya baris), plus daftar materi
    wajib = N materi pertama sesuai urutan permintaan.

    Mengembalikan (pemetaan, materi_wajib). persentase berbobot
    (poin_didapat/poin_maksimal × 100, aturan final v1), 0.0 bila materi tak
    punya soal.
    """
    if jumlah_materi_wajib > len(materi):
        raise ValueError(
            f"jumlah_materi_wajib ({jumlah_materi_wajib}) melebihi "
            f"jumlah materi ({len(materi)})"
        )

    benar = {s.soal_id: _benar(s) for s in soal}
    per_materi: dict[int, list[LaravelPretestSoalItem]] = {}
    for s in soal:
        per_materi.setdefault(s.materi_id, []).append(s)

    pemetaan: list[dict[str, object]] = []
    for peringkat, m in enumerate(materi, start=1):
        milik = per_materi.get(m.materi_id, [])
        poin_maksimal = sum(s.bobot for s in milik)
        poin_didapat = sum(s.bobot for s in milik if benar[s.soal_id])
        pemetaan.append(
            {
                "materi_id": m.materi_id,
                "jumlah_soal": len(milik),
                "jumlah_benar": sum(1 for s in milik if benar[s.soal_id]),
                "poin_didapat": poin_didapat,
                "poin_maksimal": poin_maksimal,
                "persentase": round(poin_didapat / poin_maksimal * 100, 2)
                if poin_maksimal
                else 0.0,
                "peringkat": peringkat,
            }
        )

    materi_wajib = [
        {"materi_id": m.materi_id, "prioritas": prioritas}
        for prioritas, m in enumerate(materi[:jumlah_materi_wajib], start=1)
    ]

    return pemetaan, materi_wajib
