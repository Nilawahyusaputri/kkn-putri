# app.py
import streamlit as st
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
from fpdf import FPDF
from dateutil.relativedelta import relativedelta
import os

# =====================================================
# Konfigurasi Halaman & Tema — Fokus Tampilan (Neumorphism + Pastel)
# =====================================================
st.set_page_config(page_title="Deteksi Stunting Anak | 0–5 & 5–19 Tahun", page_icon="📏", layout="wide")

# ---- Palet Pastel & CSS Neumorphism ----
PALET = {
    "bg": "#f3f5fa",
    "card": "#f7f9ff",
    "text": "#2d3142",
    "accent": "#a0c4ff",
    "accent2": "#bde0fe",
    "accent3": "#ffc8dd",
    "accent4": "#caffbf",
}

NEUMO_CSS = f"""
<style>
:root {{
  --bg: {PALET['bg']};
  --card: {PALET['card']};
  --text: {PALET['text']};
  --accent: {PALET['accent']};
  --accent2: {PALET['accent2']};
  --accent3: {PALET['accent3']};
  --accent4: {PALET['accent4']};
}}

/* Global */
html, body, [class*="css"]  {{
  font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, sans-serif;
}}

/* Background */
.main > div {{
  background: var(--bg);
  border-radius: 24px;
  padding: 12px 12px 80px 12px;
}}

/* Header title */
h1, h2, h3, h4 {{
  color: var(--text);
}}

/* Neumorphic card helper */
.neumo {{
  background: var(--card);
  border-radius: 24px;
  padding: 24px;
  box-shadow: 12px 12px 24px rgba(0,0,0,0.08), -12px -12px 24px rgba(255,255,255,0.9);
}}

.badge {{
  display:inline-block; padding:6px 12px; border-radius:999px; font-weight:600; font-size:0.9rem; color:#2d3142;
  background: linear-gradient(145deg, var(--accent2), var(--accent));
  box-shadow: 6px 6px 12px rgba(0,0,0,0.08), -6px -6px 12px rgba(255,255,255,0.8);
}}

.cta-btn {{
  display:inline-block; padding:12px 18px; border-radius:16px; text-decoration:none; color:#1d1f2b; font-weight:700;
  background: linear-gradient(145deg, var(--accent4), var(--accent2));
  box-shadow: 8px 8px 18px rgba(0,0,0,0.1), -8px -8px 18px rgba(255,255,255,0.9);
  border: 0; cursor: pointer;
}}
.cta-btn:hover {{ transform: translateY(-1px); }}

/* Info strip */
.info-strip {{
  padding: 10px 16px; border-radius: 16px; margin: 8px 0 16px 0; font-size: 0.95rem;
  background: linear-gradient(145deg, var(--accent3), var(--accent2));
  color: #2d3142; font-weight:600;
}}

/* Tables */
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ padding: 10px 12px; border-bottom: 1px solid #e8ebf7; }}
th {{ text-align: left; color: #4b4f68; }}

/* Footer */
.footer {{ text-align:center; color:#6b7280; padding: 24px 0; font-size: 0.9rem; }}

/* Sidebar look */
section[data-testid="stSidebar"] > div {{
  background: var(--bg);
}}
.sidebar-card {{
  background: var(--card); padding: 16px; border-radius: 18px; margin-top: 8px;
  box-shadow: 10px 10px 20px rgba(0,0,0,0.08), -10px -10px 20px rgba(255,255,255,0.8);
}}
</style>
"""

st.markdown(NEUMO_CSS, unsafe_allow_html=True)

# =====================================================
# Utilitas Umum (ikon & kartu)
# =====================================================

def card(title: str, body: str, emoji: str = "", footer: str = ""):
    st.markdown(
        f"""
        <div class="neumo">
            <div style="display:flex; align-items:center; gap:10px;">
                <h3 style="margin:0;">{emoji} {title}</h3>
            </div>
            <div style="margin-top:8px; font-size:1.02rem; line-height:1.6; color:#2d3142;">{body}</div>
            {f'<div class="info-strip">{footer}</div>' if footer else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )

# =====================================================
# FUNGSI-FUNGSI PERHITUNGAN YANG SUDAH ADA (5–19 tahun)
# =====================================================

def hitung_umur(tgl_lahir):
    today = datetime.date.today()
    diff = relativedelta(today, tgl_lahir)
    tahun = diff.years
    bulan = diff.months
    hari = diff.days
    umur_bulan = tahun * 12 + bulan
    return tahun, bulan, hari, umur_bulan

# Load LMS WHO (5–19 th) — file: data/hfa-boy-z.xlsx & data/hfa-girl-z.xlsx

def load_lms(gender):
    if gender == "Laki-laki":
        df = pd.read_excel("data/hfa-boy-z.xlsx")
    else:
        df = pd.read_excel("data/hfa-girl-z.xlsx")
    df = df.rename(columns={"Month": "UmurBulan"})
    return df

# Hitung z-score HFA (5–19 th)

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

# Klasifikasi WHO (HFA)

def klasifikasi_hfa(z):
    if z < -3:
        return "Severely Stunted", "#8B0000", "Segera periksakan anak ke tenaga kesehatan untuk penanganan lebih lanjut."
    elif -3 <= z < -2:
        return "Stunted", "#FF4B4B", "Perbaiki gizi anak, tambah asupan protein, dan rutin cek pertumbuhan."
    elif -2 <= z <= 2:
        return "Normal", "#4CAF50", "Pertahankan pola makan sehat dan gaya hidup aktif."
    elif 2 < z <= 3:
        return "Tall", "#1E90FF", "Jaga keseimbangan gizi dan aktivitas."
    else:
        return "Very Tall", "#800080", "Periksa ke tenaga kesehatan jika tinggi badan anak terlalu jauh di atas rata-rata."

# Avatar map
avatar_map = {
    "Severely Stunted": "severely_boy",
    "Stunted": "stunted_boy",
    "Normal": "normal_boy",
    "Tall": "tall_boy",
    "Very Tall": "very_tall_boy"
}

# Percentile (5–19 th) — file: data/perc-boy.xlsx & data/perc-girl.xlsx

def load_percentile(gender):
    if gender == "Laki-laki":
        df = pd.read_excel("data/perc-boy.xlsx")
    else:
        df = pd.read_excel("data/perc-girl.xlsx")
    df = df.rename(columns={"Month": "UmurBulan"})
    return df


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

# PDF report (tetap, tapi tidak fokus di tampilan halaman baru)

def buat_pdf(data, gender):
    pdf = FPDF()
    pdf.add_page()

    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10, 8, 20)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt="Hasil Deteksi Pertumbuhan Anak", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Data Anak", ln=True)
    pdf.set_font("Arial", size=11)
    for key, value in data.items():
        pdf.cell(60, 8, f"{key}", 1)
        pdf.cell(0, 8, f"{value}", 1, ln=True)
    pdf.ln(5)

    if isinstance(data.get("Persentil", None), (int, float)):
        posisi = 100 - data["Persentil"]
        pdf.multi_cell(0, 8,
            f"Anak berada pada percentil {data['Persentil']} untuk tinggi badan. "
            f"Artinya, anak ini lebih tinggi dari sekitar {data['Persentil']}% anak seusianya "
            f"di seluruh dunia, dan {posisi}% anak memiliki tinggi lebih tinggi.")
    pdf.ln(5)

    pdf.multi_cell(0, 8,
        "Ilustrasi: Posisi anak digambarkan pada kurva pertumbuhan WHO, "
        "di mana garis merah menandakan tinggi anak Anda, dan garis lainnya adalah percentil standar.")

    df_percentil = load_percentile(data.get("Jenis Kelamin", "Laki-laki"))
    plt.figure(figsize=(6,4))
    for col in ["P3","P15","P50","P85","P97"]:
        plt.plot(df_percentil["UmurBulan"], df_percentil[col], label=col)
    plt.scatter([data.get("Umur (bulan)")], [data.get("Tinggi Badan (cm)")], color="red", zorder=5, label="Anak Anda")
    plt.title(f"Kurva Pertumbuhan ({data.get('Jenis Kelamin','-')})")
    plt.xlabel("Umur (bulan)")
    plt.ylabel("Tinggi (cm)")
    plt.legend()
    plt.tight_layout()

    grafik_path = "grafik_temp.png"
    plt.savefig(grafik_path)
    plt.close()
    if os.path.exists(grafik_path):
        pdf.image(grafik_path, x=20, w=170)

    os.makedirs("pdf", exist_ok=True)
    nama_file = f"pdf/Hasil_{str(data.get('Nama Anak','Anak')).replace(' ', '_')}.pdf"
    pdf.output(nama_file)
    return nama_file

# =====================================================
# Kalkulator Tinggi Maksimal (Midparental Height, tampilan dulu)
# =====================================================

def kalkulator_tinggi_section():
    st.markdown("""
        <div class="neumo">
            <h2>📐 Kalkulator Perkiraan Tinggi Dewasa Anak</h2>
            <p>Perhitungan sederhana berbasis <i>midparental height</i> (tinggi rata-rata orang tua). ✨
            <br><b>Catatan:</b> Hasil hanyalah perkiraan. Perkembangan akhir dipengaruhi gizi, aktivitas fisik, kesehatan, tidur, hormon, dan lingkungan.</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        with st.container():
            st.markdown("<div class='neumo'>", unsafe_allow_html=True)
            st.subheader("👨 Tinggi Ayah (cm)")
            ayah = st.number_input("Masukkan tinggi ayah", min_value=120.0, max_value=220.0, value=170.0, step=0.5, key="ayah")
            st.subheader("👩 Tinggi Ibu (cm)")
            ibu = st.number_input("Masukkan tinggi ibu", min_value=120.0, max_value=220.0, value=160.0, step=0.5, key="ibu")
            gender = st.selectbox("Jenis Kelamin Anak", ["Laki-laki", "Perempuan"], key="gender_kalkulator")
            st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        with st.container():
            st.markdown("<div class='neumo'>", unsafe_allow_html=True)
            st.subheader("🔮 Perkiraan Hasil")
            if gender == "Laki-laki":
                perkiraan = (ayah + ibu + 13) / 2
            else:
                perkiraan = (ayah + ibu - 13) / 2
            low = perkiraan - 8.5
            high = perkiraan + 8.5
            st.metric(label="Perkiraan tinggi dewasa (sentral)", value=f"{perkiraan:.1f} cm")
            st.write(f"Rentang ±8.5 cm: **{low:.1f} – {high:.1f} cm**")
            st.markdown(
                "<div class='info-strip'>Hasil bukan diagnosis. Optimalkan gizi seimbang, tidur cukup, aktivitas fisik, dan rutin pantau tumbuh kembang. 🥗💤🏃‍♀️</div>",
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

# =====================================================
# Deteksi 0–5 Tahun (Tampilan placeholder — form & kartu)
# =====================================================

def deteksi_0_5_section():
    st.markdown("""
        <div class="neumo">
            <h2>🍼 Deteksi Pertumbuhan Anak 0–5 Tahun</h2>
            <p>Gunakan standar WHO 2006 (Length/Height-for-Age). Pada rentang usia ini, panjang badan bisa diukur terlentang (length) hingga ±2 tahun, lalu berdiri (height). ✍️</p>
        </div>
    """, unsafe_allow_html=True)

    with st.form("form_bayi_balita"):
        c1, c2, c3 = st.columns(3)
        with c1:
            nama = st.text_input("Nama Anak ✨")
            tgl = st.date_input("Tanggal Lahir", value=datetime.date(2023,1,1), min_value=datetime.date(2006,1,1), max_value=datetime.date.today())
        with c2:
            gender = st.selectbox("Jenis Kelamin", ["Laki-laki", "Perempuan"])        
            cara_ukur = st.selectbox("Metode Pengukuran", ["Panjang (terlentang)", "Tinggi (berdiri)"])
        with c3:
            tb = st.number_input("Panjang/Tinggi (cm)", min_value=40.0, max_value=130.0, step=0.1)
            bb = st.number_input("Berat (kg)", min_value=2.0, max_value=40.0, step=0.1)
        submitted = st.form_submit_button("🔎 Analisis (UI Preview)")

    if submitted:
        tahun, bulan, hari, umur_bulan = hitung_umur(tgl)
        colA, colB = st.columns([1,1])
        with colA:
            card("Ringkasan", f"Nama: <b>{nama or '-'} </b><br>Usia: <b>{tahun} th {bulan} bln</b><br>Jenis Kelamin: <b>{gender}</b><br>Metode: <b>{cara_ukur}</b><br>Tinggi/Panjang: <b>{tb} cm</b>", "📊")
        with colB:
            card("Status (contoh tampilan)", "Z-score HFA: <b>—</b><br>Persentil: <b>—</b><br>Kategori: <b>—</b>", "🧭", footer="Ini hanya pratinjau UI. Integrasi rumus WHO 2006 bisa ditambahkan menyusul.")

        st.markdown("<div class='neumo'>", unsafe_allow_html=True)
        st.subheader("📈 Kurva Pertumbuhan (Placeholder)")
        fig, ax = plt.subplots(figsize=(8,4))
        x = np.linspace(0, 60, 61)
        for mul, lbl in [(0.9, "P15"), (1.0, "P50"), (1.1, "P85")]:
            ax.plot(x, 50 + mul*np.sin(x/8)*4 + mul*0.2*x, label=lbl)
        ax.scatter([umur_bulan], [tb], label="Anak Anda")
        ax.set_xlabel("Umur (bulan)"); ax.set_ylabel("Tinggi/Panjang (cm)"); ax.legend()
        st.pyplot(fig)
        st.markdown("</div>", unsafe_allow_html=True)

# =====================================================
# Deteksi 5–19 Tahun (UI + logika singkat dari kode awal)
# =====================================================

def deteksi_5_19_section():
    st.markdown("""
        <div class="neumo">
            <h2>🏫 Deteksi Pertumbuhan Anak 5–19 Tahun</h2>
            <p>Menggunakan referensi WHO 2007 (Height-for-Age Z-score). Masukkan data di bawah ini untuk melihat status dan posisi pada kurva. 📈</p>
        </div>
    """, unsafe_allow_html=True)

    with st.form("form_anak_5_19"):
        c1, c2, c3 = st.columns(3)
        with c1:
            nama = st.text_input("Nama Anak")
            tgl_lahir = st.date_input("Tanggal Lahir", value=datetime.date(2015, 6, 1),
                                      min_value=datetime.date(2000, 1, 1),
                                      max_value=datetime.date.today())
        with c2:
            gender = st.selectbox("Jenis Kelamin", ["Laki-laki", "Perempuan"])
            tinggi = st.number_input("Tinggi Badan (cm)", min_value=50.0, max_value=200.0)
        with c3:
            berat = st.number_input("Berat Badan (kg)", min_value=5.0, max_value=100.0)
            kelas = st.text_input("Kelas")
        submit = st.form_submit_button("🔎 Deteksi")

    if "data_anak" not in st.session_state:
        st.session_state.data_anak = []

    if submit:
        tahun, bulan, hari, umur_bulan = hitung_umur(tgl_lahir)
        if umur_bulan < 61:
            st.warning("⚠️ Anak berusia di bawah 5 tahun. Gunakan standar WHO 2006 untuk hasil yang lebih tepat.")

        z = hitung_zscore(umur_bulan, tinggi, gender)
        if z is None:
            st.warning("Umur belum tersedia dalam standar WHO 2007.")
            return
        status, warna, tips = klasifikasi_hfa(z)
        percentil_value = hitung_percentil(umur_bulan, tinggi, gender)
        kategori_percentil = None
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

        st.subheader("📊 Hasil Analisis")
        st.markdown(f"**Umur:** {tahun} tahun {bulan} bulan {hari} hari")
        st.write(f"**Z-score HFA:** {z}")
        if kategori_percentil:
            st.write(f"**Persentil Tinggi:** {percentil_value} → {kategori_percentil}")
            st.write(f"Anak ini lebih tinggi dari {percentil_value}% anak seusianya di dunia.")
        st.markdown(
            f"<div class='neumo'><div class='badge'>Status</div><h3 style='margin-top:6px'>{status}</h3><p><i>{tips}</i></p></div>",
            unsafe_allow_html=True,
        )

        avatar_key = avatar_map.get(status, "normal_boy")
        avatar_path = f"avatars/{avatar_key if gender=='Laki-laki' else avatar_key.replace('_boy', '_girl')}.png"
        if os.path.exists(avatar_path):
            st.image(avatar_path, width=220, caption="Gambaran Anak")
        else:
            st.info("[Avatar tidak tersedia]")

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
            "Persentil": percentil_value if percentil_value else "-"
        }
        st.session_state.data_anak.append(hasil_data)

        try:
            pdf_path = buat_pdf(hasil_data, gender)
            with open(pdf_path, "rb") as f:
                st.download_button("📥 Download PDF Hasil Anak Ini", f, file_name=os.path.basename(pdf_path))
        except Exception as e:
            st.warning("Gagal membuat PDF. Pastikan folder/izin tersedia.")

        df_percentil = load_percentile(gender)
        plt.figure(figsize=(8,5))
        for col in ["P3","P15","P50","P85","P97"]:
            plt.plot(df_percentil["UmurBulan"], df_percentil[col], label=col)
        plt.scatter([umur_bulan], [tinggi], zorder=5, label="Anak Anda")
        plt.title(f"Kurva Pertumbuhan ({gender})")
        plt.xlabel("Umur (bulan)")
        plt.ylabel("Tinggi (cm)")
        plt.legend()
        st.pyplot(plt)

    if st.session_state.data_anak:
        st.subheader("📋 Data Semua Anak yang Sudah Diperiksa")
        df_all = pd.DataFrame(st.session_state.data_anak)
        st.dataframe(df_all, use_container_width=True)

        csv = df_all.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Semua Data (CSV)", csv, file_name="data_semua_anak.csv", mime="text/csv")

        st.subheader("📊 Distribusi Status Gizi Berdasarkan Gender")
        status_order = ["Severely Stunted", "Stunted", "Normal", "Tall", "Very Tall"]
        gender_order = ["Laki-laki", "Perempuan"]

        df_counts = df_all.groupby(["Status", "Jenis Kelamin"]).size().unstack(fill_value=0)
        df_counts = df_counts.reindex(index=status_order, columns=gender_order, fill_value=0)

        x = np.arange(len(status_order))
        width = 0.35
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(x - width/2, df_counts["Laki-laki"], width, label="Laki-laki")
        ax.bar(x + width/2, df_counts["Perempuan"], width, label="Perempuan")
        ax.set_ylabel("Jumlah Anak")
        ax.set_xlabel("Kategori Status")
        ax.set_title("Distribusi Status Gizi Berdasarkan Gender")
        ax.set_xticks(x)
        ax.set_xticklabels(status_order, rotation=20)
        ax.legend()
        for i in range(len(status_order)):
            ax.text(x[i] - width/2, df_counts["Laki-laki"].iloc[i] + 0.05,
                    int(df_counts["Laki-laki"].iloc[i]), ha="center", va="bottom", fontsize=9)
            ax.text(x[i] + width/2, df_counts["Perempuan"].iloc[i] + 0.05,
                    int(df_counts["Perempuan"].iloc[i]), ha="center", va="bottom", fontsize=9)
        st.pyplot(fig)

        st.subheader("📈 Distribusi Z-score dengan Kategori Warna")
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

        color_map = {
            "Severely Stunted": "#ef476f",
            "Stunted": "#f78c6b",
            "Normal": "#06d6a0",
            "Tall": "#118ab2",
            "Very Tall": "#9b5de5"
        }
        df_all["Kategori Z-score"] = df_all["Z-score"].apply(kategori_zscore)
        df_zscore_counts = df_all.groupby(["Z-score", "Kategori Z-score"]).size().reset_index(name="Jumlah")
        fig2, ax2 = plt.subplots(figsize=(8, 5))
        for idx, row in df_zscore_counts.iterrows():
            ax2.bar(row["Z-score"], row["Jumlah"], color=color_map[row["Kategori Z-score"]], width=0.15)
        ax2.axvline(x=-3, linestyle="--", label="Batas Severe (-3)")
        ax2.axvline(x=-2, linestyle="--", label="Batas Stunted (-2)")
        ax2.axvline(x=2, linestyle="--", label="Batas Normal/Tinggi (+2)")
        ax2.axvline(x=3, linestyle="--", label="Batas Sangat Tinggi (+3)")
        ax2.set_xlabel("Z-score"); ax2.set_ylabel("Jumlah Anak"); ax2.set_title("Distribusi Z-score Anak")
        ax2.legend()
        st.pyplot(fig2)

# =====================================================
# Halaman: Standar yang Digunakan (konten informatif ringan)
# =====================================================

def standar_section():
    st.markdown("""
    <div class="neumo">
      <h2>📚 Standar yang Digunakan</h2>
      <ul>
        <li>👶 <b>WHO 2006</b> — Growth Standards untuk <i>0–5 tahun</i> (length/height-for-age, weight-for-age, weight-for-length/height, BMI-for-age).</li>
        <li>🧒 <b>WHO 2007</b> — Growth Reference untuk <i>5–19 tahun</i> (BMI-for-age, height-for-age, weight-for-age 5–10 th).</li>
        <li>🧮 Z-score dihitung dari parameter <b>L, M, S</b> sesuai umur & jenis kelamin.</li>
      </ul>
      <div class="info-strip">Catatan: Implementasi lengkap membutuhkan tabel referensi resmi WHO (file Excel/CSV) yang disertakan dalam folder <code>data/</code>.</div>
    </div>
    """, unsafe_allow_html=True)

# =====================================================
# Halaman: Serba-serbi Stunting (edukasi singkat + emoji & gambar)
# =====================================================

def serba_serbi_section():
    col1, col2 = st.columns([1.2, 1])
    with col1:
        card(
            "Apa itu Stunting?",
            "Stunting adalah kondisi gagal tumbuh pada anak akibat kekurangan gizi kronis, ditandai tinggi badan lebih pendek dari standar usianya. Terjadi terutama pada 1000 hari pertama kehidupan.",
            "🌱",
        )
        card(
            "Mengapa Penting?",
            "Dampak jangka panjang bisa mencakup perkembangan kognitif, prestasi belajar, produktivitas, dan risiko penyakit metabolik di masa depan.",
            "🎯",
        )
        card(
            "Pencegahan",
            "Makanan bergizi seimbang, ASI eksklusif, MPASI sesuai umur, imunisasi lengkap, sanitasi bersih, tidur cukup, dan pantau tumbuh kembang secara berkala.",
            "🛡️",
        )
    with col2:
        st.markdown("<div class='neumo' style='text-align:center'>", unsafe_allow_html=True)
        if os.path.exists("assets/family_pastel.png"):
            st.image("assets/family_pastel.png", use_container_width=True)
        else:
            st.markdown("<h3>👨‍👩‍👧‍👦</h3>")
            st.caption("Tambahkan gambar ilustrasi di folder assets/")
        st.markdown("</div>", unsafe_allow_html=True)


# =====================================================
# HOME — Selamat Datang & Latar Belakang
# =====================================================

def home_section():
    hero_left, hero_right = st.columns([1.2, 1])
    with hero_left:
        st.markdown(
            """
            <div class="neumo">
              <span class="badge">Versi Edukasi</span>
              <h1 style="margin-top:8px">Selamat Datang di Aplikasi Deteksi Pertumbuhan Anak 📏✨</h1>
              <p style="font-size:1.05rem; line-height:1.7">
              Aplikasi ini membantu orang tua, guru, dan tenaga kesehatan <b>memantau pertumbuhan anak</b> menggunakan referensi WHO. 
              Fitur mencakup deteksi untuk <b>0–5 tahun</b> dan <b>5–19 tahun</b>, kurva pertumbuhan, serta <i>kalkulator perkiraan tinggi dewasa</i>.
              </p>
              <a class="cta-btn" href="#navigasi">Mulai sekarang ➜</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hero_right:
        st.markdown("<div class='neumo' style='text-align:center'>", unsafe_allow_html=True)
        if os.path.exists("assets/hero_kids.png"):
            st.image("assets/hero_kids.png", use_container_width=True)
        else:
            st.markdown("<h2>🧒👧</h2>")
            st.caption("Letakkan ilustrasi di assets/hero_kids.png untuk tampilan optimal.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="neumo">
          <h2>🎯 Latar Belakang</h2>
          <p>
            Stunting masih menjadi tantangan kesehatan masyarakat. Pemantauan tinggi dan berat badan secara rutin membantu 
            deteksi dini dan intervensi tepat waktu. Aplikasi ini dibuat untuk <b>memudahkan input data</b>, 
            <b>menampilkan status</b> sesuai standar internasional, dan <b>memberi edukasi</b> praktis.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# =====================================================
# Navigasi Sidebar (Sederhana, bersih, emoji)
# =====================================================

st.sidebar.markdown("<div class='sidebar-card'><h3 id='navigasi'>🧭 Navigasi</h3></div>", unsafe_allow_html=True)
menu = st.sidebar.radio(
    label="Pilih Halaman",
    options=[
        "🏠 Home",
        "🍼 Deteksi 0–5 Tahun",
        "🏫 Deteksi 5–19 Tahun",
        "📐 Kalkulator Tinggi Maksimal",
        "📚 Standar yang Digunakan",
        "🌿 Serba-serbi Stunting",
    ],
    index=0,
)

# =====================================================
# Router Halaman
# =====================================================

if menu == "🏠 Home":
    home_section()
elif menu == "🍼 Deteksi 0–5 Tahun":
    deteksi_0_5_section()
elif menu == "🏫 Deteksi 5–19 Tahun":
    deteksi_5_19_section()
elif menu == "📐 Kalkulator Tinggi Maksimal":
    kalkulator_tinggi_section()
elif menu == "📚 Standar yang Digunakan":
    standar_section()
elif menu == "🌿 Serba-serbi Stunting":
    serba_serbi_section()

# =====================================================
# Footer
# =====================================================

st.markdown(
    """
    <div class="footer">
      Dibuat untuk edukasi. Bukan alat diagnosis. Konsultasikan ke tenaga kesehatan bila ragu. 💚
    </div>
    """,
    unsafe_allow_html=True,
)
