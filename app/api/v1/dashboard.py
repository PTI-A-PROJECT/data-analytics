from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import hitung_metrik_dashboard

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
def get_admin_dashboard(
    sekolah_id: Optional[str] = Query(None, description="Filter opsional ID sekolah"),
    tingkat_seleksi_id: Optional[int] = Query(None, description="Filter opsional tingkat seleksi"),
    rentang_waktu: str = Query("30d", description="Rentang waktu: 7d, 30d, 90d, atau all"),
    db: Session = Depends(get_db),
):
    """
    Endpoint agregasi metrik Dashboard Super Admin secara real-time (Tiket 04):
    - KPI Utama (siswa aktif, tes selesai, rata skor, rasio kelulusan tingkat)
    - Distribusi tingkat aktif siswa
    - Tren aktivitas harian
    - Distribusi predikat simulasi
    - Analisis kelemahan & kekuatan kompetensi (termasuk efisiensi waktu)
    - Komparasi performa antar-sekolah pilot
    """
    return hitung_metrik_dashboard(
        db=db,
        sekolah_id=sekolah_id,
        tingkat_seleksi_id=tingkat_seleksi_id,
        rentang_waktu=rentang_waktu,
    )
