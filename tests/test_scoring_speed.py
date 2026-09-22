from app.models.hasil_tes import JawabanSiswa, HasilTes


def test_kecepatan_pengerjaan_dan_is_lambat(client, db):
    """
    Tiket 05:
    - Soal 1: batas_waktu = 60s. Siswa mengerjakan dalam 75s -> is_lambat = True.
    - Soal 2: batas_waktu = 60s. Siswa mengerjakan dalam 40s -> is_lambat = False.
    """
    payload = {
        "siswa_id": "siswa-01",
        "sekolah_id": "sch-01",
        "tingkat_seleksi_id": 1,
        "jenis_tes": "pre_test",
        "jawaban": [
            {"soal_id": 1, "jawaban_dipilih": "A", "durasi_detik": 75},
            {"soal_id": 2, "jawaban_dipilih": "B", "durasi_detik": 40},
        ],
    }

    response = client.post("/api/v1/tes/submit", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["total_soal"] == 2
    assert data["jumlah_benar"] == 2
    assert data["skor"] == 100.0

    # Cek di database pada tabel jawaban_siswa
    hasil_id = data["hasil_tes_id"]
    jawaban_rows = db.query(JawabanSiswa).filter(JawabanSiswa.hasil_tes_id == hasil_id).order_by(JawabanSiswa.soal_id).all()
    assert len(jawaban_rows) == 2

    # Soal 1 (75s > 60s) -> is_lambat = True
    assert jawaban_rows[0].soal_id == 1
    assert jawaban_rows[0].is_benar is True
    assert jawaban_rows[0].durasi_detik == 75
    assert jawaban_rows[0].is_lambat is True

    # Soal 2 (40s <= 60s) -> is_lambat = False
    assert jawaban_rows[1].soal_id == 2
    assert jawaban_rows[1].is_benar is True
    assert jawaban_rows[1].durasi_detik == 40
    assert jawaban_rows[1].is_lambat is False


def test_flag_butuh_optimasi_peta_kompetensi(client, db):
    """
    Tiket 05:
    - SK1 (Looping) memiliki 2 soal (Soal 1 & Soal 2).
    - Siswa menjawab benar kedua soal (100% correct -> status 'Cukup').
    - Namun, 1 dari 2 jawaban benar dikerjakan lambat (rasio lambat = 1/2 = 50% >= 50%).
    - Flag 'butuh_optimasi' harus bernilai True!
    - Status tetap 'Cukup' (ramah motivasi, tidak menggagalkan penguasaan).
    """
    payload = {
        "siswa_id": "siswa-02",
        "sekolah_id": "sch-01",
        "tingkat_seleksi_id": 1,
        "jenis_tes": "pre_test",
        "jawaban": [
            {"soal_id": 1, "jawaban_dipilih": "A", "durasi_detik": 80},  # benar, lambat (80 > 60)
            {"soal_id": 2, "jawaban_dipilih": "B", "durasi_detik": 45},  # benar, cepat (45 <= 60)
        ],
    }

    response = client.post("/api/v1/tes/submit", json=payload)
    assert response.status_code == 201
    data = response.json()

    peta = data["peta_kompetensi"]
    # Cari Subkompetensi SK1 (Looping) di dalam K1
    k1 = next(k for k in peta if k["kompetensi_id"] == 1)
    sk1 = next(sk for sk in k1["subkompetensi"] if sk["subkompetensi_id"] == 1)

    assert sk1["status"] == "Cukup"
    assert sk1["jumlah_soal"] == 2
    assert sk1["total_jawaban_benar"] == 2
    assert sk1["total_benar_lambat"] == 1
    assert sk1["butuh_optimasi"] is True


def test_subkompetensi_cukup_tanpa_butuh_optimasi(client, db):
    """
    Tiket 05:
    - SK1 dijawab benar semua dan semua pengerjaan cepat (< batas waktu).
    - rasio lambat = 0% < 50% -> butuh_optimasi = False.
    """
    payload = {
        "siswa_id": "siswa-03",
        "sekolah_id": "sch-01",
        "tingkat_seleksi_id": 1,
        "jenis_tes": "pre_test",
        "jawaban": [
            {"soal_id": 1, "jawaban_dipilih": "A", "durasi_detik": 30},  # benar, cepat
            {"soal_id": 2, "jawaban_dipilih": "B", "durasi_detik": 25},  # benar, cepat
        ],
    }

    response = client.post("/api/v1/tes/submit", json=payload)
    assert response.status_code == 201
    data = response.json()

    peta = data["peta_kompetensi"]
    k1 = next(k for k in peta if k["kompetensi_id"] == 1)
    sk1 = next(sk for sk in k1["subkompetensi"] if sk["subkompetensi_id"] == 1)

    assert sk1["status"] == "Cukup"
    assert sk1["total_benar_lambat"] == 0
    assert sk1["butuh_optimasi"] is False

