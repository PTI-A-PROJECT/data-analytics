from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class AturanKenaikanTingkat(Base):
    __tablename__ = "aturan_kenaikan_tingkat"

    id = Column(Integer, primary_key=True, index=True)
    tingkat_asal_id = Column(Integer, ForeignKey("tingkat_seleksi.id"), nullable=False)
    tingkat_tujuan_id = Column(Integer, ForeignKey("tingkat_seleksi.id"), nullable=False)
    skor_simulasi_min = Column(Float, nullable=False, default=75.0)
    persentase_kompetensi_cukup_min = Column(Float, nullable=False, default=80.0)
    aktif = Column(Boolean, default=True, nullable=False)
    dibuat_pada = Column(DateTime, default=utc_now, nullable=False)
    diperbarui_pada = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    tingkat_asal = relationship("TingkatSeleksi", foreign_keys=[tingkat_asal_id])
    tingkat_tujuan = relationship("TingkatSeleksi", foreign_keys=[tingkat_tujuan_id])

    __table_args__ = (
        UniqueConstraint("tingkat_asal_id", "tingkat_tujuan_id", name="uq_aturan_kenaikan_transisi"),
    )


class AksesTingkatSiswa(Base):
    __tablename__ = "akses_tingkat_siswa"

    id = Column(Integer, primary_key=True, index=True)
    siswa_id = Column(String(100), nullable=False, index=True)
    tingkat_seleksi_id = Column(Integer, ForeignKey("tingkat_seleksi.id"), nullable=False)
    status = Column(String(20), nullable=False, default="terkunci")  # 'terbuka', 'terkunci'
    dibuka_karena = Column(String(50), nullable=True)  # 'default_awal', 'lulus_evaluasi', 'manual_admin'
    hasil_tes_id = Column(Integer, ForeignKey("hasil_tes.id"), nullable=True)
    dibuka_pada = Column(DateTime, nullable=True)
    catatan = Column(String(255), nullable=True)
    dibuat_pada = Column(DateTime, default=utc_now, nullable=False)
    diperbarui_pada = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    tingkat_seleksi = relationship("TingkatSeleksi")
    hasil_tes = relationship("HasilTes")

    __table_args__ = (
        UniqueConstraint("siswa_id", "tingkat_seleksi_id", name="uq_siswa_tingkat_akses"),
        Index("idx_akses_tingkat_dashboard", "status", "tingkat_seleksi_id"),
    )


class RiwayatEvaluasiKenaikan(Base):
    __tablename__ = "riwayat_evaluasi_kenaikan"

    id = Column(Integer, primary_key=True, index=True)
    siswa_id = Column(String(100), nullable=False, index=True)
    hasil_tes_id = Column(Integer, ForeignKey("hasil_tes.id"), nullable=False)
    aturan_kenaikan_id = Column(Integer, ForeignKey("aturan_kenaikan_tingkat.id"), nullable=False)
    skor_aktual = Column(Float, nullable=False)
    skor_target = Column(Float, nullable=False)
    syarat_skor_lulus = Column(Boolean, nullable=False)
    persentase_cukup_aktual = Column(Float, nullable=False)
    persentase_cukup_target = Column(Float, nullable=False)
    syarat_kompetensi_lulus = Column(Boolean, nullable=False)
    hasil_evaluasi = Column(String(20), nullable=False)  # 'lulus', 'tidak_lulus'
    dievaluasi_pada = Column(DateTime, default=utc_now, nullable=False)

    hasil_tes = relationship("HasilTes")
    aturan_kenaikan = relationship("AturanKenaikanTingkat")

    __table_args__ = (
        Index("idx_riwayat_eval_dashboard", "hasil_evaluasi", "dievaluasi_pada"),
    )
