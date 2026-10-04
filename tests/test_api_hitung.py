from fastapi.testclient import TestClient

from data_analytics.api import app

client = TestClient(app)


def _soal(i, level, kunci, jawaban, materi=None):
    return {
        "soal_id": i,
        "level": level,
        "kunci": kunci,
        "jawaban": jawaban,
        "materi_id": materi,
    }


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_hitung_penilaian_dengan_predikat():
    r = client.post(
        "/hitung/penilaian",
        json={
            "soal": [_soal("a", "mudah", "A", "B"), _soal("b", "sedang", "A", "A")],
            "aturan_predikat": [
                {"label": "Dasar", "batas_bawah": 0},
                {"label": "Baik", "batas_bawah": 60},
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["skor"] == 66.67
    assert body["predikat"] == "Baik"
    assert [h["benar"] for h in body["hasil_soal"]] == [False, True]


def test_level_menengah_lama_ditolak():
    r = client.post(
        "/hitung/penilaian",
        json={"soal": [_soal("a", "menengah", "A", "A")]},
    )
    assert r.status_code == 422


def test_aturan_predikat_tanpa_nol_ditolak():
    r = client.post(
        "/hitung/penilaian",
        json={
            "soal": [_soal("a", "mudah", "A", "A")],
            "aturan_predikat": [{"label": "Baik", "batas_bawah": 50}],
        },
    )
    assert r.status_code == 422


def test_hitung_pretest_mengembalikan_pemetaan():
    r = client.post(
        "/hitung/pretest",
        json={
            "soal": [
                _soal("1", "mudah", "A", "A", "m1"),
                _soal("2", "sulit", "A", "B", "m2"),
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["materi_lemah"] == ["m2"]
    status = {p["materi_id"]: p["status"] for p in body["pemetaan"]}
    assert status == {"m1": "kuat", "m2": "belum_cukup"}


def test_hitung_pretest_wajib_materi_id():
    r = client.post(
        "/hitung/pretest", json={"soal": [_soal("1", "mudah", "A", "A")]}
    )
    assert r.status_code == 422


def test_hitung_simulasi_kabupaten_gagal_di_bawah_70():
    soal = []
    for lvl, n, benar in (("mudah", 5, 4), ("sedang", 3, 2), ("sulit", 2, 1)):
        for i in range(n):
            soal.append(_soal(f"{lvl}{i}", lvl, "A", "A" if i < benar else "B", "m1"))
    r = client.post("/hitung/simulasi", json={"tingkat": "kabupaten", "soal": soal})
    assert r.status_code == 200
    body = r.json()
    assert body["skor"] == 64.71
    assert body["passing_grade"] == 70.0
    assert body["lulus"] is False


def test_hitung_simulasi_tingkat_tidak_dikenal_ditolak():
    r = client.post(
        "/hitung/simulasi",
        json={"tingkat": "nasional", "soal": [_soal("a", "mudah", "A", "A", "m1")]},
    )
    assert r.status_code == 422


def test_hitung_latihan_skor_rendah_tidak_lulus_dan_akurasi_per_materi():
    r = client.post(
        "/hitung/latihan",
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
    r = client.post("/hitung/latihan", json={"soal": soal})
    assert r.json()["skor"] == 49.99
    assert r.json()["lulus"] is False


def test_hitung_latihan_threshold_kustom_dan_validasi():
    soal = [_soal("1", "mudah", "A", "A", "m1"), _soal("2", "mudah", "A", "B", "m1")]
    ok = client.post("/hitung/latihan", json={"soal": soal, "threshold": 50.01})
    assert ok.json()["lulus"] is False
    bad = client.post("/hitung/latihan", json={"soal": soal, "threshold": 101})
    assert bad.status_code == 422


def test_hitung_latihan_wajib_materi_id():
    r = client.post("/hitung/latihan", json={"soal": [_soal("1", "mudah", "A", "A")]})
    assert r.status_code == 422



def test_hitung_simulasi_kabupaten_tepat_70_lulus():
    # 7 dari 10 soal mudah benar = 70 -> lulus kabupaten (inklusif).
    soal = [_soal(f"x{i}", "mudah", "A", "A" if i < 7 else "B", "m1") for i in range(10)]
    r = client.post("/hitung/simulasi", json={"tingkat": "kabupaten", "soal": soal})
    assert r.status_code == 200
    body = r.json()
    assert body["skor"] == 70.0
    assert body["passing_grade"] == 70.0
    assert body["lulus"] is True


def test_hitung_simulasi_provinsi_tepat_80_lulus():
    # 8 dari 10 soal mudah benar = 80 -> lulus provinsi (inklusif).
    soal = [_soal(f"x{i}", "mudah", "A", "A" if i < 8 else "B", "m1") for i in range(10)]
    r = client.post("/hitung/simulasi", json={"tingkat": "provinsi", "soal": soal})
    assert r.status_code == 200
    body = r.json()
    assert body["skor"] == 80.0
    assert body["passing_grade"] == 80.0
    assert body["lulus"] is True


def test_hitung_simulasi_provinsi_di_bawah_80_tidak_lulus():
    # 7 dari 10 soal mudah benar = 70 -> tidak lulus provinsi (passing 80).
    soal = [_soal(f"x{i}", "mudah", "A", "A" if i < 7 else "B", "m1") for i in range(10)]
    r = client.post("/hitung/simulasi", json={"tingkat": "provinsi", "soal": soal})
    assert r.status_code == 200
    body = r.json()
    assert body["skor"] == 70.0
    assert body["passing_grade"] == 80.0
    assert body["lulus"] is False
    