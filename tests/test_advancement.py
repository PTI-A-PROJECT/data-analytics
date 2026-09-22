from app.models.kenaikan_tingkat import AksesTingkatSiswa, RiwayatEvaluasiKenaikan


def test_akses_awal_siswa_baru(client, db):
    """
    Tiket 03: Siswa baru otomatis memiliki Kabupaten 'terbuka' (default_awal),
    sedangkan Provinsi dan Nasional 'terkunci'.
    """
    resp = client.get("/api/v1/tingkat/siswa/siswa-baru/akses")
    assert resp.status_code == 200
    data = resp.json()
    assert data["siswa_id"] == "siswa-baru"

    akses_list = {item["kode"]: item for item in data["daftar_akses"]}
    assert akses_list["KABUPATEN"]["status"] == "terbuka"
    assert akses_list["KABUPATEN"]["dibuka_karena"] == "default_awal"
    assert akses_list["PROVINSI"]["status"] == "terkunci"
    assert akses_list["NASIONAL"]["status"] == "terkunci"


def test_kelulusan_kenaikan_tingkat_simulasi(client, db):
    """
    Tiket 03:
    - Simulasi mencakup soal dari K1 (Soal 1, 2, 3) dan K2 (Soal 4).
    - Siswa menjawab benar semua soal (Skor = 100% >= 75%, K1 dan K2 berstatus Cukup -> 100% >= 80%).
    - Evaluasi harus 'lulus', membuka tingkat Provinsi secara permanen, dan mencatat audit log.
    """
    payload = {
        "siswa_id": "siswa-osn-01",
        "sekolah_id": "sch-01",
        "tingkat_seleksi_id": 1,
        "jenis_tes": "simulasi",
        "jawaban": [
            {"soal_id": 1, "jawaban_dipilih": "A", "durasi_detik": 40},
            {"soal_id": 2, "jawaban_dipilih": "B", "durasi_detik": 40},
            {"soal_id": 3, "jawaban_dipilih": "C", "durasi_detik": 20},
            {"soal_id": 4, "jawaban_dipilih": "D", "durasi_detik": 35},
        ],
    }

    resp = client.post("/api/v1/tes/submit", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    # Kenaikan tingkat terpicu
    kt = data["kenaikan_tingkat"]
    assert kt is not None
    assert kt["evaluasi_dilakukan"] is True
    assert kt["hasil_evaluasi"] == "lulus"
    assert kt["syarat_skor_lulus"] is True
    assert kt["syarat_kompetensi_lulus"] is True
    assert kt["tingkat_berikutnya_terbuka"] == "Tingkat Provinsi"

    # Periksa di database status akses
    prov_akses = (
        db.query(AksesTingkatSiswa)
        .filter(AksesTingkatSiswa.siswa_id == "siswa-osn-01", AksesTingkatSiswa.tingkat_seleksi_id == 2)
        .first()
    )
    assert prov_akses.status == "terbuka"
    assert prov_akses.dibuka_karena == "lulus_evaluasi"
    assert prov_akses.hasil_tes_id == data["hasil_tes_id"]

    # Periksa audit log di RiwayatEvaluasiKenaikan
    audit = (
        db.query(RiwayatEvaluasiKenaikan)
        .filter(RiwayatEvaluasiKenaikan.siswa_id == "siswa-osn-01")
        .first()
    )
    assert audit is not None
    assert audit.hasil_evaluasi == "lulus"
    assert audit.skor_aktual == 100.0


def test_gagal_naik_tingkat_karena_kompetensi_kurang(client, db):
    """
    Tiket 03:
    - Siswa mendapat skor 75% (3 benar dari 4 soal).
    - Namun soal yang salah ada di K2 (Soal 4 salah -> K2 Belum Cukup).
    - Hanya K1 yang Cukup (1 dari 2 kompetensi = 50% < target 80%).
    - Evaluasi harus 'tidak_lulus', Provinsi tetap terkunci.
    """
    payload = {
        "siswa_id": "siswa-osn-02",
        "sekolah_id": "sch-01",
        "tingkat_seleksi_id": 1,
        "jenis_tes": "simulasi",
        "jawaban": [
            {"soal_id": 1, "jawaban_dipilih": "A", "durasi_detik": 40},
            {"soal_id": 2, "jawaban_dipilih": "B", "durasi_detik": 40},
            {"soal_id": 3, "jawaban_dipilih": "C", "durasi_detik": 20},
            {"soal_id": 4, "jawaban_dipilih": "X", "durasi_detik": 35},  # salah!
        ],
    }

    resp = client.post("/api/v1/tes/submit", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    kt = data["kenaikan_tingkat"]
    assert kt["evaluasi_dilakukan"] is True
    assert kt["skor_aktual"] == 75.0
    assert kt["syarat_skor_lulus"] is True
    assert kt["persentase_cukup_aktual"] == 50.0  # 1 dari 2
    assert kt["syarat_kompetensi_lulus"] is False
    assert kt["hasil_evaluasi"] == "tidak_lulus"

    # Status Provinsi tetap terkunci
    prov_akses = (
        db.query(AksesTingkatSiswa)
        .filter(AksesTingkatSiswa.siswa_id == "siswa-osn-02", AksesTingkatSiswa.tingkat_seleksi_id == 2)
        .first()
    )
    assert prov_akses.status == "terkunci"


def test_akses_permanen_tidak_pernah_terkunci_kembali(client, db):
    """
    Tiket 03 (Once unlocked, always unlocked):
    - Siswa lolos ke Provinsi pada tes 1.
    - Pada tes 2 (simulasi berikutnya), nilai anjlok (skor = 25%).
    - Akses Provinsi harus TETAP berstatus 'terbuka'.
    """
    # Attempt 1: Lolos
    client.post(
        "/api/v1/tes/submit",
        json={
            "siswa_id": "siswa-permanen",
            "sekolah_id": "sch-01",
            "tingkat_seleksi_id": 1,
            "jenis_tes": "simulasi",
            "jawaban": [
                {"soal_id": 1, "jawaban_dipilih": "A", "durasi_detik": 40},
                {"soal_id": 2, "jawaban_dipilih": "B", "durasi_detik": 40},
                {"soal_id": 3, "jawaban_dipilih": "C", "durasi_detik": 20},
                {"soal_id": 4, "jawaban_dipilih": "D", "durasi_detik": 35},
            ],
        },
    )

    # Attempt 2: Nilai anjlok
    client.post(
        "/api/v1/tes/submit",
        json={
            "siswa_id": "siswa-permanen",
            "sekolah_id": "sch-01",
            "tingkat_seleksi_id": 1,
            "jenis_tes": "simulasi",
            "jawaban": [
                {"soal_id": 1, "jawaban_dipilih": "A", "durasi_detik": 40},
                {"soal_id": 2, "jawaban_dipilih": "X", "durasi_detik": 40},
                {"soal_id": 3, "jawaban_dipilih": "X", "durasi_detik": 20},
                {"soal_id": 4, "jawaban_dipilih": "X", "durasi_detik": 35},
            ],
        },
    )

    # Periksa status akses di database
    prov_akses = (
        db.query(AksesTingkatSiswa)
        .filter(AksesTingkatSiswa.siswa_id == "siswa-permanen", AksesTingkatSiswa.tingkat_seleksi_id == 2)
        .first()
    )
    assert prov_akses.status == "terbuka"


def test_manual_override_super_admin(client, db):
    """
    Tiket 03: Super Admin dapat memberikan akses manual langsung (manual_admin)
    ke tingkat berikutnya.
    """
    resp = client.post(
        "/api/v1/tingkat/admin/override",
        json={
            "siswa_id": "siswa-bintang",
            "tingkat_seleksi_id": 3,  # Langsung buka Nasional
            "status": "terbuka",
            "catatan": "Juara 1 OSN Tingkat Provinsi",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tingkat_seleksi_id"] == 3
    assert data["status"] == "terbuka"
    assert data["dibuka_karena"] == "manual_admin"
    assert data["catatan"] == "Juara 1 OSN Tingkat Provinsi"


def test_advancement_nasional_no_next_tier(client, db):
    """
    Tiket 03: Siswa yang mengerjakan simulasi di tingkat Nasional (urutan 3/puncak)
    tidak memicu evaluasi kenaikan tingkat lanjutan (evaluasi_dilakukan = False).
    """
    payload = {
        "siswa_id": "siswa-nasional",
        "sekolah_id": "sch-01",
        "tingkat_seleksi_id": 3,
        "jenis_tes": "simulasi",
        "jawaban": [],
    }
    resp = client.post("/api/v1/tes/submit", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["kenaikan_tingkat"]["evaluasi_dilakukan"] is False


def test_crud_aturan_kenaikan_super_admin(client, db):
    """
    Tiket 03: Super Admin dapat melihat dan mengubah ambang batas aturan kenaikan tingkat.
    """
    # 1. Get semua aturan
    resp_get = client.get("/api/v1/tingkat/admin/aturan")
    assert resp_get.status_code == 200
    aturan_list = resp_get.json()
    assert len(aturan_list) >= 2

    # 2. Update aturan id=1 (Kabupaten -> Provinsi)
    payload_update = {
        "skor_simulasi_min": 80.0,
        "persentase_kompetensi_cukup_min": 85.0,
    }
    resp_put = client.put("/api/v1/tingkat/admin/aturan/1", json=payload_update)
    assert resp_put.status_code == 200
    updated = resp_put.json()
    assert updated["skor_simulasi_min"] == 80.0
    assert updated["persentase_kompetensi_cukup_min"] == 85.0
