"""Orkestrasi Aturan Skor & Hasil Simulasi — lihat resolusi tiket 01 di
.scratch/osn-data-analytics/issues/01-aturan-skor-hasil-simulasi.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from data_analytics.models import AturanPredikat, HasilTes, HasilTesSubkompetensi, JenisTes
from data_analytics.scoring import hitung_skor, tentukan_predikat

DEFAULT_ATURAN_PREDIKAT: Final[tuple[tuple[str, float], ...]] = (
    ("Sangat Baik", 90),
    ("Baik", 80),
    ("Cukup", 70),
    ("Perlu Latihan", 0),
)


def _validasi_aturan(aturan: Sequence[tuple[str, float]]) -> None:
    if not aturan:
        raise ValueError("aturan tidak boleh kosong")
    for label, batas_bawah in aturan:
        if not (0 <= batas_bawah <= 100):
            raise ValueError(
                f"batas_bawah untuk '{label}' harus di antara 0 dan 100, dapat {batas_bawah}"
            )
    if not any(batas_bawah == 0 for _, batas_bawah in aturan):
        raise ValueError("aturan harus menyertakan predikat dengan batas_bawah=0")


def get_or_create_aturan_predikat(
    session: Session, tingkat_seleksi_id: int
) -> list[AturanPredikat]:
    """Aturan predikat milik satu Tingkat Seleksi. Kalau belum pernah dikonfigurasi
    Super Admin (lewat set_aturan_predikat), di-seed otomatis dengan
    DEFAULT_ATURAN_PREDIKAT supaya penilaian tidak gagal/terblokir karena config
    belum diisi.
    """
    existing = session.scalars(
        select(AturanPredikat).where(
            AturanPredikat.tingkat_seleksi_id == tingkat_seleksi_id
        )
    ).all()
    if existing:
        return list(existing)

    seeded = [
        AturanPredikat(
            tingkat_seleksi_id=tingkat_seleksi_id, label=label, batas_bawah=batas_bawah
        )
        for label, batas_bawah in DEFAULT_ATURAN_PREDIKAT
    ]
    session.add_all(seeded)
    session.flush()
    return seeded


def set_aturan_predikat(
    session: Session, tingkat_seleksi_id: int, aturan: Sequence[tuple[str, float]]
) -> list[AturanPredikat]:
    """Super Admin mengganti seluruh Aturan Predikat suatu Tingkat Seleksi
    (menggantikan default hasil seed maupun aturan kustom sebelumnya). Hasil tes
    yang sudah tersimpan tidak terpengaruh — predikat_label mereka sudah
    dibekukan saat dihitung (lihat catat_hasil_tes).
    """
    _validasi_aturan(aturan)

    session.execute(
        delete(AturanPredikat).where(
            AturanPredikat.tingkat_seleksi_id == tingkat_seleksi_id
        )
    )
    baru = [
        AturanPredikat(
            tingkat_seleksi_id=tingkat_seleksi_id, label=label, batas_bawah=batas_bawah
        )
        for label, batas_bawah in aturan
    ]
    session.add_all(baru)
    session.flush()
    return baru


@dataclass(frozen=True, slots=True)
class BreakdownSubkompetensi:
    subkompetensi_id: int
    jumlah_soal: int
    jumlah_benar: int


def catat_hasil_tes(
    session: Session,
    *,
    siswa_id: int,
    tingkat_seleksi_id: int,
    jenis_tes: JenisTes,
    total_soal: int,
    jumlah_benar: int,
    breakdown_subkompetensi: Sequence[BreakdownSubkompetensi],
    diselesaikan_pada: datetime,
    simulasi_id: int | None = None,
) -> HasilTes:
    """Hitung skor & predikat satu attempt (Pre-Test atau Simulasi), lalu simpan
    sebagai HasilTes + breakdown HasilTesSubkompetensi-nya. predikat_label
    dibekukan pada baris HasilTes saat fungsi ini dipanggil — perubahan
    AturanPredikat setelahnya tidak memengaruhi hasil yang sudah tersimpan.
    """
    if jenis_tes is JenisTes.SIMULASI and simulasi_id is None:
        raise ValueError("simulasi_id wajib diisi untuk jenis_tes='simulasi'")
    if jenis_tes is JenisTes.PRE_TEST and simulasi_id is not None:
        raise ValueError("simulasi_id harus kosong untuk jenis_tes='pre_test'")

    jumlah_soal_breakdown = sum(b.jumlah_soal for b in breakdown_subkompetensi)
    if jumlah_soal_breakdown != total_soal:
        raise ValueError(
            "total jumlah_soal pada breakdown_subkompetensi "
            f"({jumlah_soal_breakdown}) harus sama dengan total_soal ({total_soal})"
        )

    skor = hitung_skor(jumlah_benar=jumlah_benar, total_soal=total_soal)

    aturan = get_or_create_aturan_predikat(session, tingkat_seleksi_id)
    predikat_label = tentukan_predikat(skor, [(a.label, a.batas_bawah) for a in aturan])

    hasil = HasilTes(
        siswa_id=siswa_id,
        tingkat_seleksi_id=tingkat_seleksi_id,
        jenis_tes=jenis_tes,
        simulasi_id=simulasi_id,
        total_soal=total_soal,
        jumlah_benar=jumlah_benar,
        jumlah_salah=total_soal - jumlah_benar,
        skor=skor,
        predikat_label=predikat_label,
        diselesaikan_pada=diselesaikan_pada,
        breakdown_subkompetensi=[
            HasilTesSubkompetensi(
                subkompetensi_id=b.subkompetensi_id,
                jumlah_soal=b.jumlah_soal,
                jumlah_benar=b.jumlah_benar,
            )
            for b in breakdown_subkompetensi
        ],
    )

    session.add(hasil)
    session.flush()
    return hasil
