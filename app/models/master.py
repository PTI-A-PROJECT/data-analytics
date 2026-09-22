from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class TingkatSeleksi(Base):
    __tablename__ = "tingkat_seleksi"

    id = Column(Integer, primary_key=True, index=True)
    kode = Column(String(50), unique=True, nullable=False)  # 'KABUPATEN', 'PROVINSI', 'NASIONAL'
    nama = Column(String(100), nullable=False)
    urutan = Column(Integer, nullable=False)  # 1 for Kabupaten, 2 for Provinsi, 3 for Nasional

    kompetensi = relationship("Kompetensi", back_populates="tingkat_seleksi")


class Kompetensi(Base):
    __tablename__ = "kompetensi"

    id = Column(Integer, primary_key=True, index=True)
    tingkat_seleksi_id = Column(Integer, ForeignKey("tingkat_seleksi.id"), nullable=False)
    kode = Column(String(50), nullable=False)
    nama = Column(String(100), nullable=False)

    tingkat_seleksi = relationship("TingkatSeleksi", back_populates="kompetensi")
    subkompetensi = relationship("Subkompetensi", back_populates="kompetensi")


class Subkompetensi(Base):
    __tablename__ = "subkompetensi"

    id = Column(Integer, primary_key=True, index=True)
    kompetensi_id = Column(Integer, ForeignKey("kompetensi.id"), nullable=False)
    kode = Column(String(50), nullable=False)
    nama = Column(String(100), nullable=False)

    kompetensi = relationship("Kompetensi", back_populates="subkompetensi")
    soal = relationship("Soal", back_populates="subkompetensi")


class Soal(Base):
    __tablename__ = "soal"

    id = Column(Integer, primary_key=True, index=True)
    subkompetensi_id = Column(Integer, ForeignKey("subkompetensi.id"), nullable=False)
    tingkat_seleksi_id = Column(Integer, ForeignKey("tingkat_seleksi.id"), nullable=False)
    kunci_jawaban = Column(String(10), nullable=False)
    # Tiket 05: Batas waktu ideal pengerjaan butir soal dalam detik
    batas_waktu_detik = Column(Integer, default=60, nullable=False)

    subkompetensi = relationship("Subkompetensi", back_populates="soal")
