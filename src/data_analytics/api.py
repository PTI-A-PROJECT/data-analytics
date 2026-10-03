"""FastAPI app stateless untuk kalkulasi skor — dipanggil backend Laravel lewat
network Docker privat. Tidak ada akses database & autentikasi di layanan ini
(keduanya tanggung jawab Laravel).

Endpoint:
- GET  /health
- POST /hitung/penilaian : skor berbobot (+ predikat opsional) dari jawaban
- POST /hitung/pretest   : skor + Peta Kompetensi per Materi + Materi lemah
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from data_analytics.penilaian import (
    HasilPenilaian,
    SoalDijawab,
    hitung_pemetaan,
    nilai_jawaban,
)
from data_analytics.schemas import (
    HitungHasilSoalItem,
    HitungPenilaianRequest,
    HitungPenilaianResponse,
    HitungPetaMateriItem,
    HitungPretestRequest,
    HitungPretestResponse,
)

app = FastAPI(title="SIAP OSN — Layanan Hitung Skor")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _soal(req: HitungPenilaianRequest) -> list[SoalDijawab]:
    return [
        SoalDijawab(
            soal_id=s.soal_id,
            level=s.level,
            tipe=s.tipe,
            kunci=s.kunci,
            jawaban=s.jawaban,
            materi_id=s.materi_id,
        )
        for s in req.soal
    ]


def _aturan(req: HitungPenilaianRequest) -> list[tuple[str, float]] | None:
    if req.aturan_predikat is None:
        return None
    return [(a.label, a.batas_bawah) for a in req.aturan_predikat]


def _response_dasar(hasil: HasilPenilaian) -> dict:
    return {
        "skor": hasil.skor,
        "bobot_benar": hasil.bobot_benar,
        "bobot_total": hasil.bobot_total,
        "jumlah_soal": hasil.jumlah_soal,
        "jumlah_benar": hasil.jumlah_benar,
        "jumlah_salah": hasil.jumlah_salah,
        "predikat": hasil.predikat,
        "hasil_soal": [
            HitungHasilSoalItem(soal_id=h.soal_id, benar=h.benar, bobot=h.bobot)
            for h in hasil.hasil_soal
        ],
    }


@app.post("/hitung/penilaian", response_model=HitungPenilaianResponse)
def hitung_penilaian(req: HitungPenilaianRequest) -> HitungPenilaianResponse:
    try:
        hasil = nilai_jawaban(_soal(req), aturan_predikat=_aturan(req))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return HitungPenilaianResponse(**_response_dasar(hasil))


@app.post("/hitung/pretest", response_model=HitungPretestResponse)
def hitung_pretest(req: HitungPretestRequest) -> HitungPretestResponse:
    soal = _soal(req)
    try:
        hasil = nilai_jawaban(soal, aturan_predikat=_aturan(req))
        peta, lemah = hitung_pemetaan(
            soal, ambang_lemah=req.ambang_lemah, ambang_kuat=req.ambang_kuat
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return HitungPretestResponse(
        **_response_dasar(hasil),
        pemetaan=[
            HitungPetaMateriItem(
                materi_id=p.materi_id,
                jumlah_soal=p.jumlah_soal,
                jumlah_benar=p.jumlah_benar,
                akurasi=p.akurasi,
                status=p.status,
            )
            for p in peta
        ],
        materi_lemah=lemah,
    )
