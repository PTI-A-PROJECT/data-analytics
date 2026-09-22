from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.master import TingkatSeleksi
from app.models.kenaikan_tingkat import AksesTingkatSiswa
from app.schemas.tingkat import AksesTingkatItem, AksesTingkatSiswaResponse, OverrideAksesRequest
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
