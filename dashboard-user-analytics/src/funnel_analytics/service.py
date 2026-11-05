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
    def __init__(self, message: str, error_type: RegistrationErrorType) -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type


class DuplicateEmailError(RegistrationError):
    def __init__(self, email: str) -> None:
        super().__init__(
            f"Email '{email}' sudah terdaftar pada sistem SIAP OSN (FR-01).",
            RegistrationErrorType.DUPLICATE_EMAIL,
        )


class RegistrationValidationError(RegistrationError):
    def __init__(self, message: str) -> None:
        super().__init__(message, RegistrationErrorType.VALIDATION_FAILED)


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

    if payload.auto_backfill:
        existing_stages = set(
            session.scalars(
                select(FunnelEvent.stage).where(
                    FunnelEvent.anonymous_id == payload.anonymous_id
                )
            ).all()
        )
        required_chain = _prerequisites_for_stage(payload.stage, payload.page_path)
        stages_to_write: list[FunnelStage] = []
        for candidate in required_chain:
            if candidate == payload.stage or candidate not in existing_stages:
                stages_to_write.append(candidate)
    else:
        stages_to_write = [payload.stage]

    recorded: list[FunnelStage] = []
    for idx, stg in enumerate(stages_to_write):
        event_time = occurred_at + timedelta(milliseconds=idx)
        row = FunnelEvent(
            anonymous_id=payload.anonymous_id,
            session_id=payload.session_id,
            siswa_id=payload.siswa_id if stg == FunnelStage.ACCOUNT_CREATED else None,
            sekolah_id=payload.sekolah_id,
            stage=stg,
            page_path=payload.page_path,
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
        record_funnel_event(
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
            "Nama, email, dan password wajib diisi sesuai ketentuan FR-01."
        )

    if not EMAIL_REGEX.match(email_clean) or len(password_raw) < 8:
        record_funnel_event(
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
            "Format email harus valid dan password minimal 8 karakter."
        )

    existing_user = session.scalar(
        select(UserAccount).where(func.lower(UserAccount.email) == email_clean)
    )
    if existing_user is not None:
        record_funnel_event(
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
        raise DuplicateEmailError(email_clean)

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

    record_funnel_event(
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
    """Menghitung himpunan `anonymous_id` monotonik ketat S1 >= S2 >= S3 >= S4."""
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

    eligible: dict[FunnelStage, set[str]] = {}
    s1 = FunnelStage.PAGE_VISIT
    eligible[s1] = {u for u, stages in min_time_by_user.items() if s1 in stages}

    prev_stage = s1
    for current_stage in ORDERED_FUNNEL_STAGES[1:]:
        current_set: set[str] = set()
        for u in eligible[prev_stage]:
            if current_stage in max_time_by_user[u]:
                if max_time_by_user[u][current_stage] >= min_time_by_user[u][s1]:
                    current_set.add(u)
        eligible[current_stage] = current_set
        prev_stage = current_stage

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
        t_visit = min_time_by_user[u][FunnelStage.PAGE_VISIT]
        t_created = min_time_by_user[u][FunnelStage.ACCOUNT_CREATED]
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

        # Tahap 1: 200 pengunjung unik membuka halaman
        session.add(
            FunnelEvent(
                anonymous_id=anon_id,
                session_id=sess_id,
                stage=FunnelStage.PAGE_VISIT,
                page_path="/",
                device_type=dev,
                utm_source=ch,
                occurred_at=base_time,
            )
        )

        # Tahap 2: 144 pengunjung menekan tombol Daftar (72% dari Tahap 1)
        if i < 144:
            t_click = base_time + timedelta(seconds=12 + (i % 20))
            session.add(
                FunnelEvent(
                    anonymous_id=anon_id,
                    session_id=sess_id,
                    stage=FunnelStage.CLICK_REGISTER,
                    page_path="/register",
                    device_type=dev,
                    utm_source=ch,
                    occurred_at=t_click,
                )
            )

        # Tahap 3: 112 pengunjung mulai mengisi form Nama/Email/Password
        if i < 112:
            t_start = base_time + timedelta(seconds=25 + (i % 25))
            session.add(
                FunnelEvent(
                    anonymous_id=anon_id,
                    session_id=sess_id,
                    stage=FunnelStage.START_REGISTRATION,
                    page_path="/register",
                    device_type=dev,
                    utm_source=ch,
                    occurred_at=t_start,
                )
            )

        # Tahap 4: 76 berhasil membuat akun siswa (FR-01)
        if i < 76:
            duration_sec = 48 + ((i * 9) % 110)
            t_created = base_time + timedelta(seconds=duration_sec)
            uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"siswa-{i}@siaposn.id"))
            email = f"siswa{i + 1}@sman-osn.sch.id"
            session.add(
                UserAccount(
                    id=uid,
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
                    siswa_id=uid,
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
            t_err = base_time + timedelta(seconds=55 + (i % 30))
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
