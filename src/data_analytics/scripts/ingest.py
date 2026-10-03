"""CLI ingest bank soal OSN ke PostgreSQL + pgvector (fase 2 issue 01).

    uv sync --group ingest
    uv run python -m data_analytics.scripts.ingest [--folder soal_osn] [--folder-materi Materi] [--recompute]

Membaca soal_osn/ dan dokumen Materi/ (sumber_osn.baca_bank_soal), menghitung embedding MiniLM
secara lokal, lalu upsert Materi & Soal per Tingkat Seleksi (Kabupaten =
urutan 1, Provinsi = urutan 2). Idempoten: embedding hanya dihitung ulang
untuk soal baru/berubah, kecuali --recompute. Satu transaksi per tingkat.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from data_analytics.config import get_settings
from data_analytics.ingest import Embedder, ingest_bank_konten
from data_analytics.models import TingkatSeleksi
from data_analytics.sumber_osn import BankSumber, baca_bank_soal

SessionLocal = sessionmaker(
    bind=create_engine(get_settings().database_url), autoflush=False, autocommit=False
)

URUTAN_TINGKAT = {"kabupaten": 1, "provinsi": 2}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", default=get_settings().folder_soal)
    parser.add_argument(
        "--folder-materi", default=get_settings().folder_materi, help="dokumen Materi (.docx)"
    )
    parser.add_argument("--recompute", action="store_true", help="hitung ulang semua embedding")
    args = parser.parse_args()

    bank = baca_bank_soal(Path(args.folder), Path(args.folder_materi))
    for nama, daftar in bank.materi.items():
        tanpa_halaman = [m.id for m in daftar if not m.halaman]
        print(f"Materi {nama}: {len(daftar)}, halaman {sum(len(m.halaman) for m in daftar)}")
        if tanpa_halaman:
            print(f"  tanpa dokumen: {', '.join(tanpa_halaman)}")
    if bank.dokumen_tanpa_materi:
        print(f"Dokumen tanpa Materi di materi.json: {', '.join(bank.dokumen_tanpa_materi)}")
    alasan = Counter(bank.dilewati.values())
    print(f"Dilewati {len(bank.dilewati)} entri:")
    for teks, jumlah in alasan.most_common():
        print(f"  {jumlah:4d}  {teks}")

    # Diimpor di sini: dependency group `ingest` tidak terpasang di image API.
    from data_analytics.embedding import EmbedderMiniLM

    embedder = EmbedderMiniLM()
    with SessionLocal() as session:
        for nama, urutan in URUTAN_TINGKAT.items():
            _ingest_tingkat(session, bank, nama, urutan, embedder, args.recompute)


def _ingest_tingkat(
    session: Session,
    bank: BankSumber,
    nama: str,
    urutan: int,
    embedder: Embedder,
    recompute: bool,
) -> None:
    tingkat = session.scalars(select(TingkatSeleksi).where(TingkatSeleksi.urutan == urutan)).one()
    laporan = ingest_bank_konten(
        session,
        tingkat_seleksi_id=tingkat.id,
        materi=bank.materi.get(nama, []),
        soal=bank.soal.get(nama, []),
        embedder=embedder,
        recompute=recompute,
    )
    session.commit()
    print(f"\n{tingkat.nama}: {laporan.soal_disimpan} soal disimpan")
    if laporan.soal_dinonaktifkan:
        print(f"  {len(laporan.soal_dinonaktifkan)} soal dinonaktifkan (tidak ada lagi di bank sumber)")
    if laporan.soal_tanpa_materi:
        print(f"  {len(laporan.soal_tanpa_materi)} soal tanpa Materi yang dikenal (tidak disimpan)")
    stok = Counter[str]()
    for (materi_id, level), jumlah in laporan.stok.items():
        stok[f"{materi_id} {level.value}"] = jumlah
    print("  Stok per Materi & Level:")
    for kunci, jumlah in sorted(stok.items()):
        print(f"    {jumlah:4d}  {kunci}")
    if laporan.stok_tipis:
        print(f"  Stok tipis: {', '.join(f'{m} {lv.value}' for m, lv in laporan.stok_tipis)}")


if __name__ == "__main__":
    main()
