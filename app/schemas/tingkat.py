from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class AksesTingkatItem(BaseModel):
    tingkat_seleksi_id: int
    kode: str
    nama: str
    status: str  # 'terbuka', 'terkunci'
    dibuka_karena: Optional[str] = None
    dibuka_pada: Optional[datetime] = None
    catatan: Optional[str] = None


class AksesTingkatSiswaResponse(BaseModel):
    siswa_id: str
    daftar_akses: List[AksesTingkatItem]


class OverrideAksesRequest(BaseModel):
    siswa_id: str
    tingkat_seleksi_id: int
    status: str = "terbuka"  # 'terbuka', 'terkunci'
    catatan: Optional[str] = None


class AturanKenaikanItem(BaseModel):
    id: int
    tingkat_asal_id: int
    tingkat_tujuan_id: int
    skor_simulasi_min: float
    persentase_kompetensi_cukup_min: float
    aktif: bool


class UpdateAturanKenaikanRequest(BaseModel):
    skor_simulasi_min: Optional[float] = None
    persentase_kompetensi_cukup_min: Optional[float] = None
    aktif: Optional[bool] = None


