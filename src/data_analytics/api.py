"""FastAPI app — health endpoints (tiket 09). Endpoint domain (skor, progress,
dsb.) menyusul di tiket kontrak API (tiket 11).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from data_analytics.db import get_db

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
