# Aturan Kalkulasi Konversi, Jendela Waktu & Atribusi Drop-Off

Type: grilling
Status: resolved
Blocked by: none

## Question

Agar angka konversi di website akurat dan tidak bias:
1. **Unit Perhitungan**: Apakah funnel dihitung berbasis **Pengunjung Unik (`DISTINCT anonymous_id`)** atau berbasis **Sesi (`DISTINCT session_id`)**?
2. **Ketertiban Urutan (Strict vs Loose Funnel)**: Apakah seorang `anonymous_id` hanya dihitung mencapai Tahap $N$ jika ia sudah tercatat di Tahap $1 \dots (N-1)$ (monotonic/ordered funnel), sehingga persentase konversi tidak pernah melebihi 100%?
3. **Jendela Waktu & Filter Periode**: Bagaimana filter `rentang_waktu` (`7d`, `30d`, `90d`, `all`) bekerja pada perhitungan jumlah pengunjung tiap tahap dan **Time-to-Convert** (durasi dari `page_visit` pertama ke `account_created`)?
4. **Atribusi Drop-off Tahap 3 -> Tahap 4**: Bagaimana membedakan pengguna yang *Abandon Form* (mulai mengetik di Tahap 3 tetapi tidak pernah submit/tidak berhasil) vs pengguna yang terhenti karena *Validation Error* (`duplicate_email` atau `validation_failed`)?

## Resolution

Aturan perhitungan metrik Conversion Funnel dikunci sebagai berikut:

1. **Deduplikasi Berbasis Pengunjung Unik & Urutan Monotonik Ketat (Strict Monotonic Funnel)**:
   - Unit perhitungan adalah `anonymous_id` unik (`COUNT(DISTINCT anonymous_id)`).
   - Urutan tahap adalah $S_1 = \texttt{page\_visit} \rightarrow S_2 = \texttt{click\_register} \rightarrow S_3 = \texttt{start\_registration} \rightarrow S_4 = \texttt{account\_created}$.
   - Seorang `anonymous_id` memenuhi syarat dihitung pada tahap $S_k$ hanya jika ia memenuhi syarat pada tahap $S_{k-1}$ DAN memiliki minimal satu event $S_k$ dengan waktu kejadian $\text{min\_time}(S_1) \le \text{max\_time}(S_k)$ dalam periode filter yang dipilih.
   - Aturan ini menjamin jumlah pengguna selalu monoton turun atau tetap ($N_1 \ge N_2 \ge N_3 \ge N_4$), sehingga `step_conversion_rate` dan `overall_conversion_rate` selalu berada pada rentang $0\% \dots 100\%$.

2. **Rumus Konversi dan Drop-Off**:
   - **Step Conversion Rate ($S_k$)**:
     - Untuk $k = 1$: $100.0\%$ (jika $N_1 > 0$, selain itu $0.0\%$).
     - Untuk $k \in \{2, 3, 4\}$: $\text{round}\left(\frac{N_k}{N_{k-1}} \times 100, 1\right)$ (jika $N_{k-1} > 0$, selain itu $0.0\%$).
   - **Overall Conversion Rate ($S_k$)**:
     - $\text{round}\left(\frac{N_k}{N_1} \times 100, 1\right)$ (jika $N_1 > 0$, selain itu $0.0\%$).
   - **Drop-Off Antar-Tahap ($S_{k-1} \rightarrow S_k$)**:
     - $\text{drop\_off\_count} = N_{k-1} - N_k$
     - $\text{drop\_off\_rate} = \text{round}\left(\frac{N_{k-1} - N_k}{N_{k-1}} \times 100, 1\right)$

3. **Atribusi Drop-Off Tahap 3 (`start_registration`) ke Tahap 4 (`account_created`)**:
   - Bagi himpunan pengguna yang mencapai Tahap 3 tetapi tidak mencapai Tahap 4 ($D_{3\rightarrow 4} = U_3 \setminus U_4$):
     - **Failed Validation (`validation_error_users`)**: Pengguna di $D_{3\rightarrow 4}$ yang memiliki minimal satu event `registration_error`. Dirinci lebih lanjut berdasarkan `error_type`: `duplicate_email` (gagal `cekEmailTerdaftar` FR-01) dan `validation_failed` (input wajib kosong atau format salah).
     - **Form Abandonment (`form_abandonment_users`)**: Pengguna di $D_{3\rightarrow 4}$ yang tidak memiliki event `registration_error` sama sekali (meninggalkan halaman saat mengisi form sebelum menekan submit).

4. **Perhitungan Waktu Konversi (`Time-to-Convert`) & Filter Rentang Waktu**:
   - Dihitung khusus bagi pengguna yang mencapai Tahap 4 ($u \in U_4$): $\Delta t(u) = \text{min\_time}(u, \texttt{account\_created}) - \text{min\_time}(u, \texttt{page\_visit})$ dalam satuan detik.
   - Disajikan menggunakan kuantil **Median (P50)** dan **P90** (`p50_seconds`, `p90_seconds`) agar tahan terhadap outlier tab browser yang dibiarkan terbuka lama.
   - Mendukung filter `rentang_waktu` (`7d`, `30d`, `90d`, `all`; default `30d`), `device_type` (`desktop`, `mobile`, `tablet`), dan `utm_source`.
