"""Skema penyimpanan untuk Aturan Skor & Hasil Simulasi — lihat resolusi tiket 01
di .scratch/osn-data-analytics/issues/01-aturan-skor-hasil-simulasi.md.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class JenisTes(enum.StrEnum):
    PRE_TEST = "pre_test"
    SIMULASI = "simulasi"


# tingkat_seleksi_id, simulasi_id, dan subkompetensi_id (di bawah) merujuk ke
# entitas yang dikelola tim fullstack, bukan tabel di database ini — sengaja
# tanpa ForeignKey() SQLAlchemy, sama seperti pola di ADR 0002 (layanan ini
# tidak memiliki katalog Materi/Tingkat Seleksi/Simulasi/Subkompetensi sendiri).
class AturanPredikat(Base):
    """Config Super Admin, per Tingkat Seleksi. Di-seed otomatis dengan 4 predikat
    default saat sebuah Tingkat Seleksi belum punya aturan sendiri — lihat
    repository.get_or_create_aturan_predikat.
    """

    __tablename__ = "aturan_predikat"
    __table_args__ = (
        UniqueConstraint("tingkat_seleksi_id", "label"),
        CheckConstraint(
            "batas_bawah >= 0 AND batas_bawah <= 100", name="ck_aturan_predikat_rentang"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tingkat_seleksi_id: Mapped[int]
    label: Mapped[str]
    batas_bawah: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HasilTes(Base):
    """Satu baris per attempt (Pre-Test atau Simulasi). predikat_label adalah
    snapshot yang dibekukan saat attempt dihitung — lihat resolusi tiket 01,
    bagian "Histori".
    """

    __tablename__ = "hasil_tes"
    __table_args__ = (
        CheckConstraint(
            f"(jenis_tes = '{JenisTes.SIMULASI}' AND simulasi_id IS NOT NULL) "
            f"OR (jenis_tes = '{JenisTes.PRE_TEST}' AND simulasi_id IS NULL)",
            name="ck_hasil_tes_simulasi_id_konsisten",
        ),
        CheckConstraint("skor >= 0 AND skor <= 100", name="ck_hasil_tes_skor_rentang"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    siswa_id: Mapped[int]
    tingkat_seleksi_id: Mapped[int]
    jenis_tes: Mapped[JenisTes] = mapped_column(
        SqlEnum(
            JenisTes,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        )
    )
    simulasi_id: Mapped[int | None]
    total_soal: Mapped[int]
    jumlah_benar: Mapped[int]
    jumlah_salah: Mapped[int]
    skor: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False))
    predikat_label: Mapped[str]
    diselesaikan_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    breakdown_subkompetensi: Mapped[list[HasilTesSubkompetensi]] = relationship(
        back_populates="hasil_tes", cascade="all, delete-orphan"
    )


class HasilTesSubkompetensi(Base):
    """Breakdown per Subkompetensi dalam satu attempt — input untuk Peta
    Kompetensi. Tidak menyimpan identitas soal atau isi jawaban.
    """

    __tablename__ = "hasil_tes_subkompetensi"
    __table_args__ = (UniqueConstraint("hasil_tes_id", "subkompetensi_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hasil_tes_id: Mapped[int] = mapped_column(
        ForeignKey("hasil_tes.id", ondelete="CASCADE")
    )
    subkompetensi_id: Mapped[int]
    jumlah_soal: Mapped[int]
    jumlah_benar: Mapped[int]

    hasil_tes: Mapped[HasilTes] = relationship(back_populates="breakdown_subkompetensi")
