"""Parser dokumen Materi (.docx) menjadi Halaman Materi."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from data_analytics.materi_docx import baca_docx, baca_folder_materi

_NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
)


def _p(teks: str, *, tebal: bool = False, daftar: bool = False, kode: bool = False) -> str:
    ppr = ""
    if daftar:
        ppr += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
    if kode:
        ppr += '<w:pBdr><w:top w:val="single"/></w:pBdr>'
    rpr = "<w:rPr><w:b/></w:rPr>" if tebal else ""
    return f'<w:p><w:pPr>{ppr}</w:pPr><w:r>{rpr}<w:t xml:space="preserve">{teks}</w:t></w:r></w:p>'


def _tulis_docx(path: Path, *paragraf: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f"<w:document {_NS}><w:body>{''.join(paragraf)}</w:body></w:document>")
    return path


RUMUS_PECAHAN = (
    "<w:p><w:r><w:t xml:space=\"preserve\">Peluang </w:t></w:r>"
    "<m:oMath><m:f><m:num><m:r><m:t>1</m:t></m:r></m:num>"
    "<m:den><m:r><m:t>n</m:t></m:r></m:den></m:f></m:oMath></w:p>"
)


def test_memecah_halaman_per_judul_bagian(tmp_path: Path) -> None:
    path = _tulis_docx(
        tmp_path / "Topik 1_ X.docx",
        _p("Topik 1: Judul Dokumen", tebal=True),
        _p("Pengantar singkat."),
        _p("1. Konsep Dasar", tebal=True),
        _p("A. Sub Bagian", tebal=True),
        _p("Butir satu", daftar=True),
        _p("Butir dua", daftar=True),
        RUMUS_PECAHAN,
        _p("Studi Kasus 1: Contoh", tebal=True),
        _p("C++"),
        _p("int main() {", kode=True),
        _p("}", kode=True),
    )

    halaman = baca_docx(path)

    assert [h.judul for h in halaman] == ["Pendahuluan", "1. Konsep Dasar", "Studi Kasus 1: Contoh"]
    assert halaman[0].konten == "Pengantar singkat."
    assert halaman[1].konten == (
        "### A. Sub Bagian\n\n- Butir satu\n- Butir dua\n\nPeluang $\\frac{1}{n}$"
    )
    assert halaman[2].konten == "```cpp\nint main() {\n}\n```"


def test_judul_bagian_tanpa_isi_digantikan_dan_judul_kembar_dibedakan(tmp_path: Path) -> None:
    path = _tulis_docx(
        tmp_path / "Topik 2_ Y.docx",
        _p("Topik 2", tebal=True),
        _p("1. Konsep", tebal=True),
        _p("Isi konsep."),
        _p("Use Case &amp; Contoh Soal:", tebal=True),
        _p("1. Konsep", tebal=True),
        _p("Contoh konsep."),
    )

    assert [h.judul for h in baca_docx(path)] == ["1. Konsep", "1. Konsep (Contoh)"]


def test_folder_dikunci_tingkat_dan_nomor_topik(tmp_path: Path) -> None:
    _tulis_docx(tmp_path / "Kabupaten" / "Topik 1_ A.docx", _p("Judul"), _p("Isi"))
    _tulis_docx(tmp_path / "Provinsi" / "TOPIK 10_ B.docx", _p("Judul"), _p("Isi"))

    dokumen = baca_folder_materi(tmp_path)

    assert sorted(dokumen) == [("kabupaten", 1), ("provinsi", 10)]
    assert dokumen[("provinsi", 10)].halaman[0].konten == "Isi"


def test_nama_file_tanpa_nomor_topik_ditolak(tmp_path: Path) -> None:
    _tulis_docx(tmp_path / "Kabupaten" / "Catatan.docx", _p("Judul"))

    with pytest.raises(ValueError, match="nomor topik"):
        baca_folder_materi(tmp_path)


def test_dokumen_materi_di_repo_terbaca_semua() -> None:
    folder = Path(__file__).resolve().parents[1] / "Materi"
    if not folder.is_dir():
        pytest.skip("folder Materi tidak ada")

    dokumen = baca_folder_materi(folder)

    assert {t for t, _ in dokumen} == {"kabupaten", "provinsi"}
    for dok in dokumen.values():
        assert dok.halaman, dok.path
        assert all(h.konten.strip() for h in dok.halaman), dok.path
