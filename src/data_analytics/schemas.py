"""DTO Pydantic untuk kontrak API publik: endpoint submit Pre-Test/Simulasi
(tiket 11), Kenaikan Tingkat (tiket 03), dan event Progress Halaman Materi
(tiket 14). Terpisah dari model SQLAlchemy (models.py) supaya bentuk wire
format (mis. jenis_tes UPPERCASE, label status_pemetaan berkapital) tidak
membocorkan representasi penyimpanan internal.
"""

from __future__ import annotations

from datetime import datetime
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


# --- Kenaikan Tingkat (tiket 03) ---------------------------------------------
# tingkat_seleksi_id di sini merujuk ke katalog TingkatSeleksi LOKAL (int) —
# lihat catatan gap id di models.AturanKenaikanTingkat.


class AksesTingkatItem(BaseModel):
    tingkat_seleksi_id: int
    nama: str
    status: str
    simulasi_terbuka: bool = False
    dibuka_karena: str | None
    catatan: str | None


class AksesTingkatSiswaResponse(BaseModel):
    siswa_id: str
    daftar_akses: list[AksesTingkatItem]


class OverrideAksesRequest(BaseModel):
    siswa_id: str
    tingkat_seleksi_id: int
    status: Literal["terbuka", "terkunci"]
    catatan: str | None = None


class AturanKenaikanItem(BaseModel):
    id: int
    tingkat_asal_id: int
    tingkat_tujuan_id: int
    skor_simulasi_min: float
    persentase_kompetensi_cukup_min: float
    aktif: bool


class UpdateAturanKenaikanRequest(BaseModel):
    skor_simulasi_min: float | None = Field(default=None, ge=0, le=100)
    persentase_kompetensi_cukup_min: float | None = Field(default=None, ge=0, le=100)
    aktif: bool | None = None


class EvaluasiKenaikanRequest(BaseModel):
    siswa_id: str
    hasil_tes_id: int
    tingkat_asal_id: int
    skor: float = Field(ge=0, le=100)
    jumlah_kompetensi_cukup: int = Field(ge=0)
    total_kompetensi_silabus: int = Field(gt=0)


class EvaluasiKenaikanResponse(BaseModel):
    evaluasi_dilakukan: bool
    hasil_evaluasi: str | None = None
    syarat_skor_lulus: bool | None = None
    syarat_kompetensi_lulus: bool | None = None
    persentase_cukup_aktual: float | None = None


# --- Dashboard Super Admin (tiket 04) ----------------------------------------
# Section "analisis_kompetensi" (top/bottom 3 Kompetensi) resolusi tiket 04
# sengaja BELUM diimplementasikan di sini: butuh join HasilTesSubkompetensi.
# subkompetensi_id (str, caller-supplied UUID sejak tiket 11) ke katalog
# Subkompetensi/Kompetensi LOKAL (int) — gap yang sama dengan "progress_materi
# dan PK katalog seed lokal belum diselaraskan ke UUID" yang sudah dicatat
# tiket 11. Menunggu penyelarasan skema id itu, bukan sesuatu yang aman
# ditambal di sini.


class DashboardFilter(BaseModel):
    sekolah_id: str | None
    rentang_waktu: str


class DashboardKPI(BaseModel):
    total_siswa_aktif: int
    total_tes_selesai: int
    total_pre_test: int
    total_simulasi: int
    rata_rata_skor_simulasi: float
    rasio_kelulusan_tingkat: float


class DistribusiTingkatItem(BaseModel):
    tingkat_id: int
    nama: str
    jumlah_siswa: int
    persentase: float


class TrenAktivitasItem(BaseModel):
    tanggal: str
    pre_test: int
    simulasi: int


class DistribusiPredikatItem(BaseModel):
    label: str
    jumlah: int
    persentase: float


class KomparasiSekolahItem(BaseModel):
    sekolah_id: str
    total_siswa_aktif: int
    total_simulasi: int
    rata_rata_skor: float
    rasio_kelulusan_tingkat: float


class DashboardResponse(BaseModel):
    rentang_waktu: str
    filter: DashboardFilter
    kpi: DashboardKPI
    distribusi_tingkat: list[DistribusiTingkatItem]
    tren_aktivitas: list[TrenAktivitasItem]
    distribusi_predikat: list[DistribusiPredikatItem]
    komparasi_sekolah: list[KomparasiSekolahItem]


# --- Progress Halaman Materi (tiket 14) ---------------------------------------
# Field id di sini int, mengikuti tipe kolom ProgressMateri yang sudah ada
# (tiket 02/09) — BUKAN UUID string seperti diusulkan resolusi tiket 14/06.
# Migrasi progress_materi ke UUID sudah dicatat sebagai utang teknis terpisah
# sejak tiket 11 ("sengaja belum diselaraskan"); tidak dilakukan di sini
# supaya blast radius tiket ini tetap terbatas pada endpoint yang belum ada
# (lihat resolusi/Implementation tiket 14).


class HalamanMateriEventRequest(BaseModel):
    siswa_id: int
    materi_id: int
    subkompetensi_id: int
    tingkat_seleksi_id: int
    total_halaman: int = Field(gt=0)
    halaman_dibuka: int = Field(ge=1)
    # Divalidasi (payload wajib menyertakannya, sesuai kontrak tiket 14) tapi
    # tidak disimpan sebagai kolom terpisah — diperbarui_pada (server-side,
    # ProgressMateri) sudah menangkap "kapan terakhir disentuh", konsisten
    # dengan pola diselesaikan_pada di endpoint submit (tiket 11).
    timestamp: datetime


class HalamanMateriEventResponse(BaseModel):
    status: Literal["success"] = "success"
    siswa_id: int
    materi_id: int
    halaman_tertinggi_dicapai: int
    total_halaman: int
    persentase_selesai: float


# --- Aturan Kelulusan & Akses Pre-Test Berjenjang (tiket 15) -----------------


class AturanPreTestItem(BaseModel):
    id: int
    tingkat_seleksi_id: int
    skor_min: float
    aktif: bool


class UpdateAturanPreTestRequest(BaseModel):
    skor_min: float | None = Field(default=None, ge=0, le=100)
    aktif: bool | None = None


class EvaluasiPreTestRequest(BaseModel):
    siswa_id: str
    hasil_tes_id: int
    tingkat_seleksi_id: int
    skor: float = Field(ge=0, le=100)


class EvaluasiPreTestResponse(BaseModel):
    evaluasi_dilakukan: bool
    hasil_evaluasi: str | None = None  # "lulus" | "tidak_lulus"
    lulus: bool | None = None
    skor_aktual: float | None = None
    passing_grade: float | None = None
    simulasi_terbuka: bool | None = None
    tingkat_berikutnya_terbuka: bool | None = None

