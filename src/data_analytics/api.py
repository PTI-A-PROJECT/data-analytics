"""FastAPI app stateless untuk kalkulasi skor — dipanggil backend Laravel lewat
network Docker privat.

Endpoint:
- GET  /health
- POST /hitung/penilaian : nilai berbobot dari jawaban (kontrak Laravel:
  request {soal[{soal_id, tipe_soal, bobot, jawaban_user, kunci_jawaban}]},
  respons {nilai, jawaban[{soal_id, status_benar}]})
- POST /hitung/pretest   : nilai + pemetaan per materi + materi wajib
  (kontrak Laravel, dipakai LatihanService/PretestService/SimulasiService
  lewat PerhitunganClient)
- POST /hitung/latihan   : skor + lulus + akurasi per materi (skema internal,
  saat ini tidak dipanggil Laravel)
- POST /hitung/simulasi  : seperti pretest + lulus/tidak (skema internal,
  saat ini tidak dipanggil Laravel)

Bobot dikirim eksplisit per soal oleh Laravel (bukan diturunkan dari level).
Semua endpoint /hitung/* mewajibkan header X-Internal-Token sesuai kontrak
BE-11 backend Laravel.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException

from data_analytics.config import get_settings
from data_analytics.laravel import nilai_paket, peta_pretest
from data_analytics.penilaian import (
    HasilPenilaian,
    PetaBerbobot,
    SoalDijawab,
    hitung_pemetaan,
    nilai_jawaban,
    nilai_latihan,
    nilai_simulasi,
)
from data_analytics.schemas import (
    HitungAkurasiMateriItem,
    HitungLatihanRequest,
    HitungLatihanResponse,
    HitungHasilSoalItem,
    HitungPetaMateriItem,
    HitungPretestRequest,
    HitungSimulasiRequest,
    HitungSimulasiResponse,
    LaravelPenilaianRequest,
    LaravelPenilaianResponse,
    LaravelPretestRequest,
    LaravelPretestResponse,
)

app = FastAPI(title="SIAP OSN — Layanan Hitung Skor")


def _wajib_token(x_internal_token: str | None = Header(default=None)) -> None:
    """Setiap permintaan /hitung/* membawa header X-Internal-Token (kontrak
    BE-11). Token salah/dihilangkan → 403, yang di sisi Laravel dicatat kritis
    dan tidak dicoba lagi."""
    if x_internal_token != get_settings().internal_api_token:
        raise HTTPException(status_code=403, detail="token internal tidak valid")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _soal(req: HitungPenilaianRequest | HitungLatihanRequest) -> list[SoalDijawab]:
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


@app.post("/hitung/penilaian", response_model=LaravelPenilaianResponse)
def hitung_penilaian(
    req: LaravelPenilaianRequest, _: None = Depends(_wajib_token)
) -> LaravelPenilaianResponse:
    try:
        nilai, jawaban = nilai_paket(req.soal)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return LaravelPenilaianResponse(nilai=nilai, jawaban=jawaban)  # type: ignore[arg-type]


@app.post("/hitung/pretest", response_model=LaravelPretestResponse)
def hitung_pretest(
    req: LaravelPretestRequest, _: None = Depends(_wajib_token)
) -> LaravelPretestResponse:
    try:
        nilai, jawaban = nilai_paket(req.soal)
        pemetaan, materi_wajib = peta_pretest(req.soal, req.materi, req.jumlah_materi_wajib)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return LaravelPretestResponse(  # type: ignore[arg-type]
        nilai=nilai, jawaban=jawaban, pemetaan=pemetaan, materi_wajib=materi_wajib
    )


def _peta(peta: list[PetaBerbobot]) -> list[HitungPetaMateriItem]:
    return [
        HitungPetaMateriItem(
            materi_id=p.materi_id,
            jumlah_soal=p.jumlah_soal,
            jumlah_benar=p.jumlah_benar,
            bobot_total=p.bobot_total,
            bobot_benar=p.bobot_benar,
            akurasi=p.akurasi,
            status=p.status,
        )
        for p in peta
    ]


@app.post("/hitung/simulasi", response_model=HitungSimulasiResponse)
def hitung_simulasi(
    req: HitungSimulasiRequest, _: None = Depends(_wajib_token)
) -> HitungSimulasiResponse:
    try:
        h = nilai_simulasi(
            _soal(req),
            tingkat=req.tingkat,
            ambang_lemah=req.ambang_lemah,
            ambang_kuat=req.ambang_kuat,
            aturan_predikat=_aturan(req),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return HitungSimulasiResponse(
        **_response_dasar(h.penilaian),
        pemetaan=_peta(h.pemetaan),
        materi_lemah=h.materi_lemah,
        passing_grade=h.passing_grade,
        lulus=h.lulus,
    )


@app.post("/hitung/latihan", response_model=HitungLatihanResponse)
def hitung_latihan(
    req: HitungLatihanRequest, _: None = Depends(_wajib_token)
) -> HitungLatihanResponse:
    try:
        h = nilai_latihan(_soal(req), threshold=req.threshold)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return HitungLatihanResponse(
        skor=h.skor,
        lulus=h.lulus,
        akurasi_per_materi=[
            HitungAkurasiMateriItem(
                materi_id=a.materi_id, akurasi=a.akurasi, lulus=a.lulus
            )
            for a in h.akurasi_per_materi
        ],
    )
