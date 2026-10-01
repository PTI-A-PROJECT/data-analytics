"""Inti ingest bank konten (fase 2 issue 01) — menyimpan Materi, Halaman Materi,
dan Soal ke katalog lokal beserta embedding (pgvector). Materi & Level Soal
berasal dari data sumber (sudah dilabeli), bukan ditebak model. Berjalan
offline, bukan di jalur request API.

Masukan berupa objek internal (MateriMasukan/SoalMasukan), bukan JSON: parser
file sumber cukup menerjemahkan ke objek ini. Embedder diinjeksikan supaya
model lokal (embedding.EmbedderMiniLM) hanya dimuat oleh CLI ingest.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from data_analytics.models import HalamanMateri, LevelSoal, Materi, Soal, TipeSoal

# Samakan dengan kuota minimum per Materi di simulasi (issue fase 2 #03).
STOK_MINIMUM_DEFAULT = 2


@dataclass(frozen=True)
class HalamanMasukan:
    konten: str
    judul: str | None = None


@dataclass(frozen=True)
class MateriMasukan:
    id: str
    judul: str
    # str = halaman tanpa judul.
    halaman: Sequence[HalamanMasukan | str]
    # Ringkasan cakupan Materi — ikut di-embed (tidak disimpan) supaya Materi
    # tanpa halaman tetap punya embedding yang bermakna.
    cakupan: str | None = None
    topik: int | None = None

    @property
    def daftar_halaman(self) -> list[HalamanMasukan]:
        return [HalamanMasukan(konten=h) if isinstance(h, str) else h for h in self.halaman]


@dataclass(frozen=True)
class SoalMasukan:
    id: str
    # None kalau data sumber tidak menandai Materi — ingest mengusulkan Materi
    # terdekat lewat vector search, tapi tidak menyimpan soalnya.
    materi_id: str | None
    level: LevelSoal
    pertanyaan: str
    pilihan_jawaban: dict[str, str]
    kunci_jawaban: str
    pembahasan: str | None
    tipe: TipeSoal = TipeSoal.PILIHAN_GANDA
    deskripsi: str | None = None
    kode: str | None = None
    gambar: str | None = None
    tahun: int | None = None


class Embedder(Protocol):
    def embed(self, teks: Sequence[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class UsulanMateri:
    """Materi terdekat (vector search) untuk soal yang tag Materi-nya kosong,
    atau tidak dikenal — untuk ditinjau manual, tidak diterapkan otomatis."""

    soal_id: str
    materi_id_tag: str | None
    materi_id_terdekat: str | None


@dataclass
class LaporanIngest:
    soal_disimpan: int = 0
    # Soal yang TIDAK disimpan/diperbarui karena tag Materi kosong/tidak ada di
    # tingkat ini.
    soal_tanpa_materi: list[UsulanMateri] = field(default_factory=list)
    # Bagian dari soal_tanpa_materi yang sudah tersimpan dari ingest
    # sebelumnya — versi lamanya (termasuk tag lama) tetap utuh di database.
    soal_tidak_diperbarui: list[str] = field(default_factory=list)
    # Jumlah soal per (materi, level) di seluruh bank soal tingkat ini,
    # termasuk kombinasi yang kosong.
    stok: dict[tuple[str, LevelSoal], int] = field(default_factory=dict)
    # (materi, level) dengan stok < stok_minimum — mesin adaptif (issue 03)
    # akan jatuh ke fallback di sini.
    stok_tipis: list[tuple[str, LevelSoal]] = field(default_factory=list)
    # Soal tingkat ini yang tersimpan tapi tidak ada lagi di masukan.
    soal_dinonaktifkan: list[str] = field(default_factory=list)


def ingest_bank_konten(
    session: Session,
    *,
    tingkat_seleksi_id: int,
    materi: Sequence[MateriMasukan],
    soal: Sequence[SoalMasukan],
    embedder: Embedder,
    recompute: bool = False,
    stok_minimum: int = STOK_MINIMUM_DEFAULT,
) -> LaporanIngest:
    """Upsert idempoten per id. Embedding hanya dihitung untuk entri baru atau
    yang teks ter-embed-nya berubah (hash_konten), atau semuanya kalau
    recompute=True; perubahan level/pilihan/kunci saja cukup memperbarui kolom. Tidak commit;
    pemanggil yang menentukan transaksinya.

    Stok di laporan dihitung atas seluruh bank soal tingkat ini (bukan hanya
    batch masukan); (materi, level) dengan soal < stok_minimum ditandai tipis.

    ValueError kalau masukan memuat id Materi/Soal kembar.
    """
    _tolak_id_kembar("Materi", materi)
    _tolak_id_kembar("Soal", soal)
    laporan = LaporanIngest()
    _upsert_materi(session, tingkat_seleksi_id, materi, embedder, recompute)

    tersimpan = {
        baris.id: baris
        for baris in session.scalars(select(Soal).where(Soal.id.in_([x.id for x in soal])))
    }
    perlu_dihitung = _perlu_dihitung(soal, _hash_tersimpan(tersimpan), _teks_soal, recompute)
    embedding_baru = dict(
        zip(
            [x.id for x in perlu_dihitung],
            embedder.embed([_teks_soal(x) for x in perlu_dihitung]) if perlu_dihitung else [],
            strict=True,
        )
    )

    materi_tingkat = set(
        session.scalars(select(Materi.id).where(Materi.tingkat_seleksi_id == tingkat_seleksi_id))
    )

    for masukan in soal:
        baris = tersimpan.get(masukan.id)
        embedding = embedding_baru.get(masukan.id)
        if embedding is None:
            # Tidak perlu dihitung ulang ⇒ pasti sudah tersimpan.
            assert baris is not None
            embedding = baris.embedding
        usulan = UsulanMateri(
            soal_id=masukan.id,
            materi_id_tag=masukan.materi_id,
            materi_id_terdekat=_materi_terdekat(session, tingkat_seleksi_id, embedding),
        )
        if masukan.materi_id not in materi_tingkat:
            laporan.soal_tanpa_materi.append(usulan)
            if baris is not None:
                laporan.soal_tidak_diperbarui.append(masukan.id)
            continue
        if baris is None:
            baris = Soal(id=masukan.id)
            session.add(baris)
        baris.materi_id = masukan.materi_id
        baris.tingkat_seleksi_id = tingkat_seleksi_id
        baris.aktif = True
        baris.level = masukan.level
        baris.pertanyaan = masukan.pertanyaan
        baris.tipe = masukan.tipe
        baris.deskripsi = masukan.deskripsi
        baris.kode = masukan.kode
        baris.gambar = masukan.gambar
        baris.tahun = masukan.tahun
        baris.pilihan_jawaban = masukan.pilihan_jawaban
        baris.kunci_jawaban = masukan.kunci_jawaban
        baris.pembahasan = masukan.pembahasan
        if masukan.id in embedding_baru:
            baris.embedding = embedding_baru[masukan.id]
            baris.hash_konten = _hash(_teks_soal(masukan))
        laporan.soal_disimpan += 1
    session.flush()

    # Masukan = seluruh bank soal tingkat ini: yang tidak ada lagi dinonaktifkan
    # (tidak dihapus — Paket Tes lama mungkin merujuknya).
    id_masukan = {x.id for x in soal}
    for hilang in session.scalars(
        select(Soal).where(
            Soal.tingkat_seleksi_id == tingkat_seleksi_id,
            Soal.aktif.is_(True),
            Soal.id.not_in(id_masukan) if id_masukan else true(),
        )
    ):
        hilang.aktif = False
        laporan.soal_dinonaktifkan.append(hilang.id)
    laporan.soal_dinonaktifkan.sort()
    session.flush()

    laporan.stok = _hitung_stok(session, tingkat_seleksi_id)
    laporan.stok_tipis = [kunci for kunci, jumlah in laporan.stok.items() if jumlah < stok_minimum]
    return laporan


def _hitung_stok(session: Session, tingkat_seleksi_id: int) -> dict[tuple[str, LevelSoal], int]:
    jumlah = {
        (materi_id, level): n
        for materi_id, level, n in session.execute(
            select(Soal.materi_id, Soal.level, func.count())
            .where(Soal.tingkat_seleksi_id == tingkat_seleksi_id, Soal.aktif.is_(True))
            .group_by(Soal.materi_id, Soal.level)
        ).tuples()
    }
    materi_ids = session.scalars(
        select(Materi.id)
        .where(Materi.tingkat_seleksi_id == tingkat_seleksi_id)
        .order_by(Materi.id)
    )
    return {
        (materi_id, level): jumlah.get((materi_id, level), 0)
        for materi_id in materi_ids
        for level in LevelSoal
    }


def _upsert_materi(
    session: Session,
    tingkat_seleksi_id: int,
    materi: Sequence[MateriMasukan],
    embedder: Embedder,
    recompute: bool,
) -> None:
    tersimpan = {
        baris.id: baris
        for baris in session.scalars(select(Materi).where(Materi.id.in_([x.id for x in materi])))
    }
    # Pindah tingkat tidak mengubah teks (hash), jadi diterapkan terpisah dari
    # perhitungan ulang embedding.
    for masukan in materi:
        if (materi_tersimpan := tersimpan.get(masukan.id)) is not None:
            materi_tersimpan.tingkat_seleksi_id = tingkat_seleksi_id
            materi_tersimpan.topik = masukan.topik
    perlu_dihitung = _perlu_dihitung(materi, _hash_tersimpan(tersimpan), _teks_materi, recompute)
    embedding_baru = embedder.embed([_teks_materi(x) for x in perlu_dihitung]) if perlu_dihitung else []

    for masukan, embedding in zip(perlu_dihitung, embedding_baru, strict=True):
        baris = tersimpan.get(masukan.id)
        if baris is None:
            baris = Materi(id=masukan.id)
            session.add(baris)
        else:
            # Hapus halaman lama dulu — unit of work menjalankan INSERT sebelum
            # DELETE, jadi mengganti list langsung akan melanggar unik
            # (materi_id, nomor).
            baris.halaman.clear()
            session.flush()
        baris.tingkat_seleksi_id = tingkat_seleksi_id
        baris.judul = masukan.judul
        baris.topik = masukan.topik
        baris.embedding = embedding
        baris.hash_konten = _hash(_teks_materi(masukan))
        baris.halaman = [
            HalamanMateri(nomor=nomor, judul=h.judul, konten=h.konten)
            for nomor, h in enumerate(masukan.daftar_halaman, start=1)
        ]
    session.flush()


class _PunyaId(Protocol):
    @property
    def id(self) -> str: ...


_Masukan = TypeVar("_Masukan", bound=_PunyaId)


def _perlu_dihitung(
    masukan: Sequence[_Masukan],
    hash_tersimpan: Mapping[str, str],
    teks: Callable[[_Masukan], str],
    recompute: bool,
) -> list[_Masukan]:
    """Entri baru, entri yang teksnya berubah, atau semuanya kalau recompute."""
    return [
        x
        for x in masukan
        if recompute or hash_tersimpan.get(x.id) != _hash(teks(x))
    ]


def _hash_tersimpan(tersimpan: Mapping[str, Materi] | Mapping[str, Soal]) -> dict[str, str]:
    return {id_: baris.hash_konten for id_, baris in tersimpan.items()}


def _tolak_id_kembar(jenis: str, masukan: Sequence[_PunyaId]) -> None:
    kembar = sorted(id_ for id_, n in Counter(x.id for x in masukan).items() if n > 1)
    if kembar:
        raise ValueError(f"Id {jenis} kembar dalam masukan: {', '.join(kembar)}")


def _materi_terdekat(
    session: Session, tingkat_seleksi_id: int, embedding: list[float]
) -> str | None:
    return session.scalars(
        select(Materi.id)
        .where(Materi.tingkat_seleksi_id == tingkat_seleksi_id)
        .order_by(Materi.embedding.cosine_distance(embedding))
        .limit(1)
    ).first()


def _hash(teks: str) -> str:
    return hashlib.sha256(teks.encode("utf-8")).hexdigest()


def _teks_materi(materi: MateriMasukan) -> str:
    halaman = [
        f"{h.judul}\n{h.konten}" if h.judul else h.konten for h in materi.daftar_halaman
    ]
    return "\n".join([materi.judul, *([materi.cakupan] if materi.cakupan else []), *halaman])


def _teks_soal(soal: SoalMasukan) -> str:
    # Deskripsi (konteks) + pertanyaan: banyak pertanyaan hanya bermakna
    # bersama ceritanya. Pilihan jawaban (angka/opsi pendek) menambah noise ke
    # makna, jadi perubahan level/pilihan/kunci tidak memicu embedding ulang.
    return f"{soal.deskripsi}\n\n{soal.pertanyaan}" if soal.deskripsi else soal.pertanyaan
