"""FastAPI app — health endpoints (tiket 09) dan endpoint admin internal
(tiket 10). Endpoint domain (skor, progress, dsb.) menyusul di tiket kontrak
API (tiket 11).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from data_analytics.auth import verify_internal_token
from data_analytics.config import get_settings
from data_analytics.db import get_db
from data_analytics.repository import anonimkan_hasil_tes_kedaluwarsa

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
