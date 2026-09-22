from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class DashboardFilter(BaseModel):
    sekolah_id: Optional[str] = None
    tingkat_seleksi_id: Optional[int] = None
    rentang_waktu: str = "30d"


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


class AnalisisKompetensiItem(BaseModel):
    kompetensi_id: int
    nama: str
    rata_rata_skor: float
    total_soal_dikerjakan: int
    persentase_butuh_optimasi: float = 0.0


class AnalisisKompetensiResponse(BaseModel):
    terkuat: List[AnalisisKompetensiItem]
    terlemah: List[AnalisisKompetensiItem]


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
    distribusi_tingkat: List[DistribusiTingkatItem]
    tren_aktivitas: List[TrenAktivitasItem]
    distribusi_predikat: List[DistribusiPredikatItem]
    analisis_kompetensi: AnalisisKompetensiResponse
    komparasi_sekolah: List[KomparasiSekolahItem]
