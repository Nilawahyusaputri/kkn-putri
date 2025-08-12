import streamlit as st
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
import plotly.express as px
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io
import os

# -------------------------
# Fungsi utilitas
# -------------------------
def hitung_usia(tgl_lahir):
    today = datetime.date.today()
    usia_tahun = today.year - tgl_lahir.year - ((today.month, today.day) < (tgl_lahir.month, tgl_lahir.day))
    usia_bulan_total = (today.year - tgl_lahir.year) * 12 + today.month - tgl_lahir.month
    return usia_tahun, usia_bulan_total

def load_who_standard(file_path):
    return pd.read_csv(file_path)

def get_status_gizi(usia_bulan, jenis_kelamin, tinggi, df):
    # Filter berdasarkan usia & jenis kelamin
    row = df[(df['Month'] == usia_bulan) & (df['Sex'] == jenis_kelamin)]
    if row.empty:
        return None, None
    median = row['Median'].values[0]
    sd = row['SD'].values[0]
    zscore = (tinggi - median) / sd

    if zscore < -2:
        status = "Tinggi di bawah rata-rata (indikasi risiko stunting)"
        avatar = f"assets/{'boy' if jenis_kelamin=='M' else 'girl'}_under.png"
    else:
        status = "Tinggi normal"
        avatar = f"assets/{'boy' if jenis_kelamin=='M' else 'girl'}_normal.png"
    return status, avatar

def buat_pdf(nama, usia_tahun, usia_bulan_total, jenis_kelamin, tinggi, status):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica", 14)
    c.drawString(50, 800, "Hasil Pengukuran Status Gizi")
    c.drawString(50, 770, f"Nama Anak: {nama}")
    c.drawString(50, 750, f"Jenis Kelamin: {'Laki-laki' if jenis_kelamin=='M' else 'Perempuan'}")
    c.drawString(50, 730, f"Usia: {usia_tahun} tahun ({usia_bulan_total} bulan)")
    c.drawString(50, 710, f"Tinggi Badan: {tinggi} cm")
    c.drawString(50, 690, f"Status: {status}")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# -------------------------
# Sidebar
# -------------------------
st.sidebar.title("📌 Menu")
menu = st.sidebar.radio("Navigasi", ["🏠 Home", "👶 Usia 0-5 Tahun", "🧒 Usia 5-19 Tahun", 
                                      "📜 Disclaimer", "📏 Tutorial Pengukuran", "📐 Prediksi Tinggi Anak"])

# -------------------------
# Halaman Home
# -------------------------
if menu == "🏠 Home":
    st.title("🌱 Aplikasi Deteksi Status Gizi Anak (Non-Diagnosis)")
    st.write("""
    Aplikasi ini menggunakan **standar WHO** untuk memberikan informasi status gizi anak berdasarkan tinggi badan dan usia.
    Data yang dihasilkan **bukan untuk diagnosis medis**, melainkan sebagai edukasi.
    """)

# -------------------------
# Halaman 0-5 Tahun & 5-19 Tahun
# -------------------------
elif menu in ["👶 Usia 0-5 Tahun", "🧒 Usia 5-19 Tahun"]:
    st.title(f"{menu}")
    nama = st.text_input("Nama Anak")
    ttl = st.date_input("Tanggal Lahir")
    jenis_kelamin = st.selectbox("Jenis Kelamin", ["Laki-laki", "Perempuan"])
    tinggi = st.number_input("Tinggi Badan (cm)", min_value=20.0, max_value=200.0, step=0.1)

    if st.button("Proses"):
        usia_tahun, usia_bulan_total = hitung_usia(ttl)
        jk_code = 'M' if jenis_kelamin == "Laki-laki" else 'F'

        if menu == "👶 Usia 0-5 Tahun":
            df_who = load_who_standard("who_standards/who_0_5.csv")
        else:
            df_who = load_who_standard("who_standards/who_5_19.csv")

        status, avatar_path = get_status_gizi(usia_bulan_total, jk_code, tinggi, df_who)
        
        if status:
            st.image(avatar_path, width=150)
            st.subheader(f"Hasil: {status}")
            st.write(f"Usia: {usia_tahun} tahun ({usia_bulan_total} bulan)")
            st.write(f"Tinggi: {tinggi} cm")
            st.success("Informasi ini bersifat edukasi, bukan diagnosis medis.")

            pdf_buffer = buat_pdf(nama, usia_tahun, usia_bulan_total, jk_code, tinggi, status)
            st.download_button("📄 Download Hasil PDF", pdf_buffer, file_name=f"hasil_{nama}.pdf")

# -------------------------
# Halaman Disclaimer
# -------------------------
elif menu == "📜 Disclaimer":
    st.title("📜 Disclaimer")
    st.write("""
    Web ini dibuat untuk memberikan informasi edukatif tentang status gizi anak berdasarkan standar WHO.
    Data yang digunakan berasal dari tabel **WHO Child Growth Standards** dan **WHO Growth Reference**.
    """)

# -------------------------
# Halaman Tutorial
# -------------------------
elif menu == "📏 Tutorial Pengukuran":
    st.title("📏 Tutorial Mengukur Tinggi Badan Anak yang Benar")
    st.write("""
    1. Pastikan anak berdiri tegak.
    2. Kepala, bahu, pantat, dan tumit menempel di dinding.
    3. Pandangan lurus ke depan.
    4. Gunakan alat ukur resmi.
    """)

# -------------------------
# Halaman Prediksi Tinggi
# -------------------------
elif menu == "📐 Prediksi Tinggi Anak":
    st.title("📐 Prediksi Tinggi Anak Optimal")
    ayah = st.number_input("Tinggi Ayah (cm)", min_value=100.0, max_value=250.0)
    ibu = st.number_input("Tinggi Ibu (cm)", min_value=100.0, max_value=250.0)
    jenis_kelamin = st.selectbox("Jenis Kelamin Anak", ["Laki-laki", "Perempuan"])

    if st.button("Prediksi"):
        if jenis_kelamin == "Laki-laki":
            prediksi = (ayah + ibu + 13) / 2
        else:
            prediksi = (ayah + ibu - 13) / 2
        st.success(f"Prediksi tinggi optimal: {prediksi:.1f} cm")
