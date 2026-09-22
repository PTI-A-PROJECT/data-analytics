from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.master import Subkompetensi, Kompetensi
from app.schemas.tes import SubkompetensiMapItem, KompetensiMapItem


def hitung_peta_kompetensi(
    db: Session,
    evaluated_answers: List[Dict[str, Any]],
    tingkat_seleksi_id: int,
    ambang_benar_subkompetensi: float = 70.0,
    ambang_benar_kompetensi: float = 70.0,
) -> List[KompetensiMapItem]:
    """
    Menghitung Peta Kompetensi per Subkompetensi dan Kompetensi:
    - Menghitung persentase benar per subkompetensi -> Cukup / Belum Cukup
    - Tiket 05: Menyematkan flag 'butuh_optimasi = True' jika status 'Cukup' tetapi >= 50%
      jawaban benarnya dikerjakan melebihi batas waktu (is_lambat == True).
    - Mengagregasi status Kompetensi berdasarkan subkompetensi anaknya.
    """
    # Group jawaban berdasarkan subkompetensi_id
    subkomp_answers: Dict[int, List[Dict[str, Any]]] = {}
    for ans in evaluated_answers:
        sk_id = ans.get("subkompetensi_id")
        if sk_id:
            subkomp_answers.setdefault(sk_id, []).append(ans)

    # Ambil semua kompetensi & subkompetensi pada tingkat seleksi ini
    kompetensi_list = (
        db.query(Kompetensi)
        .filter(Kompetensi.tingkat_seleksi_id == tingkat_seleksi_id)
        .all()
    )

    result_kompetensi: List[KompetensiMapItem] = []

    for komp in kompetensi_list:
        subkomp_items: List[SubkompetensiMapItem] = []
        cukup_subkomp_count = 0
        total_valid_subkomp = 0

        for sk in komp.subkompetensi:
            answers = subkomp_answers.get(sk.id, [])
            total_soal = len(answers)
            if total_soal == 0:
                # Belum ada soal yang dikerjakan untuk subkompetensi ini
                subkomp_items.append(
                    SubkompetensiMapItem(
                        subkompetensi_id=sk.id,
                        nama_subkompetensi=sk.nama,
                        status="Belum Teruji",
                        jumlah_soal=0,
                        jumlah_benar=0,
                        total_jawaban_benar=0,
                        total_benar_lambat=0,
                        butuh_optimasi=False,
                    )
                )
                continue

            benar_items = [a for a in answers if a["is_benar"]]
            total_benar = len(benar_items)
            total_benar_lambat = sum(1 for a in benar_items if a["is_lambat"])

            pct_correct = (total_benar / total_soal) * 100.0
            is_cukup = pct_correct >= ambang_benar_subkompetensi
            status_subkomp = "Cukup" if is_cukup else "Belum Cukup"

            # Tiket 05: butuh_optimasi flag
            # True jika status 'Cukup' tetapi >= 50% dari jawaban benarnya lambat
            butuh_optimasi = False
            if is_cukup and total_benar > 0:
                rasio_lambat = total_benar_lambat / total_benar
                if rasio_lambat >= 0.5:
                    butuh_optimasi = True

            if is_cukup:
                cukup_subkomp_count += 1
            total_valid_subkomp += 1

            subkomp_items.append(
                SubkompetensiMapItem(
                    subkompetensi_id=sk.id,
                    nama_subkompetensi=sk.nama,
                    status=status_subkomp,
                    jumlah_soal=total_soal,
                    jumlah_benar=total_benar,
                    total_jawaban_benar=total_benar,
                    total_benar_lambat=total_benar_lambat,
                    butuh_optimasi=butuh_optimasi,
                )
            )

        # Status Kompetensi induk
        if total_valid_subkomp == 0:
            status_komp = "Belum Teruji"
        else:
            pct_subkomp_cukup = (cukup_subkomp_count / total_valid_subkomp) * 100.0
            status_komp = "Cukup" if pct_subkomp_cukup >= ambang_benar_kompetensi else "Belum Cukup"

        result_kompetensi.append(
            KompetensiMapItem(
                kompetensi_id=komp.id,
                nama_kompetensi=komp.nama,
                status=status_komp,
                subkompetensi=subkomp_items,
            )
        )

    return result_kompetensi
