import streamlit as st
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
from fpdf import FPDF
from dateutil.relativedelta import relativedelta
import os

# -------------------------------
# Konfigurasi halaman
# -------------------------------
st.set_page_config(page_title="Deteksi Stunting Anak Usia Sekolah (5-19 Tahun)", layout="centered")
st.title("📏 Deteksi Stunting Anak Usia Sekolah (5–19 Tahun)")

# -------------------------------
# Fungsi Hitung Umur
# -------------------------------
def hitung_umur(tgl_lahir):
    today = datetime.date.today()
    diff = relativedelta(today, tgl_lahir)
    tahun = diff.years
    bulan = diff.months
    hari = diff.days
    umur_bulan = tahun * 12 + bulan
    return tahun, bulan, hari, umur_bulan

# -------------------------------
# Fungsi Load LMS WHO
# -------------------------------
def load_lms(gender):
    if gender == "Laki-laki":
        df = pd.read_excel("data/hfa-boy-z.xlsx")
    else:
        df = pd.read_excel("data/hfa-girl-z.xlsx")
    df = df.rename(columns={"Month": "UmurBulan"})
    return df

# -------------------------------
# Fungsi Hitung Z-score HFA
# -------------------------------
def hitung_zscore(umur_bulan, tinggi, gender):
    lms_df = load_lms(gender)
    # Interpolasi jika umur tidak ada di data
    lms_df = lms_df.set_index("UmurBulan").reindex(
        range(lms_df["UmurBulan"].min(), lms_df["UmurBulan"].max() + 1)
    ).interpolate()
    if umur_bulan not in lms_df.index:
        return None
    L = float(lms_df.loc[umur_bulan, "L"])
    M = float(lms_df.loc[umur_bulan, "M"])
    S = float(lms_df.loc[umur_bulan, "S"])
    z = ((tinggi / M)**L - 1) / (L * S)
    return round(z, 2)

# -------------------------------
# Fungsi Klasifikasi WHO + Edukasi
# -------------------------------
# -------------------------------
# Fungsi Klasifikasi WHO + Edukasi (versi konsisten)
# -------------------------------
def klasifikasi_hfa(z):
    if z < -3:
        return "Severely Stunted", "darkred", "Segera periksakan anak ke tenaga kesehatan untuk penanganan lebih lanjut."
    elif -3 <= z < -2:
        return "Stunted", "red", "Perbaiki gizi anak, tambah asupan protein, dan rutin cek pertumbuhan."
    elif -2 <= z <= 2:
        return "Normal", "green", "Pertahankan pola makan sehat dan gaya hidup aktif."
    elif 2 < z <= 3:
        return "Tall", "blue", "Jaga keseimbangan gizi dan aktivitas."
    else:  # z > 3
        return "Very Tall", "purple", "Pastikan asupan gizi seimbang dan periksa kesehatan secara berkala."

# -------------------------------
# Mapping Avatar (sesuai kategori baru)
# -------------------------------
avatar_map = {
    "Severely Stunted": "severely_boy",
    "Stunted": "stunted_boy",
    "Normal": "normal_boy",
    "Tall": "tall_boy",
    "Very Tall": "tall_boy"  # pakai avatar Tall sementara
}

# -------------------------------
# Warna untuk status gizi (konsisten di semua grafik)
# -------------------------------
status_color_map = {
    "Severely Stunted": "darkred",
    "Stunted": "red",
    "Normal": "green",
    "Tall": "blue",
    "Very Tall": "purple"
}

# -------------------------------
# Fungsi Kategori Z-score (untuk grafik distribusi)
# -------------------------------
def kategori_zscore(z):
    if z < -3:
        return "Severely Stunted"
    elif -3 <= z < -2:
        return "Stunted"
    elif -2 <= z <= 2:
        return "Normal"
    elif 2 < z <= 3:
        return "Tall"
    else:
        return "Very Tall"

# -------------------------------
# Visualisasi hanya jika ada data
# -------------------------------
if st.session_state.data_anak:
    st.subheader("📋 Data Semua Anak yang Sudah Diperiksa")
    df_all = pd.DataFrame(st.session_state.data_anak)
    st.dataframe(df_all, use_container_width=True)

    # Download CSV
    csv = df_all.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download Semua Data (CSV)", csv, file_name="data_semua_anak.csv", mime="text/csv")

    # -------------------------------
    # Chart distribusi status gizi per gender
    # -------------------------------
    st.subheader("📊 Distribusi Status Gizi Berdasarkan Gender")

    status_order = ["Severely Stunted", "Stunted", "Normal", "Tall", "Very Tall"]
    gender_order = ["Laki-laki", "Perempuan"]

    df_counts = df_all.groupby(["Status", "Jenis Kelamin"]).size().unstack(fill_value=0)
    df_counts = df_counts.reindex(index=status_order, columns=gender_order, fill_value=0)

    x = np.arange(len(status_order))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - width/2, df_counts["Laki-laki"], width, label="Laki-laki", color="skyblue")
    ax.bar(x + width/2, df_counts["Perempuan"], width, label="Perempuan", color="pink")

    ax.set_ylabel("Jumlah Anak")
    ax.set_xlabel("Kategori Status")
    ax.set_title("Distribusi Status Gizi Berdasarkan Gender")
    ax.set_xticks(x)
    ax.set_xticklabels(status_order, rotation=20)
    ax.legend()

    for i in range(len(status_order)):
        ax.text(x[i] - width/2, df_counts["Laki-laki"].iloc[i] + 0.05, int(df_counts["Laki-laki"].iloc[i]),
                ha="center", va="bottom", fontsize=9)
        ax.text(x[i] + width/2, df_counts["Perempuan"].iloc[i] + 0.05, int(df_counts["Perempuan"].iloc[i]),
                ha="center", va="bottom", fontsize=9)

    st.pyplot(fig)

    # -------------------------------
    # Grafik Distribusi Z-score
    # -------------------------------
    st.subheader("📈 Distribusi Z-score dengan Kategori Warna")

    df_all["Kategori Z-score"] = df_all["Z-score"].apply(kategori_zscore)
    df_zscore_counts = df_all.groupby(["Z-score", "Kategori Z-score"]).size().reset_index(name="Jumlah")

    fig, ax = plt.subplots(figsize=(8, 5))
    for idx, row in df_zscore_counts.iterrows():
        ax.bar(row["Z-score"], row["Jumlah"], color=status_color_map[row["Kategori Z-score"]], width=0.15)

    ax.axvline(x=-3, color="darkred", linestyle="--", label="Batas Severe Stunted (-3)")
    ax.axvline(x=-2, color="red", linestyle="--", label="Batas Stunted (-2)")
    ax.axvline(x=2, color="blue", linestyle="--", label="Batas Tall (+2)")
    ax.axvline(x=3, color="purple", linestyle="--", label="Batas Very Tall (+3)")

    ax.set_xlabel("Z-score")
    ax.set_ylabel("Jumlah Anak")
    ax.set_title("Distribusi Z-score Anak Berdasarkan Kategori")
    ax.legend()

    st.pyplot(fig)
