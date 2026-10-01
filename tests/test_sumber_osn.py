"""Parser bank soal soal_osn/ (JSON sumber + label Materi & Level) menjadi
masukan ingest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_analytics.models import LevelSoal, TipeSoal
from data_analytics.sumber_osn import baca_bank_soal


def _tulis(path: Path, isi: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(isi, ensure_ascii=False), encoding="utf-8")


def _pg(soal: str, kunci: str = "c", **lain: object) -> dict[str, object]:
    return {
        "soal": soal,
        "pilihan": {"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"},
        "kode": None,
        "gambar_url": None,
        "gambar_lokal": None,
        "jawaban_benar": kunci,
        "pembahasan": f"Pembahasan {soal}",
        **lain,
    }


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    _tulis(
        tmp_path / "materi.json",
        [
            {"id": "kab-a", "tingkat": "kabupaten", "topik": 1, "judul": "Materi A", "cakupan": "Isi A"},
            {"id": "prov-b", "tingkat": "provinsi", "judul": "Materi B", "cakupan": "Isi B"},
        ],
    )
    _tulis(
        tmp_path / "soal_kabupaten_pembahasan" / "soal_kab_2020.json",
        [
            _pg("Soal satu", gambar_lokal="../gambar_kabupaten/soal_1_kab_2020.png"),
            {
                "deskripsi_soal": "Deskripsi Untuk Soal Nomor 2 dan 3",
                "soal": "Konteks bersama",
                "pilihan": {},
                "jawaban_benar": None,
            },
            _pg("Soal dua"),
            _pg("Soal tiga", kode="x := 1;"),
            _pg("Soal empat", gambar_url="https://contoh/x.png", gambar_lokal="hilang.png"),
            {"soal": "Isian", "pilihan": {}, "jawaban_benar": " 1260 ", "pembahasan": None},
            {"soal": "Tanpa kunci", "pilihan": {}, "jawaban_benar": None},
            {"soal": "Uraian", "pilihan": {}, "jawaban_benar": "26, 17, 11 (atau rincian)"},
            _pg("Dikecualikan"),
            _pg("Belum berlabel"),
            _pg("Punya deskripsi", deskripsi_soal="Deskripsi sendiri"),
        ],
    )
    (tmp_path / "gambar_kabupaten").mkdir()
    (tmp_path / "gambar_kabupaten" / "soal_1_kab_2020.png").write_bytes(b"png")
    _tulis(
        tmp_path / "soal_provinsi_pembahasan" / "soal_prov_2021.json",
        [_pg("Soal provinsi", kunci="a")],
    )
    _tulis(
        tmp_path / "label_materi_level.json",
        {
            "label": {
                "kab-2020-001": ["kab-a", "mudah"],
                "kab-2020-003": ["kab-a", "menengah"],
                "kab-2020-004": ["kab-a", "sulit"],
                "kab-2020-005": ["kab-a", "mudah"],
                "kab-2020-006": ["kab-a", "mudah"],
                "kab-2020-011": ["kab-a", "mudah"],
                "prov-2021-001": ["prov-b", "sulit"],
            },
            "dikecualikan": {"kab-2020-009": "duplikat"},
        },
    )
    return tmp_path


def _per_id(folder: Path) -> dict[str, object]:
    bank = baca_bank_soal(folder)
    return {s.id: s for soal in bank.soal.values() for s in soal}


class TestBacaBankSoal:
    def test_pilihan_ganda_dengan_materi_level_dan_kunci_huruf_kapital(self, folder: Path) -> None:
        soal = baca_bank_soal(folder).soal["kabupaten"][0]

        assert (soal.id, soal.materi_id, soal.level, soal.tipe, soal.tahun) == (
            "kab-2020-001",
            "kab-a",
            LevelSoal.MUDAH,
            TipeSoal.PILIHAN_GANDA,
            2020,
        )
        assert soal.pilihan_jawaban == {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"}
        assert soal.kunci_jawaban == "C"
        assert soal.pembahasan == "Pembahasan Soal satu"

    def test_konteks_dipasang_ke_soal_dalam_rentangnya_saja(self, folder: Path) -> None:
        soal = _per_id(folder)

        assert soal["kab-2020-003"].deskripsi == "Konteks bersama"  # type: ignore[attr-defined]
        assert soal["kab-2020-004"].deskripsi == "Konteks bersama"  # type: ignore[attr-defined]
        assert soal["kab-2020-005"].deskripsi is None  # type: ignore[attr-defined]
        assert soal["kab-2020-011"].deskripsi == "Deskripsi sendiri"  # type: ignore[attr-defined]

    def test_isian_singkat(self, folder: Path) -> None:
        isian = _per_id(folder)["kab-2020-006"]

        assert (isian.tipe, isian.pilihan_jawaban, isian.kunci_jawaban) == (  # type: ignore[attr-defined]
            TipeSoal.ISIAN_SINGKAT,
            {},
            "1260",
        )

    def test_kode_dan_gambar(self, folder: Path) -> None:
        soal = _per_id(folder)

        assert soal["kab-2020-004"].kode == "x := 1;"  # type: ignore[attr-defined]
        assert soal["kab-2020-001"].gambar == "kabupaten/soal_1_kab_2020.png"  # type: ignore[attr-defined]
        # File lokal tidak ada → pakai URL sumber.
        assert soal["kab-2020-005"].gambar == "https://contoh/x.png"  # type: ignore[attr-defined]
        assert soal["kab-2020-003"].gambar is None  # type: ignore[attr-defined]

    def test_soal_yang_dilewati_beserta_alasannya(self, folder: Path) -> None:
        bank = baca_bank_soal(folder)

        assert set(bank.dilewati) == {"kab-2020-007", "kab-2020-008", "kab-2020-009", "kab-2020-010"}
        assert bank.dilewati["kab-2020-009"] == "duplikat"
        assert "berlabel" in bank.dilewati["kab-2020-010"]

    def test_materi_per_tingkat_dan_soal_provinsi(self, folder: Path) -> None:
        bank = baca_bank_soal(folder)

        assert [(m.id, m.judul) for m in bank.materi["kabupaten"]] == [("kab-a", "Materi A")]
        assert [s.id for s in bank.soal["provinsi"]] == ["prov-2021-001"]
        assert bank.soal["provinsi"][0].kunci_jawaban == "A"


@pytest.fixture
def folder_konteks(tmp_path: Path) -> Path:
    _tulis(tmp_path / "materi.json", [{"id": "kab-a", "tingkat": "kabupaten", "judul": "A", "cakupan": ""}])
    _tulis(
        tmp_path / "soal_kabupaten_pembahasan" / "soal_kab_2007.json",
        [
            # Konteks tanpa penanda "Nomor A dan B", dikenali dari pembahasannya.
            {"soal": "function apaitu(a, b) ...", "pilihan": {}, "jawaban_benar": "",
             "pembahasan": "Fungsi apaitu mencari FPB."},
            _pg("apaitu(1001, 1331)?"),
            _pg("apaitu(1000, 5040)?"),
            _pg("Soal lain", deskripsi_soal="Deskripsi sendiri"),
            _pg("Setelah soal berdeskripsi"),
            # Soal tanpa kunci & tanpa pembahasan tetap dilewati (bukan konteks).
            {"soal": "Tanpa kunci", "pilihan": {"a": "1"}, "jawaban_benar": "", "pembahasan": ""},
            # "pilihan" berisi keterangan, bukan opsi; kuncinya isian.
            {"soal": "Berapa minimal?", "pilihan": {"a": "Penghargaan A untuk 6 pion"},
             "jawaban_benar": "2", "pembahasan": "Inklusi-eksklusi."},
            {"soal": "Berapa detik?", "pilihan": {}, "jawaban_benar": "2016000 detik (atau 560 jam)"},
        ],
    )
    _tulis(
        tmp_path / "label_materi_level.json",
        {
            "label": {f"kab-2007-{n:03d}": ["kab-a", "mudah"] for n in range(2, 9)},
            "kunci_koreksi": {"kab-2007-008": "2016000"},
        },
    )
    return tmp_path


class TestKonteksDanKoreksi:
    def test_konteks_tanpa_penanda_berlaku_sampai_soal_berdeskripsi(self, folder_konteks: Path) -> None:
        soal = _per_id(folder_konteks)

        assert soal["kab-2007-002"].deskripsi == "function apaitu(a, b) ..."  # type: ignore[attr-defined]
        assert soal["kab-2007-003"].deskripsi == "function apaitu(a, b) ..."  # type: ignore[attr-defined]
        assert soal["kab-2007-004"].deskripsi == "Deskripsi sendiri"  # type: ignore[attr-defined]
        assert soal["kab-2007-005"].deskripsi is None  # type: ignore[attr-defined]
        assert "kab-2007-001" not in baca_bank_soal(folder_konteks).dilewati

    def test_soal_tanpa_kunci_dan_pembahasan_tetap_dilewati(self, folder_konteks: Path) -> None:
        assert baca_bank_soal(folder_konteks).dilewati["kab-2007-006"] == "tanpa kunci jawaban"

    def test_pilihan_berisi_keterangan_menjadi_isian_dengan_deskripsi(self, folder_konteks: Path) -> None:
        soal = _per_id(folder_konteks)["kab-2007-007"]

        assert (soal.tipe, soal.kunci_jawaban, soal.pilihan_jawaban) == (TipeSoal.ISIAN_SINGKAT, "2", {})  # type: ignore[attr-defined]
        assert "Penghargaan A untuk 6 pion" in soal.deskripsi  # type: ignore[attr-defined]

    def test_kunci_koreksi_manual_dipakai(self, folder_konteks: Path) -> None:
        soal = _per_id(folder_konteks)["kab-2007-008"]

        assert (soal.tipe, soal.kunci_jawaban) == (TipeSoal.ISIAN_SINGKAT, "2016000")  # type: ignore[attr-defined]


class TestKunciTambahan:
    def test_kunci_dan_pembahasan_tambahan_dipakai_untuk_soal_tanpa_kunci(self, folder_konteks: Path) -> None:
        _tulis(
            folder_konteks / "kunci_tambahan.json",
            {"soal": {"kab-2007-006": {"kunci": "a", "pembahasan": "Karena 1."}}},
        )

        soal = _per_id(folder_konteks)["kab-2007-006"]

        assert (soal.kunci_jawaban, soal.pembahasan, soal.tipe) == ("A", "Karena 1.", TipeSoal.PILIHAN_GANDA)  # type: ignore[attr-defined]


class TestKoreksiTeks:
    def test_konteks_pertanyaan_kode_pilihan_dari_file_koreksi(self, folder_konteks: Path) -> None:
        _tulis(
            folder_konteks / "koreksi_teks.json",
            {
                "konteks": {"kab-2007-K1": "Cerita lengkap dari PDF."},
                "soal": {
                    "kab-2007-002": {"konteks": "kab-2007-K1", "pertanyaan": "Pertanyaan lengkap?",
                                     "kode": "x := 2;", "pilihan": {"a": "10", "b": "20", "c": "30"}},
                    "kab-2007-003": {"konteks": "kab-2007-K1"},
                },
            },
        )

        soal = _per_id(folder_konteks)

        dua = soal["kab-2007-002"]
        assert (dua.deskripsi, dua.pertanyaan, dua.kode, dua.pilihan_jawaban) == (  # type: ignore[attr-defined]
            "Cerita lengkap dari PDF.", "Pertanyaan lengkap?", "x := 2;", {"A": "10", "B": "20", "C": "30"}
        )
        assert soal["kab-2007-003"].deskripsi == "Cerita lengkap dari PDF."  # type: ignore[attr-defined]
        assert soal["kab-2007-003"].pertanyaan == "apaitu(1000, 5040)?"  # type: ignore[attr-defined]

    def test_gambar_sumber_bisa_dihapus_lewat_file_koreksi(self, folder_konteks: Path) -> None:
        _tulis(
            folder_konteks / "koreksi_teks.json",
            {"konteks": {}, "soal": {"kab-2007-002": {"gambar": None}}},
        )
        mentah_path = folder_konteks / "soal_kabupaten_pembahasan" / "soal_kab_2007.json"
        mentah = json.loads(mentah_path.read_text(encoding="utf-8"))
        mentah[1]["gambar_url"] = "http://latex.codecogs.com/gif.latex?%5Cleq"
        _tulis(mentah_path, mentah)

        assert _per_id(folder_konteks)["kab-2007-002"].gambar is None  # type: ignore[attr-defined]


class TestDataSumberDipercaya:
    """Kunci & teks sumber sudah disortir tim data dan dianggap valid: kunci
    berbentuk keterangan dan konteks/kode ringkas tetap di-ingest apa adanya."""

    @pytest.mark.parametrize(
        ("kunci", "deskripsi", "soal"),
        [
            ("Jumlah bebek", None, "Berapa?"),
            ("Program / Solusi Algoritma", None, "Buat program"),
            ("1260", "A. String Cantik OSN...", "Berapa?"),
            ("1260", None, "Apa output program berikut? [program rekursif pascal dengan array A]"),
        ],
    )
    def test_tetap_masuk(self, tmp_path: Path, kunci: str, deskripsi: str | None, soal: str) -> None:
        _tulis(tmp_path / "materi.json", [{"id": "kab-a", "tingkat": "kabupaten", "judul": "A", "cakupan": ""}])
        _tulis(tmp_path / "soal_kabupaten_pembahasan" / "soal_kab_2020.json",
               [{"soal": soal, "pilihan": {}, "jawaban_benar": kunci, "deskripsi_soal": deskripsi}])
        _tulis(tmp_path / "label_materi_level.json", {"label": {"kab-2020-001": ["kab-a", "mudah"]}})

        bank = baca_bank_soal(tmp_path)

        assert bank.dilewati == {}
        assert bank.soal["kabupaten"][0].kunci_jawaban == kunci


def test_halaman_materi_dari_dokumen_bernomor_topik(folder: Path, tmp_path: Path) -> None:
    import zipfile

    dok = tmp_path / "Materi" / "Kabupaten" / "Topik 1_ Materi A.docx"
    dok.parent.mkdir(parents=True)
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    with zipfile.ZipFile(dok, "w") as z:
        z.writestr(
            "word/document.xml",
            f"<w:document {ns}><w:body>"
            "<w:p><w:r><w:t>Topik 1</w:t></w:r></w:p>"
            "<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>1. Pengantar</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Isi pengantar.</w:t></w:r></w:p>"
            "</w:body></w:document>",
        )
    lain = tmp_path / "Materi" / "Provinsi" / "Topik 7_ Tanpa Materi.docx"
    lain.parent.mkdir(parents=True)
    lain.write_bytes(dok.read_bytes())

    bank = baca_bank_soal(folder, tmp_path / "Materi")

    [materi_a] = bank.materi["kabupaten"]
    assert materi_a.topik == 1
    assert [(h.judul, h.konten) for h in materi_a.daftar_halaman] == [("1. Pengantar", "Isi pengantar.")]
    assert bank.materi["provinsi"][0].halaman == []
    assert bank.dokumen_tanpa_materi == [str(lain)]
