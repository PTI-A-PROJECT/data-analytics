"""Benchmark embedder MiniLM (ONNX int8) — kualitas "memahami makna" pada soal
OSN berbahasa Indonesia dengan TF-IDF sebagai pembanding tanpa model, efek
sliding window untuk soal panjang, serta RAM & kecepatan.

Jalankan: uv run --group ingest python -m data_analytics.scripts.benchmark_embedding

Pemilihan model (2026-09-29, 12 triplet ini): MiniLM-paraphrase int8 recall@1
0.38 / MRR 0.53 vs multilingual-e5-small 0.25 / 0.43, e5-base 0.25 / 0.48,
mpnet-paraphrase 0.38 / 0.56 (2x RAM, 3x lebih lambat), TF-IDF 0.04 / 0.24.
int8 setara fp32 dengan RAM setengahnya. Ulangi dengan soal asli setelah data
masuk repo.

Kualitas diuji dengan triplet (acuan, positif, jebakan): positif bermakna sama
dengan kata berbeda; jebakan berkata mirip tapi bermakna lain.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import time
from collections import Counter

import numpy as np

# (acuan, positif: makna sama kata beda, jebakan: kata mirip makna beda)
TRIPLET: list[tuple[str, str, str]] = [
    (
        "Tentukan panjang lintasan terpendek dari kota A ke kota F pada peta jalan berbobot berikut.",
        "Berapa total jarak minimum untuk bepergian dari simpul 1 ke simpul 6 jika setiap sisi memiliki biaya?",
        "Tentukan banyaknya kota pada peta yang dapat dicapai dari kota A tanpa melewati jalan yang sama dua kali.",
    ),
    (
        "Sebuah larik berisi 1000 bilangan terurut. Berapa perbandingan maksimum yang dibutuhkan untuk menemukan sebuah nilai dengan pencarian biner?",
        "Data sebanyak seribu angka sudah diurutkan menaik. Paling banyak berapa kali kita perlu membandingkan jika setiap langkah membagi dua ruang pencarian?",
        "Sebuah larik berisi 1000 bilangan. Berapa banyak pertukaran yang dilakukan bubble sort untuk mengurutkan larik tersebut?",
    ),
    (
        "Berapa banyak cara memilih 3 orang pengurus dari 10 siswa jika urutan tidak diperhatikan?",
        "Dari sepuluh anak akan dibentuk sebuah tim beranggotakan tiga orang. Ada berapa kemungkinan susunan tim?",
        "Berapa banyak cara 10 siswa duduk berbaris jika 3 orang tertentu harus selalu bersebelahan?",
    ),
    (
        "Apa keluaran program jika fungsi rekursif f(n) mengembalikan f(n-1) + f(n-2) dengan f(0)=0 dan f(1)=1, untuk n=7?",
        "Hitung suku ke-7 barisan Fibonacci yang dimulai dari 0 dan 1.",
        "Apa keluaran program jika perulangan for dijalankan dari n=7 hingga 0 dan mencetak setiap nilai n?",
    ),
    (
        "Sebuah antrean menerapkan prinsip yang pertama masuk adalah yang pertama keluar. Elemen apa yang dikeluarkan setelah operasi berikut?",
        "Pada struktur data queue (FIFO), setelah enqueue 5, enqueue 8, lalu dequeue, nilai apa yang berada di depan?",
        "Sebuah tumpukan menerapkan prinsip yang terakhir masuk adalah yang pertama keluar. Elemen apa yang berada di atas setelah operasi berikut?",
    ),
    (
        "Pak Budi memiliki tas berkapasitas 15 kg dan beberapa barang dengan berat serta nilai berbeda. Barang mana yang dibawa agar total nilai maksimal?",
        "Diberikan wadah dengan batas muatan tertentu dan sejumlah objek berbobot dan berharga, pilih objek sehingga keuntungan terbesar tanpa melebihi batas.",
        "Pak Budi memiliki 15 kg beras dan akan membaginya ke beberapa tas dengan berat yang sama. Berapa kg beras di setiap tas?",
    ),
    (
        "Berapa sisa pembagian 2 pangkat 100 dengan 7?",
        "Tentukan nilai 2^100 mod 7.",
        "Berapa hasil pembagian 100 dengan 7 dibulatkan ke bawah?",
    ),
    (
        "Pohon biner lengkap memiliki kedalaman 4. Berapa jumlah maksimum simpul daunnya?",
        "Sebuah binary tree penuh setinggi 4 level. Paling banyak ada berapa node yang tidak memiliki anak?",
        "Pohon mangga di halaman sekolah memiliki 4 cabang dan setiap cabang memiliki 12 daun. Berapa jumlah daunnya?",
    ),
    (
        "Tentukan kesimpulan dari pernyataan: jika hujan maka jalan basah, diketahui jalan tidak basah.",
        "Dengan modus tollens, jika P mengimplikasikan Q dan Q salah, apa yang dapat disimpulkan tentang P?",
        "Jika hujan turun setiap hari selama seminggu dan jalan basah pada 5 hari, berapa persen hari jalan basah?",
    ),
    (
        "Algoritma pengurutan manakah yang membagi larik menjadi dua bagian, mengurutkan masing-masing, lalu menggabungkannya?",
        "Sebutkan metode sorting berbasis divide and conquer yang melakukan merge pada dua potongan yang sudah terurut.",
        "Algoritma manakah yang membagi dua bilangan bulat dan mengembalikan sisa baginya?",
    ),
    (
        "Berapa kompleksitas waktu dua perulangan bersarang yang masing-masing berjalan dari 1 sampai n?",
        "Jika sebuah loop berada di dalam loop lain dan keduanya beriterasi sebanyak n kali, notasi Big-O nya adalah?",
        "Berapa kali perulangan berjalan jika dimulai dari 1 sampai n dengan langkah 2?",
    ),
    (
        "Ada 5 kotak dan 6 bola. Buktikan bahwa setidaknya satu kotak berisi lebih dari satu bola.",
        "Prinsip sarang merpati: jika n+1 benda dimasukkan ke n wadah, pasti ada wadah yang memuat dua benda.",
        "Ada 5 kotak dan 6 bola berwarna merah. Berapa peluang mengambil bola merah dari kotak pertama?",
    ),
]


def korpus_throughput(jumlah: int) -> list[str]:
    """Teks sepanjang soal OSN nyata (~3 kalimat + pilihan jawaban)."""
    kalimat = [t for triplet in TRIPLET for t in triplet]
    return [
        f"{kalimat[i % len(kalimat)]} {kalimat[(i * 7 + 3) % len(kalimat)]} "
        f"Pilihan: A. {i} B. {i + 1} C. {i * 2} D. {i * 3} E. Tidak ada jawaban yang benar."
        for i in range(jumlah)
    ]


def _memori_puncak_mb() -> float:
    if sys.platform == "win32":
        import psutil

        return float(psutil.Process().memory_info().peak_wset) / 1e6
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # Linux: KB


# Pembuka cerita ~150 token yang sama untuk semua soal — meniru soal OSN
# berbasis cerita, sehingga inti pertanyaan jatuh setelah token ke-128.
PEMBUKA_CERITA = (
    "Pak Dengklek adalah seorang peternak bebek yang tinggal di sebuah desa di kaki gunung. "
    "Setiap pagi ia bangun sebelum matahari terbit, memberi makan bebek-bebeknya, lalu "
    "membersihkan kandang dan memeriksa persediaan air. Desa tempat tinggalnya dikelilingi "
    "sawah yang luas, sungai kecil yang jernih, dan jalan-jalan setapak yang menghubungkan "
    "rumah-rumah penduduk. Suatu hari, kepala desa meminta bantuan Pak Dengklek untuk "
    "menyelesaikan sebuah persoalan yang sedang dihadapi warga. Pak Dengklek yang gemar "
    "berpikir logis pun menerima tantangan itu dengan senang hati dan mencatat semua "
    "informasi penting di buku kecilnya sebelum mulai menghitung. Persoalannya adalah sebagai berikut. "
)


def ukur_sumber_daya(thread: int, jumlah_teks: int) -> dict[str, float]:
    """Dijalankan di subprocess tersendiri supaya RAM terisolasi."""
    import psutil

    from data_analytics.embedding import EmbedderMiniLM

    rss_awal = psutil.Process().memory_info().rss / 1e6
    mulai = time.perf_counter()
    embedder = EmbedderMiniLM(jumlah_thread=thread)
    waktu_muat = time.perf_counter() - mulai
    teks = korpus_throughput(jumlah_teks)
    mulai = time.perf_counter()
    embedder.embed(teks)
    waktu_embed = time.perf_counter() - mulai
    return {
        "muat_s": round(waktu_muat, 1),
        "teks_per_s": round(jumlah_teks / waktu_embed, 1),
        "ram_puncak_mb": round(_memori_puncak_mb() - rss_awal),
        "1800_soal_s": round(1800 / (jumlah_teks / waktu_embed)),
    }


def _tfidf(dokumen: list[str]) -> np.ndarray:
    token = [re.findall(r"\w+", d.lower()) for d in dokumen]
    kosakata = sorted({t for ts in token for t in ts})
    indeks = {t: i for i, t in enumerate(kosakata)}
    df = Counter(t for ts in token for t in set(ts))
    matriks = np.zeros((len(dokumen), len(kosakata)))
    for baris, ts in enumerate(token):
        for t, n in Counter(ts).items():
            matriks[baris, indeks[t]] = n * math.log((1 + len(dokumen)) / (1 + df[t]))
    return matriks / np.linalg.norm(matriks, axis=1, keepdims=True)


def skor_triplet(vektor: np.ndarray) -> tuple[int, float]:
    """(jumlah triplet benar, rata-rata selisih sim positif - sim jebakan)."""
    benar, selisih = 0, []
    for i in range(len(TRIPLET)):
        acuan, positif, jebakan = vektor[3 * i], vektor[3 * i + 1], vektor[3 * i + 2]
        beda = float(acuan @ positif - acuan @ jebakan)
        benar += beda > 0
        selisih.append(beda)
    return benar, round(float(np.mean(selisih)), 3)


def skor_pencarian(vektor: np.ndarray) -> tuple[float, float]:
    """Acuan mencari positifnya (dan sebaliknya) di antara SEMUA teks lain:
    (recall@1, MRR). Lebih mirip kegunaan nyata daripada triplet satu lawan satu."""
    sim = vektor @ vektor.T
    np.fill_diagonal(sim, -np.inf)
    peringkat = []
    for i in range(len(TRIPLET)):
        for kueri, target in ((3 * i, 3 * i + 1), (3 * i + 1, 3 * i)):
            urutan = np.argsort(-sim[kueri])
            peringkat.append(int(np.where(urutan == target)[0][0]) + 1)
    return (
        round(float(np.mean([p == 1 for p in peringkat])), 2),
        round(float(np.mean([1 / p for p in peringkat])), 2),
    )


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--ukur":
        print(json.dumps(ukur_sumber_daya(int(sys.argv[2]), int(sys.argv[3]))))
        return

    from data_analytics.embedding import EmbedderMiniLM

    teks = [t for triplet in TRIPLET for t in triplet]
    print(f"== Kualitas makna ({len(TRIPLET)} triplet sulit; pencarian di antara {len(teks)} teks) ==")
    print(f"{'metode':44} {'triplet':>8} {'selisih':>8} {'recall@1':>9} {'MRR':>5}")

    def baris(nama: str, v: np.ndarray) -> None:
        benar, selisih = skor_triplet(v)
        recall, mrr = skor_pencarian(v)
        print(f"{nama:44} {benar:>5}/{len(TRIPLET)} {selisih:>8} {recall:>9} {mrr:>5}")

    baris("TF-IDF (tanpa model)", _tfidf(teks))
    baris("MiniLM int8", np.array(EmbedderMiniLM().embed(teks)))

    panjang = [PEMBUKA_CERITA + t for t in teks]
    print("\nSoal panjang (pembuka cerita ~150 token + inti pertanyaan):")
    baris("MiniLM dipotong 128 token", np.array(EmbedderMiniLM(jendela=False).embed(panjang)))
    baris("MiniLM sliding window", np.array(EmbedderMiniLM().embed(panjang)))

    print("\n== Sumber daya (proses terpisah, 300 teks sepanjang soal) ==")
    for thread in (1, 2):
        keluaran = subprocess.run(
            [sys.executable, "-m", "data_analytics.scripts.benchmark_embedding", "--ukur", str(thread), "300"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip().splitlines()[-1]
        print(f"MiniLM int8 {thread} thread: {json.loads(keluaran)}")


if __name__ == "__main__":
    main()
