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
# Fungsi bantu hitung umur
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
# Fungsi load LMS untuk 0-5 tahun (file WHO tunggal)
# ---------------------------
def load_who_0_5(path):
    if not os.path.exists(path):
        st.error(f"File LMS WHO 0-5 tahun tidak ditemukan di {path}")
        return None
    df = pd.read_excel(path)
    # Normalize kolom umur
    if 'Month' in df.columns:
        df = df.rename(columns={'Month':'UmurBulan'})
    # Pastikan kolom penting ada
    for col in ['UmurBulan','Sex','L','M','S']:
        if col not in df.columns:
            st.error(f"File LMS 0-5 tidak lengkap, tidak ada kolom '{col}'")
            return None
    return df

# ---------------------------
# Fungsi load LMS 5-19 tahun (2 file terpisah)
# ---------------------------
def load_who_5_19(path_boys, path_girls):
    if not os.path.exists(path_boys):
        st.error(f"File LMS WHO 5-19 laki-laki tidak ditemukan: {path_boys}")
        return None, None
    if not os.path.exists(path_girls):
        st.error(f"File LMS WHO 5-19 perempuan tidak ditemukan: {path_girls}")
        return None, None
    df_boys = pd.read_excel(path_boys)
    df_girls = pd.read_excel(path_girls)

    # Normalize kolom 'Month' jadi 'UmurBulan'
    for df in [df_boys, df_girls]:
        if 'Month' in df.columns:
            df.rename(columns={'Month':'UmurBulan'}, inplace=True)
        # Pastikan kolom L,M,S ada
        for col in ['UmurBulan','L','M','S']:
            if col not in df.columns:
                st.error(f"File LMS 5-19 tidak lengkap, kolom '{col}' hilang")
                return None, None
        df['UmurBulan'] = df['UmurBulan'].astype(int)
        df.sort_values('UmurBulan', inplace=True)

    return df_boys.reset_index(drop=True), df_girls.reset_index(drop=True)

# ---------------------------
# Cari/interpolasi LMS 0-5 tahun (berdasarkan umur_bulan dan sex 'M'/'F')
# ---------------------------
def find_lms_0_5(df, sex_code, umur_bulan):
    sub = df[df['Sex'].str.upper() == sex_code].copy()
    sub = sub.sort_values('UmurBulan')
    # Exact match
    exact = sub[sub['UmurBulan'] == umur_bulan]
    if not exact.empty:
        row = exact.iloc[0]
        return float(row['L']), float(row['M']), float(row['S'])
    # Interpolasi linear
    lower = sub[sub['UmurBulan'] < umur_bulan]
    upper = sub[sub['UmurBulan'] > umur_bulan]
    if lower.empty or upper.empty:
        return None
    low = lower.iloc[-1]
    up = upper.iloc[0]
    t0, t1 = int(low['UmurBulan']), int(up['UmurBulan'])
    w = (umur_bulan - t0) / (t1 - t0)
    L = low['L'] + w * (up['L'] - low['L'])
    M = low['M'] + w * (up['M'] - low['M'])
    S = low['S'] + w * (up['S'] - low['S'])
    return float(L), float(M), float(S)

# ---------------------------
# Cari/interpolasi LMS 5-19 tahun (dari file terpisah laki dan perempuan)
# ---------------------------
def find_lms_5_19(umur_bulan, gender, df_boys, df_girls):
    # gender: "Laki-laki" / "Perempuan"
    df = df_boys if gender == "Laki-laki" else df_girls
    sub = df
    # cari umur_bulan persis
    exact = sub[sub['UmurBulan'] == umur_bulan]
    if not exact.empty:
        row = exact.iloc[0]
        return float(row['L']), float(row['M']), float(row['S'])
    # interpolasi linear
    lower = sub[sub['UmurBulan'] < umur_bulan]
    upper = sub[sub['UmurBulan'] > umur_bulan]
    if lower.empty or upper.empty:
        return None
    low = lower.iloc[-1]
    up = upper.iloc[0]
    t0, t1 = int(low['UmurBulan']), int(up['UmurBulan'])
    w = (umur_bulan - t0) / (t1 - t0)
    L = low['L'] + w * (up['L'] - low['L'])
    M = low['M'] + w * (up['M'] - low['M'])
    S = low['S'] + w * (up['S'] - low['S'])
    return float(L), float(M), float(S)

# ---------------------------
# Hitung z-score LMS
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
    except:
        return None

# ---------------------------
# Klasifikasi WHO Height-for-Age (HFA) + pesan edukasi
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
# Avatar mapping (folder avatars)
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
    fallback = os.path.join('avatars', f"default_{gender_short}.png")
    if os.path.exists(fallback):
        return fallback
    return None

# ---------------------------
# PDF helper (FPDF)
# ---------------------------
def buat_pdf(data_dict):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Laporan Hasil Pengukuran Status Gizi (Edukasi)", ln=True, align='C')
    pdf.ln(6)
    pdf.set_font("Arial", size=11)
    for k,v in data_dict.items():
        pdf.multi_cell(0, 8, f"{k}: {v}")
    pdf.ln(4)
    pdf.set_font("Arial", 'I', 9)
    pdf.multi_cell(0,6,"Catatan: Hasil bersifat edukasi dan bukan diagnosis medis. Untuk pemeriksaan klinis, kunjungi fasilitas kesehatan.")
    bio = io.BytesIO()
    pdf.output(bio)
    bio.seek(0)
    return bio

# ---------------------------
# Inisialisasi data session
# ---------------------------
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=[
        'Timestamp','Nama','TanggalLahir','JenisKelamin','Kelas',
        'UmurTahun','UmurBulanTotal','Tinggi_cm','Berat_kg','Zscore','Persentil','Status'
    ])

# ---------------------------
# Sidebar & Navigasi
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
    Aplikasi ini menghitung **Z-score Height-for-Age (HFA)** menggunakan parameter LMS WHO.
    Hasil bersifat **edukasi**, bukan diagnosis.
    Pastikan file LMS tersedia di folder `data/`, avatar di `avatars/`.
    """)

# ---------------------------
# Deteksi 0-5 Tahun
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

            path_0_5 = "data/who_0_5.xlsx"
            df_lms = load_who_0_5(path_0_5)
            if df_lms is not None:
                sex_code = 'M' if jenis_kelamin == 'Laki-laki' else 'F'
                lms = find_lms_0_5(df_lms, sex_code, umur_bulan)
                if lms is None:
                    st.warning("Umur (bulan) tidak tersedia di tabel LMS (dan tidak dapat diinterpolasi).")
                else:
                    L, M, S = lms
                    z = lms_zscore(tinggi, L, M, S)
                    if z is None:
                        st.error("Gagal menghitung z-score.")
                    else:
                        z_disp = round(z,2)
                        pers = norm.cdf(z)*100
                        pers_disp = round(pers,1)
                        label, warna, tips = klasifikasi_hfa(z)
                        st.markdown(f"**Z-score (HFA):** {z_disp}")
                        st.markdown(f"**Persentil dunia (aproksimasi):** {pers_disp} %")
                        st.markdown(f"<div style='background:{warna}; padding:10px; border-radius:8px; color:white;'><b>{label}</b><br/>{tips}</div>", unsafe_allow_html=True)
                        avatar = get_avatar(label, jenis_kelamin)
                        if avatar:
                            st.image(avatar, width=220)

                        # Simpan data
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

                        # Download PDF
                        pdf_buf = buat_pdf(new_row)
                        st.download_button("📄 Download PDF Ringkasan", data=pdf_buf, file_name=f"Hasil_{nama.replace(' ','_')}.pdf", mime="application/pdf")

# ---------------------------
# Deteksi 5-19 Tahun
# ---------------------------
elif page == "Deteksi 5-19 Tahun":
    st.header("🧒 Deteksi Usia 5-19 Tahun (WHO Growth Reference)")

    # Load LMS files sekali saja
    if 'df_boys_5_19' not in st.session_state or 'df_girls_5_19' not in st.session_state:
        path_boys = "data/hfa-boy-z.xlsx"   # Ganti sesuai file mu
        path_girls = "data/hfa-girl-z.xlsx" # Ganti sesuai file mu
        df_boys, df_girls = load_who_5_19(path_boys, path_girls)
        st.session_state.df_boys_5_19 = df_boys
        st.session_state.df_girls_5_19 = df_girls

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

            df_boys = st.session_state.df_boys_5_19
            df_girls = st.session_state.df_girls_5_19

            if df_boys is None or df_girls is None:
                st.error("File LMS WHO 5-19 tidak tersedia atau salah format.")
            else:
                lms = find_lms_5_19(umur_bulan, jenis_kelamin, df_boys, df_girls)
                if lms is None:
                    st.warning("Umur (bulan) tidak tersedia di tabel LMS 5-19 (dan tidak dapat diinterpolasi).")
                else:
                    L, M, S = lms
                    z = lms_zscore(tinggi, L, M, S)
                    if z is None:
                        st.error("Gagal menghitung z-score.")
                    else:
                        z_disp = round(z,2)
                        pers = norm.cdf(z)*100
                        pers_disp = round(pers,1)
                        label, warna, tips = klasifikasi_hfa(z)
                        st.markdown(f"**Z-score (HFA):** {z_disp}")
                        st.markdown(f"**Persentil dunia (aproksimasi):** {pers_disp} %")
                        st.markdown(f"<div style='background:{warna}; padding:10px; border-radius:8px; color:white;'><b>{label}</b><br/>{tips}</div>", unsafe_allow_html=True)
                        avatar = get_avatar(label, jenis_kelamin)
                        if avatar:
                            st.image(avatar, width=220)

                        # Simpan data
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

                        # Download PDF
                        pdf_buf = buat_pdf(new_row)
                        st.download_button("📄 Download PDF Ringkasan", data=pdf_buf, file_name=f"Hasil_{nama.replace(' ','_')}.pdf", mime="application/pdf")

# ---------------------------
# Prediksi Tinggi Anak (mid-parental height)
# ---------------------------
elif page == "Prediksi Tinggi Anak":
    st.header("📐 Kalkulator Prediksi Tinggi (Mid-parental Height)")
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

        # Download CSV
        csv_buf = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", data=csv_buf, file_name="data_pengukuran.csv", mime="text/csv")

        # Download Excel
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='data', index=False)
            writer.save()
        excel_buf.seek(0)
        st.download_button("📥 Download Excel", data=excel_buf, file_name="data_pengukuran.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Visualisasi sederhana Z-score vs UmurBulanTotal
        st.subheader("Visualisasi: Z-score vs Umur (bulan)")
        try:
            chart_df = df.dropna(subset=['UmurBulanTotal','Zscore'])
            if not chart_df.empty:
                chart_df = chart_df.sort_values('UmurBulanTotal')
                st.line_chart(chart_df.set_index('UmurBulanTotal')['Zscore'])
        except:
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
# Footer ringkasan sesi
# ---------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("Ringkasan sesi")
st.sidebar.write(f"Total pengukuran sesi ini: {len(st.session_state.df)}")
