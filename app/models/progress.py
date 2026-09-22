from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime, timezone
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ProgressMateri(Base):
    __tablename__ = "progress_materi"

    id = Column(Integer, primary_key=True, index=True)
    siswa_id = Column(String(100), nullable=False, index=True)
    materi_id = Column(String(100), nullable=False)
    subkompetensi_id = Column(Integer, ForeignKey("subkompetensi.id"), nullable=False)
    tingkat_seleksi_id = Column(Integer, ForeignKey("tingkat_seleksi.id"), nullable=False)
    total_halaman = Column(Integer, nullable=False)
    halaman_tertinggi_dicapai = Column(Integer, nullable=False, default=1)
    pertama_dibuka_pada = Column(DateTime, default=utc_now, nullable=False)
    diperbarui_pada = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("siswa_id", "materi_id", name="uq_siswa_materi_progress"),
    )
