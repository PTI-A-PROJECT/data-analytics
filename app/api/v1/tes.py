from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.api.deps import get_db
from app.models.hasil_tes import HasilTes, HasilTesSubkompetensi, JawabanSiswa
from app.schemas.tes import SubmitTesRequest, SubmitTesResponse
from app.services.scoring_service import evaluasi_jawaban_dan_durasi
from app.services.mapping_service import hitung_peta_kompetensi
from app.services.advancement_service import evaluasi_kenaikan_tingkat, inisialisasi_akses_siswa

router = APIRouter()


@router.post("/submit", response_model=SubmitTesResponse, status_code=status.HTTP_201_CREATED)
def submit_tes(payload: SubmitTesRequest, db: Session = Depends(get_db)):
    """
    Endpoint utama pengiriman pengerjaan Pre-Test atau Simulasi:
    - Mengevaluasi kebenaran jawaban & kecepatan pengerjaan per butir soal (Tiket 05)
    - Menyimpan log hasil_tes, jawaban_siswa, dan breakdown subkompetensi
    - Menghitung Peta Kompetensi dan flag 'butuh_optimasi' jika lambat (Tiket 05)
    - Jika simulasi, mengevaluasi Kenaikan Tingkat secara otomatis & permanen (Tiket 03)
    """
    # Pastikan hak akses dasar siswa ada
    inisialisasi_akses_siswa(db, payload.siswa_id)

    # 1. Evaluasi jawaban dan durasi pengerjaan (Tiket 05 & Tiket 01)
    evaluated_answers, total_soal, jumlah_benar, skor, predikat = evaluasi_jawaban_dan_durasi(
        db, payload.jawaban
    )
    jumlah_salah = total_soal - jumlah_benar

    # 2. Simpan master HasilTes
    hasil_tes = HasilTes(
        siswa_id=payload.siswa_id,
        sekolah_id=payload.sekolah_id,
        tingkat_seleksi_id=payload.tingkat_seleksi_id,
        jenis_tes=payload.jenis_tes,
        simulasi_id=payload.simulasi_id,
        total_soal=total_soal,
        jumlah_benar=jumlah_benar,
        jumlah_salah=jumlah_salah,
        skor=skor,
        predikat_label=predikat,
        diselesaikan_pada=datetime.now(timezone.utc),
    )
    db.add(hasil_tes)
    db.flush()  # dapatkan hasil_tes.id

    # 3. Simpan butir jawaban siswa (Tiket 05)
    for ans in evaluated_answers:
        jawaban_row = JawabanSiswa(
            hasil_tes_id=hasil_tes.id,
            soal_id=ans["soal_id"],
            jawaban_dipilih=ans["jawaban_dipilih"],
            is_benar=ans["is_benar"],
            durasi_detik=ans["durasi_detik"],
            is_lambat=ans["is_lambat"],
        )
        db.add(jawaban_row)

    # 4. Agregasi per subkompetensi dan simpan ke hasil_tes_subkompetensi (Tiket 01)
    subkomp_agg = {}
    for ans in evaluated_answers:
        sk_id = ans.get("subkompetensi_id")
        if sk_id:
            subkomp_agg.setdefault(sk_id, {"soal": 0, "benar": 0})
            subkomp_agg[sk_id]["soal"] += 1
            if ans["is_benar"]:
                subkomp_agg[sk_id]["benar"] += 1

    for sk_id, val in subkomp_agg.items():
        ht_sub = HasilTesSubkompetensi(
            hasil_tes_id=hasil_tes.id,
            subkompetensi_id=sk_id,
            jumlah_soal=val["soal"],
            jumlah_benar=val["benar"],
        )
        db.add(ht_sub)

    db.commit()

    # 5. Hitung Peta Kompetensi (dengan flag butuh_optimasi - Tiket 05)
    peta_kompetensi = hitung_peta_kompetensi(
        db, evaluated_answers, payload.tingkat_seleksi_id
    )

    # 6. Evaluasi Kenaikan Tingkat jika jenis tes adalah 'simulasi' (Tiket 03)
    kenaikan_tingkat_detail = None
    if payload.jenis_tes == "simulasi":
        kenaikan_tingkat_detail = evaluasi_kenaikan_tingkat(
            db=db,
            siswa_id=payload.siswa_id,
            hasil_tes_id=hasil_tes.id,
            tingkat_seleksi_id=payload.tingkat_seleksi_id,
            skor=skor,
            peta_kompetensi=peta_kompetensi,
        )

    return SubmitTesResponse(
        hasil_tes_id=hasil_tes.id,
        siswa_id=payload.siswa_id,
        tingkat_seleksi_id=payload.tingkat_seleksi_id,
        jenis_tes=payload.jenis_tes,
        skor=skor,
        predikat_label=predikat,
        total_soal=total_soal,
        jumlah_benar=jumlah_benar,
        jumlah_salah=jumlah_salah,
        peta_kompetensi=peta_kompetensi,
        kenaikan_tingkat=kenaikan_tingkat_detail,
    )
