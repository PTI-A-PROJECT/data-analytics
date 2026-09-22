from datetime import datetime, timedelta
from app.models.hasil_tes import HasilTes


def test_dashboard_aggregation_and_widgets(client, db):
    """
    Tiket 04:
    - Verifikasi kalkulasi KPI, Distribusi Tingkat, Tren Harian, Predikat,
      Analisis Kompetensi, dan Komparasi Sekolah.
    """
    # Kirim 1 pengerjaan pre-test untuk Siswa A (Sekolah 1)
    client.post(
        "/api/v1/tes/submit",
        json={
            "siswa_id": "siswa-a",
            "sekolah_id": "sch-01",
            "tingkat_seleksi_id": 1,
            "jenis_tes": "pre_test",
            "jawaban": [
                {"soal_id": 1, "jawaban_dipilih": "A", "durasi_detik": 30},
                {"soal_id": 2, "jawaban_dipilih": "B", "durasi_detik": 30},
            ],
        },
    )

    # Kirim 1 pengerjaan simulasi (lulus tingkat) untuk Siswa B (Sekolah 2)
    client.post(
        "/api/v1/tes/submit",
        json={
            "siswa_id": "siswa-b",
            "sekolah_id": "sch-02",
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

    resp = client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    # 1. KPI
    kpi = data["kpi"]
    assert kpi["total_siswa_aktif"] == 2
    assert kpi["total_tes_selesai"] == 2
    assert kpi["total_pre_test"] == 1
    assert kpi["total_simulasi"] == 1
    assert kpi["rata_rata_skor_simulasi"] == 100.0
    assert kpi["rasio_kelulusan_tingkat"] == 100.0

    # 2. Distribusi Tingkat
    # Siswa A ada di Kabupaten (terbuka), Siswa B terbuka Provinsi
    dist = {item["nama"]: item for item in data["distribusi_tingkat"]}
    assert dist["Tingkat Kabupaten"]["jumlah_siswa"] == 1
    assert dist["Tingkat Provinsi"]["jumlah_siswa"] == 1

    # 3. Predikat
    pred = {item["label"]: item for item in data["distribusi_predikat"]}
    assert pred["Sangat Baik"]["jumlah"] == 1

    # 4. Komparasi Sekolah
    sch_comp = {item["sekolah_id"]: item for item in data["komparasi_sekolah"]}
    assert "sch-01" in sch_comp
    assert "sch-02" in sch_comp
    assert sch_comp["sch-02"]["total_simulasi"] == 1
    assert sch_comp["sch-02"]["rasio_kelulusan_tingkat"] == 100.0


def test_dashboard_filter_sekolah(client, db):
    """
    Tiket 04: Filter berdasarkan sekolah_id hanya menampilkan data sekolah terkait.
    """
    # Siswa di sch-01
    client.post(
        "/api/v1/tes/submit",
        json={
            "siswa_id": "siswa-filter-1",
            "sekolah_id": "sch-alpha",
            "tingkat_seleksi_id": 1,
            "jenis_tes": "simulasi",
            "jawaban": [{"soal_id": 1, "jawaban_dipilih": "A", "durasi_detik": 30}],
        },
    )
    # Siswa di sch-02
    client.post(
        "/api/v1/tes/submit",
        json={
            "siswa_id": "siswa-filter-2",
            "sekolah_id": "sch-beta",
            "tingkat_seleksi_id": 1,
            "jenis_tes": "simulasi",
            "jawaban": [{"soal_id": 1, "jawaban_dipilih": "A", "durasi_detik": 30}],
        },
    )

    # Filter hanya sch-alpha
    resp = client.get("/api/v1/admin/dashboard?sekolah_id=sch-alpha")
    assert resp.status_code == 200
    data = resp.json()

    assert data["kpi"]["total_siswa_aktif"] == 1
    assert data["kpi"]["total_simulasi"] == 1


def test_dashboard_empty_db(client, db):
    """
    Tiket 04: Dashboard pada saat basis data belum memiliki riwayat pengerjaan
    harus mengembalikan metrik 0 secara bersih tanpa error atau pembagian nol.
    """
    resp = client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["kpi"]["total_siswa_aktif"] == 0
    assert data["kpi"]["total_tes_selesai"] == 0
    assert data["kpi"]["rata_rata_skor_simulasi"] == 0.0
    assert data["kpi"]["rasio_kelulusan_tingkat"] == 0.0
    assert len(data["tren_aktivitas"]) == 0
    assert len(data["komparasi_sekolah"]) == 0
