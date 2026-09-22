"""DTO Pydantic untuk kontrak API publik (tiket 11) — endpoint
POST /api/v1/analytics/assessment/submit. Terpisah dari model SQLAlchemy
(models.py) supaya bentuk wire format (mis. jenis_tes UPPERCASE, label
status_pemetaan berkapital) tidak membocorkan representasi penyimpanan
internal.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from data_analytics.models import JenisTes, StatusPemetaan

STATUS_PEMETAAN_LABEL: dict[StatusPemetaan, str] = {
    StatusPemetaan.CUKUP: "Cukup",
    StatusPemetaan.BELUM_CUKUP: "Belum Cukup",
    StatusPemetaan.BELUM_TERUJI: "Belum Teruji",
}

JENIS_TES_DARI_WIRE: dict[str, JenisTes] = {
    "PRE_TEST": JenisTes.PRE_TEST,
    "SIMULASI": JenisTes.SIMULASI,
}


class JawabanSiswaRequest(BaseModel):
    soal_id: str
    subkompetensi_id: str
    jawaban_dipilih: str
    is_benar: bool
    durasi_detik: int = Field(ge=0)
    batas_waktu_detik: int = Field(gt=0)


class SubmitAssessmentRequest(BaseModel):
    siswa_id: str
    sekolah_id: str | None = None
    tingkat_seleksi_id: str
    jenis_tes: Literal["PRE_TEST", "SIMULASI"]
    simulasi_id: str | None = None
    jawaban_siswa: list[JawabanSiswaRequest] = Field(min_length=1)


class PetaKompetensiItem(BaseModel):
    subkompetensi_id: str
    status_pemetaan: str
    butuh_optimasi: bool


class SubmitAssessmentData(BaseModel):
    peta_kompetensi: list[PetaKompetensiItem]


class SubmitAssessmentResponse(BaseModel):
    status: Literal["success"] = "success"
    message: str = "Pemetaan kompetensi berhasil dihitung"
    data: SubmitAssessmentData
