"""Logika domain untuk pencatatan event funnel, registrasi siswa FR-01,
dan agregasi metrik Dashboard Super Admin FR-24.
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from funnel_analytics.models import (
    ORDERED_FUNNEL_STAGES,
    STAGE_LABELS,
    DeviceType,
    FunnelEvent,
    FunnelStage,
    RegistrationErrorType,
    UserAccount,
)
from funnel_analytics.schemas import (
    ChannelSegmentMetrics,
    DeviceSegmentMetrics,
    DropOffAttribution,
    FunnelDashboardResponse,
    FunnelEventCreateRequest,
    FunnelEventIngestResponse,
    FunnelFilterState,
    FunnelKpiSummary,
    FunnelStageMetrics,
    RegisterSiswaRequest,
    RegisterSiswaResponse,
    RentangWaktu,
)

BOT_PATTERNS: tuple[str, ...] = (
    "bot",
    "crawler",
    "spider",
    "headless",
    "lighthouse",
    "python-requests",
    "curl/",
    "wget/",
    "slurp",
    "bingpreview",
)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegistrationError(Exception):
    def __init__(
        self,
        message: str,
        error_type: RegistrationErrorType,
        recorded_stages: list[FunnelStage] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.recorded_stages: list[FunnelStage] = recorded_stages or []


class DuplicateEmailError(RegistrationError):
    def __init__(
        self,
        email: str,
        recorded_stages: list[FunnelStage] | None = None,
    ) -> None:
        super().__init__(
            f"Email '{email}' sudah terdaftar pada sistem SIAP OSN (FR-01).",
            RegistrationErrorType.DUPLICATE_EMAIL,
            recorded_stages=recorded_stages,
        )


class RegistrationValidationError(RegistrationError):
    def __init__(
        self,
        message: str,
        recorded_stages: list[FunnelStage] | None = None,
    ) -> None:
        super().__init__(
            message,
            RegistrationErrorType.VALIDATION_FAILED,
            recorded_stages=recorded_stages,
        )


def ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_bot_user_agent(user_agent: str | None) -> bool:
    if not isinstance(user_agent, str) or not user_agent:
        return False
    lowered = user_agent.lower()
    return any(pattern in lowered for pattern in BOT_PATTERNS)


def detect_device_type(
    user_agent: str | None, explicit_device: DeviceType | None = None
) -> DeviceType:
    if explicit_device is not None:
        return explicit_device
    if not isinstance(user_agent, str) or not user_agent:
        return DeviceType.DESKTOP
    ua = user_agent.lower()
    if "ipad" in ua or "tablet" in ua:
        return DeviceType.TABLET
    if "mobi" in ua or "android" in ua or "iphone" in ua:
        return DeviceType.MOBILE
    return DeviceType.DESKTOP


def _prerequisites_for_stage(
    stage: FunnelStage, page_path: str
) -> list[FunnelStage]:
    if stage == FunnelStage.PAGE_VISIT and page_path.rstrip("/") == "/register":
        return [FunnelStage.PAGE_VISIT, FunnelStage.CLICK_REGISTER]
    if stage == FunnelStage.CLICK_REGISTER:
        return [FunnelStage.PAGE_VISIT, FunnelStage.CLICK_REGISTER]
    if stage == FunnelStage.START_REGISTRATION:
        return [
            FunnelStage.PAGE_VISIT,
            FunnelStage.CLICK_REGISTER,
            FunnelStage.START_REGISTRATION,
        ]
    if stage == FunnelStage.ACCOUNT_CREATED:
        return [
            FunnelStage.PAGE_VISIT,
            FunnelStage.CLICK_REGISTER,
            FunnelStage.START_REGISTRATION,
            FunnelStage.ACCOUNT_CREATED,
        ]
    if stage == FunnelStage.REGISTRATION_ERROR:
        return [
            FunnelStage.PAGE_VISIT,
            FunnelStage.CLICK_REGISTER,
            FunnelStage.START_REGISTRATION,
            FunnelStage.REGISTRATION_ERROR,
        ]
    return [stage]


def record_funnel_event(
    session: Session,
    payload: FunnelEventCreateRequest,
    user_agent: str | None = None,
) -> FunnelEventIngestResponse:
    """Mencatat event funnel dengan penyaringan bot dan auto-backfill tahap sebelumnya."""
    if is_bot_user_agent(user_agent):
        return FunnelEventIngestResponse(
            status="ignored_bot",
            recorded_stages=[],
            anonymous_id=payload.anonymous_id,
            session_id=payload.session_id,
        )

    occurred_at = ensure_utc(payload.occurred_at)
    device_type = detect_device_type(user_agent, payload.device_type)

    existing_events = list(
        session.scalars(
            select(FunnelEvent).where(
                FunnelEvent.anonymous_id == payload.anonymous_id
            )
        ).all()
    )
    existing_stages = {ev.stage for ev in existing_events}

    if existing_events:
        latest_existing = max(ensure_utc(ev.occurred_at) for ev in existing_events)
        if occurred_at <= latest_existing:
            occurred_at = latest_existing + timedelta(milliseconds=10)

    if payload.siswa_id:
        for ev in existing_events:
            if ev.siswa_id is None:
                ev.siswa_id = payload.siswa_id

    required_chain = _prerequisites_for_stage(payload.stage, payload.page_path)
    stages_to_write: list[FunnelStage] = []
    for candidate in required_chain:
        if candidate == FunnelStage.REGISTRATION_ERROR:
            stages_to_write.append(candidate)
        elif candidate not in existing_stages:
            stages_to_write.append(candidate)

    recorded: list[FunnelStage] = []
    for idx, stg in enumerate(stages_to_write):
        event_time = occurred_at + timedelta(milliseconds=idx * 10)
        if stg == FunnelStage.PAGE_VISIT and payload.stage != FunnelStage.PAGE_VISIT:
            stg_path = "/"
        elif stg in (
            FunnelStage.CLICK_REGISTER,
            FunnelStage.START_REGISTRATION,
            FunnelStage.ACCOUNT_CREATED,
            FunnelStage.REGISTRATION_ERROR,
        ) and payload.page_path == "/":
            stg_path = "/register"
        else:
            stg_path = payload.page_path

        row = FunnelEvent(
            anonymous_id=payload.anonymous_id,
            session_id=payload.session_id,
            siswa_id=payload.siswa_id,
            sekolah_id=payload.sekolah_id,
            stage=stg,
            page_path=stg_path,
            device_type=device_type,
            utm_source=payload.utm_source or "organik",
            referrer=payload.referrer,
            error_type=payload.error_type if stg == FunnelStage.REGISTRATION_ERROR else None,
            occurred_at=event_time,
        )
        session.add(row)
        recorded.append(stg)

    session.commit()
    return FunnelEventIngestResponse(
        status="recorded",
        recorded_stages=recorded,
        anonymous_id=payload.anonymous_id,
        session_id=payload.session_id,
    )


def ensure_funnel_integrity(session: Session) -> int:
    """Memastikan setiap pengguna di database memiliki urutan tahap prasyarat yang utuh:
    - account_created wajib memiliki page_visit, click_register, start_registration, account_created
    - start_registration / registration_error wajib memiliki page_visit, click_register, start_registration
    - click_register wajib memiliki page_visit, click_register
    Serta memperbaiki urutan waktu (occurred_at) secara kronologis.
    """
    all_events = list(session.scalars(select(FunnelEvent)).all())
    by_anon: dict[str, list[FunnelEvent]] = defaultdict(list)
    stitched_user_ids: set[str] = set()

    for ev in all_events:
        by_anon[ev.anonymous_id].append(ev)
        if ev.siswa_id:
            stitched_user_ids.add(ev.siswa_id)

    fixed_count = 0

    # Pastikan semua akun di tabel users memiliki jejak funnel_events lengkap
    all_users = list(session.scalars(select(UserAccount)).all())
    for user in all_users:
        if user.id not in stitched_user_ids:
            anon_id = f"auto-anon-{user.id[:12]}"
            sess_id = f"auto-sess-{user.id[:12]}"
            t_created = ensure_utc(user.created_at)
            t_visit = t_created - timedelta(seconds=45)
            t_click = t_created - timedelta(seconds=30)
            t_start = t_created - timedelta(seconds=15)
            for stg, t_ev, path in (
                (FunnelStage.PAGE_VISIT, t_visit, "/"),
                (FunnelStage.CLICK_REGISTER, t_click, "/register"),
                (FunnelStage.START_REGISTRATION, t_start, "/register"),
                (FunnelStage.ACCOUNT_CREATED, t_created, "/register"),
            ):
                new_ev = FunnelEvent(
                    anonymous_id=anon_id,
                    session_id=sess_id,
                    siswa_id=user.id,
                    stage=stg,
                    page_path=path,
                    device_type=DeviceType.DESKTOP,
                    utm_source="organik",
                    occurred_at=t_ev,
                )
                session.add(new_ev)
                by_anon[anon_id].append(new_ev)
                fixed_count += 1

    # Periksa setiap anonymous_id agar seluruh prasyarat tahap lengkap & berurutan
    for anon_id, evs in by_anon.items():
        if not evs:
            continue
        stage_map: dict[FunnelStage, FunnelEvent] = {}
        for ev in sorted(evs, key=lambda x: ensure_utc(x.occurred_at)):
            if ev.stage not in stage_map:
                stage_map[ev.stage] = ev

        sample = evs[0]
        siswa_id = next((e.siswa_id for e in evs if e.siswa_id), None)
        if siswa_id:
            for e in evs:
                if e.siswa_id != siswa_id:
                    e.siswa_id = siswa_id
                    fixed_count += 1

        if FunnelStage.ACCOUNT_CREATED in stage_map:
            required = [
                FunnelStage.PAGE_VISIT,
                FunnelStage.CLICK_REGISTER,
                FunnelStage.START_REGISTRATION,
                FunnelStage.ACCOUNT_CREATED,
            ]
        elif (
            FunnelStage.START_REGISTRATION in stage_map
            or FunnelStage.REGISTRATION_ERROR in stage_map
        ):
            required = [
                FunnelStage.PAGE_VISIT,
                FunnelStage.CLICK_REGISTER,
                FunnelStage.START_REGISTRATION,
            ]
        elif FunnelStage.CLICK_REGISTER in stage_map:
            required = [
                FunnelStage.PAGE_VISIT,
                FunnelStage.CLICK_REGISTER,
            ]
        else:
            required = [FunnelStage.PAGE_VISIT]

        earliest_time = min(ensure_utc(e.occurred_at) for e in evs)

        for idx, req_stage in enumerate(required):
            if req_stage not in stage_map:
                backfill_time = earliest_time - timedelta(seconds=(len(required) - idx) * 5)
                new_ev = FunnelEvent(
                    anonymous_id=anon_id,
                    session_id=sample.session_id,
                    siswa_id=siswa_id,
                    sekolah_id=sample.sekolah_id,
                    stage=req_stage,
                    page_path="/" if req_stage == FunnelStage.PAGE_VISIT else "/register",
                    device_type=sample.device_type,
                    utm_source=sample.utm_source or "organik",
                    referrer=sample.referrer,
                    occurred_at=backfill_time,
                )
                session.add(new_ev)
                stage_map[req_stage] = new_ev
                fixed_count += 1

        # Pastikan urutan waktu kronologis ketat antar tahap prasyarat
        ordered_present = [stage_map[s] for s in required if s in stage_map]
        times = sorted(ensure_utc(e.occurred_at) for e in ordered_present)
        for idx, ev_obj in enumerate(ordered_present):
            target_t = times[idx]
            if idx > 0 and target_t <= ensure_utc(ordered_present[idx - 1].occurred_at):
                target_t = ensure_utc(ordered_present[idx - 1].occurred_at) + timedelta(seconds=1)
            if ensure_utc(ev_obj.occurred_at) != target_t:
                ev_obj.occurred_at = target_t
                fixed_count += 1

        if (
            FunnelStage.REGISTRATION_ERROR in stage_map
            and FunnelStage.START_REGISTRATION in stage_map
        ):
            err_ev = stage_map[FunnelStage.REGISTRATION_ERROR]
            start_t = ensure_utc(stage_map[FunnelStage.START_REGISTRATION].occurred_at)
            if ensure_utc(err_ev.occurred_at) <= start_t:
                err_ev.occurred_at = start_t + timedelta(seconds=1)
                fixed_count += 1

    if fixed_count > 0:
        session.commit()
    return fixed_count


def register_student(
    session: Session,
    payload: RegisterSiswaRequest,
    user_agent: str | None = None,
) -> RegisterSiswaResponse:
    """Implementasi `submitRegistrasi(data)` sesuai FR-01, Gambar 12, dan Gambar 18.

    - Memeriksa kelengkapan data wajib (`nama`, `email`, `password`)
    - Memeriksa keunikan email (`cekEmailTerdaftar`)
    - Jika gagal: mencatat `registration_error` ke `funnel_events` lalu melempar error
    - Jika berhasil: menyimpan akun ke tabel `users` dan mencatat `account_created`
      dengan menyatukan `anonymous_id` ke `users.id` (UUID).
    """
    occurred_at = ensure_utc(payload.occurred_at)
    device_type = detect_device_type(user_agent, payload.device_type)
    nama_clean = payload.nama.strip()
    email_clean = payload.email.strip().lower()
    password_raw = payload.password

    if not nama_clean or not email_clean or not password_raw:
        err_ingest = record_funnel_event(
            session,
            FunnelEventCreateRequest(
                anonymous_id=payload.anonymous_id,
                session_id=payload.session_id,
                sekolah_id=payload.sekolah_id,
                stage=FunnelStage.REGISTRATION_ERROR,
                page_path="/register",
                device_type=device_type,
                utm_source=payload.utm_source,
                error_type=RegistrationErrorType.VALIDATION_FAILED,
                occurred_at=occurred_at,
                auto_backfill=True,
            ),
            user_agent=user_agent,
        )
        raise RegistrationValidationError(
            "Nama, email, dan password wajib diisi sesuai ketentuan FR-01.",
            recorded_stages=err_ingest.recorded_stages,
        )

    if not EMAIL_REGEX.match(email_clean) or len(password_raw) < 8:
        err_ingest = record_funnel_event(
            session,
            FunnelEventCreateRequest(
                anonymous_id=payload.anonymous_id,
                session_id=payload.session_id,
                sekolah_id=payload.sekolah_id,
                stage=FunnelStage.REGISTRATION_ERROR,
                page_path="/register",
                device_type=device_type,
                utm_source=payload.utm_source,
                error_type=RegistrationErrorType.VALIDATION_FAILED,
                occurred_at=occurred_at,
                auto_backfill=True,
            ),
            user_agent=user_agent,
        )
        raise RegistrationValidationError(
            "Format email harus valid dan password minimal 8 karakter.",
            recorded_stages=err_ingest.recorded_stages,
        )

    existing_user = session.scalar(
        select(UserAccount).where(func.lower(UserAccount.email) == email_clean)
    )
    if existing_user is not None:
        err_ingest = record_funnel_event(
            session,
            FunnelEventCreateRequest(
                anonymous_id=payload.anonymous_id,
                session_id=payload.session_id,
                sekolah_id=payload.sekolah_id,
                stage=FunnelStage.REGISTRATION_ERROR,
                page_path="/register",
                device_type=device_type,
                utm_source=payload.utm_source,
                error_type=RegistrationErrorType.DUPLICATE_EMAIL,
                occurred_at=occurred_at,
                auto_backfill=True,
            ),
            user_agent=user_agent,
        )
        raise DuplicateEmailError(
            email_clean,
            recorded_stages=err_ingest.recorded_stages,
        )

    user_id = str(uuid.uuid4())
    password_hash = hashlib.sha256(password_raw.encode("utf-8")).hexdigest()
    new_user = UserAccount(
        id=user_id,
        nama=nama_clean,
        email=email_clean,
        password=password_hash,
        role="siswa",
        created_at=occurred_at,
    )
    session.add(new_user)
    session.flush()

    ingest_res = record_funnel_event(
        session,
        FunnelEventCreateRequest(
            anonymous_id=payload.anonymous_id,
            session_id=payload.session_id,
            siswa_id=user_id,
            sekolah_id=payload.sekolah_id,
            stage=FunnelStage.ACCOUNT_CREATED,
            page_path="/register",
            device_type=device_type,
            utm_source=payload.utm_source,
            occurred_at=occurred_at,
            auto_backfill=True,
        ),
        user_agent=user_agent,
    )

    return RegisterSiswaResponse(
        status="success",
        user_id=user_id,
        nama=nama_clean,
        email=email_clean,
        role="siswa",
        anonymous_id=payload.anonymous_id,
        message="Registrasi akun siswa SIAP OSN berhasil disimpan.",
        recorded_stages=ingest_res.recorded_stages,
    )


def _percentile(sorted_values: list[float], quantile: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return round(sorted_values[0], 1)
    pos = (len(sorted_values) - 1) * quantile
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return round(sorted_values[lower], 1)
    weight = pos - lower
    interpolated = sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight
    return round(interpolated, 1)


def _compute_monotonic_users(
    events: list[FunnelEvent],
) -> tuple[
    dict[FunnelStage, set[str]],
    dict[str, dict[FunnelStage, datetime]],
    dict[str, set[RegistrationErrorType]],
]:
    """Menghitung himpunan `anonymous_id` monotonik ketat S1 >= S2 >= S3 >= S4.

    Menjamin aturan domain:
    - Pengguna yang membuat akun (account_created) pasti tercatat di S1, S2, S3, S4.
    - Pengguna yang memulai registrasi (start_registration / registration_error) pasti tercatat di S1, S2, S3.
    - Pengguna yang klik pendaftaran (click_register) pasti tercatat di S1, S2.
    """
    min_time_by_user: dict[str, dict[FunnelStage, datetime]] = defaultdict(dict)
    max_time_by_user: dict[str, dict[FunnelStage, datetime]] = defaultdict(dict)
    errors_by_user: dict[str, set[RegistrationErrorType]] = defaultdict(set)

    for ev in events:
        occ = ensure_utc(ev.occurred_at)
        uid = ev.anonymous_id
        stg = ev.stage
        if stg not in min_time_by_user[uid] or occ < min_time_by_user[uid][stg]:
            min_time_by_user[uid][stg] = occ
        if stg not in max_time_by_user[uid] or occ > max_time_by_user[uid][stg]:
            max_time_by_user[uid][stg] = occ
        if stg == FunnelStage.REGISTRATION_ERROR and ev.error_type is not None:
            errors_by_user[uid].add(ev.error_type)

    s4_users = {
        u
        for u, stages in min_time_by_user.items()
        if FunnelStage.ACCOUNT_CREATED in stages
    }
    s3_users = s4_users | {
        u
        for u, stages in min_time_by_user.items()
        if FunnelStage.START_REGISTRATION in stages
        or FunnelStage.REGISTRATION_ERROR in stages
    }
    s2_users = s3_users | {
        u
        for u, stages in min_time_by_user.items()
        if FunnelStage.CLICK_REGISTER in stages
    }
    s1_users = s2_users | {
        u
        for u, stages in min_time_by_user.items()
        if FunnelStage.PAGE_VISIT in stages
    }

    eligible: dict[FunnelStage, set[str]] = {
        FunnelStage.PAGE_VISIT: s1_users,
        FunnelStage.CLICK_REGISTER: s2_users,
        FunnelStage.START_REGISTRATION: s3_users,
        FunnelStage.ACCOUNT_CREATED: s4_users,
    }

    return eligible, min_time_by_user, errors_by_user


def compute_funnel_dashboard(
    session: Session,
    rentang_waktu: RentangWaktu = "30d",
    device_type: DeviceType | None = None,
    utm_source: str | None = None,
    reference_time: datetime | None = None,
) -> FunnelDashboardResponse:
    """Menghitung metrik Conversion Funnel untuk Dashboard Super Admin (FR-24)."""
    now = ensure_utc(reference_time)
    window_days = {"7d": 7, "30d": 30, "90d": 90}.get(rentang_waktu)

    base_stmt = select(FunnelEvent)
    if window_days is not None:
        cutoff = now - timedelta(days=window_days)
        base_stmt = base_stmt.where(FunnelEvent.occurred_at >= cutoff)

    all_window_events = list(session.scalars(base_stmt).all())

    filtered_events = [
        ev
        for ev in all_window_events
        if (device_type is None or ev.device_type == device_type)
        and (utm_source is None or ev.utm_source == utm_source)
    ]

    eligible, min_time_by_user, errors_by_user = _compute_monotonic_users(filtered_events)

    n1 = len(eligible[FunnelStage.PAGE_VISIT])
    n4 = len(eligible[FunnelStage.ACCOUNT_CREATED])
    overall_rate = round((n4 / n1) * 100.0, 1) if n1 > 0 else 0.0

    durations: list[float] = []
    for u in eligible[FunnelStage.ACCOUNT_CREATED]:
        user_times = min_time_by_user[u]
        t_visit = user_times.get(FunnelStage.PAGE_VISIT, min(user_times.values()))
        t_created = user_times[FunnelStage.ACCOUNT_CREATED]
        delta_sec = max(0.0, (t_created - t_visit).total_seconds())
        durations.append(delta_sec)
    durations.sort()

    median_ttc = _percentile(durations, 0.50)
    p90_ttc = _percentile(durations, 0.90)

    stages_output: list[FunnelStageMetrics] = []
    for idx, stg in enumerate(ORDERED_FUNNEL_STAGES, start=1):
        count_curr = len(eligible[stg])
        if idx == 1:
            step_rate = 100.0 if count_curr > 0 else 0.0
            drop_users = 0
            drop_rate = 0.0
        else:
            prev_stg = ORDERED_FUNNEL_STAGES[idx - 2]
            count_prev = len(eligible[prev_stg])
            step_rate = round((count_curr / count_prev) * 100.0, 1) if count_prev > 0 else 0.0
            drop_users = max(0, count_prev - count_curr)
            drop_rate = round((drop_users / count_prev) * 100.0, 1) if count_prev > 0 else 0.0

        ov_rate = round((count_curr / n1) * 100.0, 1) if n1 > 0 else 0.0
        stages_output.append(
            FunnelStageMetrics(
                step=idx,
                stage=stg,
                label=STAGE_LABELS[stg],
                unique_users=count_curr,
                step_conversion_rate=step_rate,
                overall_conversion_rate=ov_rate,
                drop_off_users=drop_users,
                drop_off_rate=drop_rate,
            )
        )

    dropped_step3_to_4 = eligible[FunnelStage.START_REGISTRATION] - eligible[FunnelStage.ACCOUNT_CREATED]
    val_error_users = {u for u in dropped_step3_to_4 if len(errors_by_user.get(u, set())) > 0}
    abandon_users = dropped_step3_to_4 - val_error_users

    dup_email_count = sum(
        1
        for u in val_error_users
        if RegistrationErrorType.DUPLICATE_EMAIL in errors_by_user.get(u, set())
    )
    val_failed_count = sum(
        1
        for u in val_error_users
        if RegistrationErrorType.VALIDATION_FAILED in errors_by_user.get(u, set())
    )

    attribution = DropOffAttribution(
        total_step3_drop_off=len(dropped_step3_to_4),
        form_abandonment_users=len(abandon_users),
        validation_error_users=len(val_error_users),
        error_breakdown={
            RegistrationErrorType.DUPLICATE_EMAIL.value: dup_email_count,
            RegistrationErrorType.VALIDATION_FAILED.value: val_failed_count,
        },
    )

    device_segments: list[DeviceSegmentMetrics] = []
    for dev in (DeviceType.DESKTOP, DeviceType.MOBILE, DeviceType.TABLET):
        dev_events = [
            ev
            for ev in all_window_events
            if ev.device_type == dev and (utm_source is None or ev.utm_source == utm_source)
        ]
        dev_eligible, _, _ = _compute_monotonic_users(dev_events)
        v_cnt = len(dev_eligible[FunnelStage.PAGE_VISIT])
        c_cnt = len(dev_eligible[FunnelStage.ACCOUNT_CREATED])
        if v_cnt > 0 or c_cnt > 0:
            device_segments.append(
                DeviceSegmentMetrics(
                    device_type=dev,
                    visitors=v_cnt,
                    accounts_created=c_cnt,
                    overall_conversion_rate=round((c_cnt / v_cnt) * 100.0, 1) if v_cnt > 0 else 0.0,
                )
            )

    channels = sorted({ev.utm_source or "organik" for ev in all_window_events})
    channel_segments: list[ChannelSegmentMetrics] = []
    for ch in channels:
        ch_events = [
            ev
            for ev in all_window_events
            if (ev.utm_source or "organik") == ch
            and (device_type is None or ev.device_type == device_type)
        ]
        ch_eligible, _, _ = _compute_monotonic_users(ch_events)
        v_cnt = len(ch_eligible[FunnelStage.PAGE_VISIT])
        c_cnt = len(ch_eligible[FunnelStage.ACCOUNT_CREATED])
        if v_cnt > 0:
            channel_segments.append(
                ChannelSegmentMetrics(
                    utm_source=ch,
                    visitors=v_cnt,
                    accounts_created=c_cnt,
                    overall_conversion_rate=round((c_cnt / v_cnt) * 100.0, 1),
                )
            )
    channel_segments.sort(key=lambda item: item.visitors, reverse=True)

    return FunnelDashboardResponse(
        rentang_waktu=rentang_waktu,
        filter=FunnelFilterState(device_type=device_type, utm_source=utm_source),
        kpi=FunnelKpiSummary(
            total_visitors=n1,
            total_accounts_created=n4,
            overall_conversion_rate=overall_rate,
            median_time_to_convert_seconds=median_ttc,
            p90_time_to_convert_seconds=p90_ttc,
        ),
        stages=stages_output,
        drop_off_attribution=attribution,
        segment_by_device=device_segments,
        segment_by_channel=channel_segments,
    )


def seed_demo_funnel_data(session: Session, reset_existing: bool = True) -> dict[str, int]:
    """Mengisi data simulasi realistis (200 calon siswa OSN Informatika) untuk demo
    Dashboard Super Admin FR-24.
    """
    if reset_existing:
        session.execute(delete(FunnelEvent))
        session.execute(delete(UserAccount))
        session.commit()

    now = datetime.now(timezone.utc)
    channels = ["grup_pembina_osn", "organik_google", "instagram_toki", "portal_sekolah"]
    devices = [
        DeviceType.DESKTOP,
        DeviceType.DESKTOP,
        DeviceType.MOBILE,
        DeviceType.MOBILE,
        DeviceType.TABLET,
    ]

    total_visitors = 200
    created_accounts = 0

    for i in range(total_visitors):
        anon_id = f"demo-anon-{i:04d}-siaposn"
        sess_id = f"demo-sess-{i:04d}-siaposn"
        dev = devices[i % len(devices)]
        ch = channels[i % len(channels)]
        days_ago = (i % 25) + 1
        base_time = now - timedelta(days=days_ago, minutes=(i * 7) % 300)

        uid_for_user = (
            str(uuid.uuid5(uuid.NAMESPACE_DNS, f"siswa-{i}@siaposn.id"))
            if i < 76
            else None
        )
        t_visit = base_time
        t_click = t_visit + timedelta(seconds=12 + (i % 15))
        t_start = t_click + timedelta(seconds=15 + (i % 20))

        # Tahap 1: 200 pengunjung unik membuka halaman
        session.add(
            FunnelEvent(
                anonymous_id=anon_id,
                session_id=sess_id,
                siswa_id=uid_for_user,
                stage=FunnelStage.PAGE_VISIT,
                page_path="/",
                device_type=dev,
                utm_source=ch,
                occurred_at=t_visit,
            )
        )

        # Tahap 2: 144 pengunjung menekan tombol Daftar (72% dari Tahap 1)
        if i < 144:
            session.add(
                FunnelEvent(
                    anonymous_id=anon_id,
                    session_id=sess_id,
                    siswa_id=uid_for_user,
                    stage=FunnelStage.CLICK_REGISTER,
                    page_path="/register",
                    device_type=dev,
                    utm_source=ch,
                    occurred_at=t_click,
                )
            )

        # Tahap 3: 112 pengunjung mulai mengisi form Nama/Email/Password
        if i < 112:
            session.add(
                FunnelEvent(
                    anonymous_id=anon_id,
                    session_id=sess_id,
                    siswa_id=uid_for_user,
                    stage=FunnelStage.START_REGISTRATION,
                    page_path="/register",
                    device_type=dev,
                    utm_source=ch,
                    occurred_at=t_start,
                )
            )

        # Tahap 4: 76 berhasil membuat akun siswa (FR-01)
        if i < 76 and uid_for_user is not None:
            t_created = t_start + timedelta(seconds=25 + ((i * 7) % 60))
            email = f"siswa{i + 1}@sman-osn.sch.id"
            session.add(
                UserAccount(
                    id=uid_for_user,
                    nama=f"Siswa OSN {i + 1}",
                    email=email,
                    password=hashlib.sha256(b"osninformatika").hexdigest(),
                    role="siswa",
                    created_at=t_created,
                )
            )
            session.flush()
            session.add(
                FunnelEvent(
                    anonymous_id=anon_id,
                    session_id=sess_id,
                    siswa_id=uid_for_user,
                    stage=FunnelStage.ACCOUNT_CREATED,
                    page_path="/register",
                    device_type=dev,
                    utm_source=ch,
                    occurred_at=t_created,
                )
            )
            created_accounts += 1
        elif 76 <= i < 92:
            # 16 pengguna gagal karena validasi (10 duplicate_email, 6 validation_failed)
            err_type = (
                RegistrationErrorType.DUPLICATE_EMAIL
                if i < 86
                else RegistrationErrorType.VALIDATION_FAILED
            )
            t_err = t_start + timedelta(seconds=20 + (i % 20))
            session.add(
                FunnelEvent(
                    anonymous_id=anon_id,
                    session_id=sess_id,
                    stage=FunnelStage.REGISTRATION_ERROR,
                    page_path="/register",
                    device_type=dev,
                    utm_source=ch,
                    error_type=err_type,
                    occurred_at=t_err,
                )
            )
        # Sisanya (92 <= i < 112, yaitu 20 pengguna) adalah Form Abandonment murni

    session.commit()
    return {"seeded_visitors": total_visitors, "created_accounts": created_accounts}
