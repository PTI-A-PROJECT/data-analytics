"""Parser bank soal sumber di folder soal_osn/ menjadi masukan ingest
(ingest.MateriMasukan/SoalMasukan).

Isi folder:
- soal_<tingkat>_pembahasan/soal_<kab|prov>_<tahun>.json — daftar soal:
  deskripsi_soal, soal, pilihan {a..e} (kosong = isian singkat), kode,
  gambar_url, gambar_lokal, jawaban_benar, pembahasan.
- gambar_<tingkat>/ — gambar soal.
- materi.json — daftar Materi per tingkat (silabus osn.toki.id); "topik"
  menunjuk dokumen Materi/<Tingkat>/Topik N_*.docx (lihat materi_docx).
- label_materi_level.json — Materi & Level per id soal, plus soal yang
  sengaja dikecualikan. Data sumber tidak membawa Materi/Level sendiri.

Id soal = <kab|prov>-<tahun>-<nomor urut di file, mulai 1>, stabil selama
urutan file sumber tidak berubah.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from data_analytics.ingest import HalamanMasukan, MateriMasukan, SoalMasukan
from data_analytics.materi_docx import DokumenMateri, baca_folder_materi
from data_analytics.models import LevelSoal, TipeSoal

TINGKAT: dict[str, str] = {"kab": "kabupaten", "prov": "provinsi"}
# "Deskripsi Untuk Soal Nomor 13 dan 17" → konteks untuk 5 soal berikutnya.
_RENTANG_KONTEKS = re.compile(r"Nomor (\d+) (?:dan|sampai|-|s\.d\.?) (\d+)")
_INFO_DESKRIPSI = "Informasi Deskripsi"
_MAKS_PANJANG_ISIAN = 30


@dataclass
class BankSumber:
    # Kunci: "kabupaten" / "provinsi".
    materi: dict[str, list[MateriMasukan]] = field(default_factory=dict)
    soal: dict[str, list[SoalMasukan]] = field(default_factory=dict)
    # id soal → alasan tidak di-ingest.
    dilewati: dict[str, str] = field(default_factory=dict)
    # Dokumen Materi yang (tingkat, topik)-nya tidak ada di materi.json.
    dokumen_tanpa_materi: list[str] = field(default_factory=list)


def baca_bank_soal(folder: Path, folder_materi: Path | None = None) -> BankSumber:
    """folder_materi: folder dokumen Materi (materi_docx) — halaman tiap Materi
    diambil dari dokumen bertingkat & bernomor topik sama. Materi tanpa
    dokumen (atau tanpa folder_materi) disimpan tanpa halaman."""
    bank = BankSumber()
    dokumen: dict[tuple[str, int], DokumenMateri] = (
        baca_folder_materi(folder_materi) if folder_materi is not None else {}
    )
    for m in json.loads((folder / "materi.json").read_text(encoding="utf-8")):
        topik = m.get("topik")
        dok = dokumen.pop((m["tingkat"], topik), None)
        bank.materi.setdefault(m["tingkat"], []).append(
            MateriMasukan(
                id=m["id"],
                judul=m["judul"],
                halaman=[HalamanMasukan(konten=h.konten, judul=h.judul) for h in dok.halaman]
                if dok is not None
                else [],
                cakupan=m.get("cakupan"),
                topik=topik,
            )
        )
    bank.dokumen_tanpa_materi = sorted(str(d.path) for d in dokumen.values())
    label_file = json.loads((folder / "label_materi_level.json").read_text(encoding="utf-8"))
    label: dict[str, list[str]] = label_file["label"]
    dikecualikan: dict[str, str] = label_file.get("dikecualikan", {})
    # Kunci yang dibersihkan manual (sumber menulis mis. "144 (atau ...)").
    koreksi: dict[str, str] = dict(label_file.get("kunci_koreksi", {}))
    # Kunci + pembahasan untuk soal yang sumbernya tanpa kunci, diselesaikan
    # manual (kunci_tambahan.json, opsional) — lihat field "sumber" di file itu.
    tambahan: dict[str, dict[str, str]] = {}
    path_tambahan = folder / "kunci_tambahan.json"
    if path_tambahan.is_file():
        tambahan = json.loads(path_tambahan.read_text(encoding="utf-8"))["soal"]
    koreksi.update({soal_id: t["kunci"] for soal_id, t in tambahan.items()})
    # Teks soal yang ditulis ulang karena di sumber terpotong/diringkas atau
    # meminta jawaban yang tak bisa dinilai otomatis (koreksi_teks.json, opsional).
    teks: dict[str, Any] = {"konteks": {}, "soal": {}}
    path_teks = folder / "koreksi_teks.json"
    if path_teks.is_file():
        teks = json.loads(path_teks.read_text(encoding="utf-8"))

    for path in sorted(folder.glob("soal_*_pembahasan/soal_*_*.json")):
        _, prefix, tahun = path.stem.split("_")
        tingkat = TINGKAT[prefix]
        for soal_id, mentah, deskripsi in _iterasi_soal(path, prefix, tahun, koreksi):
            mentah, deskripsi = _terapkan_koreksi_teks(mentah, deskripsi, teks, soal_id)
            kunci = _kunci(mentah, soal_id, koreksi)
            alasan = _alasan_dilewati(mentah, kunci, soal_id, label, dikecualikan)
            if alasan:
                bank.dilewati[soal_id] = alasan
                continue
            assert kunci is not None
            materi_id, level = label[soal_id]
            bank.soal.setdefault(tingkat, []).append(
                _soal_masukan(
                    mentah,
                    kunci=kunci,
                    soal_id=soal_id,
                    materi_id=materi_id,
                    level=LevelSoal(level),
                    deskripsi=deskripsi,
                    gambar=_gambar(mentah, folder, tingkat),
                    tahun=int(tahun),
                    pembahasan=tambahan.get(soal_id, {}).get("pembahasan"),
                )
            )
    return bank


def _terapkan_koreksi_teks(
    x: dict[str, Any], deskripsi: str | None, teks: dict[str, Any], soal_id: str
) -> tuple[dict[str, Any], str | None]:
    k = teks["soal"].get(soal_id)
    if not k:
        return x, deskripsi
    x = dict(x)
    for sumber, tujuan in (("pertanyaan", "soal"), ("kode", "kode"), ("pilihan", "pilihan")):
        if sumber in k:
            x[tujuan] = k[sumber]
    if "gambar" in k:
        # null = buang gambar sumber yang tidak relevan (mis. gif simbol LaTeX).
        x["gambar_lokal"], x["gambar_url"] = k["gambar"], None
    if "konteks" in k:
        deskripsi = teks["konteks"][k["konteks"]]
    elif "deskripsi" in k:
        deskripsi = k["deskripsi"]
    return x, deskripsi


def _kunci(x: dict[str, Any], soal_id: str, koreksi: dict[str, str]) -> str | None:
    if soal_id in koreksi:
        return koreksi[soal_id]
    jawaban = str(x.get("jawaban_benar") or "").strip()
    return None if not jawaban or jawaban == _INFO_DESKRIPSI else jawaban


def _iterasi_soal(
    path: Path, prefix: str, tahun: str, koreksi: dict[str, str]
) -> list[tuple[str, dict[str, Any], str | None]]:
    """(id, entri mentah, deskripsi) untuk setiap entri yang bukan konteks.

    Entri konteks = tanpa kunci, dan bertanda "Deskripsi Untuk Soal Nomor A
    dan B" atau punya pembahasan (teks pengantar/kode bersama). Konteks
    bertanda dipasang ke B-A+1 entri berikutnya; konteks tanpa tanda berlaku
    sampai konteks berikutnya atau soal yang punya deskripsi sendiri. Soal
    tanpa kunci yang pembahasannya kosong bukan konteks (tetap dilewati).
    """
    hasil = []
    konteks, sisa, terbuka = "", 0, False
    for nomor, x in enumerate(json.loads(path.read_text(encoding="utf-8")), start=1):
        soal_id = f"{prefix}-{tahun}-{nomor:03d}"
        rentang = _RENTANG_KONTEKS.search(str(x.get("deskripsi_soal") or ""))
        tanpa_kunci = _kunci(x, soal_id, koreksi) is None
        if tanpa_kunci and (rentang or (x.get("pembahasan") or "").strip()):
            konteks = (x.get("soal") or "").strip()
            if rentang:
                sisa, terbuka = int(rentang.group(2)) - int(rentang.group(1)) + 1, False
            else:
                sisa, terbuka = 0, True
            continue
        sendiri = (x.get("deskripsi_soal") or "").strip()
        if sendiri:
            terbuka = False
        deskripsi = sendiri or (konteks if sisa > 0 or terbuka else "")
        sisa -= 1
        hasil.append((soal_id, x, deskripsi or None))
    return hasil


def _pilihan_valid(x: dict[str, Any], kunci: str) -> dict[str, str] | None:
    """Pilihan jawaban kalau entri benar-benar pilihan ganda (kunci adalah
    salah satu hurufnya); None kalau tidak ada / berisi keterangan."""
    pilihan = x.get("pilihan")
    if isinstance(pilihan, dict) and pilihan and kunci.lower() in {k.lower() for k in pilihan}:
        return {k.upper(): str(v) for k, v in pilihan.items()}
    return None


def _alasan_dilewati(
    x: dict[str, Any],
    kunci: str | None,
    soal_id: str,
    label: dict[str, list[str]],
    dikecualikan: dict[str, str],
) -> str | None:
    if soal_id in dikecualikan:
        return dikecualikan[soal_id]
    if not (x.get("soal") or "").strip():
        return "tanpa teks soal"
    if kunci is None:
        return "tanpa kunci jawaban"
    if _pilihan_valid(x, kunci) is None and not _isian_bisa_dinilai(kunci):
        pilihan = x.get("pilihan")
        if isinstance(pilihan, dict) and pilihan:
            return "kunci bukan salah satu pilihan"
        return "jawaban isian tidak bisa dinilai otomatis"
    if soal_id not in label:
        return "belum berlabel Materi & Level"
    return None


def _isian_bisa_dinilai(jawaban: str) -> bool:
    j = jawaban.strip()
    return (
        0 < len(j) <= _MAKS_PANJANG_ISIAN
        and "\n" not in j
        and " atau " not in j
        and "sesuai" not in j
        and "..." not in j
    )


def _soal_masukan(
    x: dict[str, Any],
    *,
    kunci: str,
    soal_id: str,
    materi_id: str,
    level: LevelSoal,
    deskripsi: str | None,
    gambar: str | None,
    tahun: int,
    pembahasan: str | None = None,
) -> SoalMasukan:
    pilihan = _pilihan_valid(x, kunci)
    mentah = x.get("pilihan")
    if pilihan is None and isinstance(mentah, dict) and mentah:
        # "pilihan" berisi keterangan soal, bukan opsi jawaban: ikut ditampilkan.
        keterangan = "\n".join(str(v) for v in mentah.values() if str(v).strip(" .") != "")
        deskripsi = "\n\n".join(t for t in (deskripsi, keterangan) if t) or None
    return SoalMasukan(
        id=soal_id,
        materi_id=materi_id,
        level=level,
        tipe=TipeSoal.PILIHAN_GANDA if pilihan else TipeSoal.ISIAN_SINGKAT,
        deskripsi=deskripsi,
        pertanyaan=x["soal"].strip(),
        kode=(x.get("kode") or "").strip() or None,
        gambar=gambar,
        tahun=tahun,
        pilihan_jawaban=pilihan or {},
        kunci_jawaban=kunci.upper() if pilihan else kunci,
        pembahasan=pembahasan or (x.get("pembahasan") or "").strip() or None,
    )


def _gambar(x: dict[str, Any], folder: Path, tingkat: str) -> str | None:
    """Path relatif "<tingkat>/<file>" kalau file lokal ada di
    gambar_<tingkat>/, else URL sumber, else None."""
    lokal = x.get("gambar_lokal")
    if lokal:
        nama = Path(str(lokal)).name
        if (folder / f"gambar_{tingkat}" / nama).is_file():
            return f"{tingkat}/{nama}"
    url = x.get("gambar_url")
    return str(url) if url else None
