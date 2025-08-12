# app.py
import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import datetime
import os
from fpdf import FPDF
import io

# ---------------------------
# Konfigurasi dasar
# ---------------------------
st.set_page_config(page_title="Aplikasi Deteksi Status Gizi Anak", layout="wide")
st.title("🌱 Aplikasi Deteksi Status Gizi Anak (Edukasi — Bukan Diagnosis)")

# ---------------------------
# Utility: umur
# ---------------------------
def hitung_umur(tgl_lahir: datetime.date):
    today = datetime.date.today()
    delta = today - tgl_lahir
    tahun = delta.days // 365
    sisa = delta.days % 365
    bulan = sisa // 30
    hari = sisa % 30
    umur_bulan = tahun * 12 + bulan
    return tahun, bulan, hari, umur_bulan

# ---------------------------
# Utility: load LMS (0-5 & 5-19)
# - Letakkan file LMS di folder `data/`
#   * who_0_5.xlsx  (kolom Month atau UmurBulan, Sex, L, M, S)
#   * who_5_19.xlsx (kolom AgeYear atau Month/UmurBulan, Sex, L, M, S)
# ---------------------------
def load_who_lms(path):
    if not os.path.exists(path):
        st.error(f"File standar WHO tidak ditemukan: {path}")
        return None
    df = pd.read_excel(path)
    # standardize column names
    if 'Month' in df.columns:
        df = df.rename(columns={'Month':'UmurBulan'})
    if 'AgeYear' in df.columns:
        # keep AgeYear if present; also allow Month
        pass
    return df

# ---------------------------
# Utility: cari / interpolasi L M S
# - df harus berisi kolom: UmurBulan (int) atau AgeYear (int), Sex, L, M, S
# - kita dukung dua mode: index berdasarkan 'UmurBulan' (bulan) atau 'AgeYear' (tahun)
# ---------------------------
def find_lms_for_age(df, sex_code, umur_bulan):
    """
    df: DataFrame LMS
    sex_code: 'M' atau 'F'
    umur_bulan: int
    return: (L,M,S) atau None
    """
    # prefer UmurBulan kalau ada
    if 'UmurBulan' in df.columns:
        col = 'UmurBulan'
        # ambil subset sex
        sub = df[df['Sex'] == sex_code].copy()
        sub[col] = sub[col].astype(int)
        sub = sub.sort_values(col)
        # exact match
        exact = sub[sub[col] == int(umur_bulan)]
        if not exact.empty:
            row = exact.iloc[0]
            return float(row['L']), float(row['M']), float(row['S'])
        # interpolation
        lower = sub[sub[col] < umur_bulan]
        upper = sub[sub[col] > umur_bulan]
        if lower.empty or upper.empty:
            return None
        low = lower.iloc[-1]
        up = upper.iloc[0]
        # linear interpolation for L, M, S
        t0, t1 = int(low[col]), int(up[col])
        w = (umur_bulan - t0) / (t1 - t0)
        L = low['L'] + w * (up['L'] - low['L'])
        M = low['M'] + w * (up['M'] - low['M'])
        S = low['S'] + w * (up['S'] - low['S'])
        return float(L), float(M), float(S)
    elif 'AgeYear' in df.columns:
        # convert umur_bulan to AgeYear by rounding to nearest year
        umur_tahun = round(umur_bulan / 12)
        sub = df[df['Sex'] == sex_code].copy()
        sub['AgeYear'] = sub['AgeYear'].astype(int)
        sub = sub.sort_values('AgeYear')
        exact = sub[sub['AgeYear'] == int(umur_tahun)]
        if not exact.empty:
            row = exact.iloc[0]
            return float(row['L']), float(row['M']), float(row['S'])
        # interpolation on year
        lower = sub[sub['AgeYear'] < umur_tahun]
        upper = sub[sub['AgeYear'] > umur_tahun]
        if lower.empty or upper.empty:
            return None
        low = lower.iloc[-1]
        up = upper.iloc[0]
        t0, t1 = int(low['AgeYear']), int(up['AgeYear'])
        w = (umur_tahun - t0) / (t1 - t0)
        L = low['L'] + w * (up['L'] - low['L'])
        M = low['M'] + w * (up['M'] - low['M'])
        S = low['S'] + w * (up['S'] - low['S'])
        return float(L), float(M), float(S)
    else:
        return None

# ---------------------------
# LMS z-score dengan handling L==0
# ---------------------------
def lms_zscore(value_cm, L, M, S):
    try:
        L = float(L); M = float(M); S = float(S)
        if M <= 0 or S == 0:
            return None
        if abs(L) < 1e-9:
            z = np.log(value_cm / M) / S
        else:
            z = ((value_cm / M) ** L - 1) / (L * S)
        return float(z)
    except Exception:
        return None

# ---------------------------
# Klasifikasi WHO (HFA) + pesan edukasi
# ---------------------------
def klasifikasi_hfa(z):
    if z is None:
        return "Data tidak tersedia", "#808080", "Tidak dapat menghitung z-score."
    if z < -3:
        return "Stunting Berat (< -3 SD)", "#8B0000", "Segera konsultasikan ke tenaga kesehatan untuk evaluasi."
    elif z < -2:
        return "Stunting (-3 sampai < -2 SD)", "#FF0000", "Perlu pemantauan & intervensi gizi; kunjungi puskesmas/posyandu."
    elif z <= 3:
        return "Normal (-2 sampai +3 SD)", "#2E8B57", "Pertahankan pola makan sehat, imunisasi, dan pemantauan tumbuh kembang."
    else:
        return "Tinggi di atas normal (> +3 SD)", "#1E90FF", "Tinggi di atas rata-rata; bila perlu observasi lebih lanjut."

# ---------------------------
# Avatar mapping
# ---------------------------
AVATAR_KEYMAP = {
    "Stunting Berat (< -3 SD)": "stunting_berat",
    "Stunting (-3 sampai < -2 SD)": "stunting",
    "Normal (-2 sampai +3 SD)": "normal",
    "Tinggi di atas normal (> +3 SD)": "tinggi",
    "Data tidak tersedia": "default"
}

def get_avatar(label, gender):
    key = AVATAR_KEYMAP.get(label, "default")
    gender_short = 'boy' if gender == 'Laki-laki' else 'girl'
    path = os.path.join('avatars', f"{key}_{gender_short}.png")
    if os.path.exists(path):
        return path
    # fallback
    fallback = os.path.join('avatars', f"default_{gender_short}.png")
    if os.path.exists(fallback):
        return fallback
    return None

# ---------------------------
# PDF helper (FPDF) -> return BytesIO
# ---------------------------
def buat_pdf(data_dict):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Laporan Hasil Pengukuran Status Gizi (Edukasi)", ln=True, align='C')
    pdf.ln(6)
    pdf.set_font("Arial", size=11)
    for k, v in data_dict.items():
        pdf.multi_cell(0, 8, f"{k}: {v}")
    pdf.ln(4)
    pdf.set_font("Arial", 'I', 9)
    pdf.multi_cell(0, 6, "Catatan: Hasil bersifat edukasi dan bukan diagnosis medis. Untuk pemeriksaan klinis, kunjungi fasilitas kesehatan.")
    bio = io.BytesIO()
    pdf.output(bio)
    bio.seek(0)
    return bio

# ---------------------------
# Inisialisasi session_state (DataFrame)
# ---------------------------
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=[
        'Timestamp','Nama','TanggalLahir','JenisKelamin','Kelas','UmurTahun','UmurBulanTotal','Tinggi_cm','Berat_kg','Zscore','Persentil','Status'
    ])

# ---------------------------
# Sidebar & Navigation
# ---------------------------
st.sidebar.title("Navigasi")
page = st.sidebar.radio("Pilih Halaman", [
    "Home",
    "Deteksi 0-5 Tahun",
    "Deteksi 5-19 Tahun",
    "Prediksi Tinggi Anak",
    "Data & Ekspor",
    "Tutorial Pengukuran",
    "Disclaimer"
])

# ---------------------------
# Home
# ---------------------------
if page == "Home":
    st.header("Selamat datang 🌿")
    st.markdown("""
    Aplikasi ini menghitung **Z-score Height-for-Age (HFA)** menggunakan parameter LMS WHO (jika file tersedia).
    Hasil bersifat **edukasi** dan **bukan diagnosis**. Untuk masalah klinis, kunjungi fasilitas kesehatan.
    """)
    st.info("Pastikan file WHO LMS tersedia di folder `data/` dan avatar di folder `avatars/`.")

# ---------------------------
# Deteksi 0-5 Tahun (WHO Child Growth Standards)
# - expects a file like 'who_0_5.xlsx' with 'UmurBulan','Sex','L','M','S'
# ---------------------------
elif page == "Deteksi 0-5 Tahun":
    st.header("👶 Deteksi Usia 0-5 Tahun (WHO Child Growth Standards)")
    with st.form("form_0_5"):
        nama = st.text_input("Nama Anak")
        ttl = st.date_input("Tanggal Lahir", max_value=datetime.date.today())
        jenis_kelamin = st.selectbox("Jenis Kelamin", ["Laki-laki","Perempuan"])
        kelas = st.text_input("Kelas (opsional)")
        tinggi = st.number_input("Tinggi (cm)", min_value=30.0, max_value=120.0, step=0.1)
        berat = st.number_input("Berat (kg)", min_value=1.0, max_value=50.0, step=0.1)
        submitted = st.form_submit_button("Proses Deteksi")
    if submitted:
        if not nama:
            st.warning("Isi nama anak dahulu.")
        else:
            tahun, bulan, hari, umur_bulan = hitung_umur(ttl)
            st.write(f"Usia: **{tahun} tahun {bulan} bulan {hari} hari** — total **{umur_bulan} bulan**")
            # load file WHO 0-5 (adjust path sesuai file mu)
            path0_5 = "data/who_0_5.xlsx"  # ubah sesuai file
            df_lms = load_who_lms(path0_5)
            if df_lms is None:
                st.error("File WHO 0-5 tidak tersedia atau format salah.")
            else:
                # filter sex: expect Sex values like 'M'/'F' or 'Male'/'Female'
                # normalize Sex column to 'M'/'F'
                if 'Sex' not in df_lms.columns:
                    st.error("Kolom 'Sex' tidak ditemukan di file WHO 0-5.")
                else:
                    # normalize Sex values
                    df_lms['Sex'] = df_lms['Sex'].astype(str).str.upper().map(lambda x: 'M' if x.startswith('M') else ('F' if x.startswith('F') else x))
                    sex_code = 'M' if jenis_kelamin == 'Laki-laki' else 'F'
                    lms = find_lms_for_age(df_lms, sex_code, umur_bulan)
                    if lms is None:
                        st.warning("Umur (bulan) tidak tersedia di tabel LMS (dan tidak bisa diinterpolasi).")
                    else:
                        L, M, S = lms
                        z = lms_zscore(tinggi, L, M, S)
                        if z is None:
                            st.error("Gagal menghitung z-score.")
                        else:
                            z_disp = round(z, 2)
                            pers = norm.cdf(z) * 100
                            pers_disp = round(pers, 1)
                            label, warna, tips = klasifikasi_hfa(z)
                            st.markdown(f"**Z-score (HFA):** {z_disp}")
                            st.markdown(f"**Persentil dunia (aproksimasi):** {pers_disp} %")
                            st.markdown(f"<div style='background:{warna}; padding:10px; border-radius:8px; color:white;'><b>{label}</b><br/>{tips}</div>", unsafe_allow_html=True)
                            avatar = get_avatar(label, jenis_kelamin)
                            if avatar:
                                st.image(avatar, width=220)
                            # simpan
                            now = datetime.datetime.now()
                            new_row = {
                                'Timestamp': now,
                                'Nama': nama,
                                'TanggalLahir': ttl.strftime("%Y-%m-%d"),
                                'JenisKelamin': jenis_kelamin,
                                'Kelas': kelas,
                                'UmurTahun': tahun,
                                'UmurBulanTotal': umur_bulan,
                                'Tinggi_cm': tinggi,
                                'Berat_kg': berat,
                                'Zscore': z_disp,
                                'Persentil': pers_disp,
                                'Status': label
                            }
                            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                            # PDF
                            pdf_buf = buat_pdf(new_row)
                            st.download_button("📄 Download PDF Ringkasan", data=pdf_buf, file_name=f"Hasil_{nama.replace(' ','_')}.pdf", mime="application/pdf")

# ---------------------------
# Deteksi 5-19 Tahun (WHO Growth Reference)
# - expects a file like 'who_5_19.xlsx' with AgeYear or UmurBulan, Sex, L, M, S
# ---------------------------
elif page == "Deteksi 5-19 Tahun":
    st.header("🧒 Deteksi Usia 5-19 Tahun (WHO Growth Reference)")
    with st.form("form_5_19"):
        nama = st.text_input("Nama Anak")
        ttl = st.date_input("Tanggal Lahir", max_value=datetime.date.today())
        jenis_kelamin = st.selectbox("Jenis Kelamin", ["Laki-laki","Perempuan"])
        kelas = st.text_input("Kelas (opsional)")
        tinggi = st.number_input("Tinggi (cm)", min_value=80.0, max_value=220.0, step=0.1)
        berat = st.number_input("Berat (kg)", min_value=10.0, max_value=200.0, step=0.1)
        submitted = st.form_submit_button("Proses Deteksi")
    if submitted:
        if not nama:
            st.warning("Isi nama anak dahulu.")
        else:
            tahun, bulan, hari, umur_bulan = hitung_umur(ttl)
            st.write(f"Usia: **{tahun} tahun {bulan} bulan {hari} hari** — total **{umur_bulan} bulan**")
            path5_19 = "data/who_5_19.xlsx"  # ubah sesuai file
            df_lms = load_who_lms(path5_19)
            if df_lms is None:
                st.error("File WHO 5-19 tidak tersedia atau format salah.")
            else:
                if 'Sex' not in df_lms.columns:
                    st.error("Kolom 'Sex' tidak ditemukan di file WHO 5-19.")
                else:
                    df_lms['Sex'] = df_lms['Sex'].astype(str).str.upper().map(lambda x: 'M' if x.startswith('M') else ('F' if x.startswith('F') else x))
                    sex_code = 'M' if jenis_kelamin == 'Laki-laki' else 'F'
                    lms = find_lms_for_age(df_lms, sex_code, umur_bulan)
                    if lms is None:
                        st.warning("Umur tidak tersedia di tabel LMS (dan tidak bisa diinterpolasi).")
                    else:
                        L, M, S = lms
                        z = lms_zscore(tinggi, L, M, S)
                        if z is None:
                            st.error("Gagal menghitung z-score.")
                        else:
                            z_disp = round(z, 2)
                            pers = norm.cdf(z) * 100
                            pers_disp = round(pers, 1)
                            label, warna, tips = klasifikasi_hfa(z)
                            st.markdown(f"**Z-score (HFA):** {z_disp}")
                            st.markdown(f"**Persentil dunia (aproksimasi):** {pers_disp} %")
                            st.markdown(f"<div style='background:{warna}; padding:10px; border-radius:8px; color:white;'><b>{label}</b><br/>{tips}</div>", unsafe_allow_html=True)
                            avatar = get_avatar(label, jenis_kelamin)
                            if avatar:
                                st.image(avatar, width=220)
                            # simpan
                            now = datetime.datetime.now()
                            new_row = {
                                'Timestamp': now,
                                'Nama': nama,
                                'TanggalLahir': ttl.strftime("%Y-%m-%d"),
                                'JenisKelamin': jenis_kelamin,
                                'Kelas': kelas,
                                'UmurTahun': tahun,
                                'UmurBulanTotal': umur_bulan,
                                'Tinggi_cm': tinggi,
                                'Berat_kg': berat,
                                'Zscore': z_disp,
                                'Persentil': pers_disp,
                                'Status': label
                            }
                            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                            pdf_buf = buat_pdf(new_row)
                            st.download_button("📄 Download PDF Ringkasan", data=pdf_buf, file_name=f"Hasil_{nama.replace(' ','_')}.pdf", mime="application/pdf")

# ---------------------------
# Prediksi Tinggi Anak (mid-parental)
# ---------------------------
elif page == "Prediksi Tinggi Anak":
    st.header("📐 Kalkulator Prediksi Tinggi (Mid-parental)")
    ayah = st.number_input("Tinggi Ayah (cm)", min_value=100.0, max_value=250.0, value=170.0)
    ibu = st.number_input("Tinggi Ibu (cm)", min_value=100.0, max_value=250.0, value=160.0)
    jk = st.selectbox("Jenis Kelamin Anak", ["Laki-laki","Perempuan"])
    if st.button("Hitung Prediksi"):
        if jk == "Laki-laki":
            pred = (ayah + ibu + 13) / 2
        else:
            pred = (ayah + ibu - 13) / 2
        st.success(f"Prediksi tinggi dewasa (rata-rata): {pred:.1f} cm")
        st.info(f"Perkiraan rentang (±5 cm): {pred-5:.1f} - {pred+5:.1f} cm")

# ---------------------------
# Data & Ekspor
# ---------------------------
elif page == "Data & Ekspor":
    st.header("📂 Data Pengukuran & Ekspor")
    df = st.session_state.df.copy()
    if df.empty:
        st.info("Belum ada data pada sesi ini.")
    else:
        st.dataframe(df, use_container_width=True)
        # CSV
        csv_buf = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", data=csv_buf, file_name="data_pengukuran.csv", mime="text/csv")
        # Excel
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='data', index=False)
            writer.save()
        excel_buf.seek(0)
        st.download_button("📥 Download Excel", data=excel_buf, file_name="data_pengukuran.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        # Visualisasi sederhana
        st.subheader("Visualisasi: Z-score vs Umur (bulan)")
        try:
            fig = None
            chart_df = df.dropna(subset=['UmurBulanTotal','Zscore'])
            if not chart_df.empty:
                chart_df = chart_df.sort_values('UmurBulanTotal')
                st.line_chart(chart_df.set_index('UmurBulanTotal')['Zscore'])
        except Exception:
            st.info("Tidak cukup data untuk visualisasi.")

# ---------------------------
# Tutorial Pengukuran
# ---------------------------
elif page == "Tutorial Pengukuran":
    st.header("📏 Tutorial Mengukur Tinggi Badan Anak yang Benar")
    st.markdown("""
    1. Anak berdiri tegak tanpa sepatu, tumit menempel.
    2. Kepala dalam posisi normal (Frankfurt plane).
    3. Gunakan stadiometer atau alat ukur yang terkalibrasi.
    4. Untuk anak <2 tahun biasanya diukur berbaring (length) — pastikan memakai standar yang sesuai.
    5. Catat pengukuran secara hati-hati (satuan cm).
    """)

# ---------------------------
# Disclaimer
# ---------------------------
elif page == "Disclaimer":
    st.header("📜 Disclaimer & Latar Belakang")
    st.markdown("""
    - Aplikasi ini menggunakan **parameter LMS WHO** untuk menghitung z-score Height-for-Age (HFA).
    - Hasil ini **bukan diagnosis medis**, hanya informasi edukasi.
    - Pastikan file LMS WHO benar dan up-to-date di folder `data/`.
    - Untuk perbaikan fitur: interpolasi L/M/S dilakukan linear jika umur (bulan) tidak persis ada pada tabel.
    """)

# ---------------------------
# Footer: ringkasan di sidebar
# ---------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("Ringkasan sesi")
st.sidebar.write(f"Total pengukuran sesi ini: {len(st.session_state.df)}")
