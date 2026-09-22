from pydantic import BaseModel, Field
from typing import List, Optional


class SubmitJawabanItem(BaseModel):
    soal_id: int
    jawaban_dipilih: str
    durasi_detik: int = Field(ge=0, description="Durasi pengerjaan butir soal dalam detik (Tiket 05)")


class SubmitTesRequest(BaseModel):
    siswa_id: str
    sekolah_id: Optional[str] = None
    tingkat_seleksi_id: int
    jenis_tes: str = Field(description="'pre_test' atau 'simulasi'")
    simulasi_id: Optional[int] = None
    jawaban: List[SubmitJawabanItem]


class SubkompetensiMapItem(BaseModel):
    subkompetensi_id: int
    nama_subkompetensi: str
    status: str  # 'Cukup', 'Belum Cukup', 'Belum Teruji'
    jumlah_soal: int
    jumlah_benar: int
    total_jawaban_benar: int
    total_benar_lambat: int
    butuh_optimasi: bool = Field(description="True jika status Cukup dan >= 50% jawaban benar tergolong lambat (Tiket 05)")


class KompetensiMapItem(BaseModel):
    kompetensi_id: int
    nama_kompetensi: str
    status: str  # 'Cukup', 'Belum Cukup', 'Belum Teruji'
    subkompetensi: List[SubkompetensiMapItem]


class KenaikanTingkatDetail(BaseModel):
    evaluasi_dilakukan: bool
    hasil_evaluasi: Optional[str] = None  # 'lulus', 'tidak_lulus'
    skor_aktual: Optional[float] = None
    skor_target: Optional[float] = None
    syarat_skor_lulus: Optional[bool] = None
    persentase_cukup_aktual: Optional[float] = None
    persentase_cukup_target: Optional[float] = None
    syarat_kompetensi_lulus: Optional[bool] = None
    tingkat_berikutnya_terbuka: Optional[str] = None


class SubmitTesResponse(BaseModel):
    hasil_tes_id: int
    siswa_id: str
    tingkat_seleksi_id: int
    jenis_tes: str
    skor: float
    predikat_label: str
    total_soal: int
    jumlah_benar: int
    jumlah_salah: int
    peta_kompetensi: List[KompetensiMapItem]
    kenaikan_tingkat: Optional[KenaikanTingkatDetail] = None
