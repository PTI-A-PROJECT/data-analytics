"""Auth antar-layanan (tiket 10) — endpoint internal hanya boleh dipanggil
backend aplikasi utama lewat network Docker privat, divalidasi via header
X-Internal-Token (bukan diekspos ke publik sama sekali, lihat resolusi tiket
"Rencana Deployment/Hosting untuk Sekolah Pilot").
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from data_analytics.config import get_settings


def verify_internal_token(x_internal_token: Annotated[str, Header()]) -> None:
    """Header X-Internal-Token wajib ada (FastAPI mengembalikan 422 kalau
    tidak) dan harus cocok dengan INTERNAL_API_TOKEN (403 kalau salah).
    """
    if x_internal_token != get_settings().internal_api_token:
        raise HTTPException(status_code=403, detail="Token internal tidak valid")
