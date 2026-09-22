"""Orkestrasi Aturan Skor & Hasil Simulasi (tiket 01) dan Progress Belajar
(tiket 02) — lihat .scratch/osn-data-analytics/issues/.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from data_analytics.kenaikan import evaluasi_syarat_kenaikan
from data_analytics.models import (
    AksesTingkatSiswa,
    AturanKenaikanTingkat,
    AturanPemetaan,
    AturanPredikat,
    HasilTes,
    HasilTesSubkompetensi,
    JawabanSiswa,
    JenisTes,
    ProgressMateri,
    RiwayatEvaluasiKenaikan,
    TingkatSeleksi,
)
from data_analytics.pemetaan import tentukan_butuh_optimasi, tentukan_status_pemetaan
from data_analytics.progress import persentase_selesai, validasi_halaman
from data_analytics.scoring import hitung_skor, tentukan_predikat

DEFAULT_ATURAN_PREDIKAT: Final[tuple[tuple[str, float], ...]] = (
    ("Sangat Baik", 90),
    ("Baik", 80),
    ("Cukup", 70),
    ("Perlu Latihan", 0),
)

# (ambang_cukup_persen, ambang_representasi_persen) — sama dengan default yang
# dipakai seed script (tiket 09); lihat CONTEXT.md "Aturan Pemetaan".
DEFAULT_ATURAN_PEMETAAN: Final[tuple[float, float]] = (70.0, 20.0)


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
    dibekukan saat dihitung (lihat catat_hasil_tes).
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


def get_or_create_aturan_pemetaan(
    session: Session, tingkat_seleksi_id: str
) -> AturanPemetaan:
    """Aturan pemetaan milik satu Tingkat Seleksi. Kalau belum pernah
    dikonfigurasi Super Admin, di-seed otomatis dengan DEFAULT_ATURAN_PEMETAAN
    — pola yang sama dengan get_or_create_aturan_predikat, supaya Pemetaan
    Kompetensi tidak gagal/terblokir karena config belum diisi.
    """
    existing = session.scalars(
        select(AturanPemetaan).where(
            AturanPemetaan.tingkat_seleksi_id == tingkat_seleksi_id
        )
    ).one_or_none()
    if existing is not None:
        return existing

    ambang_cukup, ambang_representasi = DEFAULT_ATURAN_PEMETAAN
    baru = AturanPemetaan(
        tingkat_seleksi_id=tingkat_seleksi_id,
        ambang_cukup_persen=ambang_cukup,
        ambang_representasi_persen=ambang_representasi,
    )
    session.add(baru)
    session.flush()
    return baru


@dataclass(frozen=True, slots=True)
class BreakdownSubkompetensi:
    subkompetensi_id: str
    jumlah_soal: int
    jumlah_benar: int
    # Dari jumlah_benar, berapa yang durasi_detik > batas_waktu_detik (tiket 05)
    # — dipakai menghitung flag butuh_optimasi. Default 0 untuk pemanggil yang
    # tidak melacak kecepatan (mis. seed data).
    jumlah_benar_lambat: int = 0


def catat_hasil_tes(
    session: Session,
    *,
    siswa_id: str,
    tingkat_seleksi_id: str,
    jenis_tes: JenisTes,
    total_soal: int,
    jumlah_benar: int,
    breakdown_subkompetensi: Sequence[BreakdownSubkompetensi],
    diselesaikan_pada: datetime,
    simulasi_id: str | None = None,
    sekolah_id: str | None = None,
) -> HasilTes:
    """Hitung skor & predikat satu attempt (Pre-Test atau Simulasi), lalu simpan
    sebagai HasilTes + breakdown HasilTesSubkompetensi-nya (termasuk Status
    Pemetaan & flag butuh_optimasi per Subkompetensi — FR-07/tiket 11).
    predikat_label & status_pemetaan/butuh_optimasi dibekukan pada baris ini
    saat fungsi dipanggil — perubahan AturanPredikat/AturanPemetaan setelahnya
    tidak memengaruhi hasil yang sudah tersimpan.
    """
    if jenis_tes is JenisTes.SIMULASI and simulasi_id is None:
        raise ValueError("simulasi_id wajib diisi untuk jenis_tes='simulasi'")
    if jenis_tes is JenisTes.PRE_TEST and simulasi_id is not None:
        raise ValueError("simulasi_id harus kosong untuk jenis_tes='pre_test'")

    jumlah_soal_breakdown = sum(b.jumlah_soal for b in breakdown_subkompetensi)
    if jumlah_soal_breakdown != total_soal:
        raise ValueError(
            "total jumlah_soal pada breakdown_subkompetensi "
            f"({jumlah_soal_breakdown}) harus sama dengan total_soal ({total_soal})"
        )

    skor = hitung_skor(jumlah_benar=jumlah_benar, total_soal=total_soal)

    aturan_predikat = get_or_create_aturan_predikat(session, tingkat_seleksi_id)
    predikat_label = tentukan_predikat(
        skor, [(a.label, a.batas_bawah) for a in aturan_predikat]
    )

    aturan_pemetaan = get_or_create_aturan_pemetaan(session, tingkat_seleksi_id)

    breakdown_rows = []
    for b in breakdown_subkompetensi:
        status = tentukan_status_pemetaan(
            jumlah_soal_subkompetensi=b.jumlah_soal,
            jumlah_benar=b.jumlah_benar,
            total_soal_tes=total_soal,
            ambang_cukup_persen=aturan_pemetaan.ambang_cukup_persen,
            ambang_representasi_persen=aturan_pemetaan.ambang_representasi_persen,
        )
        butuh_optimasi = tentukan_butuh_optimasi(
            status=status,
            jumlah_benar=b.jumlah_benar,
            jumlah_benar_lambat=b.jumlah_benar_lambat,
        )
        breakdown_rows.append(
            HasilTesSubkompetensi(
                subkompetensi_id=b.subkompetensi_id,
                jumlah_soal=b.jumlah_soal,
                jumlah_benar=b.jumlah_benar,
                status_pemetaan=status,
                butuh_optimasi=butuh_optimasi,
            )
        )

    hasil = HasilTes(
        siswa_id=siswa_id,
        sekolah_id=sekolah_id,
        tingkat_seleksi_id=tingkat_seleksi_id,
        jenis_tes=jenis_tes,
        simulasi_id=simulasi_id,
        total_soal=total_soal,
        jumlah_benar=jumlah_benar,
        jumlah_salah=total_soal - jumlah_benar,
        skor=skor,
        predikat_label=predikat_label,
        diselesaikan_pada=diselesaikan_pada,
        breakdown_subkompetensi=breakdown_rows,
    )

    session.add(hasil)
    session.flush()
    return hasil


@dataclass(frozen=True, slots=True)
class JawabanInput:
    """Satu jawaban butir soal dari payload submit (tiket 11/endpoint
    POST /api/v1/analytics/assessment/submit). batas_waktu_detik caller-supplied
    per jawaban (bukan dibaca dari Soal.batas_waktu_detik lokal) — konsisten
    dengan prinsip stateless ADR 0002 yang disebut resolusi tiket 11 poin 1.
    """

    soal_id: str
    subkompetensi_id: str
    jawaban_dipilih: str
    is_benar: bool
    durasi_detik: int
    batas_waktu_detik: int


def catat_submission_tes(
    session: Session,
    *,
    siswa_id: str,
    tingkat_seleksi_id: str,
    jenis_tes: JenisTes,
    jawaban_siswa: Sequence[JawabanInput],
    diselesaikan_pada: datetime,
    simulasi_id: str | None = None,
    sekolah_id: str | None = None,
) -> HasilTes:
    """Orkestrasi endpoint submit (tiket 11): kelompokkan jawaban_siswa per
    Subkompetensi (menghitung is_lambat & rasio benar-tapi-lambat), delegasikan
    ke catat_hasil_tes untuk skor/predikat/Peta Kompetensi, lalu simpan log
    JawabanSiswa (tiket 05) terhubung ke HasilTes yang dihasilkan.
    """
    if not jawaban_siswa:
        raise ValueError("jawaban_siswa tidak boleh kosong")

    per_subkompetensi: dict[str, list[JawabanInput]] = defaultdict(list)
    for jawaban in jawaban_siswa:
        per_subkompetensi[jawaban.subkompetensi_id].append(jawaban)

    breakdown = [
        BreakdownSubkompetensi(
            subkompetensi_id=subkompetensi_id,
            jumlah_soal=len(daftar),
            jumlah_benar=sum(1 for j in daftar if j.is_benar),
            jumlah_benar_lambat=sum(
                1
                for j in daftar
                if j.is_benar and j.durasi_detik > j.batas_waktu_detik
            ),
        )
        for subkompetensi_id, daftar in per_subkompetensi.items()
    ]

    # total_soal/jumlah_benar diturunkan dari breakdown (bukan dihitung ulang
    # dari jawaban_siswa mentah) supaya hanya ada satu sumber kebenaran untuk
    # agregat ini — sama-sama berasal dari pengelompokan per_subkompetensi.
    hasil = catat_hasil_tes(
        session,
        siswa_id=siswa_id,
        sekolah_id=sekolah_id,
        tingkat_seleksi_id=tingkat_seleksi_id,
        jenis_tes=jenis_tes,
        simulasi_id=simulasi_id,
        total_soal=sum(b.jumlah_soal for b in breakdown),
        jumlah_benar=sum(b.jumlah_benar for b in breakdown),
        breakdown_subkompetensi=breakdown,
        diselesaikan_pada=diselesaikan_pada,
    )

    session.add_all(
        JawabanSiswa(
            hasil_tes_id=hasil.id,
            soal_id=j.soal_id,
            subkompetensi_id=j.subkompetensi_id,
            jawaban_dipilih=j.jawaban_dipilih,
            is_benar=j.is_benar,
            durasi_detik=j.durasi_detik,
            is_lambat=j.durasi_detik > j.batas_waktu_detik,
        )
        for j in jawaban_siswa
    )
    session.flush()

    return hasil


def catat_progress_halaman(
    session: Session,
    *,
    siswa_id: int,
    materi_id: int,
    subkompetensi_id: int,
    tingkat_seleksi_id: int,
    total_halaman: int,
    halaman_dicapai: int,
) -> ProgressMateri:
    """Catat siswa mencapai suatu halaman Materi. halaman_tertinggi_dicapai adalah
    high-water mark — tidak pernah turun walau siswa navigasi mundur.
    subkompetensi_id/tingkat_seleksi_id/total_halaman selalu diperbarui ke nilai
    terbaru dari payload (snapshot), sesuai ADR 0002.

    Larangan "harus urut untuk maju" dari resolusi tiket 02 adalah aturan
    navigasi UI Layanan Belajar (fullstack yang mencegah klik "lanjut" melompati
    halaman) — fungsi ini tidak menegakkan ulang bahwa halaman_dicapai persis
    existing+1; ia hanya menjamin invariant penyimpanan (rentang valid,
    monoton tidak turun), konsisten dengan ADR 0002 yang mempercayai pemanggil
    sebagai sumber kebenaran metadata Materi.
    """
    validasi_halaman(
        halaman=halaman_dicapai, total_halaman=total_halaman, nama_field="halaman_dicapai"
    )

    existing = session.scalars(
        select(ProgressMateri).where(
            ProgressMateri.siswa_id == siswa_id,
            ProgressMateri.materi_id == materi_id,
        )
    ).one_or_none()

    if existing is None:
        baris = ProgressMateri(
            siswa_id=siswa_id,
            materi_id=materi_id,
            subkompetensi_id=subkompetensi_id,
            tingkat_seleksi_id=tingkat_seleksi_id,
            total_halaman=total_halaman,
            halaman_tertinggi_dicapai=halaman_dicapai,
        )
        session.add(baris)
        session.flush()
        return baris

    mark_baru = max(existing.halaman_tertinggi_dicapai, halaman_dicapai)
    if mark_baru > total_halaman:
        raise ValueError(
            "total_halaman baru "
            f"({total_halaman}) lebih kecil dari halaman yang sudah pernah "
            f"dicapai siswa ({existing.halaman_tertinggi_dicapai})"
        )

    existing.subkompetensi_id = subkompetensi_id
    existing.tingkat_seleksi_id = tingkat_seleksi_id
    existing.total_halaman = total_halaman
    existing.halaman_tertinggi_dicapai = mark_baru
    session.flush()
    return existing


@dataclass(frozen=True, slots=True)
class MateriRelevan:
    """Satu Materi yang saat ini masuk Rekomendasi Materi siswa — dipasok
    pemanggil (tim fullstack), bukan dari katalog Materi milik layanan ini
    (ADR 0002).
    """

    materi_id: int
    subkompetensi_id: int


@dataclass(frozen=True, slots=True)
class ProgressSubkompetensi:
    subkompetensi_id: int
    jumlah_materi: int
    rata_rata_persentase: float


def hitung_progress_belajar(
    session: Session,
    *,
    siswa_id: int,
    materi_relevan: Sequence[MateriRelevan],
) -> list[ProgressSubkompetensi]:
    """Breakdown Progress Belajar per Subkompetensi, dihitung dari materi_relevan
    (Rekomendasi Materi TERKINI siswa — bukan histori kumulatif). Materi yang
    belum pernah dibuka (tidak punya baris progress_materi) dianggap 0%. Materi
    di progress_materi yang tidak ada di materi_relevan diabaikan.
    """
    if not materi_relevan:
        return []

    materi_ids = [m.materi_id for m in materi_relevan]
    baris_progress = session.scalars(
        select(ProgressMateri).where(
            ProgressMateri.siswa_id == siswa_id,
            ProgressMateri.materi_id.in_(materi_ids),
        )
    ).all()
    persentase_per_materi = {
        p.materi_id: persentase_selesai(
            halaman_tertinggi_dicapai=p.halaman_tertinggi_dicapai,
            total_halaman=p.total_halaman,
        )
        for p in baris_progress
    }

    materi_per_subkompetensi: dict[int, list[float]] = defaultdict(list)
    for materi in materi_relevan:
        materi_per_subkompetensi[materi.subkompetensi_id].append(
            persentase_per_materi.get(materi.materi_id, 0.0)
        )

    return [
        ProgressSubkompetensi(
            subkompetensi_id=subkompetensi_id,
            jumlah_materi=len(persentase_list),
            rata_rata_persentase=round(sum(persentase_list) / len(persentase_list), 2),
        )
        for subkompetensi_id, persentase_list in sorted(materi_per_subkompetensi.items())
    ]


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
            hasil.is_anonymized = True
        session.flush()

    return len(kedaluwarsa)


# --- Kenaikan Tingkat (tiket 03) ---------------------------------------------
#
# tingkat_asal_id/tingkat_tujuan_id/tingkat_seleksi_id di bawah merujuk ke
# katalog TingkatSeleksi LOKAL (int) — bukan tingkat_seleksi_id caller-supplied
# (UUID) yang dipakai HasilTes/catat_submission_tes. Lihat catatan di
# models.AturanKenaikanTingkat untuk gap ini.


def inisialisasi_akses_siswa(session: Session, siswa_id: str) -> list[AksesTingkatSiswa]:
    """Pastikan siswa punya baris AksesTingkatSiswa untuk setiap Tingkat Seleksi
    lokal. Tingkat urutan=1 default 'terbuka' (dibuka_karena='default_awal'),
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
            AksesTingkatSiswa(
                siswa_id=siswa_id,
                tingkat_seleksi_id=tingkat.id,
                status="terbuka" if is_pertama else "terkunci",
                dibuka_karena="default_awal" if is_pertama else None,
                dibuka_pada=datetime.now(timezone.utc) if is_pertama else None,
            )
        )
    if baru:
        session.add_all(baru)
        session.flush()

    return list(
        session.scalars(
            select(AksesTingkatSiswa)
            .where(AksesTingkatSiswa.siswa_id == siswa_id)
            .join(TingkatSeleksi, AksesTingkatSiswa.tingkat_seleksi_id == TingkatSeleksi.id)
            .order_by(TingkatSeleksi.urutan)
        ).all()
    )


def override_akses_admin(
    session: Session,
    *,
    siswa_id: str,
    tingkat_seleksi_id: int,
    status: str,
    catatan: str | None = None,
) -> AksesTingkatSiswa:
    """Override manual akses tingkat siswa oleh Super Admin (FR-17/tiket 03)."""
    akses = session.scalars(
        select(AksesTingkatSiswa).where(
            AksesTingkatSiswa.siswa_id == siswa_id,
            AksesTingkatSiswa.tingkat_seleksi_id == tingkat_seleksi_id,
        )
    ).one_or_none()

    if akses is None:
        akses = AksesTingkatSiswa(siswa_id=siswa_id, tingkat_seleksi_id=tingkat_seleksi_id)
        session.add(akses)

    akses.status = status
    akses.catatan = catatan
    if status == "terbuka":
        akses.dibuka_karena = "manual_admin"
        akses.dibuka_pada = datetime.now(timezone.utc)

    session.flush()
    return akses


def evaluasi_dan_catat_kenaikan(
    session: Session,
    *,
    siswa_id: str,
    hasil_tes_id: int,
    tingkat_asal_id: int,
    skor: float,
    jumlah_kompetensi_cukup: int,
    total_kompetensi_silabus: int,
) -> RiwayatEvaluasiKenaikan | None:
    """Evaluasi kelayakan kenaikan dari tingkat_asal_id ke tingkat berikutnya
    (resolusi tiket 03), catat sebagai RiwayatEvaluasiKenaikan, dan buka akses
    tingkat tujuan permanen kalau lulus. `None` kalau tidak ada aturan aktif
    dari tingkat_asal_id (mis. siswa sudah di tingkat tertinggi/Nasional).
    """
    aturan = session.scalars(
        select(AturanKenaikanTingkat).where(
            AturanKenaikanTingkat.tingkat_asal_id == tingkat_asal_id,
            AturanKenaikanTingkat.aktif.is_(True),
        )
    ).one_or_none()
    if aturan is None:
        return None

    hasil = evaluasi_syarat_kenaikan(
        skor=skor,
        skor_simulasi_min=aturan.skor_simulasi_min,
        jumlah_kompetensi_cukup=jumlah_kompetensi_cukup,
        total_kompetensi_silabus=total_kompetensi_silabus,
        persentase_kompetensi_cukup_min=aturan.persentase_kompetensi_cukup_min,
    )

    riwayat = RiwayatEvaluasiKenaikan(
        siswa_id=siswa_id,
        hasil_tes_id=hasil_tes_id,
        aturan_kenaikan_id=aturan.id,
        skor_aktual=skor,
        skor_target=aturan.skor_simulasi_min,
        syarat_skor_lulus=hasil.syarat_skor_lulus,
        persentase_cukup_aktual=hasil.persentase_cukup_aktual,
        persentase_cukup_target=aturan.persentase_kompetensi_cukup_min,
        syarat_kompetensi_lulus=hasil.syarat_kompetensi_lulus,
        hasil_evaluasi=hasil.hasil_evaluasi,
    )
    session.add(riwayat)

    if hasil.hasil_evaluasi == "lulus":
        override_akses_admin(
            session,
            siswa_id=siswa_id,
            tingkat_seleksi_id=aturan.tingkat_tujuan_id,
            status="terbuka",
            catatan=None,
        )
        # override_akses_admin men-set dibuka_karena='manual_admin' — koreksi
        # jadi 'lulus_evaluasi' karena ini dipicu evaluasi otomatis, bukan
        # admin, dan catat hasil_tes_id pemicunya.
        akses_tujuan = session.scalars(
            select(AksesTingkatSiswa).where(
                AksesTingkatSiswa.siswa_id == siswa_id,
                AksesTingkatSiswa.tingkat_seleksi_id == aturan.tingkat_tujuan_id,
            )
        ).one()
        akses_tujuan.dibuka_karena = "lulus_evaluasi"
        akses_tujuan.hasil_tes_id = hasil_tes_id

    session.flush()
    return riwayat


def get_akses_siswa(session: Session, siswa_id: str) -> list[AksesTingkatSiswa]:
    """Status akses siswa ke seluruh Tingkat Seleksi lokal — inisialisasi
    otomatis dulu kalau siswa belum pernah punya baris akses sama sekali.
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
    persentase_kompetensi_cukup_min: float | None = None,
    aktif: bool | None = None,
) -> AturanKenaikanTingkat | None:
    aturan = session.get(AturanKenaikanTingkat, aturan_id)
    if aturan is None:
        return None
    if skor_simulasi_min is not None:
        aturan.skor_simulasi_min = skor_simulasi_min
    if persentase_kompetensi_cukup_min is not None:
        aturan.persentase_kompetensi_cukup_min = persentase_kompetensi_cukup_min
    if aktif is not None:
        aturan.aktif = aktif
    session.flush()
    return aturan
