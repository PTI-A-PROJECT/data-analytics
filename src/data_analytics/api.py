"""FastAPI app — health endpoints (tiket 09), endpoint admin internal
(tiket 10), akses tingkat (tiket 03, fase 2 issue 02), Paket Tes pre-test &
simulasi adaptif & Materi Wajib (fase 2 issue 02-04), Dashboard
Super Admin (tiket 04), event Progress Halaman Materi (tiket 14), dan katalog
Materi (daftar, daftar isi, konten halaman). Endpoint Rekomendasi Materi belum diimplementasikan —
bergantung tiket 06 yang masih direview ulang.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from data_analytics.auth import verify_internal_token
from data_analytics.config import Settings, get_settings
from data_analytics.dashboard import hitung_metrik_dashboard
from data_analytics.db import get_db
from data_analytics.progress import persentase_selesai
from data_analytics.models import (
    AksesTingkatSiswa,
    AturanAdaptif,
    AturanPredikat,
    AturanKenaikanTingkat,
    Materi,
    PaketTes,
    PaketTesSoal,
    StatusAkses,
)
from data_analytics.repository import (
    AksesDitolak,
    JawabanLatihan,          # ← TAMBAH
    JawabanPaket,
    KonflikPaket,
    MateriTidakDitemukan,
    PaketTidakDitemukan,
    TingkatTidakDitemukan,
    anonimkan_hasil_tes_kedaluwarsa,
    GerbangSimulasiTertutup,
    StatusGerbangSimulasi,
    catat_baca_halaman,
    daftar_materi,
    ganti_aturan_predikat,
    get_akses_siswa,
    get_materi,
    halaman_dibaca_siswa,
    get_semua_aturan_adaptif,
    get_semua_aturan_predikat,
    leaderboard_tingkat,
    get_semua_aturan_kenaikan,
    override_akses_admin,
    status_gerbang_simulasi,
    submit_latihan,          # ← TAMBAH
    submit_paket,
    susun_paket_latihan,     # ← TAMBAH
    update_aturan_adaptif,
    susun_paket_pretest,
    susun_paket_simulasi,
    update_aturan_kenaikan,
)
from data_analytics.schemas import (
    STATUS_PEMETAAN_LABEL,
    AksesTingkatItem,
    AksesTingkatSiswaResponse,
    AturanAdaptifItem,
    AturanPredikatItem,
    AturanKenaikanItem,
    DashboardResponse,
    HalamanMateriEventRequest,
    HalamanMateriEventResponse,
    HalamanMateriResponse,
    HalamanRingkasItem,
    LeaderboardResponse,
    MateriDetailResponse,
    MateriItem,
    MateriWajibItem,
    OverrideAksesRequest,
    EvaluasiJalurSimulasiItem,
    PaketRequest,
    PerubahanLevelItem,
    PeringkatItem,
    PredikatItem,
    GerbangSimulasiResponse,
    PaketResponse,
    PetaMateriItem,
    ReviewSoalItem,
    SoalPaketItem,
    SubmitPaketRequest,
    SubmitPaketResponse,
    UpdateAturanAdaptifRequest,
    UpdateAturanPredikatRequest,
    UpdateAturanKenaikanRequest,
    JawabanLatihanItem,      # ← TAMBAH
    LatihanRequest,          # ← TAMBAH
    LatihanResponse,         # ← TAMBAH
    SoalLatihanItem,         # ← TAMBAH
    SubmitLatihanRequest,    # ← TAMBAH
    SubmitLatihanResponse,   # ← TAMBAH
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


# --- Akses tingkat & aturan kenaikan (tiket 03, fase 2 issue 02) ------------


def _akses_item(akses: AksesTingkatSiswa) -> AksesTingkatItem:
    return AksesTingkatItem(
        tingkat_seleksi_id=akses.tingkat_seleksi_id,
        nama=akses.tingkat_seleksi.nama,
        status=StatusAkses(akses.status),
        dibuka_karena=akses.dibuka_karena,
        catatan=akses.catatan,
    )


def _aturan_item(aturan: AturanKenaikanTingkat) -> AturanKenaikanItem:
    return AturanKenaikanItem(
        id=aturan.id,
        tingkat_asal_id=aturan.tingkat_asal_id,
        tingkat_tujuan_id=aturan.tingkat_tujuan_id,
        skor_simulasi_min=aturan.skor_simulasi_min,
        skor_pretest_jalur_cepat=aturan.skor_pretest_jalur_cepat,
        rata_level_min=aturan.rata_level_min,
        aktif=aturan.aktif,
    )


@app.get(
    "/api/v1/siswa/{siswa_id}/akses",
    dependencies=[Depends(verify_internal_token)],
    response_model=AksesTingkatSiswaResponse,
)
def get_akses_tingkat(
    siswa_id: str, db: Annotated[Session, Depends(get_db)]
) -> AksesTingkatSiswaResponse:
    """Status akses siswa per Tingkat Seleksi (inisialisasi otomatis kalau
    belum pernah ada: Kabupaten pretest_terbuka, sisanya terkunci).
    """
    akses = get_akses_siswa(db, siswa_id)
    db.commit()
    return AksesTingkatSiswaResponse(
        siswa_id=siswa_id, daftar_akses=[_akses_item(a) for a in akses]
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
    return _akses_item(akses)


@app.get(
    "/api/v1/analytics/tingkat/aturan",
    dependencies=[Depends(verify_internal_token)],
    response_model=list[AturanKenaikanItem],
)
def get_aturan_kenaikan(
    db: Annotated[Session, Depends(get_db)],
) -> list[AturanKenaikanItem]:
    return [_aturan_item(a) for a in get_semua_aturan_kenaikan(db)]


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
        skor_pretest_jalur_cepat=payload.skor_pretest_jalur_cepat,
        rata_level_min=payload.rata_level_min,
        aktif=payload.aktif,
    )
    if aturan is None:
        raise HTTPException(
            status_code=404, detail=f"Aturan kenaikan tingkat ID {aturan_id} tidak ditemukan"
        )
    db.commit()
    return _aturan_item(aturan)


# --- Aturan predikat (tiket 01) -----------------------------------------------


def _aturan_predikat_item(tingkat_seleksi_id: int, aturan: list[AturanPredikat]) -> AturanPredikatItem:
    return AturanPredikatItem(
        tingkat_seleksi_id=tingkat_seleksi_id,
        predikat=[PredikatItem(label=a.label, batas_bawah=a.batas_bawah) for a in aturan],
    )


@app.get(
    "/api/v1/analytics/aturan-predikat",
    dependencies=[Depends(verify_internal_token)],
    response_model=list[AturanPredikatItem],
)
def get_aturan_predikat(db: Annotated[Session, Depends(get_db)]) -> list[AturanPredikatItem]:
    """Kelompok rentang skor → predikat per Tingkat Seleksi. Predikat hanya
    label di samping skor pada hasil submit."""
    daftar = get_semua_aturan_predikat(db)
    db.commit()  # simpan default yang baru dibuat
    return [_aturan_predikat_item(tingkat_id, aturan) for tingkat_id, aturan in daftar]


@app.put(
    "/api/v1/analytics/aturan-predikat/{tingkat_seleksi_id}",
    dependencies=[Depends(verify_internal_token)],
    response_model=AturanPredikatItem,
)
def put_aturan_predikat(
    tingkat_seleksi_id: int,
    payload: UpdateAturanPredikatRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AturanPredikatItem:
    """Ganti seluruh predikat satu tingkat. Berlaku untuk submit berikutnya;
    predikat hasil tes yang sudah tersimpan tidak berubah. 422 kalau tidak ada
    batas_bawah 0 atau label/batas ganda."""
    try:
        aturan = ganti_aturan_predikat(
            db,
            tingkat_seleksi_id=tingkat_seleksi_id,
            aturan=[(p.label, p.batas_bawah) for p in payload.predikat],
        )
    except TingkatTidakDitemukan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return _aturan_predikat_item(tingkat_seleksi_id, aturan)


# --- Aturan adaptif (fase 2 issue 03) -----------------------------------------


def _aturan_adaptif_item(aturan: AturanAdaptif) -> AturanAdaptifItem:
    return AturanAdaptifItem(
        tingkat_seleksi_id=aturan.tingkat_seleksi_id,
        jumlah_soal_pretest=aturan.jumlah_soal_pretest,
        jumlah_soal_simulasi=aturan.jumlah_soal_simulasi,
        kuota_min=aturan.kuota_min,
        bobot_lemah=aturan.bobot_lemah,
        ambang_naik=aturan.ambang_naik,
        ambang_lemah=aturan.ambang_lemah,
    )


@app.get(
    "/api/v1/analytics/aturan-adaptif",
    dependencies=[Depends(verify_internal_token)],
    response_model=list[AturanAdaptifItem],
)
def get_aturan_adaptif(db: Annotated[Session, Depends(get_db)]) -> list[AturanAdaptifItem]:
    """Parameter penyusunan paket pre-test/simulasi per Tingkat Seleksi."""
    aturan = get_semua_aturan_adaptif(db)
    db.commit()  # simpan default yang baru dibuat
    return [_aturan_adaptif_item(a) for a in aturan]


@app.put(
    "/api/v1/analytics/aturan-adaptif/{tingkat_seleksi_id}",
    dependencies=[Depends(verify_internal_token)],
    response_model=AturanAdaptifItem,
)
def put_aturan_adaptif(
    tingkat_seleksi_id: int,
    payload: UpdateAturanAdaptifRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AturanAdaptifItem:
    """Ubah sebagian parameter adaptif satu tingkat. 422 kalau hasilnya tidak
    konsisten (mis. kuota_min x jumlah Materi > jumlah_soal_simulasi)."""
    try:
        aturan = update_aturan_adaptif(
            db, tingkat_seleksi_id=tingkat_seleksi_id, **payload.model_dump(exclude_none=True)
        )
    except TingkatTidakDitemukan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return _aturan_adaptif_item(aturan)


# --- Paket Tes (fase 2 issue 02) ----------------------------------------------


URL_GAMBAR = "/api/v1/konten/gambar"


def _url_gambar(gambar: str | None) -> str | None:
    """Gambar lokal disajikan endpoint konten; URL absolut sumber apa adanya."""
    if gambar is None or gambar.startswith(("http://", "https://")):
        return gambar
    return f"{URL_GAMBAR}/{gambar}"


@app.get(
    URL_GAMBAR + "/{tingkat}/{nama_file}",
    dependencies=[Depends(verify_internal_token)],
    response_class=FileResponse,
)
def get_gambar_soal(
    tingkat: str, nama_file: str, settings: Annotated[Settings, Depends(get_settings)]
) -> FileResponse:
    """File gambar soal dari <folder_soal>/gambar_<tingkat>/. Hanya nama file
    di folder itu yang dilayani (tanpa sub-path) — 404 selain itu."""
    folder = (Path(settings.folder_soal) / f"gambar_{tingkat}").resolve()
    path = (folder / nama_file).resolve()
    if tingkat not in {"kabupaten", "provinsi"} or path.parent != folder or not path.is_file():
        raise HTTPException(status_code=404, detail="Gambar tidak ditemukan")
    return FileResponse(path)


def _paket_response(paket: PaketTes) -> PaketResponse:
    return PaketResponse(
        paket_id=paket.id,
        siswa_id=paket.siswa_id,
        tingkat_seleksi_id=paket.tingkat_seleksi_id,
        jenis_tes=paket.jenis_tes,
        jumlah_soal_diminta=paket.jumlah_soal_diminta,
        soal=[
            SoalPaketItem(
                urutan=baris.urutan,
                soal_id=baris.soal_id,
                materi_id=baris.materi_id,
                tipe=baris.soal_ref.tipe,
                deskripsi=baris.soal_ref.deskripsi,
                pertanyaan=baris.soal_ref.pertanyaan,
                kode=baris.soal_ref.kode,
                gambar=_url_gambar(baris.soal_ref.gambar),
                pilihan_jawaban=baris.soal_ref.pilihan_jawaban,
            )
            for baris in paket.soal
        ],
    )


@app.post(
    "/api/v1/pretest/paket",
    dependencies=[Depends(verify_internal_token)],
    response_model=PaketResponse,
)
def buat_paket_pretest(
    payload: PaketRequest, db: Annotated[Session, Depends(get_db)]
) -> PaketResponse:
    """Paket pre-test siswa (semua soal Mudah, rata per Materi). Idempoten
    selama belum disubmit. 403 kalau pre-test tingkat ini belum terbuka, 409
    kalau sudah dikerjakan.
    """
    try:
        paket = susun_paket_pretest(
            db, siswa_id=payload.siswa_id, tingkat_seleksi_id=payload.tingkat_seleksi_id
        )
    except TingkatTidakDitemukan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AksesDitolak as exc:
        db.commit()  # simpan inisialisasi akses siswa baru
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KonflikPaket as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _paket_response(paket)


@app.post(
    "/api/v1/simulasi/paket",
    dependencies=[Depends(verify_internal_token)],
    response_model=PaketResponse,
    responses={409: {"model": GerbangSimulasiResponse}},
)
def buat_paket_simulasi(
    payload: PaketRequest, db: Annotated[Session, Depends(get_db)]
) -> PaketResponse | JSONResponse:
    """Paket simulasi adaptif (fase 2 issue 03). Idempoten selama belum
    disubmit. 403 kalau materi & simulasi tingkat ini belum terbuka (pre-test
    belum dikerjakan); 409 (body = GerbangSimulasiResponse) kalau Materi Wajib attempt
    terakhir belum selesai dipelajari (Gerbang Simulasi, issue 04).
    """
    try:
        paket = susun_paket_simulasi(
            db, siswa_id=payload.siswa_id, tingkat_seleksi_id=payload.tingkat_seleksi_id
        )
    except TingkatTidakDitemukan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AksesDitolak as exc:
        db.commit()  # simpan inisialisasi akses siswa baru
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except GerbangSimulasiTertutup as exc:
        db.commit()
        return JSONResponse(
            status_code=409, content=_gerbang_simulasi_response(exc.status).model_dump()
        )
    db.commit()
    return _paket_response(paket)


@app.post(
    "/api/v1/paket/{paket_id}/submit",
    dependencies=[Depends(verify_internal_token)],
    response_model=SubmitPaketResponse,
)
def submit_paket_tes(
    paket_id: int, payload: SubmitPaketRequest, db: Annotated[Session, Depends(get_db)]
) -> SubmitPaketResponse:
    """Nilai Paket Tes: skor, predikat, Peta Kompetensi per Materi, Materi
    lemah, dan status akses terbaru; untuk simulasi juga perubahan Level Soal
    Siswa dan evaluasi jalur simulasi. 422 untuk soal di luar paket, 409 kalau
    paket sudah disubmit.
    """
    try:
        hasil = submit_paket(
            db,
            paket_id=paket_id,
            sekolah_id=payload.sekolah_id,
            nama_siswa=payload.nama_siswa,
            nama_sekolah=payload.nama_sekolah,
            jawaban=[
                JawabanPaket(
                    soal_id=j.soal_id,
                    jawaban_dipilih=j.jawaban_dipilih,
                    dibuka_pada=j.dibuka_pada,
                    dijawab_pada=j.dijawab_pada,
                )
                for j in payload.jawaban
            ],
            diselesaikan_pada=datetime.now(timezone.utc),
        )
    except PaketTidakDitemukan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KonflikPaket as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return SubmitPaketResponse(
        hasil_tes_id=hasil.hasil_tes.id,
        skor=hasil.hasil_tes.skor,
        predikat=hasil.hasil_tes.predikat_label,
        peta_kompetensi=[
            PetaMateriItem(
                materi_id=p.materi_id,
                jumlah_soal=p.jumlah_soal,
                jumlah_benar=p.jumlah_benar,
                akurasi=p.akurasi,
                status_pemetaan=STATUS_PEMETAAN_LABEL[p.status],
            )
            for p in hasil.peta
        ],
        materi_lemah=hasil.materi_lemah,
        daftar_akses=[_akses_item(a) for a in hasil.akses],
        perubahan_level=[
            PerubahanLevelItem(
                materi_id=p.materi_id,
                level_sebelum=p.level_sebelum,
                level_sesudah=p.level_sesudah,
                lemah=p.lemah,
                akurasi=p.akurasi,
                diperbarui=p.diperbarui,
            )
            for p in hasil.perubahan_level
        ],
        evaluasi_jalur_simulasi=(
            EvaluasiJalurSimulasiItem(
                lulus=e.lulus,
                syarat_skor_lulus=e.syarat_skor_lulus,
                syarat_level_lulus=e.syarat_level_lulus,
                rata_level_aktual=e.rata_level_aktual,
            )
            if (e := hasil.evaluasi_jalur_simulasi) is not None
            else None
        ),
        review_soal=[
            ReviewSoalItem(
                soal_id=baris.soal_id,
                pertanyaan=baris.soal_ref.pertanyaan,
                jawaban_siswa=baris.jawaban_dipilih,
                kunci_jawaban=baris.soal_ref.kunci_jawaban,
                is_benar=bool(baris.is_benar),
                pembahasan=baris.soal_ref.pembahasan,
            )
            for baris in db.scalars(
                select(PaketTesSoal)
                .where(PaketTesSoal.paket_tes_id == paket_id)
                .order_by(PaketTesSoal.urutan)
            ).all()
        ],
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
    """Siswa membuka satu halaman Materi (tiket 14, fase 2 issue 04): catat
    riwayat baca & progres Materi Wajib aktif. 422 kalau Materi tidak ada atau
    halaman di luar rentang.
    """
    try:
        hasil = catat_baca_halaman(
            db,
            siswa_id=payload.siswa_id,
            materi_id=payload.materi_id,
            halaman=payload.halaman,
            dibuka_pada=payload.timestamp,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return HalamanMateriEventResponse(
        siswa_id=hasil.siswa_id,
        materi_id=hasil.materi_id,
        halaman_dibuka=hasil.halaman_dibuka,
        total_halaman=hasil.total_halaman,
        persentase_selesai=persentase_selesai(
            halaman_dibuka=hasil.halaman_dibuka, total_halaman=hasil.total_halaman
        ),
    )


def _gerbang_simulasi_response(status: StatusGerbangSimulasi) -> GerbangSimulasiResponse:
    return GerbangSimulasiResponse(
        boleh_simulasi=status.boleh_simulasi,
        jumlah_materi_wajib=len(status.materi_wajib),
        jumlah_selesai=status.jumlah_selesai,
        materi_wajib=[
            MateriWajibItem(
                materi_id=m.materi_id,
                judul=m.judul,
                urutan=m.urutan,
                akurasi=m.akurasi,
                halaman_dibuka=m.halaman_dibuka,
                total_halaman=m.total_halaman,
                selesai=m.selesai,
            )
            for m in status.materi_wajib
        ],
    )


@app.get(
    "/api/v1/siswa/{siswa_id}/remedial",
    dependencies=[Depends(verify_internal_token)],
    response_model=GerbangSimulasiResponse,
)
def get_status_gerbang_simulasi(
    siswa_id: str, tingkat_seleksi_id: int, db: Annotated[Session, Depends(get_db)]
) -> GerbangSimulasiResponse:
    """Materi Wajib attempt terakhir siswa di satu tingkat + apakah simulasi
    berikutnya boleh dibuat (Gerbang Simulasi, fase 2 issue 04)."""
    try:
        status = status_gerbang_simulasi(db, siswa_id=siswa_id, tingkat_seleksi_id=tingkat_seleksi_id)
    except TingkatTidakDitemukan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()  # simpan inisialisasi akses siswa baru
    return _gerbang_simulasi_response(status)


@app.get(
    "/api/v1/siswa/{siswa_id}/leaderboard",
    dependencies=[Depends(verify_internal_token)],
    response_model=LeaderboardResponse,
)
def get_leaderboard(
    siswa_id: str,
    db: Annotated[Session, Depends(get_db)],
    tingkat_seleksi_id: int | None = None,
) -> LeaderboardResponse:
    """5 teratas di jenjang yang diikuti siswa (tingkat tertinggi yang sudah
    terbuka), dari skor gabungan 50% skor + 50% kecepatan attempt simulasi.
    `tingkat_seleksi_id` opsional untuk melihat tingkat lain."""
    try:
        hasil = leaderboard_tingkat(db, siswa_id=siswa_id, tingkat_seleksi_id=tingkat_seleksi_id)
    except TingkatTidakDitemukan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()  # simpan inisialisasi akses siswa baru
    return LeaderboardResponse(
        tingkat_seleksi_id=hasil.tingkat.id,
        nama_tingkat=hasil.tingkat.nama,
        peringkat=[
            PeringkatItem(
                peringkat=p.peringkat.peringkat,
                siswa_id=p.peringkat.siswa_id,
                nama_siswa=p.nama_siswa,
                sekolah_id=p.sekolah_id,
                nama_sekolah=p.nama_sekolah,
                skor=p.peringkat.skor,
                durasi_detik=p.peringkat.durasi_detik,
                skor_kecepatan=p.peringkat.skor_kecepatan,
                skor_gabungan=p.peringkat.skor_gabungan,
            )
            for p in hasil.peringkat
        ],
    )


# --- Katalog Materi -------------------------------------------------------------


def _materi_item(
    materi: Materi, dibaca: dict[str, set[int]] | None
) -> MateriItem:
    item = MateriItem(
        materi_id=materi.id,
        tingkat_seleksi_id=materi.tingkat_seleksi_id,
        nama_tingkat=materi.tingkat_seleksi.nama,
        topik=materi.topik,
        judul=materi.judul,
        total_halaman=materi.total_halaman,
    )
    if dibaca is not None:
        jumlah = len(dibaca.get(materi.id, set()) & {h.nomor for h in materi.halaman})
        item.halaman_dibaca = jumlah
        # Materi tanpa dokumen (0 halaman) tidak punya persentase.
        if materi.total_halaman:
            item.persentase_dibaca = persentase_selesai(
                halaman_dibuka=jumlah, total_halaman=materi.total_halaman
            )
    return item


@app.get(
    "/api/v1/materi",
    dependencies=[Depends(verify_internal_token)],
    response_model=list[MateriItem],
)
def get_daftar_materi(
    db: Annotated[Session, Depends(get_db)],
    tingkat_seleksi_id: int | None = None,
    siswa_id: str | None = None,
) -> list[MateriItem]:
    """Daftar Materi (urut tingkat & nomor topik), opsional difilter satu
    tingkat. Dengan siswa_id: ikut jumlah halaman yang pernah dibuka siswa."""
    try:
        materi = daftar_materi(db, tingkat_seleksi_id=tingkat_seleksi_id)
    except TingkatTidakDitemukan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    dibaca = (
        halaman_dibaca_siswa(db, siswa_id=siswa_id, materi_ids=[m.id for m in materi])
        if siswa_id is not None
        else None
    )
    return [_materi_item(m, dibaca) for m in materi]


@app.get(
    "/api/v1/materi/{materi_id}",
    dependencies=[Depends(verify_internal_token)],
    response_model=MateriDetailResponse,
)
def get_detail_materi(
    materi_id: str, db: Annotated[Session, Depends(get_db)], siswa_id: str | None = None
) -> MateriDetailResponse:
    """Satu Materi + daftar isi halamannya (nomor & judul, tanpa konten)."""
    try:
        materi = get_materi(db, materi_id)
    except MateriTidakDitemukan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    dibaca = (
        halaman_dibaca_siswa(db, siswa_id=siswa_id, materi_ids=[materi.id])
        if siswa_id is not None
        else None
    )
    nomor_dibaca = dibaca.get(materi.id, set()) if dibaca is not None else None
    return MateriDetailResponse(
        **_materi_item(materi, dibaca).model_dump(),
        halaman=[
            HalamanRingkasItem(
                nomor=h.nomor,
                judul=h.judul,
                sudah_dibaca=None if nomor_dibaca is None else h.nomor in nomor_dibaca,
            )
            for h in materi.halaman
        ],
    )


@app.get(
    "/api/v1/materi/{materi_id}/halaman/{nomor}",
    dependencies=[Depends(verify_internal_token)],
    response_model=HalamanMateriResponse,
)
def get_halaman_materi(
    materi_id: str, nomor: int, db: Annotated[Session, Depends(get_db)]
) -> HalamanMateriResponse:
    """Konten satu Halaman Materi. Hanya membaca — progres dicatat terpisah
    lewat POST /api/v1/analytics/events/materi-progress."""
    try:
        materi = get_materi(db, materi_id)
    except MateriTidakDitemukan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    halaman = next((h for h in materi.halaman if h.nomor == nomor), None)
    if halaman is None:
        raise HTTPException(
            status_code=404, detail=f"Halaman {nomor} Materi {materi_id} tidak ditemukan"
        )
    return HalamanMateriResponse(
        materi_id=materi.id,
        judul_materi=materi.judul,
        nomor=halaman.nomor,
        judul=halaman.judul,
        konten=halaman.konten,
        total_halaman=materi.total_halaman,
        nomor_sebelumnya=nomor - 1 if nomor > 1 else None,
        nomor_berikutnya=nomor + 1 if nomor < materi.total_halaman else None,
    )



# --- Latihan (formatif wajib, gate simulasi >= 50%) --------------------------


@app.post(
    "/api/v1/latihan/paket",
    dependencies=[Depends(verify_internal_token)],
    response_model=LatihanResponse,
)
def ambil_soal_latihan(
    payload: LatihanRequest, db: Annotated[Session, Depends(get_db)]
) -> LatihanResponse:
    """Ambil soal latihan untuk satu materi. Pembahasan disertakan langsung
    (latihan = formatif, beda dari simulasi)."""
    try:
        soal = susun_paket_latihan(
            db,
            siswa_id=payload.siswa_id,
            materi_id=payload.materi_id,
            jumlah_soal=payload.jumlah_soal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LatihanResponse(
        materi_id=payload.materi_id,
        jumlah_soal=len(soal),
        soal=[
            SoalLatihanItem(
                soal_id=s.id,
                tipe=s.tipe,
                deskripsi=s.deskripsi,
                pertanyaan=s.pertanyaan,
                kode=s.kode,
                gambar=_url_gambar(s.gambar),
                pilihan_jawaban=s.pilihan_jawaban,
                pembahasan=s.pembahasan,
            )
            for s in soal
        ],
    )


@app.post(
    "/api/v1/latihan/submit",
    dependencies=[Depends(verify_internal_token)],
    response_model=SubmitLatihanResponse,
)
def submit_latihan_endpoint(
    payload: SubmitLatihanRequest, db: Annotated[Session, Depends(get_db)]
) -> SubmitLatihanResponse:
    """Nilai sesi Latihan. Threshold lulus: nilai >= 50%.
    Pengulangan unlimited — setiap submit bikin baris Latihan baru."""
    try:
        hasil = submit_latihan(
            db,
            siswa_id=payload.siswa_id,
            materi_id=payload.materi_id,
            tingkat_seleksi_id=payload.tingkat_seleksi_id,
            soal_ids=payload.soal_ids,
            jawaban=[
                JawabanLatihan(soal_id=j.soal_id, jawaban_dipilih=j.jawaban_dipilih)
                for j in payload.jawaban
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return SubmitLatihanResponse(
        latihan_id=hasil.latihan_id,
        nilai=hasil.nilai,
        jumlah_benar=hasil.jumlah_benar,
        jumlah_salah=hasil.jumlah_salah,
        total_soal=hasil.total_soal,
        lulus=hasil.lulus,
    )
