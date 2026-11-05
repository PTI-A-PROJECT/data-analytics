"""Aplikasi FastAPI untuk User Analytics & Conversion Funnel SIAP OSN."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from funnel_analytics.models import Base, DeviceType, FunnelEvent, UserAccount
from funnel_analytics.schemas import (
    FunnelDashboardResponse,
    FunnelEventCreateRequest,
    FunnelEventIngestResponse,
    RegisterSiswaRequest,
    RegisterSiswaResponse,
    RentangWaktu,
)
from funnel_analytics.service import (
    DuplicateEmailError,
    RegistrationValidationError,
    compute_funnel_dashboard,
    record_funnel_event,
    register_student,
    seed_demo_funnel_data,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_DB_URL = f"sqlite:///{(BASE_DIR / 'funnel_analytics.db').as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class RealtimeBroadcaster:
    """Manajer broadcast Server-Sent Events (SSE) untuk streaming log aktivitas secara real-time."""

    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue[str]] = set()

    def publish_sync(self, event_type: str, data: dict[str, Any]) -> None:
        payload = json.dumps(
            {
                "type": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        for queue in list(self.subscribers):
            try:
                queue.put_nowait(payload)
            except Exception:
                pass

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        self.subscribers.discard(q)


broadcaster = RealtimeBroadcaster()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI(
    title="SIAP OSN — User Analytics & Conversion Funnel Service",
    version="1.0.0",
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def serve_website_ui() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Halaman website belum tersedia.")
    return FileResponse(index_path)


@app.post(
    "/api/v1/analytics/events/funnel",
    response_model=FunnelEventIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@app.post(
    "/api/v1/onboarding/step",
    response_model=FunnelEventIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def ingest_funnel_event(
    payload: FunnelEventCreateRequest,
    user_agent: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> FunnelEventIngestResponse:
    """Endpoint pencatatan tahapan funnel (`page_visit`, `click_register`, `start_registration`)."""
    res = record_funnel_event(db, payload, user_agent=user_agent)
    broadcaster.publish_sync(
        "activity_logged",
        {
            "anonymous_id": payload.anonymous_id,
            "stage": payload.stage.value if hasattr(payload.stage, "value") else str(payload.stage),
            "page_path": payload.page_path,
            "device_type": payload.device_type.value if hasattr(payload.device_type, "value") else str(payload.device_type),
            "recorded_stages": [s.value if hasattr(s, "value") else str(s) for s in res.recorded_stages],
        },
    )
    return res


@app.post(
    "/api/v1/auth/register",
    response_model=RegisterSiswaResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_siswa_endpoint(
    payload: RegisterSiswaRequest,
    user_agent: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> RegisterSiswaResponse:
    """Endpoint `Controller Auth: submitRegistrasi(data)` sesuai FR-01 & Gambar 18."""
    try:
        res = register_student(db, payload, user_agent=user_agent)
        broadcaster.publish_sync(
            "account_created",
            {
                "anonymous_id": payload.anonymous_id,
                "user_id": res.user_id,
                "nama": payload.nama,
                "email": payload.email,
                "stage": "account_created",
            },
        )
        return res
    except DuplicateEmailError as exc:
        broadcaster.publish_sync(
            "registration_error",
            {
                "anonymous_id": payload.anonymous_id,
                "stage": "registration_error",
                "error_type": exc.error_type.value,
                "message": exc.message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_type": exc.error_type.value, "message": exc.message},
        ) from exc
    except RegistrationValidationError as exc:
        broadcaster.publish_sync(
            "registration_error",
            {
                "anonymous_id": payload.anonymous_id,
                "stage": "registration_error",
                "error_type": exc.error_type.value,
                "message": exc.message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_type": exc.error_type.value, "message": exc.message},
        ) from exc


@app.get("/api/v1/admin/funnel", response_model=FunnelDashboardResponse)
def get_admin_funnel_dashboard(
    rentang_waktu: RentangWaktu = Query(default="30d"),
    device_type: DeviceType | None = Query(default=None),
    utm_source: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FunnelDashboardResponse:
    """Endpoint agregasi Conversion Funnel untuk Dashboard Super Admin (FR-24)."""
    clean_device = device_type if isinstance(device_type, DeviceType) else None
    clean_utm = utm_source if isinstance(utm_source, str) else None
    clean_window: RentangWaktu = rentang_waktu if isinstance(rentang_waktu, str) else "30d"
    return compute_funnel_dashboard(
        db,
        rentang_waktu=clean_window,
        device_type=clean_device,
        utm_source=clean_utm,
    )


@app.post("/api/v1/admin/funnel/seed")
def reseed_demo_data(db: Session = Depends(get_db)) -> dict[str, int]:
    """Mengatur ulang data simulasi 200 calon siswa untuk pengujian Dashboard Super Admin."""
    res = seed_demo_funnel_data(db, reset_existing=True)
    broadcaster.publish_sync("data_reseeded", res)
    return res


@app.get("/api/v1/admin/events/stream")
async def stream_live_events(request: Request) -> StreamingResponse:
    """Stream SSE real-time untuk log aktivitas pengguna dan metrik corong."""
    queue = broadcaster.subscribe()

    async def event_generator():
        try:
            # Kirim handshake koneksi awal
            yield 'event: ping\ndata: {"status": "connected"}\n\n'
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=12.0)
                    yield f"event: message\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive ping setiap 12 detik agar koneksi HTTP tidak terputus
                    yield 'event: ping\ndata: {"status": "heartbeat"}\n\n'
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/v1/admin/activities/recent")
def list_recent_activities(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Mengambil riwayat log aktivitas pengguna terbaru secara real-time dari database."""
    events = list(
        db.scalars(
            select(FunnelEvent).order_by(FunnelEvent.occurred_at.desc()).limit(limit)
        ).all()
    )
    result: list[dict[str, Any]] = []
    for ev in events:
        result.append(
            {
                "id": ev.id,
                "anonymous_id": ev.anonymous_id,
                "session_id": ev.session_id,
                "stage": ev.stage.value if hasattr(ev.stage, "value") else str(ev.stage),
                "page_path": ev.page_path,
                "device_type": ev.device_type.value if hasattr(ev.device_type, "value") else str(ev.device_type),
                "utm_source": ev.utm_source,
                "error_type": ev.error_type.value if ev.error_type else None,
                "siswa_id": ev.siswa_id,
                "occurred_at": ev.occurred_at.isoformat(),
            }
        )
    return result


@app.get("/api/v1/admin/users")
def list_recent_registered_users(db: Session = Depends(get_db)) -> list[dict[str, str]]:
    """Menampilkan 10 akun siswa terakhir yang berhasil dibuat (FR-01) beserta anonymous_id-nya."""
    users = list(
        db.scalars(
            select(UserAccount).order_by(UserAccount.created_at.desc()).limit(10)
        ).all()
    )
    result: list[dict[str, str]] = []
    for u in users:
        anon_id = db.scalar(
            select(FunnelEvent.anonymous_id).where(FunnelEvent.siswa_id == u.id).limit(1)
        )
        result.append(
            {
                "id": u.id,
                "nama": u.nama,
                "email": u.email,
                "role": u.role,
                "anonymous_id": anon_id or "-",
                "created_at": u.created_at.isoformat(),
            }
        )
    return result
