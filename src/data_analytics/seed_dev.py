"""Seed data dev untuk testing SIAP OSN."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from data_analytics.config import get_settings
from data_analytics.models import (
    TingkatSeleksi,
    Materi,
    Soal,
    HalamanMateri,
    LevelSoal,
    TipeSoal,
)


def main():
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session:
        # Cek kalau sudah ada
        existing = session.scalar(select(TingkatSeleksi).limit(1))
        if existing:
            print("Data sudah ada, skip.")
            return

        print("Seed tingkat seleksi...")
        kab = TingkatSeleksi(nama="Kabupaten", urutan=1)
        prov = TingkatSeleksi(nama="Provinsi", urutan=2)
        session.add_all([kab, prov])
        session.flush()
        print(f"  Kabupaten id={kab.id}, Provinsi id={prov.id}")

        print("Seed materi...")
        materi_list = []
        for i, judul in enumerate(
            ["Algoritma-Pemrograman", "Berpikir-Komputasional", "Logika-Himpunan"], start=1
        ):
            m = Materi(
                id=f"mat-kab-{i}",
                tingkat_seleksi_id=kab.id,
                judul=judul,
                topik=i,
                embedding=[0.0] * 384,
                hash_konten=f"hash-kab-{i}",
            )
            materi_list.append(m)
            session.add(m)

            for h in range(1, 4):
                session.add(
                    HalamanMateri(
                        materi_id=m.id,
                        nomor=h,
                        judul=f"Halaman {h}",
                        konten=f"# Konten {judul} halaman {h}\n\nIni contoh materi.",
                    )
                )

        for i, judul in enumerate(
            ["Rekursi", "Struktur-Data", "Graf-Tree", "DP"], start=1
        ):
            m = Materi(
                id=f"mat-prov-{i}",
                tingkat_seleksi_id=prov.id,
                judul=judul,
                topik=i,
                embedding=[0.0] * 384,
                hash_konten=f"hash-prov-{i}",
            )
            materi_list.append(m)
            session.add(m)

            for h in range(1, 4):
                session.add(
                    HalamanMateri(
                        materi_id=m.id,
                        nomor=h,
                        judul=f"Halaman {h}",
                        konten=f"# Konten {judul} halaman {h}",
                    )
                )

        session.flush()
        print(f"  Total {len(materi_list)} materi dibuat")

        print("Seed soal...")
        total_soal = 0
        for materi in materi_list:
            for level in [LevelSoal.MUDAH, LevelSoal.SEDANG, LevelSoal.SULIT]:
                for n in range(5):
                    s = Soal(
                        id=f"{materi.id}-{level.value}-{n}",
                        materi_id=materi.id,
                        tingkat_seleksi_id=materi.tingkat_seleksi_id,
                        tipe=TipeSoal.PILIHAN_GANDA,
                        pertanyaan=f"Soal {level.value} #{n} untuk {materi.judul}?",
                        pilihan_jawaban={
                            "A": "Jawaban A",
                            "B": "Jawaban B",
                            "C": "Jawaban C",
                            "D": "Jawaban D",
                        },
                        kunci_jawaban="A",
                        pembahasan="Pembahasan: jawabannya A.",
                        level=level,
                        embedding=[0.0] * 384,
                        hash_konten=f"hash-{materi.id}-{level.value}-{n}",
                        aktif=True,
                    )
                    session.add(s)
                    total_soal += 1
        print(f"  Total {total_soal} soal dibuat")

        session.commit()
        print("\n✅ Seed selesai!")


if __name__ == "__main__":
    main()