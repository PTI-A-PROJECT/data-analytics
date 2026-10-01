"""Orkestrasi Aturan Skor & Hasil Simulasi (tiket 01) — lihat
.scratch/osn-data-analytics/issues/ — serta akses tingkat, Paket Tes, simulasi
adaptif, dan Materi Wajib fase 2 (.scratch/osn-fase-2/issues/02-04).
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Final

from sqlalchemy import Select, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from data_analytics.adaptif import (
    URUTAN_LEVEL,
    LevelSoalSiswaMateri,
    alokasi_kuota,
    bagi_proporsional,
    bobot_materi,
    gabung_bergiliran,
    perbarui_level,
    urutan_level_fallback,
    validasi_aturan_adaptif,
)
from data_analytics.kenaikan import (
    HasilEvaluasiJalurSimulasi,
    evaluasi_jalur_simulasi,
)
from data_analytics.config import (
    DEFAULT_AMBANG_LEMAH as CONFIG_AMBANG_LEMAH,
    DISTRIBUSI_PRETEST,
    DISTRIBUSI_SIMULASI,
    MATERI_INTI,
    MAX_PERCOBAAN_SIMULASI,
    PASSING_GRADE,
)
from data_analytics.models import (
    AlasanPilihSoal,
    AksesTingkatSiswa,
    AturanAdaptif,
    AturanKenaikanTingkat,
    AturanPredikat,
    HasilTes,
    HalamanMateri,
    HasilTesMateri,
    JalurAkses,
    JenisTes,
    Latihan,
    LatihanJawaban,
    LevelSoal,
    LevelSoalSiswa,
    Materi,
    MateriWajib,
    MateriWajibHalaman,
    PaketTes,
    PaketTesSoal,
    RiwayatBacaHalaman,
    RiwayatEvaluasiKenaikan,
    Soal,
    StatusAkses,
    StatusPemetaan,
    TingkatSeleksi,
)
from data_analytics.paket import bagi_kuota_rata
from data_analytics.pemetaan import (
    PetaMateri,
    materi_lemah,
    petakan_per_materi,
)
from data_analytics.leaderboard import (
    AttemptSimulasi,
    Peringkat,
    durasi_pengerjaan,
    susun_leaderboard,
)
from data_analytics.materi_wajib import selesai_dipelajari
from data_analytics.scoring import cocokkan_jawaban, hitung_skor, tentukan_predikat
from tests.conftest import session

DEFAULT_ATURAN_PREDIKAT: Final[tuple[tuple[str, float], ...]] = (
    ("Sangat Baik", 90),
    ("Baik", 80),
    ("Cukup", 70),
    ("Perlu Latihan", 0),
)

def _validasi_aturan(aturan: Sequence[tuple[str, float]]) -> None:
    if not aturan:
        raise ValueError("aturan tidak boleh kosong")
    for label, batas_bawah in aturan:
        if not (0 <= batas_bawah <= 100):
            raise ValueError(
                f"batas_bawah untuk '{label}' harus di antara 0 dan 100, dapat {batas_bawah}"
            )
    if not any(batas_bawah == 0 for _, batas_bawah in aturan):
        raise ValueError("aturan harus menyertakan predikat dengan batas_bawah=0")


def get_or_create_aturan_predikat(
    session: Session, tingkat_seleksi_id: str
) -> list[AturanPredikat]:
    """Aturan predikat milik satu Tingkat Seleksi. Kalau belum pernah dikonfigurasi
    Super Admin (lewat set_aturan_predikat), di-seed otomatis dengan
    DEFAULT_ATURAN_PREDIKAT supaya penilaian tidak gagal/terblokir karena config
    belum diisi.
    """
    existing = session.scalars(
        select(AturanPredikat).where(
            AturanPredikat.tingkat_seleksi_id == tingkat_seleksi_id
        )
    ).all()
    if existing:
        return list(existing)

    seeded = [
        AturanPredikat(
            tingkat_seleksi_id=tingkat_seleksi_id, label=label, batas_bawah=batas_bawah
        )
        for label, batas_bawah in DEFAULT_ATURAN_PREDIKAT
    ]
    session.add_all(seeded)
    session.flush()
    return seeded


def set_aturan_predikat(
    session: Session, tingkat_seleksi_id: str, aturan: Sequence[tuple[str, float]]
) -> list[AturanPredikat]:
    """Super Admin mengganti seluruh Aturan Predikat suatu Tingkat Seleksi
    (menggantikan default hasil seed maupun aturan kustom sebelumnya). Hasil tes
    yang sudah tersimpan tidak terpengaruh — predikat_label mereka sudah
    dibekukan saat dihitung (lihat submit_paket).
    """
    _validasi_aturan(aturan)

    session.execute(
        delete(AturanPredikat).where(
            AturanPredikat.tingkat_seleksi_id == tingkat_seleksi_id
        )
    )
    baru = [
        AturanPredikat(
            tingkat_seleksi_id=tingkat_seleksi_id, label=label, batas_bawah=batas_bawah
        )
        for label, batas_bawah in aturan
    ]
    session.add_all(baru)
    session.flush()
    return baru


def get_semua_aturan_predikat(session: Session) -> list[tuple[int, list[AturanPredikat]]]:
    """Aturan predikat setiap Tingkat Seleksi (default dibuat kalau belum ada),
    urut jenjang; predikat dari batas_bawah tertinggi."""
    return [
        (
            tingkat.id,
            sorted(
                get_or_create_aturan_predikat(session, str(tingkat.id)),
                key=lambda a: a.batas_bawah,
                reverse=True,
            ),
        )
        for tingkat in session.scalars(select(TingkatSeleksi).order_by(TingkatSeleksi.urutan))
    ]


def ganti_aturan_predikat(
    session: Session, *, tingkat_seleksi_id: int, aturan: Sequence[tuple[str, float]]
) -> list[AturanPredikat]:
    """Super Admin mengganti seluruh predikat satu tingkat (lihat
    set_aturan_predikat). TingkatTidakDitemukan / ValueError."""
    if session.get(TingkatSeleksi, tingkat_seleksi_id) is None:
        raise TingkatTidakDitemukan(f"Tingkat Seleksi {tingkat_seleksi_id} tidak ditemukan")
    label = [lbl for lbl, _ in aturan]
    batas = [b for _, b in aturan]
    if len(set(label)) != len(label) or len(set(batas)) != len(batas):
        raise ValueError("label dan batas_bawah predikat harus unik")
    baru = set_aturan_predikat(session, str(tingkat_seleksi_id), aturan)
    return sorted(baru, key=lambda a: a.batas_bawah, reverse=True)


def anonimkan_hasil_tes_kedaluwarsa(
    session: Session,
    *,
    retention_months: int,
    sekarang: datetime | None = None,
    dry_run: bool = False,
) -> int:
    """Null-kan siswa_id pada baris HasilTes yang dibuat lebih dari
    retention_months bulan lalu (UU PDP, lihat riset tiket 12 — pengendali
    data wajib menetapkan & menegakkan periode retensinya sendiri). Baris
    yang sudah is_anonymized dilewati (idempoten). Data agregat (skor,
    predikat_label, sekolah_id, breakdown_subkompetensi) tidak disentuh —
    tetap dipakai Dashboard Admin. dry_run=True hanya menghitung tanpa
    mengubah apa pun.

    Bulan didekati 30 hari — cukup presisi untuk siklus retensi tahunan,
    tidak perlu kalender bulan sungguhan.
    """
    batas = (sekarang or datetime.now(timezone.utc)) - timedelta(days=retention_months * 30)

    kedaluwarsa = session.scalars(
        select(HasilTes).where(
            HasilTes.dibuat_pada < batas,
            HasilTes.is_anonymized.is_(False),
        )
    ).all()

    if not dry_run:
        for hasil in kedaluwarsa:
            hasil.siswa_id = None
            hasil.nama_siswa = None
            hasil.is_anonymized = True
        session.flush()

    return len(kedaluwarsa)


# --- Akses tingkat & Gerbang Pre-Test (tiket 03, fase 2 issue 02) -----------


def inisialisasi_akses_siswa(session: Session, siswa_id: str) -> list[AksesTingkatSiswa]:
    """Pastikan siswa punya baris AksesTingkatSiswa untuk setiap Tingkat Seleksi.
    Tingkat urutan=1 default 'pretest_terbuka' (dibuka_karena='default_awal'),
    sisanya 'terkunci'. Idempoten — baris yang sudah ada tidak disentuh.
    """
    tingkat_list = session.scalars(
        select(TingkatSeleksi).order_by(TingkatSeleksi.urutan)
    ).all()
    existing_ids = set(
        session.scalars(
            select(AksesTingkatSiswa.tingkat_seleksi_id).where(
                AksesTingkatSiswa.siswa_id == siswa_id
            )
        ).all()
    )

    baru = []
    for tingkat in tingkat_list:
        if tingkat.id in existing_ids:
            continue
        is_pertama = tingkat.urutan == 1
        baru.append(
            {
                "siswa_id": siswa_id,
                "tingkat_seleksi_id": tingkat.id,
                "status": StatusAkses.PRETEST_TERBUKA if is_pertama else StatusAkses.TERKUNCI,
                "dibuka_karena": JalurAkses.DEFAULT_AWAL if is_pertama else None,
                "dibuka_pada": datetime.now(timezone.utc) if is_pertama else None,
            }
        )
    if baru:
        # ON CONFLICT: permintaan bersamaan untuk siswa baru yang sama tidak
        # saling gagal karena unik (siswa_id, tingkat_seleksi_id).
        session.execute(
            pg_insert(AksesTingkatSiswa)
            .values(baru)
            .on_conflict_do_nothing(index_elements=["siswa_id", "tingkat_seleksi_id"])
        )

    return list(
        session.scalars(
            select(AksesTingkatSiswa)
            .where(AksesTingkatSiswa.siswa_id == siswa_id)
            .join(TingkatSeleksi, AksesTingkatSiswa.tingkat_seleksi_id == TingkatSeleksi.id)
            .order_by(TingkatSeleksi.urutan)
        ).all()
    )


def _akses(session: Session, siswa_id: str, tingkat_seleksi_id: int) -> AksesTingkatSiswa | None:
    return session.scalars(
        select(AksesTingkatSiswa).where(
            AksesTingkatSiswa.siswa_id == siswa_id,
            AksesTingkatSiswa.tingkat_seleksi_id == tingkat_seleksi_id,
        )
    ).one_or_none()


def override_akses_admin(
    session: Session,
    *,
    siswa_id: str,
    tingkat_seleksi_id: int,
    status: StatusAkses,
    catatan: str | None = None,
) -> AksesTingkatSiswa:
    """Override manual akses tingkat siswa oleh Super Admin (FR-17/tiket 03) —
    boleh membuka maupun menurunkan/mencabut akses."""
    akses = _akses(session, siswa_id, tingkat_seleksi_id)
    if akses is None:
        akses = AksesTingkatSiswa(siswa_id=siswa_id, tingkat_seleksi_id=tingkat_seleksi_id)
        session.add(akses)

    akses.status = status
    akses.catatan = catatan
    if status is not StatusAkses.TERKUNCI:
        akses.dibuka_karena = JalurAkses.OVERRIDE_ADMIN
        akses.dibuka_pada = datetime.now(timezone.utc)

    session.flush()
    return akses


_PERINGKAT_STATUS: Final[dict[str, int]] = {
    StatusAkses.TERKUNCI: 0,
    StatusAkses.PRETEST_TERBUKA: 1,
    StatusAkses.TERBUKA: 2,
}


def _buka_akses(
    session: Session,
    *,
    siswa_id: str,
    tingkat_seleksi_id: int,
    status: StatusAkses,
    jalur: JalurAkses,
    hasil_tes_id: int,
) -> None:
    """Buka akses dari alur otomatis (submit pre-test/simulasi). Tidak menimpa
    status yang sudah lebih tinggi — mis. Provinsi yang sudah 'terbuka' lewat
    override admin tidak diturunkan ke 'pretest_terbuka' oleh jalur cepat.
    Ini bukan jaminan akses permanen: override admin tetap boleh menurunkan."""
    akses = _akses(session, siswa_id, tingkat_seleksi_id)
    if akses is None:
        akses = AksesTingkatSiswa(
            siswa_id=siswa_id, tingkat_seleksi_id=tingkat_seleksi_id, status=StatusAkses.TERKUNCI
        )
        session.add(akses)
    if _PERINGKAT_STATUS[akses.status] >= _PERINGKAT_STATUS[status]:
        return
    akses.status = status
    akses.dibuka_karena = jalur
    akses.dibuka_pada = datetime.now(timezone.utc)
    akses.hasil_tes_id = hasil_tes_id
    session.flush()


def get_akses_siswa(session: Session, siswa_id: str) -> list[AksesTingkatSiswa]:
    """Status akses siswa ke seluruh Tingkat Seleksi — inisialisasi otomatis
    dulu kalau siswa belum pernah punya baris akses sama sekali.
    """
    return inisialisasi_akses_siswa(session, siswa_id)


def get_semua_aturan_kenaikan(session: Session) -> list[AturanKenaikanTingkat]:
    return list(
        session.scalars(
            select(AturanKenaikanTingkat).order_by(AturanKenaikanTingkat.id)
        ).all()
    )


def update_aturan_kenaikan(
    session: Session,
    *,
    aturan_id: int,
    skor_simulasi_min: float | None = None,
    skor_pretest_jalur_cepat: float | None = None,
    rata_level_min: float | None = None,
    aktif: bool | None = None,
) -> AturanKenaikanTingkat | None:
    aturan = session.get(AturanKenaikanTingkat, aturan_id)
    if aturan is None:
        return None
    if skor_simulasi_min is not None:
        aturan.skor_simulasi_min = skor_simulasi_min
    if skor_pretest_jalur_cepat is not None:
        aturan.skor_pretest_jalur_cepat = skor_pretest_jalur_cepat
    if rata_level_min is not None:
        aturan.rata_level_min = rata_level_min
    if aktif is not None:
        aturan.aktif = aktif
    session.flush()
    return aturan


def _aturan_kenaikan_aktif(session: Session, tingkat_asal_id: int) -> AturanKenaikanTingkat | None:
    return session.scalars(
        select(AturanKenaikanTingkat).where(
            AturanKenaikanTingkat.tingkat_asal_id == tingkat_asal_id,
            AturanKenaikanTingkat.aktif.is_(True),
        )
        # Unik hanya per (asal, tujuan); kalau ada lebih dari satu aturan aktif
        # dari asal yang sama, yang tertua berlaku.
        .order_by(AturanKenaikanTingkat.id)
    ).first()



# --- Paket Tes (fase 2 issue 02) ----------------------------------------------

DEFAULT_JUMLAH_SOAL_PRETEST: Final = 30
DEFAULT_AMBANG_LEMAH: Final = CONFIG_AMBANG_LEMAH  # = 60.0 dari config.py


class TingkatTidakDitemukan(LookupError):
    pass


class PaketTidakDitemukan(LookupError):
    pass


class AksesDitolak(Exception):
    """Status akses siswa tidak mengizinkan aksi ini (HTTP 403)."""


class KonflikPaket(Exception):
    """Pre-test sudah selesai / paket sudah disubmit (HTTP 409)."""


def get_or_create_aturan_adaptif(session: Session, tingkat_seleksi_id: int) -> AturanAdaptif:
    """Aturan penyusunan paket satu tingkat; dibuat dengan default kalau belum
    ada — pola sama dengan get_or_create_aturan_predikat."""
    aturan = session.scalars(
        select(AturanAdaptif).where(AturanAdaptif.tingkat_seleksi_id == tingkat_seleksi_id)
    ).one_or_none()
    if aturan is None:
        aturan = AturanAdaptif(
            tingkat_seleksi_id=tingkat_seleksi_id,
            jumlah_soal_pretest=DEFAULT_JUMLAH_SOAL_PRETEST,
            ambang_lemah=DEFAULT_AMBANG_LEMAH,
        )
        session.add(aturan)
        session.flush()
    return aturan


def get_semua_aturan_adaptif(session: Session) -> list[AturanAdaptif]:
    """Aturan penyusunan paket setiap Tingkat Seleksi (default dibuat kalau
    belum ada), urut jenjang."""
    return [
        get_or_create_aturan_adaptif(session, tingkat.id)
        for tingkat in session.scalars(select(TingkatSeleksi).order_by(TingkatSeleksi.urutan))
    ]


def update_aturan_adaptif(
    session: Session,
    *,
    tingkat_seleksi_id: int,
    jumlah_soal_pretest: int | None = None,
    jumlah_soal_simulasi: int | None = None,
    kuota_min: int | None = None,
    bobot_lemah: int | None = None,
    ambang_naik: float | None = None,
    ambang_lemah: float | None = None,
) -> AturanAdaptif:
    """Ubah sebagian aturan_adaptif satu tingkat oleh Super Admin. Hasil
    gabungannya divalidasi (adaptif.validasi_aturan_adaptif) terhadap jumlah
    Materi tingkat itu saat ini. TingkatTidakDitemukan / ValueError."""
    if session.get(TingkatSeleksi, tingkat_seleksi_id) is None:
        raise TingkatTidakDitemukan(f"Tingkat Seleksi {tingkat_seleksi_id} tidak ditemukan")
    aturan = get_or_create_aturan_adaptif(session, tingkat_seleksi_id)
    jumlah_materi = session.scalar(
        select(func.count()).select_from(Materi).where(
            Materi.tingkat_seleksi_id == tingkat_seleksi_id
        )
    )
    baru_simulasi = jumlah_soal_simulasi or aturan.jumlah_soal_simulasi
    baru_kuota_min = kuota_min or aturan.kuota_min
    baru_bobot_lemah = bobot_lemah or aturan.bobot_lemah
    baru_ambang_naik = aturan.ambang_naik if ambang_naik is None else ambang_naik
    baru_ambang_lemah = aturan.ambang_lemah if ambang_lemah is None else ambang_lemah
    validasi_aturan_adaptif(
        jumlah_soal_simulasi=baru_simulasi,
        kuota_min=baru_kuota_min,
        bobot_lemah=baru_bobot_lemah,
        ambang_naik=baru_ambang_naik,
        ambang_lemah=baru_ambang_lemah,
        jumlah_materi=jumlah_materi or 0,
    )
    aturan.jumlah_soal_pretest = jumlah_soal_pretest or aturan.jumlah_soal_pretest
    aturan.jumlah_soal_simulasi = baru_simulasi
    aturan.kuota_min = baru_kuota_min
    aturan.bobot_lemah = baru_bobot_lemah
    aturan.ambang_naik = baru_ambang_naik
    aturan.ambang_lemah = baru_ambang_lemah
    session.flush()
    return aturan


def susun_paket_pretest(session: Session, *, siswa_id: str, tingkat_seleksi_id: int) -> PaketTes:
    """Paket pre-test siswa untuk satu tingkat: semua soal Mudah, kuota dibagi
    rata per Materi (bagi_kuota_rata), soal dipilih acak. Idempoten — paket
    yang belum disubmit dikembalikan ulang.

    TingkatTidakDitemukan / AksesDitolak (status bukan pretest_terbuka) /
    KonflikPaket (pre-test tingkat ini sudah disubmit).
    """
    if session.get(TingkatSeleksi, tingkat_seleksi_id) is None:
        raise TingkatTidakDitemukan(f"Tingkat Seleksi {tingkat_seleksi_id} tidak ditemukan")

    tersimpan = _paket_pretest(session, siswa_id, tingkat_seleksi_id)
    if tersimpan is not None and tersimpan.disubmit_pada is not None:
        # Cek apakah boleh pre-test ulang: sudah gagal simulasi max kali
        jumlah_gagal = session.scalar(
            select(func.count()).select_from(RiwayatEvaluasiKenaikan).where(
                RiwayatEvaluasiKenaikan.siswa_id == siswa_id,
                RiwayatEvaluasiKenaikan.jalur == JalurAkses.JALUR_SIMULASI,
                RiwayatEvaluasiKenaikan.hasil_evaluasi == "tidak_lulus",
            )
        ) or 0

        if jumlah_gagal < MAX_PERCOBAAN_SIMULASI:
            raise KonflikPaket(
                "Pre-test tingkat ini sudah dikerjakan. "
                f"Pre-test ulang hanya setelah gagal simulasi {MAX_PERCOBAAN_SIMULASI}x."
            )

        # Reset: hapus paket pre-test lama supaya bisa bikin baru
        session.delete(tersimpan)
        session.flush()

    inisialisasi_akses_siswa(session, siswa_id)
    akses = _akses(session, siswa_id, tingkat_seleksi_id)
    if akses is None or akses.status != StatusAkses.PRETEST_TERBUKA:
        raise AksesDitolak("Pre-test tingkat ini belum terbuka untuk siswa")
    if tersimpan is not None:
        return tersimpan 
    
    aturan = get_or_create_aturan_adaptif(session, tingkat_seleksi_id)
    total = aturan.jumlah_soal_pretest

    # Distribusi 50% Mudah, 30% Menengah, 20% Sulit
    n_mudah = round(total * DISTRIBUSI_PRETEST["mudah"])
    n_menengah = round(total * DISTRIBUSI_PRETEST["menengah"])
    n_sulit = total - n_mudah - n_menengah

    terpilih: list[Soal] = []
    for level, jumlah in [
        (LevelSoal.MUDAH, n_mudah),
        (LevelSoal.MENENGAH, n_menengah),
        (LevelSoal.SULIT, n_sulit),
    ]:
        if jumlah == 0:
            continue
        stok_level = {
            materi_id: count
            for materi_id, count in session.execute(
                select(Materi.id, func.count(Soal.id))
                .outerjoin(
                    Soal,
                    (Soal.materi_id == Materi.id) & (Soal.level == level) & Soal.aktif,
                )
                .where(Materi.tingkat_seleksi_id == tingkat_seleksi_id)
                .group_by(Materi.id)
            ).tuples()
        }
        kuota_level = bagi_kuota_rata(jumlah, stok_level)
        for materi_id, jml in kuota_level.items():
            terpilih.extend(
                session.scalars(
                    select(Soal)
                    .where(
                        Soal.materi_id == materi_id,
                        Soal.level == level,
                        Soal.aktif,
                    )
                    .order_by(func.random())
                    .limit(jml)
                )
            )
    random.shuffle(terpilih)
    paket = PaketTes(
        siswa_id=siswa_id,
        tingkat_seleksi_id=tingkat_seleksi_id,
        jenis_tes=JenisTes.PRE_TEST,
        jumlah_soal_diminta=aturan.jumlah_soal_pretest,
        soal=[
            PaketTesSoal(
                soal_id=s.id,
                urutan=urutan,
                materi_id=s.materi_id,
                level_target=s.level,
                level_aktual=s.level,
                alasan=AlasanPilihSoal.ACAK,
            )
            for urutan, s in enumerate(terpilih, start=1)
        ],
    )
    # Permintaan bersamaan untuk siswa+tingkat yang sama menabrak partial unique
    # index; yang kalah memakai paket pemenang (idempoten), bukan error 500.
    try:
        with session.begin_nested():
            session.add(paket)
    except IntegrityError:
        pemenang = _paket_pretest(session, siswa_id, tingkat_seleksi_id)
        if pemenang is None:
            raise
        return pemenang
    return paket


def _paket_pretest(session: Session, siswa_id: str, tingkat_seleksi_id: int) -> PaketTes | None:
    return session.scalars(
        select(PaketTes).where(
            PaketTes.siswa_id == siswa_id,
            PaketTes.tingkat_seleksi_id == tingkat_seleksi_id,
            PaketTes.jenis_tes == JenisTes.PRE_TEST,
        )
    ).one_or_none()


def susun_paket_latihan(
    session: Session, *, siswa_id: str, materi_id: str, jumlah_soal: int = 10
) -> list[Soal]:
    """Ambil soal latihan untuk satu materi (level acak).
    Latihan = formatif, tidak pakai PaketTes. Dipilih 10-15 soal acak dari
    bank soal materi itu.
    """
    materi = session.get(Materi, materi_id)
    if materi is None:
        raise ValueError(f"Materi {materi_id} tidak ditemukan")

    soal = list(
        session.scalars(
            select(Soal)
            .where(Soal.materi_id == materi_id, Soal.aktif)
            .order_by(func.random())
            .limit(jumlah_soal)
        )
    )
    if not soal:
        raise ValueError(f"Tidak ada soal untuk materi {materi_id}")
    return soal


# --- Simulasi adaptif (fase 2 issue 03) ---------------------------------------


def susun_paket_simulasi(
    session: Session, *, siswa_id: str, tingkat_seleksi_id: int, seed: int | None = None
) -> PaketTes:
    """Paket simulasi STATIS v1: 30% Mudah, 40% Menengah, 30% Sulit.
    Distribusi dibagi rata per Materi. Adaptive di-hold untuk fase 2.
    """
    if session.get(TingkatSeleksi, tingkat_seleksi_id) is None:
        raise TingkatTidakDitemukan(f"Tingkat Seleksi {tingkat_seleksi_id} tidak ditemukan")

    inisialisasi_akses_siswa(session, siswa_id)
    akses = _akses(session, siswa_id, tingkat_seleksi_id)
    if akses is None or akses.status != StatusAkses.TERBUKA:
        raise AksesDitolak("Simulasi tingkat ini belum terbuka untuk siswa")

    # Cek kuota simulasi (maks 3x per tingkat)
    jumlah_percobaan = session.scalar(
        select(func.count()).select_from(PaketTes).where(
            PaketTes.siswa_id == siswa_id,
            PaketTes.tingkat_seleksi_id == tingkat_seleksi_id,
            PaketTes.jenis_tes == JenisTes.SIMULASI,
            PaketTes.disubmit_pada.is_not(None),
        )
    ) or 0
    if jumlah_percobaan >= MAX_PERCOBAAN_SIMULASI:
        raise KonflikPaket(
            f"Kuota simulasi habis ({MAX_PERCOBAAN_SIMULASI}x). "
            "Lakukan pre-test ulang untuk reset."
        )

    tersimpan = _paket_simulasi_aktif(session, siswa_id, tingkat_seleksi_id)
    if tersimpan is not None:
        return tersimpan

    status = status_gerbang_simulasi(
        session, siswa_id=siswa_id, tingkat_seleksi_id=tingkat_seleksi_id
    )
    if not status.boleh_simulasi:
        raise GerbangSimulasiTertutup(status)

    aturan = get_or_create_aturan_adaptif(session, tingkat_seleksi_id)
    total = aturan.jumlah_soal_simulasi

    # Distribusi 30% Mudah, 40% Menengah, 30% Sulit
    n_mudah = round(total * DISTRIBUSI_SIMULASI["mudah"])
    n_menengah = round(total * DISTRIBUSI_SIMULASI["menengah"])
    n_sulit = total - n_mudah - n_menengah

    terpilih: list[Soal] = []
    for level, jumlah in [
        (LevelSoal.MUDAH, n_mudah),
        (LevelSoal.MENENGAH, n_menengah),
        (LevelSoal.SULIT, n_sulit),
    ]:
        if jumlah == 0:
            continue
        stok_level = {
            materi_id: count
            for materi_id, count in session.execute(
                select(Materi.id, func.count(Soal.id))
                .outerjoin(
                    Soal,
                    (Soal.materi_id == Materi.id) & (Soal.level == level) & Soal.aktif,
                )
                .where(Materi.tingkat_seleksi_id == tingkat_seleksi_id)
                .group_by(Materi.id)
            ).tuples()
        }
        kuota_level = bagi_kuota_rata(jumlah, stok_level)
        for materi_id, jml in kuota_level.items():
            terpilih.extend(
                session.scalars(
                    select(Soal)
                    .where(
                        Soal.materi_id == materi_id,
                        Soal.level == level,
                        Soal.aktif,
                    )
                    .order_by(func.random())
                    .limit(jml)
                )
            )

    if seed is None:
        seed = random.SystemRandom().randrange(2**63)
    rng = random.Random(seed)
    rng.shuffle(terpilih)

    paket = PaketTes(
        siswa_id=siswa_id,
        tingkat_seleksi_id=tingkat_seleksi_id,
        jenis_tes=JenisTes.SIMULASI,
        jumlah_soal_diminta=total,
        seed=seed,
        soal=[
            PaketTesSoal(
                soal_id=s.id,
                urutan=urutan,
                materi_id=s.materi_id,
                level_target=s.level,
                level_aktual=s.level,
                alasan=AlasanPilihSoal.ACAK,
            )
            for urutan, s in enumerate(terpilih, start=1)
        ],
    )
    try:
        with session.begin_nested():
            session.add(paket)
    except IntegrityError:
        pemenang = _paket_simulasi_aktif(session, siswa_id, tingkat_seleksi_id)
        if pemenang is None:
            raise
        return pemenang
    return paket

def _paket_simulasi_aktif(
    session: Session, siswa_id: str, tingkat_seleksi_id: int
) -> PaketTes | None:
    return session.scalars(
        select(PaketTes).where(
            PaketTes.siswa_id == siswa_id,
            PaketTes.tingkat_seleksi_id == tingkat_seleksi_id,
            PaketTes.jenis_tes == JenisTes.SIMULASI,
            PaketTes.disubmit_pada.is_(None),
        )
    ).one_or_none()


def _level_soal_siswa_per_materi(
    session: Session, siswa_id: str, tingkat_seleksi_id: int
) -> dict[str, LevelSoalSiswaMateri]:
    """Level Soal Siswa untuk SEMUA Materi tingkat itu, terurut id. Materi tanpa
    baris (mis. Materi baru, atau akses dibuka admin tanpa pre-test) → Mudah,
    tidak lemah."""
    baris = session.execute(
        select(Materi.id, LevelSoalSiswa)
        .outerjoin(
            LevelSoalSiswa,
            (LevelSoalSiswa.materi_id == Materi.id) & (LevelSoalSiswa.siswa_id == siswa_id),
        )
        .where(Materi.tingkat_seleksi_id == tingkat_seleksi_id)
        .order_by(Materi.id)
    ).tuples()
    return {
        materi_id: (
            LevelSoalSiswaMateri(level=lss.level, lemah=lss.lemah, akurasi=lss.akurasi_terakhir)
            if lss is not None
            else LevelSoalSiswaMateri(level=LevelSoal.MUDAH, lemah=False, akurasi=None)
        )
        for materi_id, lss in baris
    }


def _riwayat_muncul(session: Session, siswa_id: str, tingkat_seleksi_id: int) -> dict[str, int]:
    """soal_id → id paket terakhir tempat soal itu muncul (pre-test maupun
    simulasi siswa ini di tingkat ini). Id paket naik monoton, jadi nilai
    terkecil = paling lama tidak muncul."""
    return {
        soal_id: paket_id
        for soal_id, paket_id in session.execute(
            select(PaketTesSoal.soal_id, func.max(PaketTes.id))
            .join(PaketTes, PaketTesSoal.paket_tes_id == PaketTes.id)
            .where(PaketTes.siswa_id == siswa_id, PaketTes.tingkat_seleksi_id == tingkat_seleksi_id)
            .group_by(PaketTesSoal.soal_id)
        ).tuples()
    }


def _soal_acuan(session: Session, siswa_id: str, tingkat_seleksi_id: int) -> dict[str, list[Soal]]:
    """Soal acuan per Materi: yang dijawab salah pada attempt terakhir
    (pre-test/simulasi yang sudah disubmit) yang memuat jawaban salah di Materi
    itu, dalam urutan penyajiannya. Biasanya attempt terakhir; mundur ke attempt
    sebelumnya hanya kalau Materi tetap lemah karena tampil < kuota_min soal
    di attempt terakhir (flag lemah tidak diubah) dan semuanya dijawab benar."""
    salah = session.execute(
        select(PaketTesSoal.materi_id, PaketTesSoal.paket_tes_id, Soal)
        .join(PaketTes, PaketTesSoal.paket_tes_id == PaketTes.id)
        .join(Soal, PaketTesSoal.soal_id == Soal.id)
        .where(
            PaketTes.siswa_id == siswa_id,
            PaketTes.tingkat_seleksi_id == tingkat_seleksi_id,
            PaketTes.disubmit_pada.is_not(None),
            PaketTesSoal.is_benar.is_(False),
        )
        .order_by(PaketTes.disubmit_pada.desc(), PaketTes.id.desc(), PaketTesSoal.urutan)
    ).tuples()
    paket_acuan: dict[str, int] = {}
    acuan: dict[str, list[Soal]] = defaultdict(list)
    for materi_id, paket_id, soal in salah:
        if paket_acuan.setdefault(materi_id, paket_id) == paket_id:
            acuan[materi_id].append(soal)
    return acuan


@dataclass(frozen=True, slots=True)
class _SoalTerpilih:
    soal: Soal
    alasan: AlasanPilihSoal


class _PemilihSoal:
    """Langkah 3 mesin adaptif: pilih soal per Materi dengan fallback
    berurutan (issue 03) — level target → level terdekat (lebih mudah dulu)
    → soal yang pernah muncul, paling lama dulu → sisa kuota dialihkan ke
    Materi lain sesuai bobot."""

    def __init__(
        self,
        session: Session,
        *,
        rng: random.Random,
        level_siswa: dict[str, LevelSoalSiswaMateri],
        riwayat: dict[str, int],
        acuan: dict[str, list[Soal]],
    ) -> None:
        self._session = session
        self._rng = rng
        self._level_siswa = level_siswa
        self._riwayat = riwayat
        self._acuan = acuan
        self._dipilih: set[str] = set()

    def pilih(self, kuota: dict[str, int], *, bobot: dict[str, int]) -> list[_SoalTerpilih]:
        terpilih: list[_SoalTerpilih] = []
        habis: set[str] = set()
        permintaan = kuota
        while True:
            kurang = 0
            for materi_id, jumlah in permintaan.items():
                if jumlah == 0:
                    continue
                hasil = self._pilih_materi(materi_id, jumlah)
                terpilih.extend(hasil)
                if len(hasil) < jumlah:
                    habis.add(materi_id)
                    kurang += jumlah - len(hasil)
            sisa = {m: b for m, b in bobot.items() if m not in habis}
            if kurang == 0 or not sisa:
                return terpilih
            permintaan = bagi_proporsional(kurang, sisa)

    def _pilih_materi(self, materi_id: str, jumlah: int) -> list[_SoalTerpilih]:
        lss_materi = self._level_siswa[materi_id]
        acuan = self._acuan.get(materi_id, []) if lss_materi.lemah else []
        hasil: list[_SoalTerpilih] = []

        def ambil(soal: Sequence[Soal], alasan: AlasanPilihSoal) -> None:
            for s in soal:
                self._dipilih.add(s.id)
                hasil.append(_SoalTerpilih(s, alasan))

        for level in urutan_level_fallback(lss_materi.level):
            is_target = level is lss_materi.level
            if acuan:
                ambil(
                    self._tetangga_bergiliran(materi_id, level, acuan, jumlah - len(hasil)),
                    AlasanPilihSoal.VEKTOR_MIRIP if is_target else AlasanPilihSoal.FALLBACK_LEVEL,
                )
            ambil(
                self._acak(materi_id, level, jumlah - len(hasil)),
                AlasanPilihSoal.ACAK if is_target else AlasanPilihSoal.FALLBACK_LEVEL,
            )
        ambil(self._pernah_muncul(materi_id, jumlah - len(hasil)), AlasanPilihSoal.FALLBACK_ULANG)
        return hasil

    def _belum_muncul(self, materi_id: str, level: LevelSoal) -> Select[tuple[Soal]]:
        dikecualikan = [*self._riwayat, *self._dipilih]
        query = select(Soal).where(Soal.materi_id == materi_id, Soal.level == level, Soal.aktif)
        if dikecualikan:
            query = query.where(Soal.id.not_in(dikecualikan))
        return query

    def _tetangga_bergiliran(
        self, materi_id: str, level: LevelSoal, acuan: Sequence[Soal], jumlah: int
    ) -> list[Soal]:
        """Tetangga terdekat (jarak cosine, pencarian eksak setelah filter)
        tiap soal acuan, digabung round-robin."""
        if jumlah <= 0:
            return []
        per_acuan: list[list[Soal]] = [
            list(
                self._session.scalars(
                    self._belum_muncul(materi_id, level)
                    .order_by(Soal.embedding.cosine_distance(a.embedding), Soal.id)
                    .limit(jumlah)
                )
            )
            for a in acuan
        ]
        per_id = {s.id: s for daftar in per_acuan for s in daftar}
        ids = gabung_bergiliran([[s.id for s in daftar] for daftar in per_acuan], jumlah)
        return [per_id[i] for i in ids]

    def _acak(self, materi_id: str, level: LevelSoal, jumlah: int) -> list[Soal]:
        if jumlah <= 0:
            return []
        # Kandidat diurutkan id lalu disampel dengan rng ber-seed — reproducible.
        kandidat = list(
            self._session.scalars(self._belum_muncul(materi_id, level).order_by(Soal.id))
        )
        return self._rng.sample(kandidat, min(jumlah, len(kandidat)))

    def _pernah_muncul(self, materi_id: str, jumlah: int) -> list[Soal]:
        if jumlah <= 0:
            return []
        kandidat = [
            s
            for s in self._session.scalars(
                select(Soal).where(
                    Soal.materi_id == materi_id, Soal.aktif, Soal.id.in_(list(self._riwayat))
                )
            )
            if s.id not in self._dipilih
        ]
        target = URUTAN_LEVEL.index(self._level_siswa[materi_id].level)
        kandidat.sort(
            key=lambda s: (self._riwayat[s.id], abs(URUTAN_LEVEL.index(s.level) - target), s.id)
        )
        return kandidat[:jumlah]


@dataclass(frozen=True, slots=True)
class JawabanPaket:
    soal_id: str
    # None = tidak dijawab (dihitung salah).
    jawaban_dipilih: str | None
    dibuka_pada: datetime | None = None
    dijawab_pada: datetime | None = None


@dataclass(frozen=True, slots=True)
class PerubahanLevel:
    """Level Soal Siswa satu Materi sebelum/sesudah satu simulasi disubmit."""

    materi_id: str
    level_sebelum: LevelSoal
    level_sesudah: LevelSoal
    lemah: bool
    # None kalau Materi tidak diubah (tampil < kuota_min soal) dan belum
    # pernah teruji.
    akurasi: float | None
    # False kalau Materi tampil < kuota_min soal — datanya terlalu sedikit.
    diperbarui: bool


@dataclass(frozen=True, slots=True)
class HasilSubmitPaket:
    hasil_tes: HasilTes
    peta: list[PetaMateri]
    materi_lemah: list[str]
    akses: list[AksesTingkatSiswa]
    # Hanya simulasi (issue 03); kosong/None untuk pre-test.
    perubahan_level: list[PerubahanLevel] = field(default_factory=list)
    # None kalau bukan simulasi atau tidak ada aturan kenaikan aktif dari tingkat ini.
    evaluasi_jalur_simulasi: HasilEvaluasiJalurSimulasi | None = None


def submit_paket(
    session: Session,
    *,
    paket_id: int,
    jawaban: Sequence[JawabanPaket],
    diselesaikan_pada: datetime,
    sekolah_id: str | None = None,
    nama_siswa: str | None = None,
    nama_sekolah: str | None = None,
) -> HasilSubmitPaket:
    """Nilai satu Paket Tes: skor & predikat, Peta Kompetensi per Materi (semua
    Materi tingkat itu; yang tidak muncul Belum Teruji), simpan HasilTes +
    HasilTesMateri. Untuk pre-test: inisialisasi Level Soal Siswa Mudah,
    buka materi & simulasi tingkat itu, evaluasi jalur cepat.

    PaketTidakDitemukan / KonflikPaket (sudah disubmit) / ValueError (soal di
    luar paket atau duplikat).
    """
    # Kunci baris paket: submit bersamaan menunggu, lalu melihat disubmit_pada
    # terisi dan mendapat KonflikPaket (409), bukan error 500.
    paket = session.get(PaketTes, paket_id, with_for_update=True)
    if paket is None:
        raise PaketTidakDitemukan(f"Paket {paket_id} tidak ditemukan")
    if paket.disubmit_pada is not None:
        raise KonflikPaket("Paket sudah disubmit")

    per_soal = {baris.soal_id: baris for baris in paket.soal}
    ids_jawaban = [j.soal_id for j in jawaban]
    asing = sorted(set(ids_jawaban) - per_soal.keys())
    if asing:
        raise ValueError(f"Soal di luar paket: {', '.join(asing)}")
    if len(ids_jawaban) != len(set(ids_jawaban)):
        raise ValueError("Jawaban memuat soal yang sama lebih dari sekali")

    jawaban_per_soal = {j.soal_id: j for j in jawaban}
    for soal_id, baris in per_soal.items():
        j = jawaban_per_soal.get(soal_id)
        baris.jawaban_dipilih = j.jawaban_dipilih if j else None
        baris.is_benar = j is not None and cocokkan_jawaban(
            baris.soal_ref.kunci_jawaban, j.jawaban_dipilih, baris.soal_ref.tipe
        )
        baris.dibuka_pada = j.dibuka_pada if j else None
        baris.dijawab_pada = j.dijawab_pada if j else None

    materi_tingkat = session.scalars(
        select(Materi.id).where(Materi.tingkat_seleksi_id == paket.tingkat_seleksi_id)
    ).all()
    hitungan = {materi_id: (0, 0) for materi_id in materi_tingkat}
    for baris in paket.soal:
        jumlah_soal, jumlah_benar = hitungan.get(baris.materi_id, (0, 0))
        hitungan[baris.materi_id] = (jumlah_soal + 1, jumlah_benar + int(bool(baris.is_benar)))

    aturan = get_or_create_aturan_adaptif(session, paket.tingkat_seleksi_id)
    peta = petakan_per_materi(hitungan, ambang_lemah=aturan.ambang_lemah)

    from data_analytics.scoring import bobot_dari_level

    total_soal = len(paket.soal)
    jumlah_benar = sum(1 for baris in paket.soal if baris.is_benar)
    bobot_benar = sum(
        bobot_dari_level(baris.soal_ref.level)
        for baris in paket.soal if baris.is_benar
    )
    bobot_total = sum(
        bobot_dari_level(baris.soal_ref.level) for baris in paket.soal
    )
    skor = hitung_skor(bobot_benar=bobot_benar, bobot_total=bobot_total)
    # aturan_predikat masih diindeks tingkat_seleksi_id str (fase 1).
    tingkat_str = str(paket.tingkat_seleksi_id)
    aturan_predikat = get_or_create_aturan_predikat(session, tingkat_str)

    hasil_tes = HasilTes(
        siswa_id=paket.siswa_id,
        sekolah_id=sekolah_id,
        nama_siswa=nama_siswa,
        nama_sekolah=nama_sekolah,
        durasi_detik=durasi_pengerjaan((b.dibuka_pada, b.dijawab_pada) for b in paket.soal),
        tingkat_seleksi_id=tingkat_str,
        jenis_tes=paket.jenis_tes,
        simulasi_id=str(paket.id) if paket.jenis_tes is JenisTes.SIMULASI else None,
        total_soal=total_soal,
        jumlah_benar=jumlah_benar,
        jumlah_salah=total_soal - jumlah_benar,
        skor=skor,
        predikat_label=tentukan_predikat(skor, [(a.label, a.batas_bawah) for a in aturan_predikat]),
        diselesaikan_pada=diselesaikan_pada,
        paket_tes_id=paket.id,
        breakdown_materi=[
            HasilTesMateri(
                materi_id=p.materi_id,
                jumlah_soal=p.jumlah_soal,
                jumlah_benar=p.jumlah_benar,
                akurasi=p.akurasi,
                status_pemetaan=p.status,
            )
            for p in peta
        ],
    )
    session.add(hasil_tes)
    paket.disubmit_pada = diselesaikan_pada
    session.flush()

    _catat_materi_wajib(session, paket=paket, peta=peta)

    perubahan_level: list[PerubahanLevel] = []
    evaluasi: HasilEvaluasiJalurSimulasi | None = None
    if paket.jenis_tes is JenisTes.PRE_TEST:
        _setelah_pretest(session, paket=paket, hasil_tes=hasil_tes, peta=peta)
    else:
        perubahan_level = _perbarui_level_soal_siswa(
            session, siswa_id=paket.siswa_id, peta=peta, aturan=aturan
        )
        evaluasi = _evaluasi_jalur_simulasi_dan_catat(
            session,
            siswa_id=paket.siswa_id,
            tingkat_seleksi_id=paket.tingkat_seleksi_id,
            hasil_tes=hasil_tes,
            level_per_materi=[p.level_sesudah for p in perubahan_level],
        )

    return HasilSubmitPaket(
        hasil_tes=hasil_tes,
        peta=peta,
        materi_lemah=materi_lemah(peta),
        akses=inisialisasi_akses_siswa(session, paket.siswa_id),
        perubahan_level=perubahan_level,
        evaluasi_jalur_simulasi=evaluasi,
    )

@dataclass(frozen=True, slots=True)
class JawabanLatihan:
    soal_id: str
    jawaban_dipilih: str | None


@dataclass(frozen=True, slots=True)
class HasilSubmitLatihan:
    latihan_id: int
    nilai: float
    jumlah_benar: int
    jumlah_salah: int
    total_soal: int
    lulus: bool  # nilai >= 50%


def submit_latihan(
    session: Session,
    *,
    siswa_id: str,
    materi_id: str,
    tingkat_seleksi_id: int,
    soal_ids: Sequence[str],
    jawaban: Sequence[JawabanLatihan],
    diselesaikan_pada: datetime | None = None,
) -> HasilSubmitLatihan:
    """Nilai satu sesi Latihan. Skor berbobot (Σ bobot×benar / Σ bobot × 100).
    Threshold lulus: >= 50%. Pengulangan unlimited — setiap submit bikin
    baris Latihan baru.
    """
    # Validasi: semua soal harus ada di materi ini
    soal_map = {
        s.id: s
        for s in session.scalars(
            select(Soal).where(Soal.id.in_(soal_ids), Soal.materi_id == materi_id)
        )
    }
    if len(soal_map) != len(soal_ids):
        raise ValueError("Ada soal yang tidak valid untuk materi ini")

    from data_analytics.scoring import bobot_dari_level

    jawaban_map = {j.soal_id: j for j in jawaban}

    jumlah_benar = 0
    bobot_benar = 0
    bobot_total = 0
    for soal_id, soal in soal_map.items():
        bobot = bobot_dari_level(soal.level)
        bobot_total += bobot
        j = jawaban_map.get(soal_id)
        if j is not None and cocokkan_jawaban(soal.kunci_jawaban, j.jawaban_dipilih, soal.tipe):
            jumlah_benar += 1
            bobot_benar += bobot

    total_soal = len(soal_map)
    skor = hitung_skor(bobot_benar=bobot_benar, bobot_total=bobot_total)

    latihan = Latihan(
        siswa_id=siswa_id,
        materi_id=materi_id,
        tingkat_seleksi_id=tingkat_seleksi_id,
        nilai=skor,
        jumlah_benar=jumlah_benar,
        jumlah_salah=total_soal - jumlah_benar,
        total_soal=total_soal,
        diselesaikan_pada=diselesaikan_pada or datetime.now(timezone.utc),
    )
    session.add(latihan)
    session.flush()

    # Simpan jawaban per soal
    for soal_id in soal_ids:
        j = jawaban_map.get(soal_id)
        soal = soal_map[soal_id]
        session.add(
            LatihanJawaban(
                latihan_id=latihan.id,
                soal_id=soal_id,
                jawaban=j.jawaban_dipilih if j else None,
                is_benar=(
                    j is not None
                    and cocokkan_jawaban(soal.kunci_jawaban, j.jawaban_dipilih, soal.tipe)
                ),
            )
        )
    session.flush()

    return HasilSubmitLatihan(
        latihan_id=latihan.id,
        nilai=skor,
        jumlah_benar=jumlah_benar,
        jumlah_salah=total_soal - jumlah_benar,
        total_soal=total_soal,
        lulus=skor >= 50.0,
    )

def _perbarui_level_soal_siswa(
    session: Session, *, siswa_id: str, peta: Sequence[PetaMateri], aturan: AturanAdaptif
) -> list[PerubahanLevel]:
    """Langkah 1 mesin adaptif: Level Soal Siswa setiap Materi tingkat itu
    (peta memuat semua Materi) diperbarui adaptif.perbarui_level. Baris
    yang belum ada (Materi baru / akses dibuka admin tanpa pre-test) dibuat
    mulai Mudah."""
    tersimpan = {
        lss.materi_id: lss
        for lss in session.scalars(
            select(LevelSoalSiswa)
            .where(
                LevelSoalSiswa.siswa_id == siswa_id,
                LevelSoalSiswa.materi_id.in_([p.materi_id for p in peta]),
            )
            .with_for_update()
        )
    }
    perubahan = []
    for p in peta:
        lss = tersimpan.get(p.materi_id)
        if lss is None:
            lss = LevelSoalSiswa(
                siswa_id=siswa_id, materi_id=p.materi_id, level=LevelSoal.MUDAH, lemah=False
            )
            session.add(lss)
        sebelum = LevelSoalSiswaMateri(
            level=lss.level, lemah=lss.lemah, akurasi=lss.akurasi_terakhir
        )
        sesudah = perbarui_level(
            sebelum,
            jumlah_soal=p.jumlah_soal,
            jumlah_benar=p.jumlah_benar,
            kuota_min=aturan.kuota_min,
            ambang_naik=aturan.ambang_naik,
            ambang_lemah=aturan.ambang_lemah,
        )
        lss.level, lss.lemah, lss.akurasi_terakhir = sesudah.level, sesudah.lemah, sesudah.akurasi
        perubahan.append(
            PerubahanLevel(
                materi_id=p.materi_id,
                level_sebelum=sebelum.level,
                level_sesudah=sesudah.level,
                lemah=sesudah.lemah,
                akurasi=sesudah.akurasi,
                diperbarui=sesudah is not sebelum,
            )
        )
    session.flush()
    return perubahan


def _evaluasi_jalur_simulasi_dan_catat(
    session: Session,
    *,
    siswa_id: str,
    tingkat_seleksi_id: int,
    hasil_tes: HasilTes,
    level_per_materi: Sequence[LevelSoal],
) -> HasilEvaluasiJalurSimulasi | None:
    """Jalur simulasi (issue 02): skor attempt ini + rata-rata Level Soal
    Siswa SETELAH diperbarui simulasi ini. Lulus → pre-test tingkat tujuan
    terbuka."""
    aturan = _aturan_kenaikan_aktif(session, tingkat_seleksi_id)
    if aturan is None:
        return None

    # Syarat lulus DUA LAPIS (aturan final v1):
    #   [1] Nilai >= passing grade tingkat
    #   [2] Tidak ada materi inti dengan akurasi < 50%
    tingkat = session.get(TingkatSeleksi, tingkat_seleksi_id)
    kunci = "kabupaten" if tingkat.urutan == 1 else "provinsi"
    passing = PASSING_GRADE[kunci]
    materi_inti_ids = MATERI_INTI.get(kunci, [])

    # Ambil akurasi per materi dari HasilTesMateri yang baru dibuat
    akurasi_per_materi = {
        m.materi_id: (m.akurasi if m.akurasi is not None else 0.0)
        for m in hasil_tes.breakdown_materi
    }

    skor_lulus = hasil_tes.skor >= passing
    materi_inti_ok = (
        all(akurasi_per_materi.get(mid, 0.0) >= 50.0 for mid in materi_inti_ids)
        if materi_inti_ids
        else True
    )
    lulus = skor_lulus and materi_inti_ok

    # Bikin objek hasil (untuk kompatibilitas)
    # HasilEvaluasiJalurSimulasi HANYA punya 4 field:
    # lulus, syarat_skor_lulus, syarat_level_lulus, rata_level_aktual
    hasil = HasilEvaluasiJalurSimulasi(
        lulus=lulus,
        syarat_skor_lulus=skor_lulus,
        syarat_level_lulus=materi_inti_ok,
        rata_level_aktual=None,
    )
    session.add(
            RiwayatEvaluasiKenaikan(
            siswa_id=siswa_id,
            hasil_tes_id=hasil_tes.id,
            aturan_kenaikan_id=aturan.id,
            jalur=JalurAkses.JALUR_SIMULASI,
            skor_aktual=hasil_tes.skor,
            skor_target=passing,
            syarat_skor_lulus=hasil.syarat_skor_lulus,
            rata_level_aktual=None,
            rata_level_target=None,
            syarat_level_lulus=hasil.syarat_level_lulus,
            hasil_evaluasi="lulus" if hasil.lulus else "tidak_lulus",
        )
    )
    if hasil.lulus:
        _buka_akses(
            session,
            siswa_id=siswa_id,
            tingkat_seleksi_id=aturan.tingkat_tujuan_id,
            status=StatusAkses.PRETEST_TERBUKA,
            jalur=JalurAkses.JALUR_SIMULASI,
            hasil_tes_id=hasil_tes.id,
        )
    session.flush()
    return hasil


def _setelah_pretest(
    session: Session, *, paket: PaketTes, hasil_tes: HasilTes, peta: Sequence[PetaMateri]
) -> None:
    session.add_all(
        LevelSoalSiswa(
            siswa_id=paket.siswa_id,
            materi_id=p.materi_id,
            level=LevelSoal.MUDAH,
            akurasi_terakhir=p.akurasi,
            lemah=p.status is StatusPemetaan.BELUM_CUKUP,
        )
        for p in peta
    )
    _buka_akses(
        session,
        siswa_id=paket.siswa_id,
        tingkat_seleksi_id=paket.tingkat_seleksi_id,
        status=StatusAkses.TERBUKA,
        jalur=JalurAkses.PRETEST_SELESAI,
        hasil_tes_id=hasil_tes.id,
    )


# --- Materi Wajib & Gerbang Simulasi (fase 2 issue 04) ----------------------------


class GerbangSimulasiTertutup(Exception):
    """Materi Wajib attempt terakhir belum semuanya selesai dipelajari (HTTP 409)."""

    def __init__(self, status: StatusGerbangSimulasi) -> None:
        super().__init__("Materi Wajib dari attempt terakhir belum selesai dipelajari")
        self.status = status


def _total_halaman(session: Session, materi_ids: Sequence[str]) -> dict[str, int]:
    return {
        materi_id: jumlah
        for materi_id, jumlah in session.execute(
            select(Materi.id, func.count(HalamanMateri.id))
            .outerjoin(HalamanMateri, HalamanMateri.materi_id == Materi.id)
            .where(Materi.id.in_(materi_ids))
            .group_by(Materi.id)
        ).tuples()
    }


def _catat_materi_wajib(session: Session, *, paket: PaketTes, peta: Sequence[PetaMateri]) -> None:
    """Snapshot Materi Wajib attempt ini = Materi lemah, akurasi terendah dulu.
    Materi tanpa halaman langsung selesai (tidak ada yang bisa dibaca)."""
    akurasi = {p.materi_id: p.akurasi for p in peta}
    lemah = materi_lemah(peta)
    total = _total_halaman(session, lemah)
    sekarang = datetime.now(timezone.utc)
    session.add_all(
        MateriWajib(
            paket_tes_id=paket.id,
            siswa_id=paket.siswa_id,
            tingkat_seleksi_id=paket.tingkat_seleksi_id,
            materi_id=materi_id,
            urutan=urutan,
            akurasi=akurasi[materi_id],
            selesai_pada=sekarang if total.get(materi_id, 0) == 0 else None,
        )
        for urutan, materi_id in enumerate(lemah, start=1)
    )
    session.flush()


@dataclass(frozen=True, slots=True)
class StatusMateriWajib:
    materi_id: str
    judul: str
    urutan: int
    akurasi: float
    halaman_dibuka: int
    total_halaman: int
    selesai: bool


@dataclass(frozen=True, slots=True)
class StatusGerbangSimulasi:
    """Materi Wajib attempt terakhir siswa di satu tingkat. boleh_simulasi =
    akses tingkat terbuka DAN semua Materi Wajib selesai. Progress Belajar fase 2
    = jumlah_selesai / len(materi_wajib)."""

    boleh_simulasi: bool
    materi_wajib: list[StatusMateriWajib]

    @property
    def jumlah_selesai(self) -> int:
        return sum(1 for m in self.materi_wajib if m.selesai)


def status_gerbang_simulasi(session: Session, *, siswa_id: str, tingkat_seleksi_id: int) -> StatusGerbangSimulasi:
    """Materi Wajib & Gerbang Simulasi siswa di satu tingkat — hanya attempt TERAKHIR yang
    berlaku; Materi Wajib attempt lama tidak lagi menahan gerbang.
    TingkatTidakDitemukan."""
    if session.get(TingkatSeleksi, tingkat_seleksi_id) is None:
        raise TingkatTidakDitemukan(f"Tingkat Seleksi {tingkat_seleksi_id} tidak ditemukan")
    inisialisasi_akses_siswa(session, siswa_id)
    akses = _akses(session, siswa_id, tingkat_seleksi_id)
    terbuka = akses is not None and akses.status == StatusAkses.TERBUKA

    terakhir = session.scalars(
        select(PaketTes.id)
        .where(
            PaketTes.siswa_id == siswa_id,
            PaketTes.tingkat_seleksi_id == tingkat_seleksi_id,
            PaketTes.disubmit_pada.is_not(None),
        )
        .order_by(PaketTes.disubmit_pada.desc(), PaketTes.id.desc())
        .limit(1)
    ).first()
    if terakhir is None:
        return StatusGerbangSimulasi(boleh_simulasi=terbuka, materi_wajib=[])

    daftar = session.scalars(
        select(MateriWajib)
        .where(MateriWajib.paket_tes_id == terakhir)
        .order_by(MateriWajib.urutan)
    ).all()
    dibuka = {
        materi_wajib_id: jumlah
        for materi_wajib_id, jumlah in session.execute(
            select(MateriWajibHalaman.materi_wajib_id, func.count())
            .where(MateriWajibHalaman.materi_wajib_id.in_([m.id for m in daftar]))
            .group_by(MateriWajibHalaman.materi_wajib_id)
        ).tuples()
    }
    total = _total_halaman(session, [m.materi_id for m in daftar])
    materi_wajib = [
        StatusMateriWajib(
            materi_id=m.materi_id,
            judul=m.materi.judul,
            urutan=m.urutan,
            akurasi=m.akurasi,
            halaman_dibuka=dibuka.get(m.id, 0),
            total_halaman=total.get(m.materi_id, 0),
            selesai=m.selesai_pada is not None,
        )
        for m in daftar
    ]
        # Gate latihan: setiap materi wajib harus punya minimal 1 latihan lulus (nilai >= 50)
    materi_wajib_ids = [m.materi_id for m in materi_wajib]
    latihan_lulus_per_materi: dict[str, bool] = {}
    if materi_wajib_ids:
        for mid in materi_wajib_ids:
            lulus = session.scalar(
                select(func.count()).select_from(Latihan).where(
                    Latihan.siswa_id == siswa_id,
                    Latihan.tingkat_seleksi_id == tingkat_seleksi_id,
                    Latihan.materi_id == mid,
                    Latihan.nilai >= 50.0,
                )
            ) or 0
            latihan_lulus_per_materi[mid] = lulus > 0

    semua_materi_selesai = all(m.selesai for m in materi_wajib)
    semua_latihan_lulus = all(latihan_lulus_per_materi.values()) if materi_wajib_ids else True

    return StatusGerbangSimulasi(
        boleh_simulasi=terbuka and semua_materi_selesai and semua_latihan_lulus,
        materi_wajib=materi_wajib,
    )


@dataclass(frozen=True, slots=True)
class HasilBacaHalaman:
    siswa_id: str
    materi_id: str
    # Jumlah halaman unik Materi ini yang pernah dibuka siswa (riwayat permanen).
    halaman_dibuka: int
    total_halaman: int


def catat_baca_halaman(
    session: Session, *, siswa_id: str, materi_id: str, halaman: int, dibuka_pada: datetime
) -> HasilBacaHalaman:
    """Event "siswa membuka halaman Materi" (issue 04): catat riwayat baca
    permanen, lalu untuk setiap Materi Wajib aktif (belum selesai) siswa+Materi
    ini catat halamannya dan cek kriteria selesai. Idempoten per halaman.
    ValueError kalau Materi tidak ada atau nomor halaman tidak ada di Materi itu.
    """
    if session.get(Materi, materi_id) is None:
        raise ValueError(f"Materi {materi_id} tidak ditemukan")
    halaman_materi = set(
        session.scalars(select(HalamanMateri.nomor).where(HalamanMateri.materi_id == materi_id))
    )
    if halaman not in halaman_materi:
        raise ValueError(f"Halaman {halaman} tidak ada di Materi {materi_id}")
    sekarang = datetime.now(timezone.utc)

    session.execute(
        pg_insert(RiwayatBacaHalaman)
        .values(
            siswa_id=siswa_id,
            materi_id=materi_id,
            nomor_halaman=halaman,
            pertama_dibuka_pada=dibuka_pada,
            terakhir_dibuka_pada=dibuka_pada,
        )
        .on_conflict_do_update(
            constraint="uq_riwayat_baca_halaman_siswa_materi",
            set_={"terakhir_dibuka_pada": dibuka_pada},
        )
    )

    # Kunci baris Materi Wajib: event bersamaan untuk halaman berbeda dari
    # Materi yang sama diproses bergiliran, sehingga pengecekan selesai selalu
    # melihat semua halaman yang sudah tercatat.
    aktif = session.scalars(
        select(MateriWajib)
        .where(
            MateriWajib.siswa_id == siswa_id,
            MateriWajib.materi_id == materi_id,
            MateriWajib.selesai_pada.is_(None),
        )
        .order_by(MateriWajib.id)
        .with_for_update()
    ).all()
    for materi_wajib in aktif:
        session.execute(
            pg_insert(MateriWajibHalaman)
            .values(materi_wajib_id=materi_wajib.id, nomor_halaman=halaman, dibuka_pada=dibuka_pada)
            .on_conflict_do_nothing(constraint="uq_materi_wajib_halaman_wajib_nomor")
        )
        halaman_wajib = session.scalars(
            select(MateriWajibHalaman.nomor_halaman).where(
                MateriWajibHalaman.materi_wajib_id == materi_wajib.id
            )
        ).all()
        if selesai_dipelajari(halaman_wajib, halaman_materi=halaman_materi):
            # Waktu server, bukan timestamp klien: selesai_pada tidak pernah
            # mendahului dibuat_pada walau jam klien melenceng.
            materi_wajib.selesai_pada = sekarang

    halaman_dibuka = session.scalar(
        select(func.count()).select_from(RiwayatBacaHalaman).where(
            RiwayatBacaHalaman.siswa_id == siswa_id,
            RiwayatBacaHalaman.materi_id == materi_id,
        )
    )
    session.flush()
    return HasilBacaHalaman(
        siswa_id=siswa_id,
        materi_id=materi_id,
        halaman_dibuka=halaman_dibuka or 0,
        total_halaman=len(halaman_materi),
    )


# --- Leaderboard ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PeringkatSiswa:
    peringkat: Peringkat
    nama_siswa: str | None
    sekolah_id: str | None
    nama_sekolah: str | None


@dataclass(frozen=True, slots=True)
class HasilLeaderboard:
    tingkat: TingkatSeleksi
    peringkat: list[PeringkatSiswa]


def _jenjang_diikuti(session: Session, siswa_id: str) -> TingkatSeleksi:
    """Tingkat tertinggi yang materi & simulasinya sudah terbuka bagi siswa;
    tingkat pertama kalau belum ada."""
    akses = inisialisasi_akses_siswa(session, siswa_id)
    terbuka = [a.tingkat_seleksi for a in akses if a.status == StatusAkses.TERBUKA]
    if terbuka:
        return max(terbuka, key=lambda t: t.urutan)
    pertama = session.scalars(select(TingkatSeleksi).order_by(TingkatSeleksi.urutan)).first()
    if pertama is None:
        raise TingkatTidakDitemukan("Belum ada Tingkat Seleksi")
    return pertama


def leaderboard_tingkat(
    session: Session, *, siswa_id: str, tingkat_seleksi_id: int | None = None
) -> HasilLeaderboard:
    """5 teratas di jenjang yang diikuti siswa (atau tingkat_seleksi_id kalau
    diberikan), dihitung saat dibaca dari seluruh attempt simulasi yang
    disubmit dengan waktu pengerjaan — selalu mengikuti submit terbaru.
    Nama & sekolah = snapshot terbaru yang dikirim siswa itu.
    TingkatTidakDitemukan."""
    if tingkat_seleksi_id is None:
        tingkat = _jenjang_diikuti(session, siswa_id)
    else:
        ditemukan = session.get(TingkatSeleksi, tingkat_seleksi_id)
        if ditemukan is None:
            raise TingkatTidakDitemukan(f"Tingkat Seleksi {tingkat_seleksi_id} tidak ditemukan")
        tingkat = ditemukan

    hasil = session.scalars(
        select(HasilTes)
        .where(
            HasilTes.tingkat_seleksi_id == str(tingkat.id),
            HasilTes.jenis_tes == JenisTes.SIMULASI,
            HasilTes.siswa_id.is_not(None),
        )
        .order_by(HasilTes.diselesaikan_pada, HasilTes.id)
    ).all()
    peringkat = susun_leaderboard(
        [
            AttemptSimulasi(
                siswa_id=h.siswa_id, skor=h.skor, durasi_detik=h.durasi_detik, total_soal=h.total_soal
            )
            for h in hasil
            if h.siswa_id is not None and h.durasi_detik is not None
        ]
    )
    # Terurut dari yang terlama: nilai terakhir yang terisi = snapshot terbaru.
    nama: dict[str, tuple[str | None, str | None, str | None]] = {}
    for h in hasil:
        if h.siswa_id is None:
            continue
        lama = nama.get(h.siswa_id, (None, None, None))
        nama[h.siswa_id] = (
            h.nama_siswa or lama[0],
            h.sekolah_id or lama[1],
            h.nama_sekolah or lama[2],
        )
    return HasilLeaderboard(
        tingkat=tingkat,
        peringkat=[
            PeringkatSiswa(
                peringkat=p,
                nama_siswa=nama[p.siswa_id][0],
                sekolah_id=nama[p.siswa_id][1],
                nama_sekolah=nama[p.siswa_id][2],
            )
            for p in peringkat
        ],
    )


# --- Katalog Materi (dokumen Materi/*.docx) ------------------------------------


class MateriTidakDitemukan(LookupError):
    pass


def daftar_materi(session: Session, *, tingkat_seleksi_id: int | None = None) -> list[Materi]:
    """Materi urut tingkat lalu nomor topik (Materi tanpa topik di akhir)."""
    query = (
        select(Materi)
        .join(TingkatSeleksi, Materi.tingkat_seleksi_id == TingkatSeleksi.id)
        .order_by(TingkatSeleksi.urutan, Materi.topik.asc().nulls_last(), Materi.id)
    )
    if tingkat_seleksi_id is not None:
        if session.get(TingkatSeleksi, tingkat_seleksi_id) is None:
            raise TingkatTidakDitemukan(f"Tingkat seleksi {tingkat_seleksi_id} tidak ditemukan")
        query = query.where(Materi.tingkat_seleksi_id == tingkat_seleksi_id)
    return list(session.scalars(query))


def get_materi(session: Session, materi_id: str) -> Materi:
    materi = session.get(Materi, materi_id)
    if materi is None:
        raise MateriTidakDitemukan(f"Materi {materi_id} tidak ditemukan")
    return materi


def halaman_dibaca_siswa(
    session: Session, *, siswa_id: str, materi_ids: Sequence[str]
) -> dict[str, set[int]]:
    """Nomor halaman unik yang pernah dibuka siswa (riwayat baca umum), per
    Materi."""
    hasil: dict[str, set[int]] = defaultdict(set)
    for materi_id, nomor in session.execute(
        select(RiwayatBacaHalaman.materi_id, RiwayatBacaHalaman.nomor_halaman).where(
            RiwayatBacaHalaman.siswa_id == siswa_id,
            RiwayatBacaHalaman.materi_id.in_(materi_ids),
        )
    ).tuples():
        hasil[materi_id].add(nomor)
    return hasil
