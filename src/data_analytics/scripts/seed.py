"""Data uji/seed (tiket 09) — supaya Peta Kompetensi & Rekomendasi Materi bisa
dikembangkan dan diuji sebelum data pilot nyata tersedia.

Jalankan: python -m data_analytics.scripts.seed

Idempotent: kalau tingkat_seleksi sudah pernah ter-seed, seed() berhenti tanpa
menduplikasi data.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.db import SessionLocal
from data_analytics.models import (
    AturanPemetaan,
    JenisTes,
    Kompetensi,
    Soal,
    Subkompetensi,
    TingkatSeleksi,
)
from data_analytics.repository import (
    BreakdownSubkompetensi,
    catat_hasil_tes,
    get_or_create_aturan_predikat,
)

NAMA_TINGKAT_SELEKSI: tuple[str, ...] = ("Kabupaten", "Provinsi", "Nasional")
AMBANG_CUKUP_PERSEN_DEFAULT = 70
AMBANG_REPRESENTASI_PERSEN_DEFAULT = 20

# nama Kompetensi -> daftar nama Subkompetensi di bawahnya.
KOMPETENSI_SEED: dict[str, list[str]] = {
    "Dasar Pemrograman": ["Percabangan", "Perulangan"],
    "Struktur Data": ["Graph", "Linked List"],
}

# 15 soal seimbang antar 4 subkompetensi (4/4/4/3), semua ditandai Tingkat
# Seleksi pertama (Kabupaten) — cukup untuk menguji alur skor & pemetaan tanpa
# perlu menggandakan bank soal di tiap tingkat.
JUMLAH_SOAL_PER_SUBKOMPETENSI: dict[str, int] = {
    "Percabangan": 4,
    "Perulangan": 4,
    "Graph": 4,
    "Linked List": 3,
}

DUMMY_SEKOLAH_ID = 1
DUMMY_SISWA_ID: tuple[int, ...] = (1, 2)


def _sudah_diseed(session: Session) -> bool:
    return session.scalars(select(TingkatSeleksi.id).limit(1)).first() is not None


def _seed_tingkat_seleksi(session: Session) -> list[TingkatSeleksi]:
    tingkat_list = [
        TingkatSeleksi(nama=nama, urutan=urutan)
        for urutan, nama in enumerate(NAMA_TINGKAT_SELEKSI, start=1)
    ]
    session.add_all(tingkat_list)
    session.flush()
    return tingkat_list


def _seed_aturan_predikat_dan_pemetaan(
    session: Session, tingkat_list: list[TingkatSeleksi]
) -> None:
    for tingkat in tingkat_list:
        get_or_create_aturan_predikat(session, tingkat.id)
        session.add(
            AturanPemetaan(
                tingkat_seleksi_id=tingkat.id,
                ambang_cukup_persen=AMBANG_CUKUP_PERSEN_DEFAULT,
                ambang_representasi_persen=AMBANG_REPRESENTASI_PERSEN_DEFAULT,
            )
        )
    session.flush()


def _seed_silabus(session: Session) -> dict[str, Subkompetensi]:
    subkompetensi_by_nama: dict[str, Subkompetensi] = {}
    for nama_kompetensi, nama_sub_list in KOMPETENSI_SEED.items():
        kompetensi = Kompetensi(nama=nama_kompetensi, deskripsi=None)
        session.add(kompetensi)
        session.flush()
        for nama_sub in nama_sub_list:
            sub = Subkompetensi(kompetensi_id=kompetensi.id, nama=nama_sub, deskripsi=None)
            session.add(sub)
            subkompetensi_by_nama[nama_sub] = sub
    session.flush()
    return subkompetensi_by_nama


def _seed_soal(
    session: Session,
    tingkat_kabupaten: TingkatSeleksi,
    subkompetensi_by_nama: dict[str, Subkompetensi],
) -> dict[str, list[Soal]]:
    soal_by_subkompetensi: dict[str, list[Soal]] = {}
    nomor = 1
    for nama_sub, jumlah in JUMLAH_SOAL_PER_SUBKOMPETENSI.items():
        sub = subkompetensi_by_nama[nama_sub]
        soal_list: list[Soal] = []
        for _ in range(jumlah):
            soal = Soal(
                subkompetensi_id=sub.id,
                tingkat_seleksi_id=tingkat_kabupaten.id,
                nomor=nomor,
                pertanyaan=f"Soal uji #{nomor} ({nama_sub})",
                pilihan_jawaban={
                    "A": "Pilihan A",
                    "B": "Pilihan B",
                    "C": "Pilihan C",
                    "D": "Pilihan D",
                },
                kunci_jawaban="A",
            )
            session.add(soal)
            soal_list.append(soal)
            nomor += 1
        soal_by_subkompetensi[nama_sub] = soal_list
    session.flush()
    return soal_by_subkompetensi


def _seed_dummy_hasil_tes(
    session: Session,
    tingkat_kabupaten: TingkatSeleksi,
    soal_by_subkompetensi: dict[str, list[Soal]],
) -> None:
    """2 dummy siswa dari 1 dummy sekolah, masing-masing mengerjakan seluruh
    bank soal Kabupaten, supaya agregasi analitik (mis. per sekolah) punya
    data untuk diverifikasi.
    """
    breakdown = [
        BreakdownSubkompetensi(
            subkompetensi_id=soal_list[0].subkompetensi_id,
            jumlah_soal=len(soal_list),
            jumlah_benar=max(len(soal_list) - 1, 0),
        )
        for soal_list in soal_by_subkompetensi.values()
    ]
    total_soal = sum(b.jumlah_soal for b in breakdown)
    jumlah_benar = sum(b.jumlah_benar for b in breakdown)

    for siswa_id in DUMMY_SISWA_ID:
        catat_hasil_tes(
            session,
            siswa_id=siswa_id,
            sekolah_id=DUMMY_SEKOLAH_ID,
            tingkat_seleksi_id=tingkat_kabupaten.id,
            jenis_tes=JenisTes.PRE_TEST,
            total_soal=total_soal,
            jumlah_benar=jumlah_benar,
            breakdown_subkompetensi=breakdown,
            diselesaikan_pada=datetime.now(timezone.utc),
        )


def seed(session: Session) -> None:
    """Isi database dengan dataset uji tiket 09. Tidak melakukan apa pun kalau
    sudah pernah di-seed sebelumnya (deteksi lewat baris TingkatSeleksi).
    """
    if _sudah_diseed(session):
        print("Data uji sudah pernah di-seed, tidak melakukan apa pun.")
        return

    tingkat_list = _seed_tingkat_seleksi(session)
    _seed_aturan_predikat_dan_pemetaan(session, tingkat_list)
    subkompetensi_by_nama = _seed_silabus(session)
    soal_by_subkompetensi = _seed_soal(session, tingkat_list[0], subkompetensi_by_nama)
    _seed_dummy_hasil_tes(session, tingkat_list[0], soal_by_subkompetensi)

    session.commit()
    print("Seed data uji selesai.")


def main() -> None:
    session = SessionLocal()
    try:
        seed(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
