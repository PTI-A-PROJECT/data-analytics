"""Test bukti skor berbobot: soal mudah salah, menengah+sulit benar."""
import json
import uuid
import urllib.request

BASE = "http://localhost:8000"
TOKEN = "changeme-generate-a-real-secret"
HEADERS = {"Content-Type": "application/json", "x-internal-token": TOKEN}


def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(), headers=HEADERS, method="POST"
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


# 1. Bikin paket baru
siswa_id = f"siswa-bobot-{uuid.uuid4().hex[:8]}"
print(f"Siswa ID: {siswa_id}")
paket = post("/api/v1/pretest/paket", {
    "siswa_id": siswa_id,
    "tingkat_seleksi_id": 1,
})
pid = paket["paket_id"]
print(f"Paket ID: {pid}, jumlah soal: {len(paket['soal'])}")

# 2. Cek distribusi level
from collections import Counter
level_count = Counter()
for s in paket["soal"]:
    # infer level dari soal_id (format: mat-kab-X-{level}-{n})
    parts = s["soal_id"].split("-")
    level_count[parts[3]] += 1
print(f"Distribusi: {dict(level_count)}")

# 3. Jawab: mudah SALAH, menengah+sulit BENAR
jawaban = []
for s in paket["soal"]:
    level = s["soal_id"].split("-")[3]
    if level == "mudah":
        jawaban.append({"soal_id": s["soal_id"], "jawaban_dipilih": "B"})  # salah
    else:
        jawaban.append({"soal_id": s["soal_id"], "jawaban_dipilih": "A"})  # benar

hasil = post(f"/api/v1/paket/{pid}/submit", {"jawaban": jawaban})

# 4. Hitung manual
bobot_benar = level_count["menengah"] * 2 + level_count["sulit"] * 3
bobot_total = level_count["mudah"] * 1 + level_count["menengah"] * 2 + level_count["sulit"] * 3
skor_expected = round(bobot_benar / bobot_total * 100, 2)
skor_naive = round((level_count["menengah"] + level_count["sulit"]) / sum(level_count.values()) * 100, 2)

print(f"\n=== HASIL ===")
print(f"Skor API         : {hasil['skor']}")
print(f"Skor expected    : {skor_expected}")
print(f"Skor naive       : {skor_naive}")
print(f"Beda dari naive  : {round(hasil['skor'] - skor_naive, 2)} poin")
print(f"\nPredikat: {hasil['predikat']}")
print(f"Materi lemah: {hasil['materi_lemah']}")
print(f"Review soal: {len(hasil['review_soal'])} item")

if abs(hasil["skor"] - skor_expected) < 0.01:
    print("\n✅ SKOR BERBOBOT BENAR")
else:
    print(f"\n❌ SALAH — expected {skor_expected}, dapat {hasil['skor']}")

if hasil["skor"] != skor_naive:
    print(f"✅ BUKTI BERBOBOT — beda {round(hasil['skor'] - skor_naive, 2)} poin dari naive")
else:
    print(f"❌ BELUM BERBOBOT — sama dengan naive")