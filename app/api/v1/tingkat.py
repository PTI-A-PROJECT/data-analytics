from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.master import TingkatSeleksi
from app.models.kenaikan_tingkat import AksesTingkatSiswa, AturanKenaikanTingkat
from app.schemas.tingkat import (
    AksesTingkatItem,
    AksesTingkatSiswaResponse,
    OverrideAksesRequest,
    AturanKenaikanItem,
    UpdateAturanKenaikanRequest,
)
from app.services.advancement_service import inisialisasi_akses_siswa, override_akses_admin

router = APIRouter()


@router.get("/siswa/{siswa_id}/akses", response_model=AksesTingkatSiswaResponse)
def get_akses_tingkat_siswa(siswa_id: str, db: Session = Depends(get_db)):
    """Mengambil status hak akses seluruh tingkat seleksi untuk seorang siswa (Tiket 03)."""
    inisialisasi_akses_siswa(db, siswa_id)
    akses_records = (
        db.query(AksesTingkatSiswa, TingkatSeleksi)
        .join(TingkatSeleksi, AksesTingkatSiswa.tingkat_seleksi_id == TingkatSeleksi.id)
        .filter(AksesTingkatSiswa.siswa_id == siswa_id)
        .order_by(TingkatSeleksi.urutan)
        .all()
    )

    items = []
    for aks, t in akses_records:
        items.append(
            AksesTingkatItem(
                tingkat_seleksi_id=t.id,
                kode=t.kode,
                nama=t.nama,
                status=aks.status,
                dibuka_karena=aks.dibuka_karena,
                dibuka_pada=aks.dibuka_pada,
                catatan=aks.catatan,
            )
        )

    return AksesTingkatSiswaResponse(siswa_id=siswa_id, daftar_akses=items)


@router.post("/admin/override", response_model=AksesTingkatItem)
def admin_override_akses(payload: OverrideAksesRequest, db: Session = Depends(get_db)):
    """Manual override hak akses tingkat siswa oleh Super Admin (FR-17 / Tiket 03)."""
    tingkat = db.get(TingkatSeleksi, payload.tingkat_seleksi_id)
    if not tingkat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tingkat seleksi ID {payload.tingkat_seleksi_id} tidak ditemukan",
        )

    aks = override_akses_admin(
        db=db,
        siswa_id=payload.siswa_id,
        tingkat_seleksi_id=payload.tingkat_seleksi_id,
        status=payload.status,
        catatan=payload.catatan,
    )

    return AksesTingkatItem(
        tingkat_seleksi_id=tingkat.id,
        kode=tingkat.kode,
        nama=tingkat.nama,
        status=aks.status,
        dibuka_karena=aks.dibuka_karena,
        dibuka_pada=aks.dibuka_pada,
        catatan=aks.catatan,
    )


@router.get("/admin/aturan", response_model=List[AturanKenaikanItem])
def get_semua_aturan_kenaikan(db: Session = Depends(get_db)):
    """Melihat daftar seluruh aturan kenaikan tingkat (Tiket 03)."""
    return db.query(AturanKenaikanTingkat).order_by(AturanKenaikanTingkat.id).all()


@router.put("/admin/aturan/{aturan_id}", response_model=AturanKenaikanItem)
def update_aturan_kenaikan(
    aturan_id: int,
    payload: UpdateAturanKenaikanRequest,
    db: Session = Depends(get_db),
):
    """Mengubah parameter ambang batas skor atau persentase kompetensi cukup (Tiket 03)."""
    aturan = db.get(AturanKenaikanTingkat, aturan_id)
    if not aturan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aturan kenaikan tingkat ID {aturan_id} tidak ditemukan",
        )

    if payload.skor_simulasi_min is not None:
        aturan.skor_simulasi_min = payload.skor_simulasi_min
    if payload.persentase_kompetensi_cukup_min is not None:
        aturan.persentase_kompetensi_cukup_min = payload.persentase_kompetensi_cukup_min
    if payload.aktif is not None:
        aturan.aktif = payload.aktif

    db.commit()
    db.refresh(aturan)
    return aturan
