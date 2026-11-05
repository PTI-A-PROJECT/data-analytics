# DESIGN.md — SIAP OSN Design System & Tokens
> Standard Interface Guidelines (Apple Design System & Anti-Slop Principles)
> Modul: User Analytics & Conversion Funnel (FR-01 Registrasi Siswa & FR-24 Dashboard Super Admin)

---

## 1. Design Philosophy

Antarmuka SIAP OSN mengadopsi prinsip desain **Apple Human Interface Guidelines (WWDC Fluid Interfaces)** dan **Anti-Slop Restraint**:
- **Intentional Restraint**: Menghilangkan gradien ungu-kebiruan murahan (generic AI slop), glow orbs dekoratif, dan animasi loop tanpa henti. Setiap piksel memiliki tujuan fungsional.
- **Translucent Materials & Depth**: Menggunakan *frosted glass* (`backdrop-filter: blur(20px) saturate(180%)`) pada bilah navigasi atas dan lapisan batas rambut (*hairline border* `rgba(255, 255, 255, 0.08)` / `rgba(0, 0, 0, 0.08)`).
- **Tactile Physical Feedback**: Respons klik langsung pada *pointer-down* dengan reduksi skala pegas halus (`transform: scale(0.97)`).
- **True Adaptive Canvas**: Mendukung Apple Dark Mode (Studio Obsidian `#000000` & `#161617`) dan Apple Light Mode (Museum Parchment `#f5f5f7` & `#ffffff`) melalui tombol alih instan.

---

## 2. Color Tokens

### A. Dark Mode (`data-theme="dark"`)
| Token | Nilai Hex / RGBA | Peruntukan Fungsional |
|---|---|---|
| `--canvas` | `#000000` | Latar belakang kanvas dasar (True Void Black) |
| `--surface` | `#161617` | Kartu metrik KPI, kontainer visualisasi corong |
| `--surface-secondary` | `#1f1f21` | Kartu skenario simulasi & item log telemetri |
| `--surface-tertiary` | `#272729` | Kotak input form, segmented control track |
| `--border` | `rgba(255, 255, 255, 0.08)` | Garis batas struktural kartu dan tabel |
| `--primary` | `#2997ff` | Sky Link Blue (Aksi utama pada kanvas gelap) |
| `--emerald` | `#30d158` | Indikator sukses validasi & konversi akun |
| `--rose` | `#ff453a` | Indikator drop-off corong & pesan kesalahan |
| `--amber` | `#ff9f0a` | Status menunggu interaksi / form abandonment |

### B. Light Mode (`data-theme="light"`)
| Token | Nilai Hex / RGBA | Peruntukan Fungsional |
|---|---|---|
| `--canvas` | `#f5f5f7` | Latar kanvas utama (Apple Signature Parchment) |
| `--surface` | `#ffffff` | Kartu putih bersih dengan bayangan lembut |
| `--surface-secondary` | `#fbfbfd` | Kontainer sekunder |
| `--surface-tertiary` | `#ececee` | Track kontrol tersegmentasi & input form |
| `--border` | `rgba(0, 0, 0, 0.08)` | Garis batas struktural |
| `--primary` | `#0071e3` | Apple Action Blue fungsional |
| `--emerald` | `#34c759` | Status konversi berhasil |
| `--rose` | `#ff3b30` | Status drop-off & peringatan gagal |
| `--amber` | `#ff9500` | Status jeda / evaluasi form |

---

## 3. Typography Hierarchy

Menggunakan sistem font asli platform (*Native System Font Stack*):
`-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Inter, sans-serif`

| Tingkatan Teks | Ukuran & Bobot | Tracking (Letter Spacing) | Kegunaan |
|---|---|---|---|
| **Display KPI** | `34px` / `600` | `-0.025em` | Angka metrik utama (Pengunjung, Akun, Nilai Konversi) |
| **Title Headings** | `17px` / `600` | `-0.015em` | Judul kartu analisis dan formulir |
| **Body Standard** | `14px` / `400` | `-0.010em` | Deskripsi, teks tabel, instruksi formulir |
| **Captions / Meta** | `11px` / `600` | `+0.050em` (Uppercase) | Label kolom tabel dan metadata kualitatif |
| **Telemetry Mono** | `12px` / `400` | `0` | Kode identitas `anonymous_id` & `session_id` |

---

## 4. Components & Layout Specs

1. **Top Navigation (`header`)**:
   - Pinned sticky setinggi 56px dengan *translucent backdrop blur* (`blur(20px) saturate(180%)`).
   - Kontrol tersegmentasi (*Segmented Control*) berpindah mulus antara *Dashboard Super Admin (FR-24)* dan *Simulasi Registrasi Siswa (FR-01)*.
   - Tombol alih tema instan (vektor SVG Matahari & Bulan, tanpa emoji dekoratif).
2. **Apple Tactile Funnel Track (`.bar-track` & `.bar-fill`)**:
   - Bentuk kapsul penuh (`border-radius: 9999px`) dengan ketinggian 32px.
   - Pengisian proporsional dengan kurva pegas `cubic-bezier(0.16, 1, 0.3, 1)`.
   - Menampilkan jumlah pengguna unik dan persentase terhadap titik masuk secara terpusat dan terbaca jelas.
3. **Pill Badges (`.pill`)**:
   - Menggunakan warna aksen semantik berbobot transparansi 10-14% (`tint`) dan batas halus 20% alpha.
   - Menghindari gradien neon yang menyilaukan mata.
4. **Input & Form Fields**:
   - Ketinggian nyaman 44px dengan radius sudut 12px (`--radius-md`).
   - Cincin fokus Apple (*focus ring* `box-shadow: 0 0 0 3px var(--focus-ring)`).
   - Penanganan respons langsung pada submit dengan notifikasi kesalahan bertipe spesifik (`duplicate_email`, `validation_failed`).
