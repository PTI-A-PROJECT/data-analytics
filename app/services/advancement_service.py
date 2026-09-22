from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.master import TingkatSeleksi, Kompetensi
from app.models.kenaikan_tingkat import AturanKenaikanTingkat, AksesTingkatSiswa, RiwayatEvaluasiKenaikan
from app.schemas.tes import KompetensiMapItem, KenaikanTingkatDetail


def inisialisasi_akses_siswa(db: Session, siswa_id: str) -> None:
    """
    Memastikan siswa baru memiliki entri akses tingkat:
    - Tingkat urutan 1 (Kabupaten) berstatus 'terbuka' (default_awal)
    - Tingkat urutan > 1 (Provinsi, Nasional) berstatus 'terkunci'
    """
    tingkat_list = db.query(TingkatSeleksi).order_by(TingkatSeleksi.urutan).all()
    for t in tingkat_list:
        existing = (
            db.query(AksesTingkatSiswa)
            .filter(
                AksesTingkatSiswa.siswa_id == siswa_id,
                AksesTingkatSiswa.tingkat_seleksi_id == t.id,
            )
            .first()
        )
        if not existing:
            status = "terbuka" if t.urutan == 1 else "terkunci"
            dibuka_karena = "default_awal" if t.urutan == 1 else None
            dibuka_pada = datetime.now(timezone.utc) if t.urutan == 1 else None
            akses = AksesTingkatSiswa(
                siswa_id=siswa_id,
                tingkat_seleksi_id=t.id,
                status=status,
                dibuka_karena=dibuka_karena,
                dibuka_pada=dibuka_pada,
            )
            db.add(akses)
    db.commit()


def evaluasi_kenaikan_tingkat(
    db: Session,
    siswa_id: str,
    hasil_tes_id: int,
    tingkat_seleksi_id: int,
    skor: float,
    peta_kompetensi: List[KompetensiMapItem],
) -> KenaikanTingkatDetail:
    """
    Evaluasi kelayakan kenaikan tingkat (Tiket 03):
    1. Periksa apakah ada aturan transisi dari tingkat ini ke tingkat berikutnya.
    2. Cek skor simulasi >= aturan.skor_simulasi_min.
    3. Cek persentase kompetensi Cukup >= aturan.persentase_kompetensi_cukup_min
       (dihitung terhadap total silabus kompetensi pada tingkat tersebut).
    4. Simpan log audit ke RiwayatEvaluasiKenaikan.
    5. Jika lulus, buka akses tingkat tujuan secara permanen di AksesTingkatSiswa.
    """
    # Pastikan entri akses siswa sudah terinisialisasi
    inisialisasi_akses_siswa(db, siswa_id)

    aturan = (
        db.query(AturanKenaikanTingkat)
        .filter(
            AturanKenaikanTingkat.tingkat_asal_id == tingkat_seleksi_id,
            AturanKenaikanTingkat.aktif == True,  # noqa: E712
        )
        .first()
    )

    if not aturan:
        # Tidak ada tingkat lanjutan (misal sudah di Nasional)
        return KenaikanTingkatDetail(evaluasi_dilakukan=False)

    # Hitung syarat skor
    syarat_skor_lulus = skor >= aturan.skor_simulasi_min

    # Hitung syarat penguasaan kompetensi
    total_kompetensi_silabus = (
        db.query(Kompetensi)
        .filter(Kompetensi.tingkat_seleksi_id == tingkat_seleksi_id)
        .count()
    )
    jumlah_cukup = sum(1 for k in peta_kompetensi if k.status == "Cukup")
    persentase_cukup = (
        round((jumlah_cukup / total_kompetensi_silabus) * 100.0, 2)
        if total_kompetensi_silabus > 0
        else 0.0
    )
    syarat_kompetensi_lulus = persentase_cukup >= aturan.persentase_kompetensi_cukup_min

    is_lulus = syarat_skor_lulus and syarat_kompetensi_lulus
    hasil_evaluasi = "lulus" if is_lulus else "tidak_lulus"

    # Simpan audit log
    riwayat = RiwayatEvaluasiKenaikan(
        siswa_id=siswa_id,
        hasil_tes_id=hasil_tes_id,
        aturan_kenaikan_id=aturan.id,
        skor_aktual=skor,
        skor_target=aturan.skor_simulasi_min,
        syarat_skor_lulus=syarat_skor_lulus,
        persentase_cukup_aktual=persentase_cukup,
        persentase_cukup_target=aturan.persentase_kompetensi_cukup_min,
        syarat_kompetensi_lulus=syarat_kompetensi_lulus,
        hasil_evaluasi=hasil_evaluasi,
        dievaluasi_pada=datetime.now(timezone.utc),
    )
    db.add(riwayat)

    tingkat_tujuan_nama = None
    if is_lulus:
        # Buka tingkat tujuan secara permanen
        akses_tujuan = (
            db.query(AksesTingkatSiswa)
            .filter(
                AksesTingkatSiswa.siswa_id == siswa_id,
                AksesTingkatSiswa.tingkat_seleksi_id == aturan.tingkat_tujuan_id,
            )
            .first()
        )
        if akses_tujuan:
            # Jika belum terbuka, update jadi terbuka
            if akses_tujuan.status != "terbuka":
                akses_tujuan.status = "terbuka"
                akses_tujuan.dibuka_karena = "lulus_evaluasi"
                akses_tujuan.hasil_tes_id = hasil_tes_id
                akses_tujuan.dibuka_pada = datetime.now(timezone.utc)
        else:
            akses_tujuan = AksesTingkatSiswa(
                siswa_id=siswa_id,
                tingkat_seleksi_id=aturan.tingkat_tujuan_id,
                status="terbuka",
                dibuka_karena="lulus_evaluasi",
                hasil_tes_id=hasil_tes_id,
                dibuka_pada=datetime.now(timezone.utc),
            )
            db.add(akses_tujuan)

        tingkat_tujuan = db.get(TingkatSeleksi, aturan.tingkat_tujuan_id)
        if tingkat_tujuan:
            tingkat_tujuan_nama = tingkat_tujuan.nama

    db.commit()

    return KenaikanTingkatDetail(
        evaluasi_dilakukan=True,
        hasil_evaluasi=hasil_evaluasi,
        skor_aktual=skor,
        skor_target=aturan.skor_simulasi_min,
        syarat_skor_lulus=syarat_skor_lulus,
        persentase_cukup_aktual=persentase_cukup,
        persentase_cukup_target=aturan.persentase_kompetensi_cukup_min,
        syarat_kompetensi_lulus=syarat_kompetensi_lulus,
        tingkat_berikutnya_terbuka=tingkat_tujuan_nama,
    )


def override_akses_admin(
    db: Session,
    siswa_id: str,
    tingkat_seleksi_id: int,
    status: str = "terbuka",
    catatan: Optional[str] = None,
) -> AksesTingkatSiswa:
    """Override manual akses tingkat siswa oleh Super Admin (FR-17)."""
    akses = (
        db.query(AksesTingkatSiswa)
        .filter(
            AksesTingkatSiswa.siswa_id == siswa_id,
            AksesTingkatSiswa.tingkat_seleksi_id == tingkat_seleksi_id,
        )
        .first()
    )
    if not akses:
        akses = AksesTingkatSiswa(
            siswa_id=siswa_id,
            tingkat_seleksi_id=tingkat_seleksi_id,
            status=status,
            dibuka_karena="manual_admin" if status == "terbuka" else None,
            dibuka_pada=datetime.now(timezone.utc) if status == "terbuka" else None,
            catatan=catatan,
        )
        db.add(akses)
    else:
        akses.status = status
        if status == "terbuka":
            akses.dibuka_karena = "manual_admin"
            akses.dibuka_pada = datetime.now(timezone.utc)
        akses.catatan = catatan
    db.commit()
    db.refresh(akses)
    return akses
