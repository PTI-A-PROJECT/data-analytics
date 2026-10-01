"""Parser dokumen Materi (.docx) di folder Materi/<Tingkat>/ menjadi Halaman
Materi untuk ingest.

Nama file memuat nomor topik ("Topik 3_ ....docx", "TOPIK 10_ ....docx") yang
dicocokkan ke field "topik" di soal_osn/materi.json; nama folder = tingkat
("Kabupaten", "Provinsi"). Isi dokumen dibaca langsung dari XML-nya (stdlib),
tanpa python-docx:

- paragraf pertama = judul dokumen, tidak ikut ke halaman;
- setiap judul bagian (paragraf tebal "1. ...", "Bagian A: ...",
  "Studi Kasus ...", "Use Case ...", "Kasus N: ...") membuka Halaman baru;
  teks sebelum judul bagian pertama menjadi halaman "Pendahuluan";
- konten halaman berupa Markdown: sub-judul "A. ..." → "###", daftar → "-",
  paragraf berbingkai (potongan kode) → blok ```, tabel → tabel Markdown,
  rumus Word (OMML) → LaTeX ($...$ inline, $$...$$ untuk rumus sebaris sendiri).
"""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

_NOMOR_TOPIK = re.compile(r"topik\s*(\d+)", re.IGNORECASE)
_JUDUL_BAGIAN = re.compile(
    r"^(\d+\.\s+\S|Bagian\s+\w+\s*:|Studi Kasus\b|Use Case\b|Kasus\s+\d+\s*:)", re.IGNORECASE
)
_SUB_JUDUL = re.compile(r"^[A-Z]\.\s+\S")
_FONT_KODE = {"Courier New", "Consolas", "Courier", "Lucida Console"}
_JUDUL_PENDAHULUAN = "Pendahuluan"
_BAHASA_KODE = {"c++": "cpp", "c": "c", "python": "python", "pascal": "pascal", "java": "java"}


@dataclass(frozen=True)
class HalamanDocx:
    judul: str
    konten: str


@dataclass(frozen=True)
class DokumenMateri:
    tingkat: str  # "kabupaten" / "provinsi"
    topik: int
    path: Path
    halaman: list[HalamanDocx]


def baca_folder_materi(folder: Path) -> dict[tuple[str, int], DokumenMateri]:
    """Semua .docx di folder/<Tingkat>/, dikunci (tingkat, nomor topik).
    ValueError kalau nama file tanpa nomor topik atau ada topik kembar."""
    hasil: dict[tuple[str, int], DokumenMateri] = {}
    for path in sorted(folder.glob("*/*.docx")):
        if path.name.startswith("~$"):  # file kunci Word yang sedang terbuka
            continue
        cocok = _NOMOR_TOPIK.search(path.stem)
        if cocok is None:
            raise ValueError(f"Nama file Materi tanpa nomor topik: {path}")
        kunci = (path.parent.name.lower(), int(cocok.group(1)))
        if kunci in hasil:
            raise ValueError(f"Topik kembar {kunci}: {hasil[kunci].path.name} dan {path.name}")
        hasil[kunci] = DokumenMateri(
            tingkat=kunci[0], topik=kunci[1], path=path, halaman=baca_docx(path)
        )
    return hasil


def baca_docx(path: Path) -> list[HalamanDocx]:
    with zipfile.ZipFile(path) as arsip:
        dokumen = ET.fromstring(arsip.read("word/document.xml"))
        numbering = (
            ET.fromstring(arsip.read("word/numbering.xml"))
            if "word/numbering.xml" in arsip.namelist()
            else None
        )
    body = dokumen.find(f"{_W}body")
    if body is None:
        return []
    return _pecah_halaman(_blok(body, _format_daftar(numbering)))


# --- Blok konten ---------------------------------------------------------------


@dataclass(frozen=True)
class _Blok:
    jenis: str  # "judul_bagian" | "teks" | "kode"
    teks: str


def _blok(body: ET.Element, format_daftar: dict[str, str]) -> Iterator[_Blok]:
    judul_dokumen_dilewati = False
    for el in body:
        if el.tag == f"{_W}tbl":
            yield _Blok("teks", _tabel(el))
            continue
        if el.tag != f"{_W}p":
            continue
        teks_polos = _teks_polos(el).strip()
        if _paragraf_kode(el):
            yield _Blok("kode", _teks_polos(el).rstrip())
            continue
        if not teks_polos and el.find(f".//{_M}oMath") is None:
            continue
        if not judul_dokumen_dilewati:
            judul_dokumen_dilewati = True
            continue
        num = el.find(f"{_W}pPr/{_W}numPr")
        tebal = _seluruhnya_tebal(el)
        if num is None and tebal and _JUDUL_BAGIAN.match(teks_polos):
            yield _Blok("judul_bagian", teks_polos)
        elif num is None and tebal and _SUB_JUDUL.match(teks_polos):
            yield _Blok("teks", f"### {teks_polos}")
        elif num is not None:
            ilvl = num.find(f"{_W}ilvl")
            level = int(ilvl.get(f"{_W}val", "0")) if ilvl is not None else 0
            num_id = num.find(f"{_W}numId")
            fmt = format_daftar.get(
                f"{num_id.get(f'{_W}val') if num_id is not None else ''}:{level}", "bullet"
            )
            penanda = "1." if fmt == "decimal" else "-"
            yield _Blok("teks", f"{'   ' * level}{penanda} {_teks_markdown(el)}")
        else:
            yield _Blok("teks", _teks_markdown(el))


def _pecah_halaman(blok: Iterator[_Blok]) -> list[HalamanDocx]:
    halaman: list[tuple[str, list[str]]] = [(_JUDUL_PENDAHULUAN, [])]
    kode: list[str] = []

    def tutup_kode() -> None:
        if not kode:
            return
        isi = halaman[-1][1]
        # Label bahasa ("C++") tepat di atas kode dijadikan info string fence.
        bahasa = _BAHASA_KODE.get(isi[-1].strip().lower(), "") if isi else ""
        if bahasa:
            isi.pop()
        isi.append(f"```{bahasa}\n" + "\n".join(kode).strip("\n") + "\n```")
        kode.clear()

    for b in blok:
        if b.jenis == "kode":
            kode.append(b.teks)
            continue
        tutup_kode()
        if b.jenis == "judul_bagian":
            # Judul bagian tanpa isi (mis. "Use Case & Contoh Soal:" langsung
            # disusul "Kasus 1: ...") digantikan judul berikutnya.
            if not halaman[-1][1]:
                halaman.pop()
            judul = b.teks.rstrip(":").strip()
            # Dokumen yang mengulang judul bagian untuk contoh-contohnya
            # (Topik 4 Kabupaten) — bedakan supaya daftar isi tidak kembar.
            if any(j == judul for j, _ in halaman):
                judul = f"{judul} (Contoh)"
            halaman.append((judul, []))
        else:
            halaman[-1][1].append(b.teks)
    tutup_kode()
    return [
        HalamanDocx(judul=judul, konten=_rapikan("\n\n".join(isi)))
        for judul, isi in halaman
        if isi
    ]


def _rapikan(teks: str) -> str:
    # Butir daftar berurutan tidak perlu dipisah baris kosong.
    teks = re.sub(r"(?m)^(\s*(?:-|1\.) .*)\n\n(?=\s*(?:-|1\.) )", r"\1\n", teks)
    return teks.strip()


def _format_daftar(numbering: ET.Element | None) -> dict[str, str]:
    """numId:ilvl → numFmt ("decimal", "bullet", ...)."""
    if numbering is None:
        return {}
    abstrak: dict[str, dict[str, str]] = {}
    for a in numbering.findall(f"{_W}abstractNum"):
        abstrak[a.get(f"{_W}abstractNumId", "")] = {
            lvl.get(f"{_W}ilvl", "0"): (
                fmt.get(f"{_W}val", "bullet")
                if (fmt := lvl.find(f"{_W}numFmt")) is not None
                else "bullet"
            )
            for lvl in a.findall(f"{_W}lvl")
        }
    hasil: dict[str, str] = {}
    for n in numbering.findall(f"{_W}num"):
        ref = n.find(f"{_W}abstractNumId")
        if ref is None:
            continue
        for ilvl, format_level in abstrak.get(ref.get(f"{_W}val", ""), {}).items():
            hasil[f"{n.get(f'{_W}numId')}:{ilvl}"] = format_level
    return hasil


def _paragraf_kode(p: ET.Element) -> bool:
    """Potongan kode di dokumen sumber ditulis sebagai paragraf berbingkai
    (pBdr) dan/atau berhuruf monospace."""
    if p.find(f"{_W}pPr/{_W}pBdr") is not None:
        return True
    fonts = {
        f.get(f"{_W}ascii")
        for r in p.findall(f"{_W}r")
        if _teks_run(r).strip()
        for f in r.iter(f"{_W}rFonts")
    }
    return bool(fonts) and fonts <= _FONT_KODE


def _seluruhnya_tebal(p: ET.Element) -> bool:
    run_bertekst = [r for r in p.findall(f"{_W}r") if (_teks_run(r) or "").strip()]
    return bool(run_bertekst) and all(_run_tebal(r) for r in run_bertekst)


def _run_tebal(r: ET.Element) -> bool:
    b = r.find(f"{_W}rPr/{_W}b")
    return b is not None and b.get(f"{_W}val", "true") not in {"0", "false"}


def _teks_run(r: ET.Element) -> str:
    bagian: list[str] = []
    for x in r:
        if x.tag == f"{_W}t":
            bagian.append(x.text or "")
        elif x.tag == f"{_W}tab":
            bagian.append("\t")
        elif x.tag in {f"{_W}br", f"{_W}cr"}:
            bagian.append("\n")
    return "".join(bagian)


def _teks_polos(p: ET.Element) -> str:
    bagian: list[str] = []
    for x in p:
        if x.tag == f"{_W}r":
            bagian.append(_teks_run(x))
        elif x.tag == f"{_W}hyperlink":
            bagian.append("".join(_teks_run(r) for r in x.findall(f"{_W}r")))
        elif x.tag in {f"{_M}oMath", f"{_M}oMathPara"}:
            bagian.append(_latex(x))
    return "".join(bagian)


def _teks_markdown(p: ET.Element) -> str:
    """Teks paragraf: run tebal → **...**, rumus → $...$ / $$...$$."""
    bagian: list[str] = []
    for x in p:
        if x.tag == f"{_W}r":
            bagian.append(_tebalkan(_teks_run(x)) if _run_tebal(x) else _teks_run(x))
        elif x.tag == f"{_W}hyperlink":
            bagian.append("".join(_teks_run(r) for r in x.findall(f"{_W}r")))
        elif x.tag == f"{_M}oMath":
            bagian.append(f"${_latex(x).strip()}$")
        elif x.tag == f"{_M}oMathPara":
            rumus = [_latex(m).strip() for m in x.iter(f"{_M}oMath")]
            bagian.append("\n\n" + "\n\n".join(f"$${r}$$" for r in rumus if r) + "\n\n")
    teks = "".join(bagian)
    # Gabungkan **a****b** yang berasal dari run tebal berurutan.
    teks = teks.replace("****", "").replace("** **", " ")
    return re.sub(r"\n{3,}", "\n\n", teks).strip()


def _tebalkan(teks: str) -> str:
    if not teks.strip():
        return teks
    kiri = teks[: len(teks) - len(teks.lstrip())]
    kanan = teks[len(teks.rstrip()) :]
    return f"{kiri}**{teks.strip()}**{kanan}"


def _tabel(tbl: ET.Element) -> str:
    baris = [
        [
            " ".join(_teks_markdown(p) for p in tc.findall(f"{_W}p")).replace("|", "\\|").strip()
            for tc in tr.findall(f"{_W}tc")
        ]
        for tr in tbl.findall(f"{_W}tr")
    ]
    baris = [b for b in baris if any(b)]
    if not baris:
        return ""
    lebar = max(len(b) for b in baris)
    baris = [b + [""] * (lebar - len(b)) for b in baris]
    garis = ["| " + " | ".join(b) + " |" for b in baris]
    garis.insert(1, "|" + " --- |" * lebar)
    return "\n".join(garis)


# --- OMML → LaTeX --------------------------------------------------------------

_NARY = {"∑": r"\sum", "∏": r"\prod", "∫": r"\int", "⋃": r"\bigcup", "⋂": r"\bigcap"}
_AKSEN = {"\u0305": r"\overline", "\u0302": r"\hat", "\u20d7": r"\vec", "\u0303": r"\tilde"}
_KURUNG = {"{": r"\{", "}": r"\}", "⌊": r"\lfloor", "⌋": r"\rfloor", "⌈": r"\lceil", "⌉": r"\rceil", "|": "|", "": "."}


def _anak(el: ET.Element, nama: str) -> ET.Element | None:
    return el.find(f"{_M}{nama}")


def _val(el: ET.Element | None, nama: str, default: str) -> str:
    if el is None:
        return default
    x = el.find(f"{_M}{nama}")
    return x.get(f"{_M}val", default) if x is not None else default


def _isi(el: ET.Element | None) -> str:
    return "" if el is None else "".join(_latex(x) for x in el)


def _latex(el: ET.Element) -> str:
    tag = el.tag.removeprefix(_M)
    if not el.tag.startswith(_M):
        return ""
    if tag == "r":
        teks = "".join(t.text or "" for t in el.findall(f"{_M}t"))
        teks = teks.replace("{", r"\{").replace("}", r"\}").replace("%", r"\%").replace("#", r"\#")
        if el.find(f"{_M}rPr/{_M}nor") is not None and teks.strip():
            return rf"\text{{{teks}}}"
        return teks
    if tag == "f":
        return rf"\frac{{{_isi(_anak(el, 'num'))}}}{{{_isi(_anak(el, 'den'))}}}"
    if tag == "sSup":
        return f"{{{_isi(_anak(el, 'e'))}}}^{{{_isi(_anak(el, 'sup'))}}}"
    if tag == "sSub":
        return f"{{{_isi(_anak(el, 'e'))}}}_{{{_isi(_anak(el, 'sub'))}}}"
    if tag == "sSubSup":
        return (
            f"{{{_isi(_anak(el, 'e'))}}}_{{{_isi(_anak(el, 'sub'))}}}^{{{_isi(_anak(el, 'sup'))}}}"
        )
    if tag == "sPre":
        return f"{{}}_{{{_isi(_anak(el, 'sub'))}}}^{{{_isi(_anak(el, 'sup'))}}}{_isi(_anak(el, 'e'))}"
    if tag == "rad":
        derajat = _isi(_anak(el, "deg"))
        akar = rf"\sqrt[{derajat}]" if derajat.strip() else r"\sqrt"
        return f"{akar}{{{_isi(_anak(el, 'e'))}}}"
    if tag == "d":
        pr = _anak(el, "dPr")
        buka = _KURUNG.get(b := _val(pr, "begChr", "("), b)
        tutup = _KURUNG.get(t := _val(pr, "endChr", ")"), t)
        pemisah = _val(pr, "sepChr", ",")
        isi = pemisah.join(_isi(e) for e in el.findall(f"{_M}e"))
        return rf"\left{buka}{isi}\right{tutup}"
    if tag == "nary":
        pr = _anak(el, "naryPr")
        op = _NARY.get(c := _val(pr, "chr", "∫"), c)
        bawah, atas = _isi(_anak(el, "sub")), _isi(_anak(el, "sup"))
        return (
            op
            + (f"_{{{bawah}}}" if bawah else "")
            + (f"^{{{atas}}}" if atas else "")
            + f" {_isi(_anak(el, 'e'))}"
        )
    if tag == "func":
        return f"{_isi(_anak(el, 'fName'))} {_isi(_anak(el, 'e'))}"
    if tag == "limLow":
        return f"{_isi(_anak(el, 'e'))}_{{{_isi(_anak(el, 'lim'))}}}"
    if tag == "limUpp":
        return f"{_isi(_anak(el, 'e'))}^{{{_isi(_anak(el, 'lim'))}}}"
    if tag == "bar":
        return rf"\overline{{{_isi(_anak(el, 'e'))}}}"
    if tag == "acc":
        aksen = _val(_anak(el, "accPr"), "chr", "̂")
        perintah = _AKSEN.get(aksen, r"\hat")
        return f"{perintah}{{{_isi(_anak(el, 'e'))}}}"
    if tag == "m":
        baris = [
            " & ".join(_isi(e) for e in mr.findall(f"{_M}e")) for mr in el.findall(f"{_M}mr")
        ]
        return r"\begin{matrix}" + r" \\ ".join(baris) + r"\end{matrix}"
    if tag == "eqArr":
        return r"\begin{gathered}" + r" \\ ".join(_isi(e) for e in el.findall(f"{_M}e")) + r"\end{gathered}"
    if tag in {"rPr", "ctrlPr", "dPr", "fPr", "naryPr", "radPr", "sSupPr", "sSubPr",
               "sSubSupPr", "funcPr", "mPr", "accPr", "barPr", "oMathParaPr", "limLowPr",
               "limUppPr", "eqArrPr", "sPrePr", "groupChrPr", "boxPr", "borderBoxPr"}:
        return ""
    # oMath, oMathPara, e, num, box, groupChr, borderBox, dll.: isi anak apa adanya.
    return "".join(_latex(x) for x in el)
