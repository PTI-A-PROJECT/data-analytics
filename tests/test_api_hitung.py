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
