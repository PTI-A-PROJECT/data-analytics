"""Embedder teks lokal paraphrase-multilingual-MiniLM-L12-v2 lewat ONNX
Runtime, varian int8 (fase 2 issue 01) — tanpa PyTorch, ~530 MB RAM puncak,
~30 detik untuk 1.800 soal di 2 thread CPU. Dipilih lewat
scripts/benchmark_embedding.py: kualitas makna terbaik di antara model seukuran
(mengungguli multilingual-e5-small & -base) dengan biaya sama dengan yang
terkecil.

Hanya dipakai saat ingest: runtime API tidak pernah memuat model, vector search
memakai embedding yang sudah tersimpan di pgvector.

Model dilatih dengan input <= 128 token. Teks yang lebih panjang TIDAK dipotong:
dipecah menjadi jendela 128 token yang saling tumpang-tindih, tiap jendela
di-embed, lalu dirata-rata (berbobot jumlah token) — seluruh isi soal ikut
diperhitungkan.

Butuh dependency group `ingest` (`uv sync --group ingest`). File model
(~118 MB) & tokenizer diunduh sekali ke cache Hugging Face.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from data_analytics.models import DIMENSI_EMBEDDING

REPO_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
FILE_MODEL = "onnx/model_quint8_avx2.onnx"
FILE_TOKENIZER = "tokenizer.json"
PANJANG_JENDELA = 128  # termasuk token <s> dan </s>
TUMPANG_JENDELA = 32


def potong_jendela(ids: Sequence[int], *, panjang: int, tumpang: int) -> list[list[int]]:
    """Potong id token isi menjadi jendela sepanjang <= `panjang`, tiap jendela
    berikutnya mengulang `tumpang` token terakhir jendela sebelumnya supaya
    konteks di batas jendela tidak hilang.
    """
    if not 0 <= tumpang < panjang:
        raise ValueError("tumpang harus di antara 0 dan panjang - 1")
    jendela = [list(ids[:panjang])]
    awal = panjang - tumpang
    while awal + tumpang < len(ids):
        jendela.append(list(ids[awal : awal + panjang]))
        awal += panjang - tumpang
    return jendela


class EmbedderMiniLM:
    def __init__(
        self,
        *,
        jumlah_thread: int | None = None,
        ukuran_batch: int = 32,
        jendela: bool = True,
    ) -> None:
        """jendela=False memotong teks di 128 token (perilaku bawaan model) —
        hanya untuk pembanding di benchmark; ingest selalu memakai jendela."""
        self.jendela = jendela
        # Import di sini, bukan di atas modul: onnxruntime/tokenizers/
        # huggingface_hub hanya terpasang lewat group `ingest`.
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        self.ukuran_batch = ukuran_batch
        self.tokenizer = Tokenizer.from_file(hf_hub_download(REPO_MODEL, FILE_TOKENIZER))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        id_khusus = {t: self.tokenizer.token_to_id(t) for t in ("<s>", "</s>", "<pad>")}
        if None in id_khusus.values():
            raise ValueError(f"Tokenizer {REPO_MODEL} tidak punya token khusus: {id_khusus}")
        self.id_awal: int = id_khusus["<s>"]  # type: ignore[assignment]
        self.id_akhir: int = id_khusus["</s>"]  # type: ignore[assignment]
        self.id_pad: int = id_khusus["<pad>"]  # type: ignore[assignment]

        opsi = ort.SessionOptions()
        if jumlah_thread is not None:
            opsi.intra_op_num_threads = jumlah_thread
            opsi.inter_op_num_threads = 1
        self.sesi = ort.InferenceSession(
            hf_hub_download(REPO_MODEL, FILE_MODEL),
            sess_options=opsi,
            providers=["CPUExecutionProvider"],
        )
        self.nama_input = {i.name for i in self.sesi.get_inputs()}

    def embed(self, teks: Sequence[str]) -> list[list[float]]:
        # Semua jendela dari semua teks diratakan jadi satu daftar, di-embed per
        # batch, lalu digabung kembali per teks pemiliknya.
        jendela: list[list[int]] = []
        pemilik: list[int] = []
        for indeks, isi in enumerate(self.tokenizer.encode_batch(list(teks), add_special_tokens=False)):
            daftar_potongan = potong_jendela(
                isi.ids, panjang=PANJANG_JENDELA - 2, tumpang=TUMPANG_JENDELA
            )
            for potongan in daftar_potongan if self.jendela else daftar_potongan[:1]:
                jendela.append([self.id_awal, *potongan, self.id_akhir])
                pemilik.append(indeks)

        vektor_jendela = np.concatenate(
            [
                self._embed_jendela(jendela[awal : awal + self.ukuran_batch])
                for awal in range(0, len(jendela), self.ukuran_batch)
            ]
        ) if jendela else np.zeros((0, DIMENSI_EMBEDDING))
        bobot = np.array([len(j) - 2 for j in jendela], dtype=np.float32)
        pemilik_arr = np.array(pemilik)

        hasil = []
        for indeks in range(len(teks)):
            milik = pemilik_arr == indeks
            rata = (vektor_jendela[milik] * bobot[milik, None]).sum(axis=0)
            hasil.append((rata / np.linalg.norm(rata)).tolist())
        return hasil

    def _embed_jendela(self, batch: list[list[int]]) -> np.ndarray:
        panjang = max(len(j) for j in batch)
        input_ids = np.full((len(batch), panjang), self.id_pad, dtype=np.int64)
        attention_mask = np.zeros((len(batch), panjang), dtype=np.int64)
        for baris, ids in enumerate(batch):
            input_ids[baris, : len(ids)] = ids
            attention_mask[baris, : len(ids)] = 1
        masukan = {"input_ids": input_ids, "attention_mask": attention_mask}
        if "token_type_ids" in self.nama_input:
            masukan["token_type_ids"] = np.zeros_like(input_ids)

        token = self.sesi.run(None, masukan)[0]  # (batch, token, dimensi)
        # Mean pooling atas token non-padding lalu normalisasi L2 — pooling
        # resmi model ini (cosine = dot product).
        mask = attention_mask[:, :, None].astype(np.float32)
        rata = (token * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
        vektor: np.ndarray = rata / np.linalg.norm(rata, axis=1, keepdims=True)
        if vektor.shape[1] != DIMENSI_EMBEDDING:
            raise ValueError(
                f"Embedding berdimensi {vektor.shape[1]}, kolom vector berdimensi {DIMENSI_EMBEDDING}"
            )
        return vektor
