from fastapi import APIRouter
from app.api.v1 import tes, tingkat, dashboard

api_router = APIRouter()
api_router.include_router(tes.router, prefix="/tes", tags=["Tes & Pengerjaan"])
api_router.include_router(tingkat.router, prefix="/tingkat", tags=["Tingkat Seleksi & Akses"])
api_router.include_router(dashboard.router, prefix="/admin", tags=["Super Admin Analytics"])

