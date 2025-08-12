# File: app.py
"""
Streamlit app: Aplikasi Deteksi Status Gizi Anak (Non-Diagnosis)
Fitur:
- Home
- Deteksi untuk usia 0-5 tahun (WHO Child Growth Standards, LMS-based z-score)
  - Menampilkan z-score, status, avatar, persentil
  - Pilihan standar: Height-for-age (menggunakan LMS)
- Deteksi untuk usia 5-19 tahun (WHO Growth Reference, LMS-based z-score)
- Simpan pengukuran ke tabel (Excel download seluruh anak yang diukur)
- Download PDF per anak (ringkasan hasil)
- Visualisasi data: plot tinggi vs usia, histogram z-score
- Disclaimer, Tutorial Pengukuran, Kalkulator Prediksi Tinggi Anak

Catatan:
- Siapkan file WHO LMS CSV: who_0_5.csv dan who_5_19.csv dalam folder who_standards/
  Format CSV yang diharapkan (kolom contoh):
    Untuk 0-5 tahun: Month, Sex, L, M, S  (Month = 0..60)
    Untuk 5-19 tahun: AgeYear, Sex, L, M, S (AgeYear = integer tahun 5..19) *atau* Month (>=61)
- Siapkan folder assets/ dengan avatar:
    boy_normal.png, boy_under.png, girl_normal.png, girl_under.png

Jalankan:
    pip install -r requirements.txt
    streamlit run app.py

"""

import streamlit as st
import pandas as pd
import numpy as np
import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
import plotly.express as px
from scipy import stats

# -------------------------
# Utility functions
# -------------------------

def load_who_lms(path):
    if not os.path.exists(path):
        st.error(f"File standar WHO tidak ditemukan: {path}")
        return None
    return pd.read_csv(path)


def lms_zscore(value, L, M, S):
    """Hitung Z-score berdasarkan parameter LMS (WHO method).
    value: tinggi (cm)
    L, M, S: parameter LMS
    """
    try:
        L = float(L); M = float(M); S = float(S)
        if L == 0:
            z = np.log(value / M) / S
        else:
            z = ((value / M) ** L - 1) / (L * S)
        return float(z)
    except Exception:
        return None


def z_to_percentile(z):
    return stats.norm.cdf(z) * 100


def choose_avatar(sex_code, zscore):
    if sex_code == 'M':
        pref = 'boy'
    else:
        pref = 'girl'
    if zscore is None:
        state = 'normal'
    elif zscore < -2:
        state = 'under'
    else:
        state = 'normal'
    return os.path.join('assets', f"{pref}_{state}.png")


def buat_pdf_single(nama, ttl, usia_tahun, usia_bulan_total, kelas, jenis_kelamin_text, tinggi, zscore, persentil, status):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 820, "Laporan Hasil Pengukuran Status Gizi (Edukasi)")

    c.setFont("Helvetica", 12)
    c.drawString(50, 790, f"Nama: {nama}")
    c.drawString(50, 770, f"Tanggal Lahir: {ttl}")
    c.drawString(50, 750, f"Kelas: {kelas}")
    c.drawString(50, 730, f"Jenis Kelamin: {jenis_kelamin_text}")
    c.drawString(50, 710, f"Usia: {usia_tahun} tahun ({usia_bulan_total} bulan)")
    c.drawString(50, 690, f"Tinggi: {tinggi} cm")
    if zscore is not None:
        c.drawString(50, 670, f"Z-score (Height-for-age): {zscore:.2f}")
        c.drawString(50, 650, f"Persentil: {persentil:.1f} %")
    c.drawString(50, 630, f"Status (non-diagnosis): {status}")

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 600, "Catatan: Hasil ini bersifat edukasi dan bukan diagnosis medis. Untuk evaluasi klinis, hubungi profesional kesehatan.")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


def df_to_excel_bytes(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='data_pengukuran')
        writer.save()
    buffer.seek(0)
    return buffer


# -------------------------
# App layout
# -------------------------

st.set_page_config(page_title="Aplikasi Deteksi Status Gizi Anak", layout='wide')

# Sidebar
st.sidebar.title("📌 Menu")
menu = st.sidebar.radio("Navigasi", [
    "🏠 Home",
    "👶 Usia 0-5 Tahun",
    "🧒 Usia 5-19 Tahun",
    "📜 Disclaimer",
    "📏 Tutorial Pengukuran",
    "📐 Prediksi Tinggi Anak",
])

# Initialize session state storage for measurements
if 'measurements' not in st.session_state:
    st.session_state.measurements = pd.DataFrame(columns=[
        'Timestamp','Nama','TanggalLahir','Kelas','Sex','UsiaTahun','UsiaBulan','Tinggi_cm','Zscore','Persentil','Status'
    ])


# -------------------------
# Helpers for age
# -------------------------

def hitung_usia(ttl):
    today = datetime.date.today()
    usia_tahun = today.year - ttl.year - ((today.month, today.day) < (ttl.month, ttl.day))
    usia_bulan_total = (today.year - ttl.year) * 12 + today.month - ttl.month
    return usia_tahun, usia_bulan_total


# -------------------------
# Pages
# -------------------------

if menu == "🏠 Home":
    st.title("🌱 Aplikasi Deteksi Status Gizi Anak (Edukasi)")
    st.markdown(
        """
        Aplikasi ini menggunakan parameter LMS dari standar WHO untuk menghitung **z-score** Height-for-age.

        **Penting:** Hasil aplikasi ini hanya untuk edukasi — *bukan* diagnosis medis. Untuk penilaian klinis, hubungi tenaga kesehatan.
        """
    )
    st.info("Siapkan file WHO LMS di folder who_standards/ dan avatar di folder assets/ sebelum menjalankan aplikasi secara penuh.")


elif menu == "👶 Usia 0-5 Tahun":
    st.title("👶 Deteksi Usia 0-5 Tahun (WHO Child Growth Standards)")

    with st.form('form_0_5'):
        nama = st.text_input("Nama Anak")
        ttl = st.date_input("Tanggal Lahir")
        kelas = st.text_input("Kelas (opsional)")
        jenis_kelamin = st.selectbox("Jenis Kelamin", ["Laki-laki","Perempuan"]) 
        tinggi = st.number_input("Tinggi Badan (cm)", min_value=20.0, max_value=140.0, step=0.1)
        standar_opsi = st.selectbox("Pilih standar (Height-for-age)", ["WHO (LMS)"])
        submitted = st.form_submit_button("Proses")

    if submitted:
        if not nama:
            st.warning("Masukkan nama anak.")
        else:
            usia_tahun, usia_bulan_total = hitung_usia(ttl)
            df_who = load_who_lms('who_standards/who_0_5.csv')
            sex_code = 'M' if jenis_kelamin == 'Laki-laki' else 'F'
            zscore = None
            pers = None
            status = 'Data standar tidak tersedia pada usia tersebut.'

            if df_who is not None:
                # cari row berdasarkan usia bulan dan sex
                row = df_who[(df_who['Month'] == usia_bulan_total) & (df_who['Sex'] == sex_code)]
                if not row.empty:
                    L = row['L'].values[0]
                    M = row['M'].values[0]
                    S = row['S'].values[0]
                    zscore = lms_zscore(tinggi, L, M, S)
                    if zscore is not None:
                        pers = z_to_percentile(zscore)
                        if zscore < -3:
                            status = 'Sangat pendek (< -3 SD) — risiko stunting tinggi'
                        elif zscore < -2:
                            status = 'Pendek (< -2 SD) — indikasi risiko stunting'
                        else:
                            status = 'Tinggi normal (>= -2 SD)'

            avatar_path = choose_avatar(sex_code, zscore)
            col1, col2 = st.columns([1,2])
            with col1:
                if os.path.exists(avatar_path):
                    st.image(avatar_path, width=180)
                st.write(f"**Nama:** {nama}")
                st.write(f"**Jenis kelamin:** {jenis_kelamin}")
                st.write(f"**Usia:** {usia_tahun} tahun ({usia_bulan_total} bulan)")
                st.write(f"**Tinggi:** {tinggi} cm")
            with col2:
                st.subheader("Hasil")
                st.write(f"**Status (non-diagnosis):** {status}")
                if zscore is not None:
                    st.write(f"Z-score (H/A): {zscore:.2f}")
                    st.write(f"Persentil: {pers:.1f} %")
                st.info("Informasi ini bersifat edukasi, bukan diagnosis medis.")

            # Simpan ke session
            new_row = {
                'Timestamp': datetime.datetime.now(),
                'Nama': nama,
                'TanggalLahir': ttl,
                'Kelas': kelas,
                'Sex': sex_code,
                'UsiaTahun': usia_tahun,
                'UsiaBulan': usia_bulan_total,
                'Tinggi_cm': tinggi,
                'Zscore': zscore,
                'Persentil': pers,
                'Status': status
            }
            st.session_state.measurements = pd.concat([st.session_state.measurements, pd.DataFrame([new_row])], ignore_index=True)

            # PDF download
            pdf_buf = buat_pdf_single(nama, ttl, usia_tahun, usia_bulan_total, kelas, jenis_kelamin, tinggi, zscore, pers if pers is not None else 0, status)
            st.download_button("📄 Download Hasil PDF", data=pdf_buf, file_name=f"hasil_{nama}.pdf", mime='application/pdf')

            # Excel download of all measurements
            excel_buf = df_to_excel_bytes(st.session_state.measurements)
            st.download_button("📥 Download Excel (semua pengukuran)", data=excel_buf, file_name='pengukuran_anak.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

            # Visualisasi (plot tinggi vs usia bulan)
            st.subheader('Visualisasi: Tinggi vs Usia (semua data)')
            if not st.session_state.measurements.empty:
                df_plot = st.session_state.measurements.copy()
                fig = px.scatter(df_plot, x='UsiaBulan', y='Tinggi_cm', color='Sex', hover_data=['Nama','Timestamp'])
                fig.update_layout(xaxis_title='Usia (bulan)', yaxis_title='Tinggi (cm)')
                st.plotly_chart(fig, use_container_width=True)


elif menu == "🧒 Usia 5-19 Tahun":
    st.title("🧒 Deteksi Usia 5-19 Tahun (WHO Growth Reference)")

    with st.form('form_5_19'):
        nama = st.text_input("Nama Anak")
        ttl = st.date_input("Tanggal Lahir")
        kelas = st.text_input("Kelas (opsional)")
        jenis_kelamin = st.selectbox("Jenis Kelamin", ["Laki-laki","Perempuan"]) 
        tinggi = st.number_input("Tinggi Badan (cm)", min_value=80.0, max_value=220.0, step=0.1)
        submitted = st.form_submit_button("Proses")

    if submitted:
        if not nama:
            st.warning("Masukkan nama anak.")
        else:
            usia_tahun, usia_bulan_total = hitung_usia(ttl)
            df_who = load_who_lms('who_standards/who_5_19.csv')
            sex_code = 'M' if jenis_kelamin == 'Laki-laki' else 'F'
            zscore = None
            pers = None
            status = 'Data standar tidak tersedia pada usia tersebut.'

            if df_who is not None:
                # Try matching by year first (AgeYear) or by Month if provided
                row = None
                if 'AgeYear' in df_who.columns:
                    row = df_who[(df_who['AgeYear'] == usia_tahun) & (df_who['Sex'] == sex_code)]
                if (row is None or row.empty) and 'Month' in df_who.columns:
                    row = df_who[(df_who['Month'] == usia_bulan_total) & (df_who['Sex'] == sex_code)]

                if row is not None and not row.empty:
                    L = row['L'].values[0]
                    M = row['M'].values[0]
                    S = row['S'].values[0]
                    zscore = lms_zscore(tinggi, L, M, S)
                    if zscore is not None:
                        pers = z_to_percentile(zscore)
                        if zscore < -3:
                            status = 'Sangat pendek (< -3 SD)'
                        elif zscore < -2:
                            status = 'Pendek (< -2 SD)'
                        else:
                            status = 'Tinggi normal (>= -2 SD)'

            avatar_path = choose_avatar(sex_code, zscore)
            col1, col2 = st.columns([1,2])
            with col1:
                if os.path.exists(avatar_path):
                    st.image(avatar_path, width=180)
                st.write(f"**Nama:** {nama}")
                st.write(f"**Jenis kelamin:** {jenis_kelamin}")
                st.write(f"**Usia:** {usia_tahun} tahun ({usia_bulan_total} bulan)")
                st.write(f"**Tinggi:** {tinggi} cm")
            with col2:
                st.subheader("Hasil")
                st.write(f"**Status (non-diagnosis):** {status}")
                if zscore is not None:
                    st.write(f"Z-score (H/A): {zscore:.2f}")
                    st.write(f"Persentil: {pers:.1f} %")
                st.info("Informasi ini bersifat edukasi, bukan diagnosis medis.")

            # Simpan
            new_row = {
                'Timestamp': datetime.datetime.now(),
                'Nama': nama,
                'TanggalLahir': ttl,
                'Kelas': kelas,
                'Sex': sex_code,
                'UsiaTahun': usia_tahun,
                'UsiaBulan': usia_bulan_total,
                'Tinggi_cm': tinggi,
                'Zscore': zscore,
                'Persentil': pers,
                'Status': status
            }
            st.session_state.measurements = pd.concat([st.session_state.measurements, pd.DataFrame([new_row])], ignore_index=True)

            # PDF & Excel
            pdf_buf = buat_pdf_single(nama, ttl, usia_tahun, usia_bulan_total, kelas, jenis_kelamin, tinggi, zscore, pers if pers is not None else 0, status)
            st.download_button("📄 Download Hasil PDF", data=pdf_buf, file_name=f"hasil_{nama}.pdf", mime='application/pdf')
            excel_buf = df_to_excel_bytes(st.session_state.measurements)
            st.download_button("📥 Download Excel (semua pengukuran)", data=excel_buf, file_name='pengukuran_anak.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

            # Visualisasi
            st.subheader('Visualisasi: Tinggi vs Usia (semua data)')
            if not st.session_state.measurements.empty:
                df_plot = st.session_state.measurements.copy()
                fig = px.scatter(df_plot, x='UsiaTahun', y='Tinggi_cm', color='Sex', hover_data=['Nama','Timestamp'])
                fig.update_layout(xaxis_title='Usia (tahun)', yaxis_title='Tinggi (cm)')
                st.plotly_chart(fig, use_container_width=True)


elif menu == "📜 Disclaimer":
    st.title("📜 Disclaimer & Latar Belakang")
    st.markdown(
        """
        Aplikasi ini dibuat untuk menyediakan informasi edukatif tentang status pertumbuhan anak berbasis standar WHO.

        **Standar yang digunakan:**
        - **WHO Child Growth Standards (0-5 years):** menggunakan parameter LMS (L, M, S) yang dipublikasikan WHO untuk menghitung z-score (height-for-age).
        - **WHO Growth Reference (5-19 years):** menggunakan data referensi WHO yang juga tersedia dalam bentuk parameter LMS.

        Hasil di aplikasi ini **bukan diagnosis medis**. Jika terdapat kekhawatiran terhadap pertumbuhan anak, konsultasikan ke fasilitas kesehatan.
        """
    )


elif menu == "📏 Tutorial Pengukuran":
    st.title("📏 Tutorial Mengukur Tinggi Badan Anak yang Benar")
    st.markdown(
        """
        1. Pastikan anak berdiri tegak tanpa sepatu.
        2. Kepala, bahu, pantat, dan tumit menempel pada dinding atau alat ukur.
        3. Pandangan lurus ke depan (Frankfurt plane).
        4. Gunakan alat ukur yang terkalibrasi dan catat dalam satuan cm.
        5. Untuk anak <2 tahun biasanya diukur dalam posisi berbaring (length) — pastikan standar data yang dipakai sesuai (length vs height).
        """
    )


elif menu == "📐 Prediksi Tinggi Anak":
    st.title("📐 Kalkulator Prediksi Tinggi Anak (Mid-parental height)")
    ayah = st.number_input("Tinggi Ayah (cm)", min_value=100.0, max_value=250.0, value=170.0)
    ibu = st.number_input("Tinggi Ibu (cm)", min_value=100.0, max_value=250.0, value=160.0)
    jk_balita = st.selectbox("Jenis Kelamin Anak", ["Laki-laki","Perempuan"])

    if st.button('Prediksi'):
        if jk_balita == 'Laki-laki':
            pred = (ayah + ibu + 13) / 2
        else:
            pred = (ayah + ibu - 13) / 2
        st.success(f"Prediksi tinggi optimal: {pred:.1f} cm")
        st.write(f"Perkiraan rentang (±5 cm): {pred-5:.1f} - {pred+5:.1f} cm")


# Footer: Tampilkan tabel sementara
st.sidebar.markdown('---')
st.sidebar.subheader('Data pengukuran (sementara)')
if not st.session_state.measurements.empty:
    st.sidebar.write(st.session_state.measurements[['Nama','TanggalLahir','UsiaTahun','Tinggi_cm','Status']].tail(5))
else:
    st.sidebar.write('Belum ada data')


# End of app


# -------------------------
# File: requirements.txt (tambahkan ke repo atau gunakan pip install -r)
# -------------------------

# streamlit
# pandas
# numpy
# plotly
# reportlab
# xlsxwriter
# scipy

