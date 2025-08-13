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
st.title("📏 Deteksi Stunting & Percentil Tinggi Badan Anak Usia Sekolah (5–19 Tahun)")

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
def klasifikasi_hfa(z):
    if z < -3:
        return "Severely Stunted", "darkred", "Segera periksakan anak ke tenaga kesehatan untuk penanganan lebih lanjut."
    elif -3 <= z < -2:
        return "Stunted", "red", "Perbaiki gizi anak, tambah asupan protein, dan rutin cek pertumbuhan."
    elif -2 <= z <= 2:
        return "Normal", "green", "Pertahankan pola makan sehat dan gaya hidup aktif."
    elif 2 < z <= 3:
        return "Tall", "blue", "Jaga keseimbangan gizi dan aktivitas."
    else:
        return "Very Tall", "purple", "Periksa ke tenaga kesehatan jika tinggi badan anak terlalu jauh di atas rata-rata."

# -------------------------------
# Mapping Avatar
# -------------------------------
avatar_map = {
    "Severely Stunted": "severely_boy",
    "Stunted": "stunted_boy",
    "Normal": "normal_boy",
    "Tall": "tall_boy",
    "Very Tall": "very_tall_boy"
}

# -------------------------------
# Fungsi Buat PDF
# -------------------------------
def buat_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt="Hasil Deteksi Stunting & Percentil Tinggi Badan Anak", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", size=12)
    for key, value in data.items():
        pdf.cell(0, 10, f"{key}: {value}", ln=True)
    os.makedirs("pdf", exist_ok=True)
    nama_file = f"pdf/Hasil_{data['Nama Anak'].replace(' ', '_')}.pdf"
    pdf.output(nama_file)
    return nama_file

# -------------------------------
# Fungsi Load Percentile WHO
# -------------------------------
def load_percentile(gender):
    if gender == "Laki-laki":
        df = pd.read_excel("data/perc-boy.xlsx")
    else:
        df = pd.read_excel("data/perc-girl.xlsx")
    df = df.rename(columns={"Month": "UmurBulan"})
    return df

# -------------------------------
# Fungsi Hitung Percentil
# -------------------------------
def hitung_percentil(umur_bulan, tinggi, gender):
    df = load_percentile(gender)
    df_interp = df.set_index("UmurBulan").reindex(
        range(df["UmurBulan"].min(), df["UmurBulan"].max() + 1)
    ).interpolate()
    if umur_bulan not in df_interp.index:
        return None
    data = df_interp.loc[umur_bulan]
    persentil_cols = [c for c in df.columns if c.startswith("P")]
    tinggi_list = [data[col] for col in persentil_cols]
    percentil_angka = [float(c[1:]) for c in persentil_cols]
    selisih = [abs(tinggi - t) for t in tinggi_list]
    idx_min = np.argmin(selisih)
    return percentil_angka[idx_min]

# -------------------------------
# Form Input Data
# -------------------------------
with st.form("form_anak"):
    nama = st.text_input("Nama Anak")
    tgl_lahir = st.date_input("Tanggal Lahir", value=datetime.date(2015, 6, 1),
                              min_value=datetime.date(2000, 1, 1),
                              max_value=datetime.date.today())
    gender = st.selectbox("Jenis Kelamin", ["Laki-laki", "Perempuan"])
    tinggi = st.number_input("Tinggi Badan (cm)", min_value=50.0, max_value=200.0)
    berat = st.number_input("Berat Badan (kg)", min_value=5.0, max_value=100.0)
    kelas = st.text_input("Kelas")
    submit = st.form_submit_button("Deteksi")

# -------------------------------
# Session State
# -------------------------------
if "data_anak" not in st.session_state:
    st.session_state.data_anak = []

# -------------------------------
# Proses Analisis
# -------------------------------
if submit:
    tahun, bulan, hari, umur_bulan = hitung_umur(tgl_lahir)

    if umur_bulan < 61:
        st.warning("⚠️ Anak berusia di bawah 5 tahun. Gunakan standar WHO 2006 untuk hasil yang lebih tepat.")

    z = hitung_zscore(umur_bulan, tinggi, gender)

    if z is None:
        st.warning("Umur belum tersedia dalam standar WHO 2007.")
    else:
        status, warna, tips = klasifikasi_hfa(z)

        # Hitung percentil
        percentil_value = hitung_percentil(umur_bulan, tinggi, gender)
        if percentil_value is not None:
            if percentil_value < 3:
                kategori_percentil = "Sangat Pendek"
            elif percentil_value < 15:
                kategori_percentil = "Pendek"
            elif percentil_value <= 85:
                kategori_percentil = "Normal"
            elif percentil_value <= 97:
                kategori_percentil = "Tinggi"
            else:
                kategori_percentil = "Sangat Tinggi"
        else:
            kategori_percentil = None

        st.subheader("📊 Hasil Analisis")
        st.markdown(f"**Umur:** {tahun} tahun {bulan} bulan {hari} hari")
        st.write(f"**Z-score HFA:** {z}")
        if percentil_value is not None:
            st.write(f"**Persentil Tinggi:** {percentil_value} → {kategori_percentil}")
        st.markdown(
            f"<div style='background-color:{warna}; padding:10px; border-radius:10px; color:white;'>"
            f"<b>Status: {status}</b><br/><i>{tips}</i></div>", unsafe_allow_html=True
        )

        avatar_key = avatar_map.get(status, "normal_boy")
        avatar_path = f"avatars/{avatar_key if gender=='Laki-laki' else avatar_key.replace('_boy', '_girl')}.png"
        if os.path.exists(avatar_path):
            st.image(avatar_path, width=250, caption="Gambaran Anak")
        else:
            st.info("[Avatar tidak tersedia]")

        # Simpan hasil ke session
        hasil_data = {
            "Nama Anak": nama,
            "Tanggal Lahir": tgl_lahir.strftime("%Y-%m-%d"),
            "Jenis Kelamin": gender,
            "Umur (bulan)": umur_bulan,
            "Tinggi Badan (cm)": tinggi,
            "Berat Badan (kg)": berat,
            "Kelas": kelas,
            "Z-score": z,
            "Status": status,
            "Persentil": percentil_value if percentil_value is not None else "-"
        }
        st.session_state.data_anak.append(hasil_data)

        # Buat PDF
        pdf_path = buat_pdf(hasil_data)
        with open(pdf_path, "rb") as f:
            st.download_button("📥 Download PDF Hasil Anak Ini", f, file_name=os.path.basename(pdf_path))

        # Plot kurva pertumbuhan
        df_percentil = load_percentile(gender)
        plt.figure(figsize=(8,5))
        for col in ["P3","P15","P50","P85","P97"]:
            plt.plot(df_percentil["UmurBulan"], df_percentil[col], label=col)
        plt.scatter([umur_bulan], [tinggi], color="red", zorder=5, label="Anak Anda")
        plt.title(f"Kurva Pertumbuhan ({gender})")
        plt.xlabel("Umur (bulan)")
        plt.ylabel("Tinggi (cm)")
        plt.legend()
        st.pyplot(plt)

# -------------------------------
# Visualisasi Data Semua Anak
# -------------------------------
if st.session_state.data_anak:
    st.subheader("📋 Data Semua Anak yang Sudah Diperiksa")
    df_all = pd.DataFrame(st.session_state.data_anak)
    st.dataframe(df_all, use_container_width=True)

    csv = df_all.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download Semua Data (CSV)", csv, file_name="data_semua_anak.csv", mime="text/csv")
