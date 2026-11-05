"""Kontrak DTO Pydantic untuk endpoint Ingest Funnel, Registrasi FR-01, dan
Dashboard Super Admin FR-24.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from funnel_analytics.models import DeviceType, FunnelStage, RegistrationErrorType

RentangWaktu = Literal["7d", "30d", "90d", "all"]


class FunnelEventCreateRequest(BaseModel):
    anonymous_id: str = Field(..., min_length=8, max_length=36)
    session_id: str = Field(..., min_length=8, max_length=36)
    siswa_id: str | None = Field(default=None, max_length=36)
    sekolah_id: str | None = Field(default=None, max_length=36)
    stage: FunnelStage
    page_path: str = Field(default="/", max_length=255)
    device_type: DeviceType | None = None
    utm_source: str | None = Field(default=None, max_length=100)
    referrer: str | None = Field(default=None, max_length=255)
    error_type: RegistrationErrorType | None = None
    occurred_at: datetime | None = None
    auto_backfill: bool = True


class FunnelEventIngestResponse(BaseModel):
    status: Literal["recorded", "ignored_bot"]
    recorded_stages: list[FunnelStage]
    anonymous_id: str
    session_id: str


class RegisterSiswaRequest(BaseModel):
    """Payload `submitRegistrasi(data)` sesuai Sequence Diagram Gambar 18 + identitas funnel."""

    nama: str = Field(default="")
    email: str = Field(default="")
    password: str = Field(default="")
    anonymous_id: str = Field(..., min_length=8, max_length=36)
    session_id: str = Field(..., min_length=8, max_length=36)
    sekolah_id: str | None = None
    device_type: DeviceType | None = None
    utm_source: str | None = None
    occurred_at: datetime | None = None


class RegisterSiswaResponse(BaseModel):
    status: Literal["success"]
    user_id: str
    nama: str
    email: str
    role: str
    anonymous_id: str
    message: str


class FunnelFilterState(BaseModel):
    device_type: DeviceType | None = None
    utm_source: str | None = None


class FunnelKpiSummary(BaseModel):
    total_visitors: int
    total_accounts_created: int
    overall_conversion_rate: float
    median_time_to_convert_seconds: float | None
    p90_time_to_convert_seconds: float | None


class FunnelStageMetrics(BaseModel):
    step: int
    stage: FunnelStage
    label: str
    unique_users: int
    step_conversion_rate: float
    overall_conversion_rate: float
    drop_off_users: int
    drop_off_rate: float


class DropOffAttribution(BaseModel):
    total_step3_drop_off: int
    form_abandonment_users: int
    validation_error_users: int
    error_breakdown: dict[str, int]


class DeviceSegmentMetrics(BaseModel):
    device_type: DeviceType
    visitors: int
    accounts_created: int
    overall_conversion_rate: float


class ChannelSegmentMetrics(BaseModel):
    utm_source: str
    visitors: int
    accounts_created: int
    overall_conversion_rate: float


class FunnelDashboardResponse(BaseModel):
    rentang_waktu: RentangWaktu
    filter: FunnelFilterState
    kpi: FunnelKpiSummary
    stages: list[FunnelStageMetrics]
    drop_off_attribution: DropOffAttribution
    segment_by_device: list[DeviceSegmentMetrics]
    segment_by_channel: list[ChannelSegmentMetrics]
