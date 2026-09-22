"""FastAPI app — health endpoints (tiket 09), endpoint admin internal
(tiket 10), dan endpoint submit Pre-Test/Simulasi (tiket 11). Endpoint
Rekomendasi Materi belum diimplementasikan — bergantung tiket 06 yang masih
direview ulang.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from data_analytics.auth import verify_internal_token
from data_analytics.config import get_settings
from data_analytics.db import get_db
from data_analytics.repository import (
    JawabanInput,
    anonimkan_hasil_tes_kedaluwarsa,
    catat_submission_tes,
)
from data_analytics.schemas import (
    JENIS_TES_DARI_WIRE,
    STATUS_PEMETAAN_LABEL,
    PetaKompetensiItem,
    SubmitAssessmentData,
    SubmitAssessmentRequest,
    SubmitAssessmentResponse,
)

app = FastAPI(title="Data & Analytics — OSN Informatika")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe cepat — tidak menyentuh database."""
    return {"status": "ok"}


@app.get("/api/v1/health")
def health_readiness(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """Readiness probe — query ping aktif ke database."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post(
    "/api/v1/admin/anonymize-expired",
    dependencies=[Depends(verify_internal_token)],
)
def anonymize_expired(
    db: Annotated[Session, Depends(get_db)], dry_run: bool = False
) -> dict[str, int | bool]:
    """Endpoint internal (X-Internal-Token) untuk cron bulanan UU PDP — lihat
    resolusi tiket "Rencana Deployment/Hosting untuk Sekolah Pilot". Tidak
    diekspos ke publik; hanya dipanggil backend aplikasi utama lewat network
    Docker privat.
    """
    jumlah = anonimkan_hasil_tes_kedaluwarsa(
        db, retention_months=get_settings().data_retention_months, dry_run=dry_run
    )
    if not dry_run:
        db.commit()
    return {"jumlah_dianonimkan": jumlah, "dry_run": dry_run}


@app.post(
    "/api/v1/analytics/assessment/submit",
    dependencies=[Depends(verify_internal_token)],
    response_model=SubmitAssessmentResponse,
)
def submit_assessment(
    payload: SubmitAssessmentRequest, db: Annotated[Session, Depends(get_db)]
) -> SubmitAssessmentResponse:
    """Terima jawaban Pre-Test/Simulasi siswa, hitung skor & Peta Kompetensi
    (FR-07) + flag butuh_optimasi (tiket 05), simpan HasilTes + log
    JawabanSiswa — lihat resolusi tiket 11.
    """
    jenis_tes = JENIS_TES_DARI_WIRE[payload.jenis_tes]

    try:
        hasil = catat_submission_tes(
            db,
            siswa_id=payload.siswa_id,
            sekolah_id=payload.sekolah_id,
            tingkat_seleksi_id=payload.tingkat_seleksi_id,
            jenis_tes=jenis_tes,
            simulasi_id=payload.simulasi_id,
            jawaban_siswa=[
                JawabanInput(
                    soal_id=j.soal_id,
                    subkompetensi_id=j.subkompetensi_id,
                    jawaban_dipilih=j.jawaban_dipilih,
                    is_benar=j.is_benar,
                    durasi_detik=j.durasi_detik,
                    batas_waktu_detik=j.batas_waktu_detik,
                )
                for j in payload.jawaban_siswa
            ],
            diselesaikan_pada=datetime.now(timezone.utc),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()

    return SubmitAssessmentResponse(
        data=SubmitAssessmentData(
            peta_kompetensi=[
                PetaKompetensiItem(
                    subkompetensi_id=b.subkompetensi_id,
                    status_pemetaan=STATUS_PEMETAAN_LABEL[b.status_pemetaan],
                    butuh_optimasi=b.butuh_optimasi,
                )
                for b in hasil.breakdown_subkompetensi
            ]
        )
    )
