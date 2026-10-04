"""DTO Pydantic untuk kontrak API publik: Paket Tes pre-test/simulasi (fase 2
issue 02/03), Kenaikan Tingkat (tiket 03), dan event Progress Halaman Materi
(tiket 14). Terpisah dari model SQLAlchemy (models.py) supaya bentuk wire
format (mis. label status_pemetaan berkapital) tidak
membocorkan representasi penyimpanan internal.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from data_analytics.models import JenisTes, LevelSoal, StatusAkses, StatusPemetaan, TipeSoal


# --- Akses tingkat & aturan kenaikan (tiket 03, fase 2 issue 02) ------------


class AksesTingkatItem(BaseModel):
    tingkat_seleksi_id: int
    nama: str
    status: StatusAkses
    dibuka_karena: str | None
    catatan: str | None


class AksesTingkatSiswaResponse(BaseModel):
    siswa_id: str
    daftar_akses: list[AksesTingkatItem]


class OverrideAksesRequest(BaseModel):
    siswa_id: str
    tingkat_seleksi_id: int
    status: StatusAkses
    catatan: str | None = None


class AturanKenaikanItem(BaseModel):
    id: int
    tingkat_asal_id: int
    tingkat_tujuan_id: int
    skor_simulasi_min: float
    skor_pretest_jalur_cepat: float
    rata_level_min: float
    aktif: bool


class UpdateAturanKenaikanRequest(BaseModel):
    skor_simulasi_min: float | None = Field(default=None, ge=0, le=100)
    skor_pretest_jalur_cepat: float | None = Field(default=None, ge=0, le=100)
    rata_level_min: float | None = Field(default=None, ge=1, le=3)
    aktif: bool | None = None


# --- Aturan predikat (tiket 01) -----------------------------------------------


class PredikatItem(BaseModel):
    """Satu kelompok rentang skor: berlaku untuk skor >= batas_bawah sampai
    batas_bawah predikat di atasnya (eksklusif)."""

    label: str = Field(min_length=1)
    batas_bawah: float = Field(ge=0, le=100)


class AturanPredikatItem(BaseModel):
    tingkat_seleksi_id: int
    # Dari batas_bawah tertinggi.
    predikat: list[PredikatItem]


class UpdateAturanPredikatRequest(BaseModel):
    """Mengganti SELURUH predikat satu tingkat; wajib ada batas_bawah 0."""

    predikat: list[PredikatItem] = Field(min_length=1)


# --- Aturan adaptif (fase 2 issue 03) -----------------------------------------


class AturanAdaptifItem(BaseModel):
    tingkat_seleksi_id: int
    jumlah_soal_pretest: int
    jumlah_soal_simulasi: int
    kuota_min: int
    bobot_lemah: int
    ambang_naik: float
    ambang_lemah: float


class UpdateAturanAdaptifRequest(BaseModel):
    """Semua opsional; syarat lintas field (ambang_lemah < ambang_naik,
    kuota_min x jumlah Materi <= jumlah_soal_simulasi) dicek di repository."""

    jumlah_soal_pretest: int | None = Field(default=None, gt=0)
    jumlah_soal_simulasi: int | None = Field(default=None, gt=0)
    kuota_min: int | None = Field(default=None, ge=1)
    bobot_lemah: int | None = Field(default=None, ge=1)
    ambang_naik: float | None = Field(default=None, gt=0, le=100)
    ambang_lemah: float | None = Field(default=None, ge=0, lt=100)


# --- Paket Tes (fase 2 issue 02/03) -------------------------------------------


class PaketRequest(BaseModel):
    """Body POST /api/v1/pretest/paket dan POST /api/v1/simulasi/paket."""

    siswa_id: str
    tingkat_seleksi_id: int


class SoalPaketItem(BaseModel):
    """Soal yang disajikan ke siswa — SENGAJA tanpa kunci jawaban & pembahasan."""

    urutan: int
    soal_id: str
    materi_id: str
    tipe: TipeSoal
    # Konteks bersama beberapa soal; tampilkan di atas pertanyaan.
    deskripsi: str | None
    pertanyaan: str
    # Potongan kode program; tampilkan sebagai blok kode monospace.
    kode: str | None
    # URL gambar: path API (/api/v1/konten/gambar/...) atau URL absolut sumber.
    gambar: str | None
    # Kosong untuk isian singkat (jawab dengan teks/angka).
    pilihan_jawaban: dict[str, str]


class PaketResponse(BaseModel):
    paket_id: int
    siswa_id: str
    tingkat_seleksi_id: int
    jenis_tes: JenisTes
    jumlah_soal_diminta: int
    soal: list[SoalPaketItem]


class JawabanPaketRequest(BaseModel):
    soal_id: str
    # None = dilewati; soal paket yang tidak dikirim juga dihitung salah.
    jawaban_dipilih: str | None
    dibuka_pada: datetime | None = None
    dijawab_pada: datetime | None = None


class SubmitPaketRequest(BaseModel):
    # Snapshot afiliasi sekolah untuk Dashboard Admin (resolusi tiket 08).
    sekolah_id: str | None = None
    # Snapshot nama untuk Leaderboard.
    nama_siswa: str | None = None
    nama_sekolah: str | None = None
    jawaban: list[JawabanPaketRequest]


class PetaMateriItem(BaseModel):
    materi_id: str
    jumlah_soal: int
    jumlah_benar: int
    akurasi: float | None
    status_pemetaan: str


class PerubahanLevelItem(BaseModel):
    materi_id: str
    level_sebelum: LevelSoal
    level_sesudah: LevelSoal
    lemah: bool
    akurasi: float | None
    # False kalau Materi tampil < kuota_min soal (tidak diubah).
    diperbarui: bool


class EvaluasiJalurSimulasiItem(BaseModel):
    lulus: bool
    syarat_skor_lulus: bool
    syarat_level_lulus: bool
    rata_level_aktual: float


class SubmitPaketResponse(BaseModel):
    hasil_tes_id: int
    skor: float
    predikat: str
    peta_kompetensi: list[PetaMateriItem]
    # Materi Belum Cukup, dari akurasi terendah.
    materi_lemah: list[str]
    daftar_akses: list[AksesTingkatItem]
    # Hanya simulasi: Level Soal Siswa per Materi sebelum/sesudah attempt ini.
    perubahan_level: list[PerubahanLevelItem] = []
    # Hanya simulasi dengan aturan kenaikan aktif dari tingkat ini.
    evaluasi_jalur_simulasi: EvaluasiJalurSimulasiItem | None = None
    review_soal: list[ReviewSoalItem] = []


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
    komparasi_sekolah: list[KomparasiSekolahItem]


# --- Baca halaman Materi & Materi Wajib (tiket 14, fase 2 issue 04) ---------


class HalamanMateriEventRequest(BaseModel):
    """Event "siswa membuka halaman Materi". total_halaman & tingkat dibaca
    dari katalog Materi lokal (fase 2 issue 01), tidak dikirim fullstack."""

    siswa_id: str
    materi_id: str
    halaman: int = Field(ge=1)
    # Waktu halaman dibuka menurut klien; dipakai sebagai dibuka_pada.
    timestamp: datetime


class HalamanMateriEventResponse(BaseModel):
    status: Literal["success"] = "success"
    siswa_id: str
    materi_id: str
    # Halaman unik yang pernah dibuka (navigasi bebas).
    halaman_dibuka: int
    total_halaman: int
    persentase_selesai: float


class MateriWajibItem(BaseModel):
    materi_id: str
    judul: str
    urutan: int
    akurasi: float
    # Halaman yang dibuka SEJAK Materi ini diwajibkan.
    halaman_dibuka: int
    total_halaman: int
    selesai: bool


class GerbangSimulasiResponse(BaseModel):
    """Juga body 409 POST /api/v1/simulasi/paket (Gerbang Simulasi)."""

    boleh_simulasi: bool
    # Progress Belajar fase 2: jumlah_selesai / jumlah_materi_wajib.
    jumlah_materi_wajib: int
    jumlah_selesai: int
    materi_wajib: list[MateriWajibItem]


# --- Leaderboard ----------------------------------------------------------------


class PeringkatItem(BaseModel):
    peringkat: int
    siswa_id: str
    nama_siswa: str | None
    sekolah_id: str | None
    nama_sekolah: str | None
    skor: float
    durasi_detik: float
    # 100 = waktu per soal tercepat di tingkat ini.
    skor_kecepatan: float
    # 50% skor + 50% skor_kecepatan.
    skor_gabungan: float


class LeaderboardResponse(BaseModel):
    tingkat_seleksi_id: int
    nama_tingkat: str
    # Maksimal 5, dari skor_gabungan tertinggi.
    peringkat: list[PeringkatItem]


# --- Katalog Materi -------------------------------------------------------------


class HalamanRingkasItem(BaseModel):
    nomor: int
    judul: str | None
    # Hanya terisi kalau siswa_id dikirim.
    sudah_dibaca: bool | None = None


class MateriItem(BaseModel):
    materi_id: str
    tingkat_seleksi_id: int
    nama_tingkat: str
    topik: int | None
    judul: str
    total_halaman: int
    # Hanya terisi kalau siswa_id dikirim: halaman unik yang pernah dibuka.
    halaman_dibaca: int | None = None
    persentase_dibaca: float | None = None


class MateriDetailResponse(MateriItem):
    # Daftar isi (tanpa konten) — konten per halaman lewat endpoint halaman.
    halaman: list[HalamanRingkasItem]


class HalamanMateriResponse(BaseModel):
    materi_id: str
    judul_materi: str
    nomor: int
    judul: str | None
    # Markdown; rumus LaTeX dalam $...$ (inline) dan $$...$$ (blok), kode
    # dalam fenced code block.
    konten: str
    total_halaman: int
    nomor_sebelumnya: int | None
    nomor_berikutnya: int | None



# --- Latihan (formatif wajib, gate simulasi >= 50%) --------------------------


class LatihanRequest(BaseModel):
    """Request untuk mengambil soal latihan satu materi."""
    siswa_id: str
    materi_id: str
    jumlah_soal: int = 10


class SoalLatihanItem(BaseModel):
    soal_id: str
    tipe: str
    deskripsi: str | None
    pertanyaan: str
    kode: str | None
    gambar: str | None
    pilihan_jawaban: dict[str, str]
    pembahasan: str | None


class LatihanResponse(BaseModel):
    materi_id: str
    jumlah_soal: int
    soal: list[SoalLatihanItem]


class JawabanLatihanItem(BaseModel):
    soal_id: str
    jawaban_dipilih: str | None = None


class SubmitLatihanRequest(BaseModel):
    siswa_id: str
    materi_id: str
    tingkat_seleksi_id: int
    soal_ids: list[str]
    jawaban: list[JawabanLatihanItem]


class SubmitLatihanResponse(BaseModel):
    latihan_id: int
    nilai: float
    jumlah_benar: int
    jumlah_salah: int
    total_soal: int
    lulus: bool



# --- Review Soal (pembahasan per soal) ---------------------------------------


class ReviewSoalItem(BaseModel):
    soal_id: str
    pertanyaan: str
    jawaban_siswa: str | None
    kunci_jawaban: str
    is_benar: bool
    pembahasan: str | None

# --- Endpoint stateless /hitung/* (dipanggil Laravel) -------------------------


class HitungSoalItem(BaseModel):
    soal_id: str
    level: LevelSoal
    tipe: TipeSoal = TipeSoal.PILIHAN_GANDA
    kunci: str
    jawaban: str | None = None
    materi_id: str | None = None


class HitungAturanPredikat(BaseModel):
    label: str
    batas_bawah: float = Field(ge=0, le=100)


class HitungPenilaianRequest(BaseModel):
    soal: list[HitungSoalItem] = Field(min_length=1)
    aturan_predikat: list[HitungAturanPredikat] | None = None


class HitungHasilSoalItem(BaseModel):
    soal_id: str
    benar: bool
    bobot: int


class HitungPenilaianResponse(BaseModel):
    skor: float
    bobot_benar: int
    bobot_total: int
    jumlah_soal: int
    jumlah_benar: int
    jumlah_salah: int
    predikat: str | None
    hasil_soal: list[HitungHasilSoalItem]


class HitungPretestRequest(HitungPenilaianRequest):
    ambang_lemah: float = Field(default=60.0, ge=0, le=100)
    ambang_kuat: float = Field(default=80.0, ge=0, le=100)


class HitungPetaMateriItem(BaseModel):
    materi_id: str
    jumlah_soal: int
    jumlah_benar: int
    bobot_total: int
    bobot_benar: int
    akurasi: float
    status: StatusPemetaan


class HitungPretestResponse(HitungPenilaianResponse):
    pemetaan: list[HitungPetaMateriItem]
    materi_lemah: list[str]


class HitungSimulasiRequest(HitungPretestRequest):
    tingkat: Literal["kabupaten", "provinsi"]


class HitungSimulasiResponse(HitungPretestResponse):
    passing_grade: float
    lulus: bool


class HitungLatihanRequest(BaseModel):
    soal: list[HitungSoalItem] = Field(min_length=1)
    threshold: float = Field(default=50.0, ge=0, le=100)


class HitungAkurasiMateriItem(BaseModel):
    materi_id: str
    akurasi: float
    lulus: bool


class HitungLatihanResponse(BaseModel):
    skor: float
    lulus: bool
    akurasi_per_materi: list[HitungAkurasiMateriItem]
