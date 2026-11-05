"""Skema penyimpanan SQLAlchemy untuk tabel `users` (FR-01) dan `funnel_events`
(Tiket 01 & Tiket 02 Conversion Funnel SIAP OSN).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class FunnelStage(enum.StrEnum):
    PAGE_VISIT = "page_visit"
    CLICK_REGISTER = "click_register"
    START_REGISTRATION = "start_registration"
    REGISTRATION_ERROR = "registration_error"
    ACCOUNT_CREATED = "account_created"


ORDERED_FUNNEL_STAGES: tuple[FunnelStage, ...] = (
    FunnelStage.PAGE_VISIT,
    FunnelStage.CLICK_REGISTER,
    FunnelStage.START_REGISTRATION,
    FunnelStage.ACCOUNT_CREATED,
)

STAGE_LABELS: dict[FunnelStage, str] = {
    FunnelStage.PAGE_VISIT: "Kunjungan Halaman",
    FunnelStage.CLICK_REGISTER: "Klik Pendaftaran",
    FunnelStage.START_REGISTRATION: "Memulai Registrasi",
    FunnelStage.ACCOUNT_CREATED: "Akun Berhasil Dibuat",
    FunnelStage.REGISTRATION_ERROR: "Gagal Validasi Registrasi",
}


class DeviceType(enum.StrEnum):
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"


class RegistrationErrorType(enum.StrEnum):
    DUPLICATE_EMAIL = "duplicate_email"
    VALIDATION_FAILED = "validation_failed"


class UserAccount(Base):
    """Representasi tabel `users` sesuai PDM Gambar 4 (hal. 15) dokumen System Analyst SIAP OSN."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nama: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="siswa")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class FunnelEvent(Base):
    """Log tahapan interaksi calon pengguna pra-registrasi hingga akun berhasil dibuat."""

    __tablename__ = "funnel_events"
    __table_args__ = (
        Index("ix_funnel_events_time_stage", "occurred_at", "stage"),
        Index("ix_funnel_events_anon_time", "anonymous_id", "occurred_at"),
        Index("ix_funnel_events_device_time", "device_type", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    anonymous_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    siswa_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sekolah_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    stage: Mapped[FunnelStage] = mapped_column(
        SqlEnum(
            FunnelStage,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        ),
        nullable=False,
    )
    page_path: Mapped[str] = mapped_column(String(255), nullable=False, default="/")
    device_type: Mapped[DeviceType] = mapped_column(
        SqlEnum(
            DeviceType,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        ),
        nullable=False,
        default=DeviceType.DESKTOP,
    )
    utm_source: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    referrer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_type: Mapped[RegistrationErrorType | None] = mapped_column(
        SqlEnum(
            RegistrationErrorType,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        ),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
