"""Test kontrak endpoint /hitung/* — termasuk bentuk wire Laravel.

Dua endpoint yang dipanggil backend Osn-Readiness-Web (/hitung/penilaian dan
/hitung/pretest) memakai skema Laravel: id int, bobot eksplisit per soal,
tipe_soal 'pilihan_ganda'/'isian', respons {nilai, jawaban[{soal_id,
status_benar}]} plus pemetaan/materi_wajib untuk pretest. /hitung/simulasi dan
/hitung/latihan memakai skema internal lama (saat ini tidak dipanggil Laravel).
Semua endpoint /hitung/* mewajibkan header X-Internal-Token.
"""

from fastapi.testclient import TestClient

from data_analytics.api import app
from data_analytics.config import get_settings

client = TestClient(app)
TOKEN = get_settings().internal_api_token
HEADERS = {"X-Internal-Token": TOKEN}


def _soal(i, level, kunci, jawaban, materi=None):
    """Bentuk internal lama — untuk /hitung/simulasi & /hitung/latihan."""
    return {
        "soal_id": i,
        "level": level,
        "kunci": kunci,
        "jawaban": jawaban,
        "materi_id": materi,
    }


def _lrv(soal_id, tipe_soal, bobot, kunci, jawaban, materi_id=None):
    """Satu baris soal bentuk Laravel."""
    baris = {
        "soal_id": soal_id,
        "tipe_soal": tipe_soal,
        "bobot": bobot,
        "jawaban_user": jawaban,
        "kunci_jawaban": kunci,
    }
    if materi_id is not None:
        baris["materi_id"] = materi_id
    return baris


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_hitung_tanpa_token_ditolak():
    r = client.post(
        "/hitung/penilaian",
        json={"soal": [_lrv(1, "pilihan_ganda", 1, "A", "A")]},
    )
    assert r.status_code == 403


def test_hitung_token_salah_ditolak():
    r = client.post(
        "/hitung/penilaian",
        headers={"X-Internal-Token": "salah"},
        json={"soal": [_lrv(1, "pilihan_ganda", 1, "A", "A")]},
    )
    assert r.status_code == 403


def test_hitung_penilaian_kontrak_laravel():
    # Bobot 1 benar + bobot 2 salah dari total 3 → 33.33.
    r = client.post(
        "/hitung/penilaian",
        headers=HEADERS,
        json={
            "soal": [
                _lrv(1, "pilihan_ganda", 1, "A", "A"),
                _lrv(2, "pilihan_ganda", 2, "A", "B"),
            ]
        },
    )
    assert r.status_code == 200
    assert r.json() == {
        "nilai": 33.33,
        "jawaban": [
            {"soal_id": 1, "status_benar": True},
            {"soal_id": 2, "status_benar": False},
        ],
    }


def test_hitung_penilaian_isian_dinormalisasi():
    r = client.post(
        "/hitung/penilaian",
        headers=HEADERS,
        json={
            "soal": [
                _lrv(1, "isian", 1, "4", " 4 "),
                _lrv(2, "isian", 1, "1260", "1260.0"),
                _lrv(3, "isian", 1, "x", None),
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["nilai"] == 66.67
    assert [j["status_benar"] for j in body["jawaban"]] == [True, True, False]


def test_hitung_penilaian_tipe_tidak_dikenal_ditolak():
    r = client.post(
        "/hitung/penilaian",
        headers=HEADERS,
        json={"soal": [_lrv(1, "esai", 1, "A", "A")]},
    )
    assert r.status_code == 422


def test_hitung_penilaian_kosong_dan_kembar_ditolak():
    kosong = client.post("/hitung/penilaian", headers=HEADERS, json={"soal": []})
    assert kosong.status_code == 422
    kembar = client.post(
        "/hitung/penilaian",
        headers=HEADERS,
        json={
            "soal": [
                _lrv(1, "pilihan_ganda", 1, "A", "A"),
                _lrv(1, "pilihan_ganda", 1, "A", "A"),
            ]
        },
    )
    assert kembar.status_code == 422


def test_hitung_pretest_kontrak_laravel():
    r = client.post(
        "/hitung/pretest",
        headers=HEADERS,
        json={
            "soal": [
                _lrv(1, "pilihan_ganda", 1, "A", "A", 10),
                _lrv(2, "pilihan_ganda", 2, "A", "B", 10),
                _lrv(3, "isian", 3, "4", "4", 11),
            ],
            "materi": [
                {"materi_id": 10, "urutan": 1},
                {"materi_id": 11, "urutan": 2},
                {"materi_id": 12, "urutan": 3},
            ],
            "jumlah_materi_wajib": 2,
        },
    )
    assert r.status_code == 200
    body = r.json()
    # Nilai: bobot benar 1+3 dari total 6 → 66.67.
    assert body["nilai"] == 66.67
    assert body["jawaban"] == [
        {"soal_id": 1, "status_benar": True},
        {"soal_id": 2, "status_benar": False},
        {"soal_id": 3, "status_benar": True},
    ]
    # Tiap materi yang dikirim punya baris, termasuk yang tanpa soal.
    assert body["pemetaan"] == [
        {
            "materi_id": 10,
            "jumlah_soal": 2,
            "jumlah_benar": 1,
            "poin_didapat": 1,
            "poin_maksimal": 3,
            "persentase": 33.33,
            "peringkat": 1,
        },
        {
            "materi_id": 11,
            "jumlah_soal": 1,
            "jumlah_benar": 1,
            "poin_didapat": 3,
            "poin_maksimal": 3,
            "persentase": 100.0,
            "peringkat": 2,
        },
        {
            "materi_id": 12,
            "jumlah_soal": 0,
            "jumlah_benar": 0,
            "poin_didapat": 0,
            "poin_maksimal": 0,
            "persentase": 0.0,
            "peringkat": 3,
        },
    ]
    # Materi wajib = N pertama sesuai urutan permintaan.
    assert body["materi_wajib"] == [
        {"materi_id": 10, "prioritas": 1},
        {"materi_id": 11, "prioritas": 2},
    ]


def test_hitung_pretest_wajib_berlebih_ditolak():
    r = client.post(
        "/hitung/pretest",
        headers=HEADERS,
        json={
            "soal": [_lrv(1, "pilihan_ganda", 1, "A", "A", 10)],
            "materi": [{"materi_id": 10, "urutan": 1}],
            "jumlah_materi_wajib": 2,
        },
    )
    assert r.status_code == 422


def test_hitung_simulasi_kabupaten_gagal_di_bawah_70():
    soal = []
    for lvl, n, benar in (("mudah", 5, 4), ("sedang", 3, 2), ("sulit", 2, 1)):
        for i in range(n):
            soal.append(_soal(f"{lvl}{i}", lvl, "A", "A" if i < benar else "B", "m1"))
    r = client.post(
        "/hitung/simulasi", headers=HEADERS, json={"tingkat": "kabupaten", "soal": soal}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["skor"] == 64.71
    assert body["passing_grade"] == 70.0
    assert body["lulus"] is False


def test_hitung_simulasi_tingkat_tidak_dikenal_ditolak():
    r = client.post(
        "/hitung/simulasi",
        headers=HEADERS,
        json={"tingkat": "nasional", "soal": [_soal("a", "mudah", "A", "A", "m1")]},
    )
    assert r.status_code == 422


def test_hitung_latihan_skor_rendah_tidak_lulus_dan_akurasi_per_materi():
    r = client.post(
        "/hitung/latihan",
        headers=HEADERS,
        json={
            "soal": [
                _soal("1", "mudah", "A", "A", "rekursi"),
                _soal("2", "mudah", "A", "B", "rekursi"),
                _soal("3", "sulit", "A", "B", "dp"),
                _soal("4", "mudah", "A", "A", "dp"),
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["skor"] == 33.33  # bobot benar 2 dari 6
    assert body["lulus"] is False
    assert body["akurasi_per_materi"] == [
        {"materi_id": "dp", "akurasi": 25.0, "lulus": False},
        {"materi_id": "rekursi", "akurasi": 50.0, "lulus": True},
    ]


def test_hitung_latihan_tepat_50_lulus():
    r = client.post(
        "/hitung/latihan",
        headers=HEADERS,
        json={
            "soal": [
                _soal("1", "mudah", "A", "A", "m1"),
                _soal("2", "mudah", "A", "B", "m1"),
            ]
        },
    )
    assert r.json()["skor"] == 50.0
    assert r.json()["lulus"] is True


def test_hitung_latihan_49_99_tidak_lulus():
    soal = [
        _soal(f"s{i}", "sulit", "A", "A" if i < 1666 else "B", "m1")
        for i in range(3333)
    ] + [_soal("m", "mudah", "A", "A", "m1")]
    r = client.post("/hitung/latihan", headers=HEADERS, json={"soal": soal})
    assert r.json()["skor"] == 49.99
    assert r.json()["lulus"] is False


def test_hitung_latihan_threshold_kustom_dan_validasi():
    soal = [_soal("1", "mudah", "A", "A", "m1"), _soal("2", "mudah", "A", "B", "m1")]
    ok = client.post(
        "/hitung/latihan", headers=HEADERS, json={"soal": soal, "threshold": 50.01}
    )
    assert ok.json()["lulus"] is False
    bad = client.post(
        "/hitung/latihan", headers=HEADERS, json={"soal": soal, "threshold": 101}
    )
    assert bad.status_code == 422


def test_hitung_latihan_wajib_materi_id():
    r = client.post(
        "/hitung/latihan",
        headers=HEADERS,
        json={"soal": [_soal("1", "mudah", "A", "A")]},
    )
    assert r.status_code == 422


def test_hitung_simulasi_kabupaten_tepat_70_lulus():
    # 7 dari 10 soal mudah benar = 70 -> lulus kabupaten (inklusif).
    soal = [_soal(f"x{i}", "mudah", "A", "A" if i < 7 else "B", "m1") for i in range(10)]
    r = client.post(
        "/hitung/simulasi", headers=HEADERS, json={"tingkat": "kabupaten", "soal": soal}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["skor"] == 70.0
    assert body["passing_grade"] == 70.0
    assert body["lulus"] is True


def test_hitung_simulasi_provinsi_tepat_80_lulus():
    # 8 dari 10 soal mudah benar = 80 -> lulus provinsi (passing 80).
    soal = [_soal(f"x{i}", "mudah", "A", "A" if i < 8 else "B", "m1") for i in range(10)]
    r = client.post(
        "/hitung/simulasi", headers=HEADERS, json={"tingkat": "provinsi", "soal": soal}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["skor"] == 80.0
    assert body["passing_grade"] == 80.0
    assert body["lulus"] is True


def test_hitung_simulasi_provinsi_di_bawah_80_tidak_lulus():
    # 7 dari 10 soal mudah benar = 70 -> tidak lulus provinsi (passing 80).
    soal = [_soal(f"x{i}", "mudah", "A", "A" if i < 7 else "B", "m1") for i in range(10)]
    r = client.post(
        "/hitung/simulasi", headers=HEADERS, json={"tingkat": "provinsi", "soal": soal}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["skor"] == 70.0
    assert body["passing_grade"] == 80.0
    assert body["lulus"] is False
