from typing import List, Dict, Tuple, Any
from sqlalchemy.orm import Session
from app.models.master import Soal
from app.schemas.tes import SubmitJawabanItem


def tentukan_predikat(skor: float) -> str:
    """Menentukan predikat berdasarkan aturan skor Tiket 01."""
    if skor >= 90.0:
        return "Sangat Baik"
    elif skor >= 80.0:
        return "Baik"
    elif skor >= 70.0:
        return "Cukup"
    else:
        return "Perlu Latihan"


def evaluasi_jawaban_dan_durasi(
    db: Session, jawaban_list: List[SubmitJawabanItem]
) -> Tuple[List[Dict[str, Any]], int, int, float, str]:
    """
    Mengevaluasi setiap butir soal:
    - Kunci jawaban vs jawaban dipilih -> is_benar
    - durasi_detik vs soal.batas_waktu_detik -> is_lambat (Tiket 05)
    - Menghitung skor persentase biner dan predikat (Tiket 01)
    """
    soal_ids = [j.soal_id for j in jawaban_list]
    soal_map = {s.id: s for s in db.query(Soal).filter(Soal.id.in_(soal_ids)).all()}

    evaluated_answers = []
    jumlah_benar = 0

    for item in jawaban_list:
        soal = soal_map.get(item.soal_id)
        if not soal:
            # Fallback jika soal tidak ditemukan di DB
            is_benar = False
            batas_waktu = 60
        else:
            is_benar = item.jawaban_dipilih.strip().upper() == soal.kunci_jawaban.strip().upper()
            batas_waktu = soal.batas_waktu_detik

        # Tiket 05: Jawaban berstatus lambat jika melebihi batas_waktu_detik
        is_lambat = item.durasi_detik > batas_waktu

        if is_benar:
            jumlah_benar += 1

        evaluated_answers.append({
            "soal_id": item.soal_id,
            "subkompetensi_id": soal.subkompetensi_id if soal else None,
            "jawaban_dipilih": item.jawaban_dipilih,
            "is_benar": is_benar,
            "durasi_detik": item.durasi_detik,
            "is_lambat": is_lambat,
        })

    total_soal = len(jawaban_list)
    skor = round((jumlah_benar / total_soal) * 100.0, 2) if total_soal > 0 else 0.0
    predikat = tentukan_predikat(skor)

    return evaluated_answers, total_soal, jumlah_benar, skor, predikat
