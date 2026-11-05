"""Pengujian otomatis (Unit & Integration Tests) untuk User Analytics &
Conversion Funnel SIAP OSN (FR-01 & FR-24).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Pastikan direktori src modul dashboard-user-analytics masuk ke sys.path
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from funnel_analytics.api import (
    get_admin_funnel_dashboard,
    ingest_funnel_event,
    list_recent_activities,
    list_recent_registered_users,
    register_siswa_endpoint,
)
from funnel_analytics.models import (
    Base,
    DeviceType,
    FunnelStage,
    RegistrationErrorType,
)
from funnel_analytics.schemas import (
    FunnelEventCreateRequest,
    RegisterSiswaRequest,
)
from funnel_analytics.service import (
    compute_funnel_dashboard,
    record_funnel_event,
    seed_demo_funnel_data,
)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_deduplication_on_multiple_page_refreshes(db_session: Session) -> None:
    """Refresh halaman berkali-kali oleh anonymous_id yang sama tetap dihitung 1 pengunjung."""
    t0 = datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        record_funnel_event(
            db_session,
            FunnelEventCreateRequest(
                anonymous_id="anon-siswa-001",
                session_id="sess-siswa-001",
                stage=FunnelStage.PAGE_VISIT,
                page_path="/",
                device_type=DeviceType.DESKTOP,
                occurred_at=t0 + timedelta(seconds=i * 10),
            ),
        )

    dashboard = compute_funnel_dashboard(db_session, rentang_waktu="30d", reference_time=t0 + timedelta(hours=1))
    assert dashboard.kpi.total_visitors == 1
    assert dashboard.stages[0].unique_users == 1
    assert dashboard.stages[0].step_conversion_rate == 100.0


def test_auto_backfill_direct_entry_to_register_page(db_session: Session) -> None:
    """Calon siswa yang membuka langsung URL `/register` otomatis tercatat page_visit + click_register."""
    res = ingest_funnel_event(
        FunnelEventCreateRequest(
            anonymous_id="anon-direct-reg-01",
            session_id="sess-direct-reg-01",
            stage=FunnelStage.PAGE_VISIT,
            page_path="/register",
            device_type=DeviceType.MOBILE,
        ),
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
        db=db_session,
    )
    assert res.status == "recorded"
    assert res.recorded_stages == [FunnelStage.PAGE_VISIT, FunnelStage.CLICK_REGISTER]

    dash = get_admin_funnel_dashboard(rentang_waktu="all", db=db_session)
    assert dash.stages[0].unique_users == 1
    assert dash.stages[1].unique_users == 1
    assert dash.stages[1].step_conversion_rate == 100.0


def test_bot_user_agent_is_filtered_out(db_session: Session) -> None:
    """Request dari crawler/bot diabaikan agar tidak menurunkan rasio konversi."""
    res = ingest_funnel_event(
        FunnelEventCreateRequest(
            anonymous_id="anon-bot-999",
            session_id="sess-bot-999",
            stage=FunnelStage.PAGE_VISIT,
            page_path="/",
        ),
        user_agent="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        db=db_session,
    )
    assert res.status == "ignored_bot"
    assert res.recorded_stages == []

    dash = get_admin_funnel_dashboard(rentang_waktu="all", db=db_session)
    assert dash.kpi.total_visitors == 0


def test_fr01_registration_stitches_anonymous_id_to_user_id(db_session: Session) -> None:
    """Registrasi FR-01 yang valid membuat baris di `users` dan menyatukan `anonymous_id` ke `siswa_id`."""
    anon_id = "anon-calon-juara-osn"
    sess_id = "sess-calon-juara-osn"

    # Tahap 1 -> 2 -> 3
    ingest_funnel_event(
        FunnelEventCreateRequest(anonymous_id=anon_id, session_id=sess_id, stage=FunnelStage.PAGE_VISIT, page_path="/"),
        db=db_session,
    )
    ingest_funnel_event(
        FunnelEventCreateRequest(anonymous_id=anon_id, session_id=sess_id, stage=FunnelStage.CLICK_REGISTER, page_path="/register"),
        db=db_session,
    )
    ingest_funnel_event(
        FunnelEventCreateRequest(anonymous_id=anon_id, session_id=sess_id, stage=FunnelStage.START_REGISTRATION, page_path="/register"),
        db=db_session,
    )

    # Tahap 4: Submit Registrasi (FR-01)
    reg_res = register_siswa_endpoint(
        RegisterSiswaRequest(
            nama="Budi Santoso",
            email="budi.osn@sman1.sch.id",
            password="passwordosn2026",
            anonymous_id=anon_id,
            session_id=sess_id,
            device_type=DeviceType.DESKTOP,
            utm_source="grup_pembina_osn",
        ),
        db=db_session,
    )
    assert reg_res.status == "success"
    created_user_id = reg_res.user_id
    assert reg_res.email == "budi.osn@sman1.sch.id"

    # Pastikan data tersimpan di daftar akun dan ter-stitch
    recent_users = list_recent_registered_users(db=db_session)
    matched = [u for u in recent_users if u["id"] == created_user_id]
    assert len(matched) == 1
    assert matched[0]["anonymous_id"] == anon_id

    # Pastikan dihitung di tahap 4 conversion funnel
    dash = get_admin_funnel_dashboard(rentang_waktu="all", db=db_session)
    assert dash.stages[3].unique_users == 1
    assert dash.stages[3].overall_conversion_rate == 100.0


def test_drop_off_attribution_abandonment_vs_validation_errors(db_session: Session) -> None:
    """Memisahkan drop-off Tahap 3 -> 4 menjadi Form Abandonment vs Duplicate Email vs Validation Failed."""
    # User 1: Berhasil sampai Tahap 4
    register_siswa_endpoint(
        RegisterSiswaRequest(
            nama="Siswa Satu",
            email="terdaftar@siaposn.id",
            password="password123",
            anonymous_id="anon-user-0001",
            session_id="sess-user-0001",
        ),
        db=db_session,
    )

    # User 2: Gagal karena email duplikat (FR-01 cekEmailTerdaftar)
    with pytest.raises(HTTPException) as exc_info:
        register_siswa_endpoint(
            RegisterSiswaRequest(
                nama="Siswa Dua",
                email="terdaftar@siaposn.id",
                password="password123",
                anonymous_id="anon-user-0002",
                session_id="sess-user-0002",
            ),
            db=db_session,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error_type"] == RegistrationErrorType.DUPLICATE_EMAIL.value

    # User 3: Gagal karena format password kurang dari 8 karakter
    with pytest.raises(HTTPException) as exc_info_val:
        register_siswa_endpoint(
            RegisterSiswaRequest(
                nama="Siswa Tiga",
                email="tiga@siaposn.id",
                password="123",
                anonymous_id="anon-user-0003",
                session_id="sess-user-0003",
            ),
            db=db_session,
        )
    assert exc_info_val.value.status_code == 422
    assert exc_info_val.value.detail["error_type"] == RegistrationErrorType.VALIDATION_FAILED.value

    # User 4: Mulai mengisi form (start_registration) lalu menutup tab (Form Abandonment)
    ingest_funnel_event(
        FunnelEventCreateRequest(
            anonymous_id="anon-user-0004",
            session_id="sess-user-0004",
            stage=FunnelStage.START_REGISTRATION,
            page_path="/register",
        ),
        db=db_session,
    )

    dash = get_admin_funnel_dashboard(rentang_waktu="all", db=db_session)
    assert dash.stages[2].unique_users == 4  # Semua 4 user mencapai Tahap 3
    assert dash.stages[3].unique_users == 1  # Hanya 1 user mencapai Tahap 4

    attr = dash.drop_off_attribution
    assert attr.total_step3_drop_off == 3
    assert attr.form_abandonment_users == 1
    assert attr.validation_error_users == 2
    assert attr.error_breakdown["duplicate_email"] == 1
    assert attr.error_breakdown["validation_failed"] == 1


def test_time_to_convert_and_demo_seed_data(db_session: Session) -> None:
    """Memastikan data simulasi 200 calon siswa menghitung metrik funnel dan Time-to-Convert dengan benar."""
    summary = seed_demo_funnel_data(db_session, reset_existing=True)
    assert summary["seeded_visitors"] == 200
    assert summary["created_accounts"] == 76

    dash = compute_funnel_dashboard(db_session, rentang_waktu="all")
    assert dash.kpi.total_visitors == 200
    assert dash.kpi.total_accounts_created == 76
    assert dash.kpi.overall_conversion_rate == 38.0
    assert dash.kpi.median_time_to_convert_seconds is not None
    assert dash.kpi.median_time_to_convert_seconds > 0
    assert dash.kpi.p90_time_to_convert_seconds is not None
    assert dash.kpi.p90_time_to_convert_seconds >= dash.kpi.median_time_to_convert_seconds

    # Verifikasi 4 tahap monotonik
    assert dash.stages[0].unique_users == 200
    assert dash.stages[1].unique_users == 144
    assert dash.stages[2].unique_users == 112
    assert dash.stages[3].unique_users == 76

    # Drop-off attribution
    assert dash.drop_off_attribution.total_step3_drop_off == 36
    assert dash.drop_off_attribution.validation_error_users == 16
    assert dash.drop_off_attribution.form_abandonment_users == 20
    assert dash.drop_off_attribution.error_breakdown["duplicate_email"] == 10
    assert dash.drop_off_attribution.error_breakdown["validation_failed"] == 6


def test_realtime_activity_logging_and_recent_events(db_session: Session) -> None:
    """Memastikan endpoint /api/v1/admin/activities/recent mengembalikan log aktivitas real-time terbaru."""
    ingest_funnel_event(
        FunnelEventCreateRequest(
            anonymous_id="anon-realtime-test",
            session_id="sess-realtime-test",
            stage=FunnelStage.PAGE_VISIT,
            page_path="/",
            device_type=DeviceType.DESKTOP,
        ),
        db=db_session,
    )
    activities = list_recent_activities(limit=5, db=db_session)
    assert len(activities) >= 1
    assert activities[0]["anonymous_id"] == "anon-realtime-test"
    assert activities[0]["stage"] == "page_visit"
    assert activities[0]["page_path"] == "/"
