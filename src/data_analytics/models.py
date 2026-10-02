"""Skema penyimpanan untuk Aturan Skor & Hasil Simulasi (tiket 01) dan Progress
Belajar (tiket 02) — lihat .scratch/osn-data-analytics/issues/.
"""

from __future__ import annotations

import enum
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Numeric,
    UniqueConstraint,
    false,
    func,
    text,
    true,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Constraint tanpa name= eksplisit (mis. ForeignKeyConstraint) dapat berbeda
# nama antar backend (Postgres auto-name, SQLite tanpa nama) — konvensi ini
# membuatnya deterministik supaya Alembic autogenerate bisa
# create/drop_constraint dengan andal. Lihat alembic/versions/0001 untuk
# constraint yang sudah diberi name= eksplisit mengikuti pola ini.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class JenisTes(enum.StrEnum):
    PRE_TEST = "pre_test"
    SIMULASI = "simulasi"


class StatusPemetaan(enum.StrEnum):
    """Klasifikasi Subkompetensi dari algoritma Pemetaan Kompetensi (FR-07) —
    lihat CONTEXT.md "Status Pemetaan" dan resolusi tiket 11.
    """
    KUAT = "kuat"              # ← TAMBAH
    CUKUP = "cukup"
    BELUM_CUKUP = "belum_cukup"
    BELUM_TERUJI = "belum_teruji"


# tingkat_seleksi_id, simulasi_id, subkompetensi_id, sekolah_id, dan soal_id (di
# bawah) merujuk ke entitas yang dikelola tim fullstack, bukan tabel di database
# ini — sengaja tanpa ForeignKey() SQLAlchemy, sama seperti pola di ADR 0002
# (layanan ini tidak memiliki katalog Materi/Tingkat Seleksi/Simulasi/
# Subkompetensi/Sekolah/Soal produksi sendiri — tabel Soal dkk di bagian
# "Katalog lokal" di bawah adalah data uji, lihat ADR 0003). Sejak resolusi
# tiket 05/11, seluruh id caller-supplied ini berformat UUID v4 string — disimpan
# sebagai str, bukan int, walau baris milik layanan ini sendiri (mis. HasilTes.id)
# tetap integer auto-increment biasa.
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
    tingkat_seleksi_id: Mapped[str]
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
    # Nullable: di-null-kan permanen oleh anonimkan_hasil_tes_kedaluwarsa (tiket
    # 10, kepatuhan UU PDP tiket 12) setelah retention_months lewat — lihat
    # is_anonymized. Selain itu selalu diisi.
    siswa_id: Mapped[str | None]
    # Nullable: siswa tanpa afiliasi sekolah formal. Lihat resolusi tiket 08.
    sekolah_id: Mapped[str | None]
    # Snapshot nama untuk Leaderboard, dikirim fullstack saat submit (opsional).
    nama_siswa: Mapped[str | None]
    nama_sekolah: Mapped[str | None]
    # Detik dari soal pertama dibuka sampai soal terakhir dijawab
    # (leaderboard.durasi_pengerjaan); None kalau timestamp tidak dikirim.
    durasi_detik: Mapped[float | None] = mapped_column(Numeric(10, 2, asdecimal=False))
    tingkat_seleksi_id: Mapped[str]
    jenis_tes: Mapped[JenisTes] = mapped_column(
        SqlEnum(
            JenisTes,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        )
    )
    simulasi_id: Mapped[str | None]
    total_soal: Mapped[int]
    jumlah_benar: Mapped[int]
    jumlah_salah: Mapped[int]
    skor: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False))
    predikat_label: Mapped[str]
    diselesaikan_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # True setelah anonimkan_hasil_tes_kedaluwarsa menghapus siswa_id baris ini.
    # skor/predikat_label/breakdown_subkompetensi/sekolah_id tetap utuh untuk
    # agregasi Dashboard Admin — hanya identitas siswa yang dihapus.
    is_anonymized: Mapped[bool] = mapped_column(default=False, server_default=false())
    # Diisi untuk attempt fase 2 (lewat Paket Tes); None untuk attempt fase 1
    # lewat /assessment/submit.
    paket_tes_id: Mapped[int | None] = mapped_column(
        ForeignKey("paket_tes.id", ondelete="SET NULL"), unique=True
    )

    breakdown_subkompetensi: Mapped[list[HasilTesSubkompetensi]] = relationship(
        back_populates="hasil_tes", cascade="all, delete-orphan"
    )
    breakdown_materi: Mapped[list[HasilTesMateri]] = relationship(
        order_by="HasilTesMateri.materi_id", cascade="all, delete-orphan"
    )


class HasilTesSubkompetensi(Base):
    """Breakdown per Subkompetensi dalam satu attempt — input untuk & hasil dari
    Peta Kompetensi (FR-07, tiket 11). Tidak menyimpan identitas soal atau isi
    jawaban. status_pemetaan dan butuh_optimasi dibekukan saat attempt dihitung
    — sama seperti predikat_label di HasilTes (lihat resolusi tiket 01).
    """

    __tablename__ = "hasil_tes_subkompetensi"
    __table_args__ = (UniqueConstraint("hasil_tes_id", "subkompetensi_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hasil_tes_id: Mapped[int] = mapped_column(
        ForeignKey("hasil_tes.id", ondelete="CASCADE")
    )
    subkompetensi_id: Mapped[str]
    jumlah_soal: Mapped[int]
    jumlah_benar: Mapped[int]
    status_pemetaan: Mapped[StatusPemetaan] = mapped_column(
        SqlEnum(
            StatusPemetaan,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        )
    )
    # True kalau status_pemetaan == CUKUP tapi >50% jawaban benar di
    # subkompetensi ini is_lambat (resolusi tiket 05). Selalu False kalau
    # BELUM_CUKUP/BELUM_TERUJI — "butuh optimasi kecepatan" tidak relevan kalau
    # pemahamannya sendiri belum cukup.
    butuh_optimasi: Mapped[bool] = mapped_column(default=False, server_default=false())

    hasil_tes: Mapped[HasilTes] = relationship(back_populates="breakdown_subkompetensi")


# --- Katalog lokal & bank konten (tiket 09, fase 2 issue 01) -----------------
#
# TingkatSeleksi, Materi, HalamanMateri, dan Soal di bawah ini ADALAH tabel yang
# dimiliki & dimigrasikan layanan ini. Sejak fase 2 (docs/adr/0004) layanan ini
# memiliki bank konten produksi — diisi lewat ingest offline
# (data_analytics.ingest), bukan seed data uji — dan antar-tabel konten memakai
# FK sungguhan.
#
# Tabel HasilTes/HasilTesSubkompetensi/AturanPredikat/
# JawabanSiswa di atas/bawah BELUM diberi FK ke tabel-tabel ini:
# penyesuaiannya dikerjakan bersama penulisan ulang endpoint yang memakainya
# (fase 2 issue 02–04). Sampai saat itu, id di tabel-tabel tersebut tetap
# caller-supplied apa adanya, konsisten dengan resolusi tiket 01/08.


class TingkatSeleksi(Base):
    """Kabupaten/Provinsi. urutan menentukan jenjang (1 = pertama)."""

    __tablename__ = "tingkat_seleksi"
    __table_args__ = (UniqueConstraint("urutan"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nama: Mapped[str]
    urutan: Mapped[int]


class LevelSoal(enum.StrEnum):
    """Tingkat kesulitan satu Soal — berasal dari data sumber (soal sudah
    dilabeli per Materi & tingkat kesulitan), tidak dikalibrasi ulang dari data
    jawaban (fase 2 issue 01). Materi tidak
    punya level; hanya Soal.
    """

    MUDAH = "mudah"
    MENENGAH = "menengah"
    SULIT = "sulit"


class TipeSoal(enum.StrEnum):
    PILIHAN_GANDA = "pilihan_ganda"
    # Jawaban berupa teks/angka pendek; dinilai dengan pencocokan yang
    # dinormalisasi (scoring.cocokkan_jawaban). pilihan_jawaban kosong.
    ISIAN_SINGKAT = "isian_singkat"


# Dimensi embedding paraphrase-multilingual-MiniLM-L12-v2 — lihat data_analytics.embedding.
DIMENSI_EMBEDDING = 384


class Materi(Base):
    """Materi belajar satu Tingkat Seleksi — unit evaluasi fase 2 (menggantikan
    Subkompetensi). id berasal dari data sumber, stabil antar-ingest.
    embedding satu ruang vektor dengan Soal.embedding (model yang sama), dipakai
    mencocokkan Soal ke Materi terdekat.
    """

    __tablename__ = "materi"

    id: Mapped[str] = mapped_column(primary_key=True)
    tingkat_seleksi_id: Mapped[int] = mapped_column(
        ForeignKey("tingkat_seleksi.id", ondelete="CASCADE"), index=True
    )
    judul: Mapped[str]
    # Nomor topik dokumen sumber (Materi/<Tingkat>/Topik N_*.docx) — juga
    # urutan tampil Materi dalam satu tingkat. None kalau belum ada dokumennya.
    topik: Mapped[int | None]
    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSI_EMBEDDING))
    # sha256 atas teks yang di-embed — ingest menghitung ulang embedding hanya
    # kalau hash ini berubah (atau --recompute).
    hash_konten: Mapped[str]

    tingkat_seleksi: Mapped[TingkatSeleksi] = relationship()
    halaman: Mapped[list[HalamanMateri]] = relationship(
        order_by="HalamanMateri.nomor", cascade="all, delete-orphan"
    )

    @property
    def total_halaman(self) -> int:
        return len(self.halaman)


class HalamanMateri(Base):
    """Satu halaman konten Materi. nomor dimulai dari 1. konten berupa
    Markdown dengan rumus LaTeX ($...$ / $$...$$)."""

    __tablename__ = "halaman_materi"
    __table_args__ = (
        UniqueConstraint("materi_id", "nomor"),
        CheckConstraint("nomor >= 1", name="ck_halaman_materi_nomor_positif"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    materi_id: Mapped[str] = mapped_column(ForeignKey("materi.id", ondelete="CASCADE"))
    nomor: Mapped[int]
    judul: Mapped[str | None]
    konten: Mapped[str]


class Soal(Base):
    """Soal pilihan ganda bank konten fase 2, ditandai tepat satu Materi.
    pilihan_jawaban adalah map label -> teks (mis. {"A": "...", "B": "..."}).
    tingkat_seleksi_id didenormalisasi dari Materi supaya filter
    (tingkat, materi, level) cukup satu index.
    """

    __tablename__ = "soal"
    __table_args__ = (
        # Pencarian "soal mirip" selalu difilter (tingkat, materi, level) dulu
        # lewat index ini, lalu jarak cosine dihitung EKSAK ke kandidat yang
        # tersisa (puluhan soal, ~2 ms untuk 1.800 soal). Sengaja tanpa index
        # HNSW: kalau planner memilihnya, HNSW approximate dan menyaring SETELAH
        # mengambil kandidat global, sehingga soal paling mirip bisa terlewat.
        # Pada 1.800 soal planner memang sudah memilih B-tree; menghapus HNSW
        # menjamin itu tetap begitu (fase 2 issue 01).
        Index("ix_soal_tingkat_materi_level", "tingkat_seleksi_id", "materi_id", "level"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    materi_id: Mapped[str] = mapped_column(ForeignKey("materi.id", ondelete="CASCADE"))
    tingkat_seleksi_id: Mapped[int] = mapped_column(
        ForeignKey("tingkat_seleksi.id", ondelete="CASCADE")
    )
    tipe: Mapped[TipeSoal] = mapped_column(
        SqlEnum(
            TipeSoal,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        ),
        default=TipeSoal.PILIHAN_GANDA,
        server_default=TipeSoal.PILIHAN_GANDA.value,
    )
    # Teks konteks bersama (mis. cerita untuk beberapa soal berurutan).
    deskripsi: Mapped[str | None]
    pertanyaan: Mapped[str]
    # Potongan kode program yang menyertai soal, ditampilkan sebagai blok kode.
    kode: Mapped[str | None]
    # Path relatif di soal_osn/gambar_<tingkat>/ (disajikan GET
    # /api/v1/konten/gambar/{path}) atau URL absolut sumber.
    gambar: Mapped[str | None]
    # Tahun soal sumber (OSN tahun berapa).
    tahun: Mapped[int | None]
    pilihan_jawaban: Mapped[dict[str, str]] = mapped_column(JSONB)
    kunci_jawaban: Mapped[str]
    pembahasan: Mapped[str | None]
    level: Mapped[LevelSoal] = mapped_column(
        SqlEnum(
            LevelSoal,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        )
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSI_EMBEDDING))
    # sha256 atas teks yang di-embed & dilabeli — lihat Materi.hash_konten.
    hash_konten: Mapped[str]
    # False = tidak lagi ada di bank sumber (atau ditahan karena datanya rusak).
    # Tidak dihapus supaya riwayat Paket Tes yang merujuknya tetap utuh; soal
    # nonaktif tidak pernah dipilih untuk paket baru.
    aktif: Mapped[bool] = mapped_column(default=True, server_default=true())


class JawabanSiswa(Base):
    """Log jawaban per butir soal dalam satu attempt (resolusi tiket 05) — dipakai
    untuk menghitung is_lambat & flag butuh_optimasi saat submit (tiket 11), dan
    tersedia untuk drill-down Dashboard Admin nanti. soal_id caller-supplied,
    tanpa FK ke Soal lokal (tiket 09 hanya data uji) — lihat catatan "Katalog
    lokal" di atas. Tidak ada UniqueConstraint(hasil_tes_id, soal_id): baris ini
    murni log kiriman Fullstack, dipercaya apa adanya.
    """

    __tablename__ = "jawaban_siswa"

    id: Mapped[int] = mapped_column(primary_key=True)
    hasil_tes_id: Mapped[int] = mapped_column(
        ForeignKey("hasil_tes.id", ondelete="CASCADE")
    )
    soal_id: Mapped[str]
    subkompetensi_id: Mapped[str]
    jawaban_dipilih: Mapped[str]
    is_benar: Mapped[bool]
    durasi_detik: Mapped[int]
    is_lambat: Mapped[bool]
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# --- Akses tingkat & Gerbang Pre-Test (tiket 03, fase 2 issue 02) -----------
#
# Tingkat Seleksi fase 2 hanya Kabupaten (urutan 1) & Provinsi (urutan 2).
# Pre-test Provinsi terbuka lewat jalur cepat (skor pre-test Kabupaten) atau
# jalur simulasi (skor satu attempt simulasi Kabupaten + rata-rata Level Soal
# Siswa) — lihat kenaikan.py.


class StatusAkses(enum.StrEnum):
    TERKUNCI = "terkunci"
    # Boleh mengerjakan pre-test tingkat ini; materi & simulasi belum.
    PRETEST_TERBUKA = "pretest_terbuka"
    # Pre-test sudah dikerjakan (berapa pun skornya) → materi & simulasi terbuka.
    TERBUKA = "terbuka"


class JalurAkses(enum.StrEnum):
    """Alasan satu status akses dibuka (AksesTingkatSiswa.dibuka_karena) dan
    jalur yang dievaluasi (RiwayatEvaluasiKenaikan.jalur)."""

    DEFAULT_AWAL = "default_awal"
    PRETEST_SELESAI = "pretest_selesai"
    JALUR_CEPAT_PRETEST = "jalur_cepat_pretest"
    JALUR_SIMULASI = "jalur_simulasi"
    OVERRIDE_ADMIN = "override_admin"


class AturanKenaikanTingkat(Base):
    """Config Super Admin: syarat membuka pre-test tingkat tujuan dari tingkat
    asal (fase 2 issue 02). Cukup salah satu jalur: skor pre-test asal >=
    skor_pretest_jalur_cepat, ATAU satu attempt simulasi asal dengan skor >=
    skor_simulasi_min dan rata-rata Level Soal Siswa >= rata_level_min.
    """

    __tablename__ = "aturan_kenaikan_tingkat"
    __table_args__ = (
        UniqueConstraint("tingkat_asal_id", "tingkat_tujuan_id"),
        CheckConstraint(
            "skor_simulasi_min >= 0 AND skor_simulasi_min <= 100",
            name="ck_aturan_kenaikan_skor_rentang",
        ),
        CheckConstraint(
            "skor_pretest_jalur_cepat >= 0 AND skor_pretest_jalur_cepat <= 100",
            name="ck_aturan_kenaikan_skor_pretest_rentang",
        ),
        CheckConstraint(
            "rata_level_min >= 1 AND rata_level_min <= 3",
            name="ck_aturan_kenaikan_rata_level_rentang",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tingkat_asal_id: Mapped[int] = mapped_column(
        ForeignKey("tingkat_seleksi.id", ondelete="CASCADE")
    )
    tingkat_tujuan_id: Mapped[int] = mapped_column(
        ForeignKey("tingkat_seleksi.id", ondelete="CASCADE")
    )
    skor_simulasi_min: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False))
    skor_pretest_jalur_cepat: Mapped[float] = mapped_column(
        Numeric(5, 2, asdecimal=False), default=90, server_default="90"
    )
    rata_level_min: Mapped[float] = mapped_column(
        Numeric(3, 2, asdecimal=False), default=2.0, server_default="2.0"
    )
    aktif: Mapped[bool] = mapped_column(default=True, server_default=true())


class AksesTingkatSiswa(Base):
    """Status akses satu siswa ke satu Tingkat Seleksi — lihat StatusAkses.
    Akses TIDAK dijamin permanen: override admin (dan migrasi data) boleh
    menurunkannya. Alur otomatis (submit pre-test/simulasi) hanya membuka.
    Tingkat urutan=1 default 'pretest_terbuka' saat siswa pertama kali dikenal
    sistem — lihat repository.inisialisasi_akses_siswa.
    """

    __tablename__ = "akses_tingkat_siswa"
    __table_args__ = (UniqueConstraint("siswa_id", "tingkat_seleksi_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    siswa_id: Mapped[str]
    tingkat_seleksi_id: Mapped[int] = mapped_column(
        ForeignKey("tingkat_seleksi.id", ondelete="CASCADE")
    )
    # Nilai StatusAkses.
    status: Mapped[str]
    # Nilai JalurAkses.
    dibuka_karena: Mapped[str | None]
    hasil_tes_id: Mapped[int | None] = mapped_column(
        ForeignKey("hasil_tes.id", ondelete="SET NULL")
    )
    dibuka_pada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    catatan: Mapped[str | None]
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    diperbarui_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tingkat_seleksi: Mapped[TingkatSeleksi] = relationship()


class RiwayatEvaluasiKenaikan(Base):
    """Log audit satu evaluasi syarat pre-test tingkat tujuan — satu baris per
    submit pre-test (jalur cepat) atau simulasi (jalur simulasi) tingkat asal.
    Baris ini tidak pernah diubah setelah dibuat.
    """

    __tablename__ = "riwayat_evaluasi_kenaikan"

    id: Mapped[int] = mapped_column(primary_key=True)
    siswa_id: Mapped[str]
    hasil_tes_id: Mapped[int] = mapped_column(
        ForeignKey("hasil_tes.id", ondelete="CASCADE")
    )
    aturan_kenaikan_id: Mapped[int] = mapped_column(
        ForeignKey("aturan_kenaikan_tingkat.id", ondelete="CASCADE")
    )
    # Nilai JalurAkses: jalur_cepat_pretest atau jalur_simulasi.
    jalur: Mapped[str]
    skor_aktual: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False))
    skor_target: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False))
    syarat_skor_lulus: Mapped[bool]
    # Hanya jalur simulasi; None untuk jalur cepat.
    rata_level_aktual: Mapped[float | None] = mapped_column(Numeric(3, 2, asdecimal=False))
    rata_level_target: Mapped[float | None] = mapped_column(Numeric(3, 2, asdecimal=False))
    syarat_level_lulus: Mapped[bool | None]
    hasil_evaluasi: Mapped[str]  # "lulus" | "tidak_lulus"
    dievaluasi_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# --- Paket Tes & Level Soal Siswa (fase 2 issue 02/03) ------------------------


class AturanAdaptif(Base):
    """Parameter penyusunan Paket Tes per Tingkat Seleksi (fase 2 issue 02/03).
    Default dibuat otomatis kalau belum ada baris. Syarat lintas tabel
    kuota_min x jumlah Materi <= jumlah_soal_simulasi dicek saat paket disusun
    (adaptif.alokasi_kuota)."""

    __tablename__ = "aturan_adaptif"
    __table_args__ = (
        UniqueConstraint("tingkat_seleksi_id"),
        CheckConstraint("jumlah_soal_pretest > 0", name="ck_aturan_adaptif_jumlah_pretest_positif"),
        CheckConstraint(
            "ambang_lemah >= 0 AND ambang_lemah <= 100",
            name="ck_aturan_adaptif_ambang_lemah_rentang",
        ),
        CheckConstraint(
            "jumlah_soal_simulasi > 0", name="ck_aturan_adaptif_jumlah_simulasi_positif"
        ),
        CheckConstraint("kuota_min >= 1", name="ck_aturan_adaptif_kuota_min_positif"),
        CheckConstraint("bobot_lemah >= 1", name="ck_aturan_adaptif_bobot_lemah_min"),
        CheckConstraint(
            "ambang_lemah < ambang_naik AND ambang_naik <= 100",
            name="ck_aturan_adaptif_ambang_naik_rentang",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tingkat_seleksi_id: Mapped[int] = mapped_column(
        ForeignKey("tingkat_seleksi.id", ondelete="CASCADE")
    )
    jumlah_soal_pretest: Mapped[int]
    # Materi dengan akurasi < ambang_lemah (persen) berstatus lemah/Belum Cukup.
    ambang_lemah: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False))
    jumlah_soal_simulasi: Mapped[int] = mapped_column(default=30, server_default="30")
    # Soal minimal per Materi di setiap simulasi; Materi yang tampil kurang dari
    # ini di satu attempt tidak diubah Level Soal Siswa-nya.
    kuota_min: Mapped[int] = mapped_column(default=2, server_default="2")
    # Bobot Materi lemah saat membagi sisa kuota (Materi lain berbobot 1).
    bobot_lemah: Mapped[int] = mapped_column(default=3, server_default="3")
    # Akurasi (persen) >= ambang_naik menaikkan Level Soal Siswa satu tingkat.
    ambang_naik: Mapped[float] = mapped_column(
        Numeric(5, 2, asdecimal=False), default=80, server_default="80"
    )


class LevelSoalSiswa(Base):
    """Level Soal yang disajikan kepada satu siswa untuk satu Materi pada
    simulasi berikutnya (lihat CONTEXT.md). Diinisialisasi Mudah untuk semua
    Materi tingkat itu saat pre-test disubmit; dinaikkan mesin adaptif (issue 03).
    """

    __tablename__ = "level_soal_siswa"
    __table_args__ = (UniqueConstraint("siswa_id", "materi_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    siswa_id: Mapped[str]
    materi_id: Mapped[str] = mapped_column(ForeignKey("materi.id", ondelete="CASCADE"))
    level: Mapped[LevelSoal] = mapped_column(
        SqlEnum(
            LevelSoal,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        )
    )
    # Akurasi (persen) Materi ini di attempt terakhir; None kalau Belum Teruji.
    akurasi_terakhir: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False))
    lemah: Mapped[bool] = mapped_column(default=False, server_default=false())
    diperbarui_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PaketTes(Base):
    """Susunan Soal untuk satu attempt Pre-Test/Simulasi satu siswa, disusun
    layanan ini (fase 2). Pre-test maksimal satu per siswa per tingkat;
    simulasi yang belum disubmit juga maksimal satu per siswa per tingkat.
    """

    __tablename__ = "paket_tes"
    __table_args__ = (
        Index(
            "uq_paket_tes_pretest_per_siswa_tingkat",
            "siswa_id",
            "tingkat_seleksi_id",
            unique=True,
            postgresql_where=text("jenis_tes = 'pre_test'"),
        ),
        Index(
            "uq_paket_tes_simulasi_aktif_per_siswa_tingkat",
            "siswa_id",
            "tingkat_seleksi_id",
            unique=True,
            postgresql_where=text("jenis_tes = 'simulasi' AND disubmit_pada IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    siswa_id: Mapped[str]
    tingkat_seleksi_id: Mapped[int] = mapped_column(
        ForeignKey("tingkat_seleksi.id", ondelete="CASCADE")
    )
    jenis_tes: Mapped[JenisTes] = mapped_column(
        SqlEnum(
            JenisTes,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        )
    )
    # Kuota dari aturan; bisa lebih besar dari jumlah soal aktual kalau stok kurang.
    jumlah_soal_diminta: Mapped[int]
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    disubmit_pada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Seed pengacakan simulasi (pemilihan acak & urutan soal) — reproducible
    # untuk test/debug. None untuk pre-test.
    seed: Mapped[int | None] = mapped_column(BigInteger)

    soal: Mapped[list[PaketTesSoal]] = relationship(
        order_by="PaketTesSoal.urutan", cascade="all, delete-orphan"
    )


class AlasanPilihSoal(enum.StrEnum):
    """Kenapa satu Soal masuk Paket Tes (fase 2 issue 03) — auditable."""

    # Tetangga terdekat (embedding) dari soal yang dijawab salah, Materi lemah.
    VEKTOR_MIRIP = "vektor_mirip"
    ACAK = "acak"
    # Stok level target habis; diambil dari level terdekat.
    FALLBACK_LEVEL = "fallback_level"
    # Semua soal belum-pernah-muncul habis; soal lama diulang.
    FALLBACK_ULANG = "fallback_ulang"


class PaketTesSoal(Base):
    """Satu Soal di Paket Tes, beserta jawaban siswa setelah disubmit. materi_id,
    level_target (Level Soal Siswa saat disusun) & level_aktual (level soal
    yang terpilih) adalah snapshot saat paket disusun."""

    __tablename__ = "paket_tes_soal"
    __table_args__ = (
        # Nama eksplisit: konvensi uq_ hanya memakai kolom pertama, sehingga
        # dua constraint berawalan paket_tes_id akan bernama sama.
        UniqueConstraint("paket_tes_id", "soal_id", name="uq_paket_tes_soal_paket_soal"),
        UniqueConstraint("paket_tes_id", "urutan", name="uq_paket_tes_soal_paket_urutan"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    paket_tes_id: Mapped[int] = mapped_column(ForeignKey("paket_tes.id", ondelete="CASCADE"))
    soal_id: Mapped[str] = mapped_column(ForeignKey("soal.id"))
    urutan: Mapped[int]
    materi_id: Mapped[str] = mapped_column(ForeignKey("materi.id"))
    level_target: Mapped[LevelSoal] = mapped_column(
        SqlEnum(
            LevelSoal,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        )
    )
    level_aktual: Mapped[LevelSoal] = mapped_column(
        SqlEnum(
            LevelSoal,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        )
    )
    alasan: Mapped[AlasanPilihSoal] = mapped_column(
        SqlEnum(
            AlasanPilihSoal,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        )
    )
    # Terisi saat submit; soal yang tidak dijawab: jawaban_dipilih None, is_benar False.
    jawaban_dipilih: Mapped[str | None]
    is_benar: Mapped[bool | None]
    dibuka_pada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dijawab_pada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    soal_ref: Mapped[Soal] = relationship()


class HasilTesMateri(Base):
    """Breakdown per Materi satu attempt fase 2 — Peta Kompetensi per Materi
    (menggantikan HasilTesSubkompetensi untuk attempt lewat Paket Tes).
    status_pemetaan dibekukan saat attempt dihitung."""

    __tablename__ = "hasil_tes_materi"
    __table_args__ = (UniqueConstraint("hasil_tes_id", "materi_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hasil_tes_id: Mapped[int] = mapped_column(ForeignKey("hasil_tes.id", ondelete="CASCADE"))
    materi_id: Mapped[str] = mapped_column(ForeignKey("materi.id", ondelete="CASCADE"))
    jumlah_soal: Mapped[int]
    jumlah_benar: Mapped[int]
    akurasi: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False))
    status_pemetaan: Mapped[StatusPemetaan] = mapped_column(
        SqlEnum(
            StatusPemetaan,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
        )
    )


# --- Materi Wajib & riwayat baca Materi (fase 2 issue 04) -------------------------


class RiwayatBacaHalaman(Base):
    """Riwayat baca permanen: satu baris per halaman Materi yang pernah dibuka
    siswa (navigasi bebas — menggantikan high-water mark progress_materi fase
    1, yang diarsipkan sebagai progress_materi_fase1). Terpisah dari
    MateriWajibHalaman, yang hanya menghitung halaman sejak Materi diwajibkan.
    """

    __tablename__ = "riwayat_baca_halaman"
    __table_args__ = (
        UniqueConstraint(
            "siswa_id", "materi_id", "nomor_halaman", name="uq_riwayat_baca_halaman_siswa_materi"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    siswa_id: Mapped[str]
    materi_id: Mapped[str] = mapped_column(ForeignKey("materi.id", ondelete="CASCADE"))
    nomor_halaman: Mapped[int]
    pertama_dibuka_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    terakhir_dibuka_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MateriWajib(Base):
    """Snapshot Materi Wajib satu attempt: Materi berstatus lemah (Belum Cukup)
    pada Paket Tes itu, urutan 1 = akurasi terendah. selesai_pada terisi saat
    semua halamannya sudah dibuka sejak diwajibkan (materi_wajib.selesai_dipelajari).
    Gerbang Simulasi hanya melihat Materi Wajib dari attempt terakhir.
    """

    __tablename__ = "materi_wajib"
    __table_args__ = (
        UniqueConstraint("paket_tes_id", "materi_id", name="uq_materi_wajib_paket_materi"),
        Index("ix_materi_wajib_siswa_materi", "siswa_id", "materi_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    paket_tes_id: Mapped[int] = mapped_column(ForeignKey("paket_tes.id", ondelete="CASCADE"))
    siswa_id: Mapped[str]
    tingkat_seleksi_id: Mapped[int] = mapped_column(
        ForeignKey("tingkat_seleksi.id", ondelete="CASCADE")
    )
    materi_id: Mapped[str] = mapped_column(ForeignKey("materi.id", ondelete="CASCADE"))
    urutan: Mapped[int]
    akurasi: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False))
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    selesai_pada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    materi: Mapped[Materi] = relationship()


class MateriWajibHalaman(Base):
    """Halaman Materi Wajib yang sudah dibuka sejak Materi itu diwajibkan."""

    __tablename__ = "materi_wajib_halaman"
    __table_args__ = (
        UniqueConstraint(
            "materi_wajib_id", "nomor_halaman", name="uq_materi_wajib_halaman_wajib_nomor"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    materi_wajib_id: Mapped[int] = mapped_column(
        ForeignKey("materi_wajib.id", ondelete="CASCADE")
    )
    nomor_halaman: Mapped[int]
    dibuka_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True))



# --- Latihan (formatif wajib, gate simulasi ≥ 50%) ----------------------------


class Latihan(Base):
    """Rekap hasil satu sesi Latihan siswa pada satu Materi.

    Latihan bersifat formatif (bukan penentu kelulusan), tapi WAJIB
    diselesaikan dengan nilai >= 50% sebelum simulasi tingkat itu terbuka.
    Pengulangan unlimited. Pembahasan langsung per soal.
    """

    __tablename__ = "latihan"
    __table_args__ = (
        Index("ix_latihan_siswa_tingkat_materi", "siswa_id", "tingkat_seleksi_id", "materi_id"),
        CheckConstraint("nilai >= 0 AND nilai <= 100", name="ck_latihan_nilai_rentang"),
        CheckConstraint("jumlah_benar >= 0", name="ck_latihan_jumlah_benar_nonneg"),
        CheckConstraint("jumlah_salah >= 0", name="ck_latihan_jumlah_salah_nonneg"),
        CheckConstraint("total_soal > 0", name="ck_latihan_total_soal_positif"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    siswa_id: Mapped[str]
    materi_id: Mapped[str] = mapped_column(ForeignKey("materi.id", ondelete="CASCADE"))
    tingkat_seleksi_id: Mapped[int] = mapped_column(
        ForeignKey("tingkat_seleksi.id", ondelete="CASCADE")
    )
    # Nilai berbobot: (Σ bobot×benar / Σ bobot) × 100
    nilai: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False))
    jumlah_benar: Mapped[int]
    jumlah_salah: Mapped[int]
    total_soal: Mapped[int]
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    diselesaikan_pada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    jawaban: Mapped[list[LatihanJawaban]] = relationship(
        cascade="all, delete-orphan"
    )


class LatihanJawaban(Base):
    """Jawaban per soal dalam satu sesi Latihan."""

    __tablename__ = "latihan_jawaban"
    __table_args__ = (UniqueConstraint("latihan_id", "soal_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    latihan_id: Mapped[int] = mapped_column(
        ForeignKey("latihan.id", ondelete="CASCADE")
    )
    soal_id: Mapped[str] = mapped_column(ForeignKey("soal.id"))
    jawaban: Mapped[str | None]
    is_benar: Mapped[bool]
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
