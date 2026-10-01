"""Leaderboard per Tingkat Seleksi — fungsi murni, pola sama dengan
scoring.py/adaptif.py. Query ada di repository.leaderboard_tingkat.

Skor gabungan = 50% skor + 50% skor kecepatan. Skor kecepatan relatif terhadap
seluruh attempt simulasi di tingkat itu: 100 x (detik per soal tercepat /
detik per soal attempt ini), jadi yang tercepat 100 dan peringkat ikut berubah
setiap ada submit baru. Detik per soal dipakai (bukan total durasi) supaya
paket dengan jumlah soal berbeda tetap sebanding.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

BOBOT_SKOR = 0.5
BOBOT_KECEPATAN = 0.5
JUMLAH_TERATAS = 5
# Batas bawah detik per soal: timestamp yang sama persis tidak membuat
# pembagian dengan nol.
DETIK_PER_SOAL_MIN = 1.0


def durasi_pengerjaan(waktu: Iterable[tuple[datetime | None, datetime | None]]) -> float | None:
    """Detik dari soal pertama dibuka sampai soal terakhir dijawab, dari
    pasangan (dibuka_pada, dijawab_pada) per soal. Soal tanpa kedua timestamp
    diabaikan; None kalau tidak ada satu pun yang lengkap."""
    lengkap = [(dibuka, dijawab) for dibuka, dijawab in waktu if dibuka and dijawab]
    if not lengkap:
        return None
    mulai = min(dibuka for dibuka, _ in lengkap)
    selesai = max(dijawab for _, dijawab in lengkap)
    return max((selesai - mulai).total_seconds(), 0.0)


@dataclass(frozen=True, slots=True)
class AttemptSimulasi:
    siswa_id: str
    skor: float
    durasi_detik: float
    total_soal: int


@dataclass(frozen=True, slots=True)
class Peringkat:
    peringkat: int
    siswa_id: str
    skor: float
    durasi_detik: float
    skor_kecepatan: float
    skor_gabungan: float


def _detik_per_soal(attempt: AttemptSimulasi) -> float:
    return max(attempt.durasi_detik / max(attempt.total_soal, 1), DETIK_PER_SOAL_MIN)


def susun_leaderboard(
    attempts: Sequence[AttemptSimulasi], *, jumlah: int = JUMLAH_TERATAS
) -> list[Peringkat]:
    """`jumlah` siswa teratas; tiap siswa diwakili attempt dengan skor gabungan
    tertinggi. Seri → skor lebih tinggi, lalu lebih cepat, lalu siswa_id."""
    if not attempts:
        return []
    tercepat = min(_detik_per_soal(a) for a in attempts)

    terbaik: dict[str, tuple[float, float, AttemptSimulasi]] = {}
    for a in attempts:
        kecepatan = round(tercepat / _detik_per_soal(a) * 100, 2)
        gabungan = round(BOBOT_SKOR * a.skor + BOBOT_KECEPATAN * kecepatan, 2)
        sekarang = terbaik.get(a.siswa_id)
        if sekarang is None or (gabungan, a.skor) > (sekarang[0], sekarang[2].skor):
            terbaik[a.siswa_id] = (gabungan, kecepatan, a)

    urut = sorted(
        terbaik.values(),
        key=lambda t: (-t[0], -t[2].skor, _detik_per_soal(t[2]), t[2].siswa_id),
    )
    return [
        Peringkat(
            peringkat=i,
            siswa_id=a.siswa_id,
            skor=a.skor,
            durasi_detik=a.durasi_detik,
            skor_kecepatan=kecepatan,
            skor_gabungan=gabungan,
        )
        for i, (gabungan, kecepatan, a) in enumerate(urut[:jumlah], start=1)
    ]
