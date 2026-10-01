"""FastAPI app — health endpoints (tiket 09), endpoint admin internal
(tiket 10), endpoint submit Pre-Test/Simulasi (tiket 11), Kenaikan Tingkat
(tiket 03), Dashboard Super Admin (tiket 04), dan event Progress Halaman
Materi (tiket 14). Endpoint Rekomendasi Materi belum diimplementasikan —
bergantung tiket 06 yang masih direview ulang.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from data_analytics.auth import verify_internal_token
from data_analytics.config import get_settings
from data_analytics.dashboard import hitung_metrik_dashboard
from data_analytics.db import get_db
from data_analytics.progress import persentase_selesai
from data_analytics.repository import (
    JawabanInput,
    anonimkan_hasil_tes_kedaluwarsa,
    catat_progress_halaman,
    catat_submission_tes,
    evaluasi_dan_catat_kenaikan,
    evaluasi_dan_catat_pre_test,
    get_akses_siswa,
    get_or_create_aturan_pre_test,
    get_semua_aturan_kenaikan,
    get_semua_aturan_pre_test,
    override_akses_admin,
    update_aturan_kenaikan,
    update_aturan_pre_test,
)
from data_analytics.schemas import (
    JENIS_TES_DARI_WIRE,
    STATUS_PEMETAAN_LABEL,
    AksesTingkatItem,
    AksesTingkatSiswaResponse,
    AturanKenaikanItem,
    AturanPreTestItem,
    DashboardResponse,
    EvaluasiKenaikanRequest,
    EvaluasiKenaikanResponse,
    EvaluasiPreTestRequest,
    EvaluasiPreTestResponse,
    HalamanMateriEventRequest,
    HalamanMateriEventResponse,
    OverrideAksesRequest,
    PetaKompetensiItem,
    SubmitAssessmentData,
    SubmitAssessmentRequest,
    SubmitAssessmentResponse,
    UpdateAturanKenaikanRequest,
    UpdateAturanPreTestRequest,
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


# --- Kenaikan Tingkat (tiket 03) ---------------------------------------------
# tingkat_seleksi_id/tingkat_asal_id di endpoint-endpoint ini merujuk ke
# katalog TingkatSeleksi LOKAL (int), BUKAN tingkat_seleksi_id UUID yang
# dikirim di /assessment/submit — lihat catatan gap id di
# models.AturanKenaikanTingkat. Evaluasi kenaikan karena itu dipanggil
# terpisah oleh Fullstack (bukan otomatis di dalam /assessment/submit).


@app.get(
    "/api/v1/analytics/tingkat/{siswa_id}/akses",
    dependencies=[Depends(verify_internal_token)],
    response_model=AksesTingkatSiswaResponse,
)
def get_akses_tingkat(
    siswa_id: str, db: Annotated[Session, Depends(get_db)]
) -> AksesTingkatSiswaResponse:
    """Status akses siswa ke seluruh Tingkat Seleksi lokal (inisialisasi
    otomatis kalau belum pernah ada — resolusi tiket 03).
    """
    akses = get_akses_siswa(db, siswa_id)
    db.commit()
    return AksesTingkatSiswaResponse(
        siswa_id=siswa_id,
        daftar_akses=[
            AksesTingkatItem(
                tingkat_seleksi_id=a.tingkat_seleksi_id,
                nama=a.tingkat_seleksi.nama if a.tingkat_seleksi else "",
                status=a.status,
                simulasi_terbuka=a.simulasi_terbuka,
                dibuka_karena=a.dibuka_karena,
                catatan=a.catatan,
            )
            for a in akses
        ],
    )


@app.post(
    "/api/v1/analytics/tingkat/override",
    dependencies=[Depends(verify_internal_token)],
    response_model=AksesTingkatItem,
)
def override_akses_tingkat(
    payload: OverrideAksesRequest, db: Annotated[Session, Depends(get_db)]
) -> AksesTingkatItem:
    """Override manual akses tingkat siswa oleh Super Admin (FR-17/tiket 03)."""
    akses = override_akses_admin(
        db,
        siswa_id=payload.siswa_id,
        tingkat_seleksi_id=payload.tingkat_seleksi_id,
        status=payload.status,
        catatan=payload.catatan,
    )
    db.commit()
    return AksesTingkatItem(
        tingkat_seleksi_id=akses.tingkat_seleksi_id,
        nama=akses.tingkat_seleksi.nama if akses.tingkat_seleksi else "",
        status=akses.status,
        simulasi_terbuka=akses.simulasi_terbuka,
        dibuka_karena=akses.dibuka_karena,
        catatan=akses.catatan,
    )


@app.get(
    "/api/v1/analytics/tingkat/aturan",
    dependencies=[Depends(verify_internal_token)],
    response_model=list[AturanKenaikanItem],
)
def get_aturan_kenaikan(
    db: Annotated[Session, Depends(get_db)],
) -> list[AturanKenaikanItem]:
    return [
        AturanKenaikanItem(
            id=a.id,
            tingkat_asal_id=a.tingkat_asal_id,
            tingkat_tujuan_id=a.tingkat_tujuan_id,
            skor_simulasi_min=a.skor_simulasi_min,
            persentase_kompetensi_cukup_min=a.persentase_kompetensi_cukup_min,
            aktif=a.aktif,
        )
        for a in get_semua_aturan_kenaikan(db)
    ]


@app.put(
    "/api/v1/analytics/tingkat/aturan/{aturan_id}",
    dependencies=[Depends(verify_internal_token)],
    response_model=AturanKenaikanItem,
)
def put_aturan_kenaikan(
    aturan_id: int,
    payload: UpdateAturanKenaikanRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AturanKenaikanItem:
    aturan = update_aturan_kenaikan(
        db,
        aturan_id=aturan_id,
        skor_simulasi_min=payload.skor_simulasi_min,
        persentase_kompetensi_cukup_min=payload.persentase_kompetensi_cukup_min,
        aktif=payload.aktif,
    )
    if aturan is None:
        raise HTTPException(
            status_code=404, detail=f"Aturan kenaikan tingkat ID {aturan_id} tidak ditemukan"
        )
    db.commit()
    return AturanKenaikanItem(
        id=aturan.id,
        tingkat_asal_id=aturan.tingkat_asal_id,
        tingkat_tujuan_id=aturan.tingkat_tujuan_id,
        skor_simulasi_min=aturan.skor_simulasi_min,
        persentase_kompetensi_cukup_min=aturan.persentase_kompetensi_cukup_min,
        aktif=aturan.aktif,
    )


@app.post(
    "/api/v1/analytics/tingkat/evaluasi",
    dependencies=[Depends(verify_internal_token)],
    response_model=EvaluasiKenaikanResponse,
)
def evaluasi_kenaikan(
    payload: EvaluasiKenaikanRequest, db: Annotated[Session, Depends(get_db)]
) -> EvaluasiKenaikanResponse:
    """Evaluasi kelayakan kenaikan tingkat siswa (resolusi tiket 03) — dipanggil
    Fullstack setelah submit Simulasi, membawa jumlah_kompetensi_cukup/
    total_kompetensi_silabus yang sudah mereka agregasikan dari Peta
    Kompetensi (caller-supplied, konsisten prinsip stateless ADR 0002).
    """
    try:
        riwayat = evaluasi_dan_catat_kenaikan(
            db,
            siswa_id=payload.siswa_id,
            hasil_tes_id=payload.hasil_tes_id,
            tingkat_asal_id=payload.tingkat_asal_id,
            skor=payload.skor,
            jumlah_kompetensi_cukup=payload.jumlah_kompetensi_cukup,
            total_kompetensi_silabus=payload.total_kompetensi_silabus,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()

    if riwayat is None:
        return EvaluasiKenaikanResponse(evaluasi_dilakukan=False)

    return EvaluasiKenaikanResponse(
        evaluasi_dilakukan=True,
        hasil_evaluasi=riwayat.hasil_evaluasi,
        syarat_skor_lulus=riwayat.syarat_skor_lulus,
        syarat_kompetensi_lulus=riwayat.syarat_kompetensi_lulus,
        persentase_cukup_aktual=riwayat.persentase_cukup_aktual,
    )


# --- Aturan Kelulusan & Akses Pre-Test Berjenjang (tiket 15) -----------------


@app.get(
    "/api/v1/analytics/pre-test/aturan",
    dependencies=[Depends(verify_internal_token)],
    response_model=list[AturanPreTestItem],
)
def get_aturan_pre_test_endpoint(
    db: Annotated[Session, Depends(get_db)],
) -> list[AturanPreTestItem]:
    """Daftar aturan kelulusan minimal (passing grade) Pre-Test per tingkat seleksi."""
    aturan_list = get_semua_aturan_pre_test(db)
    return [
        AturanPreTestItem(
            id=a.id,
            tingkat_seleksi_id=a.tingkat_seleksi_id,
            skor_min=a.skor_min,
            aktif=a.aktif,
        )
        for a in aturan_list
    ]


@app.put(
    "/api/v1/analytics/pre-test/aturan/{aturan_id}",
    dependencies=[Depends(verify_internal_token)],
    response_model=AturanPreTestItem,
)
def put_aturan_pre_test_endpoint(
    aturan_id: int,
    payload: UpdateAturanPreTestRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AturanPreTestItem:
    """Update konfigurasi passing grade aturan Pre-Test oleh Super Admin."""
    aturan = update_aturan_pre_test(
        db,
        aturan_id=aturan_id,
        skor_min=payload.skor_min,
        aktif=payload.aktif,
    )
    if aturan is None:
        raise HTTPException(
            status_code=404, detail=f"Aturan Pre-Test ID {aturan_id} tidak ditemukan"
        )
    db.commit()
    return AturanPreTestItem(
        id=aturan.id,
        tingkat_seleksi_id=aturan.tingkat_seleksi_id,
        skor_min=aturan.skor_min,
        aktif=aturan.aktif,
    )


@app.post(
    "/api/v1/analytics/pre-test/evaluasi",
    dependencies=[Depends(verify_internal_token)],
    response_model=EvaluasiPreTestResponse,
)
def evaluasi_pre_test_endpoint(
    payload: EvaluasiPreTestRequest, db: Annotated[Session, Depends(get_db)]
) -> EvaluasiPreTestResponse:
    """Evaluasi skor Pre-Test terhadap passing grade jenjang terkait.
    Jika lolos: buka akses simulasi jenjang ini & buka akses jenjang berikutnya.
    Jika gagal: simulasi jenjang ini & jenjang berikutnya tetap terkunci.
    """
    riwayat, simulasi_terbuka, tingkat_berikutnya_terbuka = evaluasi_dan_catat_pre_test(
        db,
        siswa_id=payload.siswa_id,
        hasil_tes_id=payload.hasil_tes_id,
        tingkat_seleksi_id=payload.tingkat_seleksi_id,
        skor=payload.skor,
    )
    if riwayat is None:
        return EvaluasiPreTestResponse(evaluasi_dilakukan=False)

    db.commit()
    return EvaluasiPreTestResponse(
        evaluasi_dilakukan=True,
        hasil_evaluasi="lulus" if riwayat.lulus else "tidak_lulus",
        lulus=riwayat.lulus,
        skor_aktual=riwayat.skor_aktual,
        passing_grade=riwayat.passing_grade,
        simulasi_terbuka=simulasi_terbuka,
        tingkat_berikutnya_terbuka=tingkat_berikutnya_terbuka,
    )


@app.get(
    "/api/v1/admin/dashboard",
    dependencies=[Depends(verify_internal_token)],
    response_model=DashboardResponse,
)
def get_dashboard(
    db: Annotated[Session, Depends(get_db)],
    sekolah_id: str | None = None,
    rentang_waktu: str = "30d",
) -> DashboardResponse:
    """Metrik agregat Dashboard Super Admin (FR-24/tiket 04) — lihat catatan
    di dashboard.py soal section 'analisis_kompetensi' yang belum diimplementasikan.
    """
    return hitung_metrik_dashboard(db, sekolah_id=sekolah_id, rentang_waktu=rentang_waktu)


@app.post(
    "/api/v1/analytics/events/materi-progress",
    dependencies=[Depends(verify_internal_token)],
    response_model=HalamanMateriEventResponse,
)
def catat_event_materi_progress(
    payload: HalamanMateriEventRequest, db: Annotated[Session, Depends(get_db)]
) -> HalamanMateriEventResponse:
    """Terima event 'siswa mencapai halaman Materi' dari Fullstack (resolusi
    tiket 14), upsert high-water mark `progress_materi` (tiket 02) —
    `catat_progress_halaman` sudah menegakkan aturan "tidak pernah turun
    walau navigasi mundur".
    """
    try:
        progress = catat_progress_halaman(
            db,
            siswa_id=payload.siswa_id,
            materi_id=payload.materi_id,
            subkompetensi_id=payload.subkompetensi_id,
            tingkat_seleksi_id=payload.tingkat_seleksi_id,
            total_halaman=payload.total_halaman,
            halaman_dicapai=payload.halaman_dibuka,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()

    return HalamanMateriEventResponse(
        siswa_id=progress.siswa_id,
        materi_id=progress.materi_id,
        halaman_tertinggi_dicapai=progress.halaman_tertinggi_dicapai,
        total_halaman=progress.total_halaman,
        persentase_selesai=persentase_selesai(
            halaman_tertinggi_dicapai=progress.halaman_tertinggi_dicapai,
            total_halaman=progress.total_halaman,
        ),
    )
