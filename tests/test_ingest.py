"""Inti ingest bank konten (fase 2 issue 01) — lewat objek masukan internal,
dengan embedder palsu yang deterministik. Materi & Level Soal berasal dari data
sumber (sudah dilabeli). Parser JSON sumber belum ada (menunggu file data); ia
cukup menerjemahkan file ke MateriMasukan/SoalMasukan.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import pytest
from sqlalchemy.orm import Session

from data_analytics.ingest import (
    LaporanIngest,
    MateriMasukan,
    SoalMasukan,
    UsulanMateri,
    ingest_bank_konten,
)
from data_analytics.models import DIMENSI_EMBEDDING, LevelSoal, Materi, Soal, TingkatSeleksi


class EmbedderPalsu:
    """Memetakan teks ke sumbu vektor berdasarkan kata kunci pertama yang
    ditemukan — cukup untuk mengatur "materi terdekat" secara pasti."""

    def __init__(self, sumbu: dict[str, int]) -> None:
        self.sumbu = sumbu
        self.teks_di_embed: list[str] = []

    def embed(self, teks: Sequence[str]) -> list[list[float]]:
        self.teks_di_embed.extend(teks)
        return [self._vektor(t) for t in teks]

    def _vektor(self, teks: str) -> list[float]:
        v = [0.0] * DIMENSI_EMBEDDING
        for kata, indeks in self.sumbu.items():
            if kata in teks.lower():
                v[indeks] = 1.0
                return v
        v[DIMENSI_EMBEDDING - 1] = 1.0
        return v


MATERI_GRAPH = MateriMasukan(
    id="m-graph", judul="Graph", halaman=["Graph adalah simpul dan sisi", "BFS pada graph"]
)
MATERI_SORTING = MateriMasukan(
    id="m-sorting", judul="Sorting", halaman=["Sorting mengurutkan data"]
)


def soal_masukan(
    id: str,
    materi_id: str | None,
    pertanyaan: str = "Soal graph",
    level: LevelSoal = LevelSoal.MUDAH,
) -> SoalMasukan:
    return SoalMasukan(
        id=id,
        materi_id=materi_id,
        level=level,
        pertanyaan=pertanyaan,
        pilihan_jawaban={"A": "1", "B": "2"},
        kunci_jawaban="A",
        pembahasan="Karena 1.",
    )


def ingest(
    session: Session,
    tingkat: TingkatSeleksi,
    embedder: EmbedderPalsu,
    materi: Sequence[MateriMasukan],
    soal: Sequence[SoalMasukan],
    *,
    recompute: bool = False,
    stok_minimum: int = 2,
) -> LaporanIngest:
    return ingest_bank_konten(
        session,
        tingkat_seleksi_id=tingkat.id,
        materi=materi,
        soal=soal,
        embedder=embedder,
        recompute=recompute,
        stok_minimum=stok_minimum,
    )


@pytest.fixture
def kabupaten(session: Session) -> TingkatSeleksi:
    tingkat = TingkatSeleksi(nama="Kabupaten", urutan=1)
    session.add(tingkat)
    session.flush()
    return tingkat


@pytest.fixture
def embedder() -> EmbedderPalsu:
    return EmbedderPalsu({"graph": 0, "sorting": 1})


class TestIngestBankKonten:
    def test_menyimpan_materi_halaman_dan_soal_dengan_level_dari_data(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        laporan = ingest(
            session, kabupaten, embedder, [MATERI_GRAPH],
            [soal_masukan("s-1", "m-graph", level=LevelSoal.SULIT)],
        )
        session.expire_all()

        materi = session.get(Materi, "m-graph")
        soal = session.get(Soal, "s-1")
        assert materi is not None and soal is not None
        assert [h.konten for h in materi.halaman] == [
            "Graph adalah simpul dan sisi",
            "BFS pada graph",
        ]
        assert soal.materi_id == "m-graph"
        assert soal.tingkat_seleksi_id == kabupaten.id
        assert soal.level is LevelSoal.SULIT
        assert soal.embedding[0] == pytest.approx(1.0)
        assert laporan.soal_disimpan == 1

    def test_yang_di_embed_hanya_teks_pertanyaan(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        ingest(session, kabupaten, embedder, [MATERI_GRAPH], [soal_masukan("s-1", "m-graph")])

        assert "Soal graph" in embedder.teks_di_embed
        assert not any("A. 1" in teks for teks in embedder.teks_di_embed)

    def test_ingest_ulang_tanpa_perubahan_tidak_menghitung_ulang(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        ingest(session, kabupaten, embedder, [MATERI_GRAPH], [soal_masukan("s-1", "m-graph")])
        embedder_kedua = EmbedderPalsu({"graph": 0})

        ingest(session, kabupaten, embedder_kedua, [MATERI_GRAPH], [soal_masukan("s-1", "m-graph")])
        session.expire_all()

        assert embedder_kedua.teks_di_embed == []
        materi = session.get(Materi, "m-graph")
        assert materi is not None and materi.total_halaman == 2

    def test_perubahan_level_atau_pilihan_saja_tidak_embed_ulang(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        ingest(session, kabupaten, embedder, [MATERI_GRAPH], [soal_masukan("s-1", "m-graph")])
        embedder_kedua = EmbedderPalsu({"graph": 0})
        direvisi = replace(
            soal_masukan("s-1", "m-graph", level=LevelSoal.SEDANG),
            pilihan_jawaban={"A": "10", "B": "20"},
        )

        ingest(session, kabupaten, embedder_kedua, [MATERI_GRAPH], [direvisi])
        session.expire_all()

        assert embedder_kedua.teks_di_embed == []
        soal = session.get(Soal, "s-1")
        assert soal is not None
        assert soal.level is LevelSoal.SEDANG
        assert soal.pilihan_jawaban == {"A": "10", "B": "20"}

    def test_teks_berubah_dihitung_ulang_hanya_untuk_yang_berubah(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        ingest(
            session, kabupaten, embedder, [MATERI_GRAPH],
            [soal_masukan("s-1", "m-graph"), soal_masukan("s-2", "m-graph")],
        )
        embedder_kedua = EmbedderPalsu({"graph": 0})
        materi_direvisi = MateriMasukan(id="m-graph", judul="Graph", halaman=["Hanya satu halaman graph"])

        ingest(
            session, kabupaten, embedder_kedua, [materi_direvisi],
            [
                soal_masukan("s-1", "m-graph"),
                soal_masukan("s-2", "m-graph", pertanyaan="Soal graph yang direvisi"),
            ],
        )
        session.expire_all()

        assert "Soal graph yang direvisi" in embedder_kedua.teks_di_embed
        assert "Soal graph" not in embedder_kedua.teks_di_embed
        soal_2 = session.get(Soal, "s-2")
        materi = session.get(Materi, "m-graph")
        assert soal_2 is not None and materi is not None
        assert soal_2.pertanyaan == "Soal graph yang direvisi"
        assert [h.konten for h in materi.halaman] == ["Hanya satu halaman graph"]

    def test_recompute_menghitung_ulang_semua(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        ingest(session, kabupaten, embedder, [MATERI_GRAPH], [soal_masukan("s-1", "m-graph")])
        embedder_kedua = EmbedderPalsu({"graph": 0})

        ingest(
            session, kabupaten, embedder_kedua, [MATERI_GRAPH], [soal_masukan("s-1", "m-graph")],
            recompute=True,
        )

        assert len(embedder_kedua.teks_di_embed) == 2  # 1 materi + 1 soal

    def test_soal_tanpa_materi_tidak_disimpan_dan_diusulkan_materi_terdekat(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        laporan = ingest(
            session, kabupaten, embedder, [MATERI_GRAPH, MATERI_SORTING],
            [
                soal_masukan("s-tanpa-tag", None, pertanyaan="Urutkan dengan sorting"),
                soal_masukan("s-tag-asing", "m-tidak-ada", pertanyaan="Soal graph"),
            ],
        )

        assert session.get(Soal, "s-tanpa-tag") is None
        assert session.get(Soal, "s-tag-asing") is None
        assert laporan.soal_tanpa_materi == [
            UsulanMateri(soal_id="s-tanpa-tag", materi_id_tag=None, materi_id_terdekat="m-sorting"),
            UsulanMateri(
                soal_id="s-tag-asing", materi_id_tag="m-tidak-ada", materi_id_terdekat="m-graph"
            ),
        ]
        assert laporan.soal_disimpan == 0

    def test_materi_pindah_tingkat_ikut_dipindah_walau_teks_sama(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        provinsi = TingkatSeleksi(nama="Provinsi", urutan=2)
        session.add(provinsi)
        session.flush()
        ingest(session, kabupaten, embedder, [MATERI_GRAPH], [])

        laporan = ingest(session, provinsi, embedder, [MATERI_GRAPH], [soal_masukan("s-1", "m-graph")])

        materi = session.get(Materi, "m-graph")
        assert materi is not None and materi.tingkat_seleksi_id == provinsi.id
        assert laporan.soal_disimpan == 1

    def test_soal_tersimpan_yang_tagnya_menjadi_tidak_valid_tidak_diubah_dan_dilaporkan(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        ingest(session, kabupaten, embedder, [MATERI_GRAPH], [soal_masukan("s-1", "m-graph")])

        laporan = ingest(
            session, kabupaten, embedder, [MATERI_GRAPH],
            [soal_masukan("s-1", None, pertanyaan="Soal graph baru")],
        )

        soal = session.get(Soal, "s-1")
        assert soal is not None and soal.pertanyaan == "Soal graph"  # versi lama utuh
        assert laporan.soal_tidak_diperbarui == ["s-1"]

    def test_id_soal_duplikat_dalam_satu_masukan_ditolak(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        with pytest.raises(ValueError, match="s-kembar"):
            ingest(
                session, kabupaten, embedder, [MATERI_GRAPH],
                [soal_masukan("s-kembar", "m-graph"), soal_masukan("s-kembar", "m-graph")],
            )

    def test_melaporkan_stok_per_materi_level_dan_stok_tipis(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        laporan = ingest(
            session, kabupaten, embedder, [MATERI_GRAPH, MATERI_SORTING],
            [
                soal_masukan("g-1", "m-graph"),
                soal_masukan("g-2", "m-graph"),
                soal_masukan("g-3", "m-graph", level=LevelSoal.SULIT),
            ],
            stok_minimum=2,
        )

        assert laporan.stok == {
            ("m-graph", LevelSoal.MUDAH): 2,
            ("m-graph", LevelSoal.SEDANG): 0,
            ("m-graph", LevelSoal.SULIT): 1,
            ("m-sorting", LevelSoal.MUDAH): 0,
            ("m-sorting", LevelSoal.SEDANG): 0,
            ("m-sorting", LevelSoal.SULIT): 0,
        }
        assert laporan.stok_tipis == [
            ("m-graph", LevelSoal.SEDANG),
            ("m-graph", LevelSoal.SULIT),
            ("m-sorting", LevelSoal.MUDAH),
            ("m-sorting", LevelSoal.SEDANG),
            ("m-sorting", LevelSoal.SULIT),
        ]

    def test_soal_yang_hilang_dari_masukan_dinonaktifkan_bukan_dihapus(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        ingest(session, kabupaten, embedder, [MATERI_GRAPH],
               [soal_masukan("s-1", "m-graph"), soal_masukan("s-2", "m-graph")])

        laporan = ingest(session, kabupaten, embedder, [MATERI_GRAPH], [soal_masukan("s-1", "m-graph")])
        session.expire_all()

        s1, s2 = session.get(Soal, "s-1"), session.get(Soal, "s-2")
        assert s1 is not None and s2 is not None
        assert (s1.aktif, s2.aktif) == (True, False)
        assert laporan.soal_dinonaktifkan == ["s-2"]
        assert laporan.stok[("m-graph", LevelSoal.MUDAH)] == 1

    def test_soal_nonaktif_aktif_lagi_saat_kembali_ke_masukan(
        self, session: Session, kabupaten: TingkatSeleksi, embedder: EmbedderPalsu
    ) -> None:
        ingest(session, kabupaten, embedder, [MATERI_GRAPH], [soal_masukan("s-1", "m-graph")])
        ingest(session, kabupaten, embedder, [MATERI_GRAPH], [])

        ingest(session, kabupaten, embedder, [MATERI_GRAPH], [soal_masukan("s-1", "m-graph")])
        session.expire_all()

        soal = session.get(Soal, "s-1")
        assert soal is not None and soal.aktif is True
