from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class HasilTes(Base):
    __tablename__ = "hasil_tes"

    id = Column(Integer, primary_key=True, index=True)
    siswa_id = Column(String(100), nullable=False, index=True)
    sekolah_id = Column(String(100), nullable=True, index=True)  # Tiket 08
    tingkat_seleksi_id = Column(Integer, ForeignKey("tingkat_seleksi.id"), nullable=False)
    jenis_tes = Column(String(20), nullable=False)  # 'pre_test' or 'simulasi'
    simulasi_id = Column(Integer, nullable=True)
    total_soal = Column(Integer, nullable=False)
    jumlah_benar = Column(Integer, nullable=False)
    jumlah_salah = Column(Integer, nullable=False)
    skor = Column(Float, nullable=False)
    predikat_label = Column(String(50), nullable=False)
    diselesaikan_pada = Column(DateTime, default=utc_now, nullable=False)
    dibuat_pada = Column(DateTime, default=utc_now, nullable=False)

    subkompetensi_details = relationship("HasilTesSubkompetensi", back_populates="hasil_tes", cascade="all, delete-orphan")
    jawaban_details = relationship("JawabanSiswa", back_populates="hasil_tes", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_hasil_tes_dashboard", "sekolah_id", "tingkat_seleksi_id", "jenis_tes", "diselesaikan_pada"),
    )


class HasilTesSubkompetensi(Base):
    __tablename__ = "hasil_tes_subkompetensi"

    id = Column(Integer, primary_key=True, index=True)
    hasil_tes_id = Column(Integer, ForeignKey("hasil_tes.id"), nullable=False)
    subkompetensi_id = Column(Integer, ForeignKey("subkompetensi.id"), nullable=False)
    jumlah_soal = Column(Integer, nullable=False)
    jumlah_benar = Column(Integer, nullable=False)

    hasil_tes = relationship("HasilTes", back_populates="subkompetensi_details")
    subkompetensi = relationship("Subkompetensi")

    __table_args__ = (
        Index("idx_hasil_tes_subkomp_aggr", "subkompetensi_id", "hasil_tes_id"),
    )


class JawabanSiswa(Base):
    __tablename__ = "jawaban_siswa"

    id = Column(Integer, primary_key=True, index=True)
    hasil_tes_id = Column(Integer, ForeignKey("hasil_tes.id"), nullable=False)
    soal_id = Column(Integer, ForeignKey("soal.id"), nullable=False)
    jawaban_dipilih = Column(String(10), nullable=False)
    is_benar = Column(Boolean, nullable=False)
    durasi_detik = Column(Integer, nullable=False)
    is_lambat = Column(Boolean, nullable=False)  # Tiket 05: True jika durasi_detik > soal.batas_waktu_detik
    dibuat_pada = Column(DateTime, default=utc_now, nullable=False)

    hasil_tes = relationship("HasilTes", back_populates="jawaban_details")
    soal = relationship("Soal")
