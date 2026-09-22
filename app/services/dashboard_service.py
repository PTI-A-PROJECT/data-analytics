from typing import Optional, List, Dict
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case
from app.models.master import TingkatSeleksi, Kompetensi, Subkompetensi, Soal
from app.models.hasil_tes import HasilTes, HasilTesSubkompetensi, JawabanSiswa
from app.models.kenaikan_tingkat import AksesTingkatSiswa, RiwayatEvaluasiKenaikan
from app.schemas.dashboard import (
    DashboardResponse,
    DashboardFilter,
    DashboardKPI,
    DistribusiTingkatItem,
    TrenAktivitasItem,
    DistribusiPredikatItem,
    AnalisisKompetensiItem,
    AnalisisKompetensiResponse,
    KomparasiSekolahItem,
)


def hitung_metrik_dashboard(
    db: Session,
    sekolah_id: Optional[str] = None,
    tingkat_seleksi_id: Optional[int] = None,
    rentang_waktu: str = "30d",
) -> DashboardResponse:
    """Menghitung metrik dashboard Super Admin secara real-time (Tiket 04)."""
    now = datetime.now(timezone.utc)
    date_threshold = None
    if rentang_waktu == "7d":
        date_threshold = now - timedelta(days=7)
    elif rentang_waktu == "30d":
        date_threshold = now - timedelta(days=30)
    elif rentang_waktu == "90d":
        date_threshold = now - timedelta(days=90)

    # Base query HasilTes
    ht_query = db.query(HasilTes)
    if sekolah_id:
        ht_query = ht_query.filter(HasilTes.sekolah_id == sekolah_id)
    if tingkat_seleksi_id:
        ht_query = ht_query.filter(HasilTes.tingkat_seleksi_id == tingkat_seleksi_id)
    if date_threshold:
        ht_query = ht_query.filter(HasilTes.diselesaikan_pada >= date_threshold)

    hasil_tes_records = ht_query.all()
    hasil_tes_ids = [ht.id for ht in hasil_tes_records]

    # 1. KPI Utama
    total_siswa_aktif = len(set(ht.siswa_id for ht in hasil_tes_records))
    total_tes_selesai = len(hasil_tes_records)
    total_pre_test = sum(1 for ht in hasil_tes_records if ht.jenis_tes == "pre_test")
    simulasi_records = [ht for ht in hasil_tes_records if ht.jenis_tes == "simulasi"]
    total_simulasi = len(simulasi_records)
    rata_skor_sim = (
        round(sum(ht.skor for ht in simulasi_records) / total_simulasi, 2)
        if total_simulasi > 0
        else 0.0
    )

    # Rasio kelulusan tingkat
    eval_query = db.query(RiwayatEvaluasiKenaikan)
    if hasil_tes_ids:
        eval_query = eval_query.filter(RiwayatEvaluasiKenaikan.hasil_tes_id.in_(hasil_tes_ids))
    eval_records = eval_query.all() if hasil_tes_ids else []
    total_eval = len(eval_records)
    total_lulus = sum(1 for e in eval_records if e.hasil_evaluasi == "lulus")
    rasio_kelulusan = round((total_lulus / total_eval) * 100.0, 2) if total_eval > 0 else 0.0

    kpi = DashboardKPI(
        total_siswa_aktif=total_siswa_aktif,
        total_tes_selesai=total_tes_selesai,
        total_pre_test=total_pre_test,
        total_simulasi=total_simulasi,
        rata_rata_skor_simulasi=rata_skor_sim,
        rasio_kelulusan_tingkat=rasio_kelulusan,
    )

    # 2. Distribusi Tingkat Siswa (Lifetime state dari AksesTingkatSiswa)
    # Tentukan tingkat tertinggi yang terbuka per siswa
    akses_query = db.query(AksesTingkatSiswa, TingkatSeleksi).join(
        TingkatSeleksi, AksesTingkatSiswa.tingkat_seleksi_id == TingkatSeleksi.id
    ).filter(AksesTingkatSiswa.status == "terbuka")

    # Jika ada filter sekolah, ambil hanya siswa_id yang pernah beraktivitas di sekolah tersebut
    if sekolah_id:
        siswa_sekolah = set(ht.siswa_id for ht in db.query(HasilTes.siswa_id).filter(HasilTes.sekolah_id == sekolah_id).all())
        akses_query = akses_query.filter(AksesTingkatSiswa.siswa_id.in_(siswa_sekolah))

    siswa_highest_tier: Dict[str, TingkatSeleksi] = {}
    for akses, tingkat in akses_query.all():
        curr = siswa_highest_tier.get(akses.siswa_id)
        if not curr or tingkat.urutan > curr.urutan:
            siswa_highest_tier[akses.siswa_id] = tingkat

    tier_counts: Dict[int, int] = {}
    for t in db.query(TingkatSeleksi).all():
        tier_counts[t.id] = 0

    for tingkat in siswa_highest_tier.values():
        tier_counts[tingkat.id] = tier_counts.get(tingkat.id, 0) + 1

    total_populasi_siswa = len(siswa_highest_tier)
    distribusi_tingkat: List[DistribusiTingkatItem] = []
    for t in db.query(TingkatSeleksi).order_by(TingkatSeleksi.urutan).all():
        cnt = tier_counts.get(t.id, 0)
        pct = round((cnt / total_populasi_siswa) * 100.0, 2) if total_populasi_siswa > 0 else 0.0
        distribusi_tingkat.append(
            DistribusiTingkatItem(
                tingkat_id=t.id,
                nama=t.nama,
                jumlah_siswa=cnt,
                persentase=pct,
            )
        )

    # 3. Tren Aktivitas Pengerjaan (Harian)
    date_counts: Dict[str, Dict[str, int]] = {}
    for ht in hasil_tes_records:
        tgl_str = ht.diselesaikan_pada.strftime("%Y-%m-%d")
        counts = date_counts.setdefault(tgl_str, {"pre_test": 0, "simulasi": 0})
        if ht.jenis_tes == "pre_test":
            counts["pre_test"] += 1
        elif ht.jenis_tes == "simulasi":
            counts["simulasi"] += 1

    tren_aktivitas: List[TrenAktivitasItem] = [
        TrenAktivitasItem(tanggal=tgl, pre_test=v["pre_test"], simulasi=v["simulasi"])
        for tgl, v in sorted(date_counts.items())
    ]

    # 4. Distribusi Predikat Simulasi
    predikat_counts: Dict[str, int] = {
        "Sangat Baik": 0,
        "Baik": 0,
        "Cukup": 0,
        "Perlu Latihan": 0,
    }
    for ht in simulasi_records:
        if ht.predikat_label in predikat_counts:
            predikat_counts[ht.predikat_label] += 1
        else:
            predikat_counts[ht.predikat_label] = 1

    distribusi_predikat: List[DistribusiPredikatItem] = []
    for label, cnt in predikat_counts.items():
        pct = round((cnt / total_simulasi) * 100.0, 2) if total_simulasi > 0 else 0.0
        distribusi_predikat.append(
            DistribusiPredikatItem(label=label, jumlah=cnt, persentase=pct)
        )

    # 5. Analisis Penguasaan Kompetensi (Termasuk Kecepatan Pengerjaan - Tiket 05)
    komp_stats: Dict[int, Dict[str, Any]] = {}
    if hasil_tes_ids:
        subkomp_rows = (
            db.query(
                HasilTesSubkompetensi.subkompetensi_id,
                HasilTesSubkompetensi.jumlah_soal,
                HasilTesSubkompetensi.jumlah_benar,
                Subkompetensi.kompetensi_id,
                Kompetensi.nama.label("kompetensi_nama"),
            )
            .join(Subkompetensi, HasilTesSubkompetensi.subkompetensi_id == Subkompetensi.id)
            .join(Kompetensi, Subkompetensi.kompetensi_id == Kompetensi.id)
            .filter(HasilTesSubkompetensi.hasil_tes_id.in_(hasil_tes_ids))
            .all()
        )

        for row in subkomp_rows:
            stats = komp_stats.setdefault(
                row.kompetensi_id,
                {"nama": row.kompetensi_nama, "total_soal": 0, "total_benar": 0},
            )
            stats["total_soal"] += row.jumlah_soal
            stats["total_benar"] += row.jumlah_benar

    kompetensi_items: List[AnalisisKompetensiItem] = []
    for k_id, stats in komp_stats.items():
        t_soal = stats["total_soal"]
        t_benar = stats["total_benar"]
        rata_skor = round((t_benar / t_soal) * 100.0, 2) if t_soal > 0 else 0.0
        kompetensi_items.append(
            AnalisisKompetensiItem(
                kompetensi_id=k_id,
                nama=stats["nama"],
                rata_rata_skor=rata_skor,
                total_soal_dikerjakan=t_soal,
            )
        )

    sorted_by_score = sorted(kompetensi_items, key=lambda x: x.rata_rata_skor, reverse=True)
    terkuat = sorted_by_score[:3]
    terlemah = sorted(sorted_by_score[-3:], key=lambda x: x.rata_rata_skor)

    # 6. Komparasi Sekolah (Tiket 08)
    sekolah_stats: Dict[str, Dict[str, Any]] = {}
    all_school_ht = db.query(HasilTes).all()
    for ht in all_school_ht:
        sch_id = ht.sekolah_id or "unassigned"
        stats = sekolah_stats.setdefault(
            sch_id,
            {"siswa_ids": set(), "simulasi_scores": [], "eval_lulus": 0, "eval_total": 0},
        )
        stats["siswa_ids"].add(ht.siswa_id)
        if ht.jenis_tes == "simulasi":
            stats["simulasi_scores"].append(ht.skor)

    # Ambil audit kenaikan per sekolah
    all_evals = (
        db.query(RiwayatEvaluasiKenaikan.hasil_evaluasi, HasilTes.sekolah_id)
        .join(HasilTes, RiwayatEvaluasiKenaikan.hasil_tes_id == HasilTes.id)
        .all()
    )
    for res, sch in all_evals:
        sch_key = sch or "unassigned"
        if sch_key in sekolah_stats:
            sekolah_stats[sch_key]["eval_total"] += 1
            if res == "lulus":
                sekolah_stats[sch_key]["eval_lulus"] += 1

    komparasi_sekolah: List[KomparasiSekolahItem] = []
    for s_id, s_data in sekolah_stats.items():
        sim_scores = s_data["simulasi_scores"]
        tot_sim = len(sim_scores)
        avg_score = round(sum(sim_scores) / tot_sim, 2) if tot_sim > 0 else 0.0
        e_tot = s_data["eval_total"]
        e_lul = s_data["eval_lulus"]
        pass_ratio = round((e_lul / e_tot) * 100.0, 2) if e_tot > 0 else 0.0

        komparasi_sekolah.append(
            KomparasiSekolahItem(
                sekolah_id=s_id,
                total_siswa_aktif=len(s_data["siswa_ids"]),
                total_simulasi=tot_sim,
                rata_rata_skor=avg_score,
                rasio_kelulusan_tingkat=pass_ratio,
            )
        )

    return DashboardResponse(
        rentang_waktu=rentang_waktu,
        filter=DashboardFilter(
            sekolah_id=sekolah_id,
            tingkat_seleksi_id=tingkat_seleksi_id,
            rentang_waktu=rentang_waktu,
        ),
        kpi=kpi,
        distribusi_tingkat=distribusi_tingkat,
        tren_aktivitas=tren_aktivitas,
        distribusi_predikat=distribusi_predikat,
        analisis_kompetensi=AnalisisKompetensiResponse(terkuat=terkuat, terlemah=terlemah),
        komparasi_sekolah=komparasi_sekolah,
    )
