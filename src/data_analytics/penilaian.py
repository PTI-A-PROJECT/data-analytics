"""Penilaian stateless untuk endpoint /hitung/* — fungsi murni, tanpa database.

Laravel mengirim kunci, jawaban, level, dan materi tiap soal; modul ini
mengembalikan skor berbobot (Mudah=1, Sedang=2, Sulit=3), predikat (opsional),
dan Peta Kompetensi per Materi. Semua rumus dipakai ulang dari scoring.py dan
pemetaan.py agar satu sumber kebenaran.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from data_analytics.config import PASSING_GRADE
from data_analytics.models import LevelSoal, StatusPemetaan, TipeSoal
from data_analytics.pemetaan import status_dari_akurasi
from data_analytics.scoring import (
    bobot_dari_level,
    cocokkan_jawaban,
    hitung_skor,
    tentukan_predikat,
)


@dataclass(frozen=True, slots=True)
class SoalDijawab:
    soal_id: str
    level: LevelSoal
    tipe: TipeSoal
    kunci: str
    jawaban: str | None
    materi_id: str | None = None


@dataclass(frozen=True, slots=True)
class HasilSoal:
    soal_id: str
    benar: bool
    bobot: int


@dataclass(frozen=True, slots=True)
class HasilPenilaian:
    skor: float
    bobot_benar: int
    bobot_total: int
    jumlah_soal: int
    jumlah_benar: int
    jumlah_salah: int
    predikat: str | None
    hasil_soal: list[HasilSoal]


def nilai_jawaban(
    soal: Sequence[SoalDijawab],
    *,
    aturan_predikat: Sequence[tuple[str, float]] | None = None,
) -> HasilPenilaian:
    """Skor = Σ bobot soal benar / Σ bobot semua soal × 100. Soal tanpa
    jawaban dihitung salah. Predikat hanya dihitung kalau aturan dikirim."""
    if not soal:
        raise ValueError("daftar soal tidak boleh kosong")
    ids = [s.soal_id for s in soal]
    if len(set(ids)) != len(ids):
        raise ValueError("soal_id harus unik")

    hasil_soal = []
    for s in soal:
        benar = cocokkan_jawaban(s.kunci, s.jawaban, s.tipe)
        hasil_soal.append(HasilSoal(s.soal_id, benar, bobot_dari_level(s.level)))

    bobot_benar = sum(h.bobot for h in hasil_soal if h.benar)
    bobot_total = sum(h.bobot for h in hasil_soal)
    jumlah_benar = sum(1 for h in hasil_soal if h.benar)
    skor = hitung_skor(bobot_benar=bobot_benar, bobot_total=bobot_total)
    predikat = tentukan_predikat(skor, aturan_predikat) if aturan_predikat else None

    return HasilPenilaian(
        skor=skor,
        bobot_benar=bobot_benar,
        bobot_total=bobot_total,
        jumlah_soal=len(soal),
        jumlah_benar=jumlah_benar,
        jumlah_salah=len(soal) - jumlah_benar,
        predikat=predikat,
        hasil_soal=hasil_soal,
    )


@dataclass(frozen=True, slots=True)
class PetaBerbobot:
    """Akurasi Materi X = Σ bobot benar di X / Σ bobot X × 100 (aturan final v1)."""

    materi_id: str
    jumlah_soal: int
    jumlah_benar: int
    bobot_total: int
    bobot_benar: int
    akurasi: float
    status: StatusPemetaan


def hitung_pemetaan(
    soal: Sequence[SoalDijawab],
    *,
    ambang_lemah: float,
    ambang_kuat: float,
) -> tuple[list[PetaBerbobot], list[str]]:
    """Peta Kompetensi per Materi dengan akurasi BERBOBOT, dan daftar Materi
    lemah (akurasi terendah dulu, seri: materi_id)."""
    if ambang_lemah > ambang_kuat:
        raise ValueError("ambang_lemah tidak boleh melebihi ambang_kuat")
    if any(s.materi_id is None for s in soal):
        raise ValueError("materi_id wajib diisi untuk setiap soal")

    agregat: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for s in soal:
        a = agregat[s.materi_id]  # type: ignore[index]
        bobot = bobot_dari_level(s.level)
        a[0] += 1
        a[2] += bobot
        if cocokkan_jawaban(s.kunci, s.jawaban, s.tipe):
            a[1] += 1
            a[3] += bobot

    peta = []
    for materi_id in sorted(agregat):
        n, benar, b_total, b_benar = agregat[materi_id]
        akurasi = round(b_benar / b_total * 100, 2)
        peta.append(
            PetaBerbobot(
                materi_id, n, benar, b_total, b_benar, akurasi,
                status_dari_akurasi(
                    akurasi, ambang_lemah=ambang_lemah, ambang_kuat=ambang_kuat
                ),
            )
        )
    lemah = [
        p.materi_id
        for p in sorted(peta, key=lambda p: (p.akurasi, p.materi_id))
        if p.status is StatusPemetaan.BELUM_CUKUP
    ]
    return peta, lemah


@dataclass(frozen=True, slots=True)
class HasilSimulasi:
    penilaian: HasilPenilaian
    pemetaan: list[PetaBerbobot]
    materi_lemah: list[str]
    passing_grade: float
    lulus: bool


def nilai_simulasi(
    soal: Sequence[SoalDijawab],
    *,
    tingkat: str,
    ambang_lemah: float,
    ambang_kuat: float,
    aturan_predikat: Sequence[tuple[str, float]] | None = None,
) -> HasilSimulasi:
    """LULUS jika nilai >= passing grade tingkat (Kabupaten 70, Provinsi 80,
    inklusif). Syarat Materi inti >= 50% adalah gate dari nilai LATIHAN dan
    dicek di Laravel (DB), bukan di sini. pemetaan & materi_lemah dipakai
    untuk remap/reset selektif setelah gagal."""
    if tingkat not in PASSING_GRADE:
        raise ValueError(f"tingkat tidak dikenal: {tingkat}")
    penilaian = nilai_jawaban(soal, aturan_predikat=aturan_predikat)
    peta, lemah = hitung_pemetaan(
        soal, ambang_lemah=ambang_lemah, ambang_kuat=ambang_kuat
    )
    passing = PASSING_GRADE[tingkat]
    return HasilSimulasi(penilaian, peta, lemah, passing, penilaian.skor >= passing)


THRESHOLD_LATIHAN = 50.0


@dataclass(frozen=True, slots=True)
class AkurasiMateri:
    materi_id: str
    akurasi: float
    lulus: bool


@dataclass(frozen=True, slots=True)
class HasilLatihan:
    skor: float
    lulus: bool
    akurasi_per_materi: list[AkurasiMateri]


def nilai_latihan(
    soal: Sequence[SoalDijawab], *, threshold: float = THRESHOLD_LATIHAN
) -> HasilLatihan:
    """Latihan lulus jika skor >= threshold (inklusif; skor dibulatkan 2 desimal
    seperti di seluruh layanan). akurasi_per_materi berbobot, lulus per materi
    dengan threshold yang sama — dipakai Laravel untuk gate simulasi."""
    if not 0 <= threshold <= 100:
        raise ValueError("threshold harus di antara 0 dan 100")
    penilaian = nilai_jawaban(soal)
    peta, _ = hitung_pemetaan(soal, ambang_lemah=threshold, ambang_kuat=100.0)
    return HasilLatihan(
        skor=penilaian.skor,
        lulus=penilaian.skor >= threshold,
        akurasi_per_materi=[
            AkurasiMateri(p.materi_id, p.akurasi, p.akurasi >= threshold) for p in peta
        ],
    )
