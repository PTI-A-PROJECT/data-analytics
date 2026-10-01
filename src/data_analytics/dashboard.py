"""Agregasi metrik Dashboard Super Admin (FR-24, tiket 04) — real-time dari
tabel transaksional yang sudah ada, tanpa tabel rollup terpisah (resolusi
tiket 04 poin 3). Filter `tingkat_seleksi_id` dari resolusi tiket 04 sengaja
TIDAK diimplementasikan di sini: KPI transaksional memfilter lewat
HasilTes.tingkat_seleksi_id (str, caller-supplied UUID — tiket 11) sedangkan
distribusi_tingkat memfilter lewat AksesTingkatSiswa.tingkat_seleksi_id (int,
katalog lokal — tiket 03); dua ruang id yang berbeda, sama seperti gap yang
sudah dicatat tiket 11. `sekolah_id` dan `rentang_waktu` aman karena
keduanya cuma menyentuh HasilTes (str/datetime, konsisten).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from data_analytics.models import AksesTingkatSiswa, HasilTes, JenisTes, RiwayatEvaluasiKenaikan, TingkatSeleksi
from data_analytics.schemas import (
    DashboardFilter,
    DashboardKPI,
    DashboardResponse,
    DistribusiTingkatItem,
    KomparasiSekolahItem,
    TrenAktivitasItem,
)

_RENTANG_HARI: dict[str, int] = {"7d": 7, "30d": 30, "90d": 90}


def hitung_metrik_dashboard(
    session: Session,
    *,
    sekolah_id: str | None = None,
    rentang_waktu: str = "30d",
) -> DashboardResponse:
    hari = _RENTANG_HARI.get(rentang_waktu)
    batas_waktu = (
        datetime.now(timezone.utc) - timedelta(days=hari) if hari is not None else None
    )

    query = select(HasilTes)
    if sekolah_id is not None:
        query = query.where(HasilTes.sekolah_id == sekolah_id)
    if batas_waktu is not None:
        query = query.where(HasilTes.diselesaikan_pada >= batas_waktu)
    hasil_tes_records = list(session.scalars(query).all())

    kpi = _hitung_kpi(session, hasil_tes_records)
    distribusi_tingkat = _hitung_distribusi_tingkat(session, sekolah_id)
    tren_aktivitas = _hitung_tren_aktivitas(hasil_tes_records)
    komparasi_sekolah = _hitung_komparasi_sekolah(session)

    return DashboardResponse(
        rentang_waktu=rentang_waktu,
        filter=DashboardFilter(sekolah_id=sekolah_id, rentang_waktu=rentang_waktu),
        kpi=kpi,
        distribusi_tingkat=distribusi_tingkat,
        tren_aktivitas=tren_aktivitas,
        komparasi_sekolah=komparasi_sekolah,
    )


def _hitung_kpi(session: Session, hasil_tes_records: list[HasilTes]) -> DashboardKPI:
    total_siswa_aktif = len({ht.siswa_id for ht in hasil_tes_records if ht.siswa_id})
    total_pre_test = sum(1 for ht in hasil_tes_records if ht.jenis_tes is JenisTes.PRE_TEST)
    simulasi_records = [ht for ht in hasil_tes_records if ht.jenis_tes is JenisTes.SIMULASI]
    total_simulasi = len(simulasi_records)
    rata_skor_simulasi = (
        round(sum(ht.skor for ht in simulasi_records) / total_simulasi, 2)
        if total_simulasi > 0
        else 0.0
    )

    hasil_tes_ids = [ht.id for ht in hasil_tes_records]
    total_eval = 0
    total_lulus = 0
    if hasil_tes_ids:
        eval_records = session.scalars(
            select(RiwayatEvaluasiKenaikan).where(
                RiwayatEvaluasiKenaikan.hasil_tes_id.in_(hasil_tes_ids)
            )
        ).all()
        total_eval = len(eval_records)
        total_lulus = sum(1 for e in eval_records if e.hasil_evaluasi == "lulus")
    rasio_kelulusan = round((total_lulus / total_eval) * 100, 2) if total_eval > 0 else 0.0

    return DashboardKPI(
        total_siswa_aktif=total_siswa_aktif,
        total_tes_selesai=len(hasil_tes_records),
        total_pre_test=total_pre_test,
        total_simulasi=total_simulasi,
        rata_rata_skor_simulasi=rata_skor_simulasi,
        rasio_kelulusan_tingkat=rasio_kelulusan,
    )


def _hitung_distribusi_tingkat(
    session: Session, sekolah_id: str | None
) -> list[DistribusiTingkatItem]:
    """Tingkat tertinggi yang 'terbuka' per siswa — lifetime snapshot, tidak
    terpotong rentang_waktu (resolusi tiket 04 poin 3).
    """
    akses_query = (
        select(AksesTingkatSiswa, TingkatSeleksi)
        .join(TingkatSeleksi, AksesTingkatSiswa.tingkat_seleksi_id == TingkatSeleksi.id)
        .where(AksesTingkatSiswa.status == "terbuka")
    )
    if sekolah_id is not None:
        siswa_sekolah = set(
            session.scalars(
                select(HasilTes.siswa_id).where(HasilTes.sekolah_id == sekolah_id)
            ).all()
        )
        akses_query = akses_query.where(AksesTingkatSiswa.siswa_id.in_(siswa_sekolah))

    tertinggi_per_siswa: dict[str, TingkatSeleksi] = {}
    for akses, tingkat in session.execute(akses_query).all():
        saat_ini = tertinggi_per_siswa.get(akses.siswa_id)
        if saat_ini is None or tingkat.urutan > saat_ini.urutan:
            tertinggi_per_siswa[akses.siswa_id] = tingkat

    jumlah_per_tingkat: dict[int, int] = defaultdict(int)
    for tingkat in tertinggi_per_siswa.values():
        jumlah_per_tingkat[tingkat.id] += 1

    total_populasi = len(tertinggi_per_siswa)
    semua_tingkat = session.scalars(select(TingkatSeleksi).order_by(TingkatSeleksi.urutan)).all()
    return [
        DistribusiTingkatItem(
            tingkat_id=t.id,
            nama=t.nama,
            jumlah_siswa=jumlah_per_tingkat.get(t.id, 0),
            persentase=(
                round((jumlah_per_tingkat.get(t.id, 0) / total_populasi) * 100, 2)
                if total_populasi > 0
                else 0.0
            ),
        )
        for t in semua_tingkat
    ]


def _hitung_tren_aktivitas(hasil_tes_records: list[HasilTes]) -> list[TrenAktivitasItem]:
    per_tanggal: dict[str, dict[str, int]] = defaultdict(lambda: {"pre_test": 0, "simulasi": 0})
    for ht in hasil_tes_records:
        tanggal = ht.diselesaikan_pada.strftime("%Y-%m-%d")
        key = "pre_test" if ht.jenis_tes is JenisTes.PRE_TEST else "simulasi"
        per_tanggal[tanggal][key] += 1

    return [
        TrenAktivitasItem(tanggal=tanggal, pre_test=v["pre_test"], simulasi=v["simulasi"])
        for tanggal, v in sorted(per_tanggal.items())
    ]


@dataclass
class _StatSekolah:
    siswa_ids: set[str] = field(default_factory=set)
    skor_simulasi: list[float] = field(default_factory=list)


def _hitung_komparasi_sekolah(session: Session) -> list[KomparasiSekolahItem]:
    """Lintas SELURUH histori (tidak difilter rentang_waktu/sekolah_id) —
    tabel komparasi antar-sekolah resolusi tiket 04 poin 1 & 2.
    """
    semua_hasil_tes = list(session.scalars(select(HasilTes)).all())

    per_sekolah: dict[str, _StatSekolah] = {}
    for ht in semua_hasil_tes:
        sekolah_key = ht.sekolah_id or "unassigned"
        stat = per_sekolah.setdefault(sekolah_key, _StatSekolah())
        if ht.siswa_id:
            stat.siswa_ids.add(ht.siswa_id)
        if ht.jenis_tes is JenisTes.SIMULASI:
            stat.skor_simulasi.append(ht.skor)

    semua_hasil_tes_ids = [ht.id for ht in semua_hasil_tes]
    eval_per_hasil_tes_id: dict[int, str] = {}
    if semua_hasil_tes_ids:
        for hasil_tes_id, hasil_evaluasi in session.execute(
            select(RiwayatEvaluasiKenaikan.hasil_tes_id, RiwayatEvaluasiKenaikan.hasil_evaluasi).where(
                RiwayatEvaluasiKenaikan.hasil_tes_id.in_(semua_hasil_tes_ids)
            )
        ).all():
            eval_per_hasil_tes_id[hasil_tes_id] = hasil_evaluasi

    hasil_tes_by_sekolah_id = {ht.id: (ht.sekolah_id or "unassigned") for ht in semua_hasil_tes}
    eval_total_per_sekolah: dict[str, int] = defaultdict(int)
    eval_lulus_per_sekolah: dict[str, int] = defaultdict(int)
    for hasil_tes_id, hasil_evaluasi in eval_per_hasil_tes_id.items():
        sekolah_key = hasil_tes_by_sekolah_id.get(hasil_tes_id, "unassigned")
        eval_total_per_sekolah[sekolah_key] += 1
        if hasil_evaluasi == "lulus":
            eval_lulus_per_sekolah[sekolah_key] += 1

    hasil = []
    for sekolah_id, stat in per_sekolah.items():
        skor_simulasi = stat.skor_simulasi
        total_simulasi = len(skor_simulasi)
        total_eval = eval_total_per_sekolah.get(sekolah_id, 0)
        total_lulus = eval_lulus_per_sekolah.get(sekolah_id, 0)
        hasil.append(
            KomparasiSekolahItem(
                sekolah_id=sekolah_id,
                total_siswa_aktif=len(stat.siswa_ids),
                total_simulasi=total_simulasi,
                rata_rata_skor=(
                    round(sum(skor_simulasi) / total_simulasi, 2) if total_simulasi > 0 else 0.0
                ),
                rasio_kelulusan_tingkat=(
                    round((total_lulus / total_eval) * 100, 2) if total_eval > 0 else 0.0
                ),
            )
        )
    return sorted(hasil, key=lambda item: item.sekolah_id)
