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
