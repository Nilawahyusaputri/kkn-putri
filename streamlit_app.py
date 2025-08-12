# Streamlit app: Deteksi Status Gizi Anak (Non-Diagnostik)
# File: streamlit_stunting_app.py
# Instruksi: letakkan file WHO LMS CSV untuk usia 0-5 dan 5-19 di folder 'data/'
#  - data/who_lms_0_5.csv    (columns: age_months, sex, L, M, S)
#  - data/who_lms_5_19.csv   (columns: age_years, sex, L, M, S)
# Menjalankan: `streamlit run streamlit_stunting_app.py`

import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, date
from math import isnan
import base64
from scipy.stats import norm

st.set_page_config(page_title="Deteksi Status Gizi (Non-Diagnostik)", layout='wide')

# ----------------------------- Utilities -----------------------------
@st.cache_data
def load_who_lms(path_0_5='data/who_lms_0_5.csv', path_5_19='data/who_lms_5_19.csv'):
    try:
        lms0 = pd.read_csv(path_0_5)
    except Exception:
        lms0 = pd.DataFrame()
    try:
        lms1 = pd.read_csv(path_5_19)
    except Exception:
        lms1 = pd.DataFrame()
    return lms0, lms1

# Compute z-score from measurement using LMS method
# x = measurement (e.g., height in cm), L,M,S from WHO table
def lms_zscore(x, L, M, S):
    # handle L close to 0
    if abs(L) < 1e-8:
        z = np.log(x / M) / S
    else:
        z = ((x / M) ** L - 1) / (L * S)
    return z

# Convert z to percentile (approx) using normal CDF
def z_to_pct(z):
    return norm.cdf(z) * 100

# Generate simple avatar SVG base64 depending on sex and status
def avatar_svg_base64(sex='Laki-laki', status='Normal'):
    # simple colored circle avatar, color varies by status
    color_map = {
        'Severe Stunting': '#c0392b',
        'Stunting': '#e67e22',
        'Risk': '#f1c40f',
        'Normal': '#2ecc71'
    }
    color = color_map.get(status, '#95a5a6')
    hair = 'short' if sex == 'Laki-laki' else 'long'
    svg = f'''<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'>
    <rect width='100%' height='100%' fill='#ecf0f1' rx='20' />
    <circle cx='80' cy='60' r='36' fill='{color}' stroke='#34495e' stroke-width='2'/>
    <rect x='48' y='96' width='64' height='48' rx='12' fill='{color}' opacity='0.85'/>
    <text x='80' y='148' font-size='12' text-anchor='middle' fill='#2c3e50'>{sex} | {status}</text>
    </svg>'''
    b = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{b}"

# Simple PDF generator using HTML->PDF is not in standard lib; create a basic text-PDF using reportlab if available
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# ----------------------------- Load WHO data -----------------------------
lms_0_5, lms_5_19 = load_who_lms()

# ----------------------------- Layout -----------------------------
st.sidebar.title("Menu")
page = st.sidebar.radio("Pilih Halaman", [
    "Home",
    "Ukuran 0-5 tahun (WHO)",
    "Ukuran 5-19 tahun (WHO)",
    "Batch Upload / Data",
    "Visualisasi Data",
    "Kalkulator Prediksi Tinggi",
    "Tutorial Pengukuran",
    "Disclaimer"
])

# Shared storage for measured children (in-memory for session)
if 'children_df' not in st.session_state:
    st.session_state.children_df = pd.DataFrame(columns=[
        'id','nama','ttl','jenis_kelamin','kelas','tanggal_ukur','umur_tahun','umur_bulan','berat_kg','tinggi_cm','z_haz','pct_h','status'
    ])

# ----------------------------- Home -----------------------------
if page == "Home":
    st.title("📊 Deteksi Status Gizi Anak — Edukatif & Non-Diagnostik")
    st.markdown("""
    Aplikasi ini membantu tenaga kesehatan, guru, atau orang tua **memetakan status gizi anak** berdasarkan standar WHO.

    **Fitur utama:**
    - Cek status gizi untuk usia 0–5 tahun dan 5–19 tahun menggunakan tabel LMS WHO.
    - Input data individu (nama, TTL, jenis kelamin, kelas) dan simpan hasil.
    - Download laporan PDF per anak dan unduh Excel semua hasil.
    - Visualisasi posisi pada kurva pertumbuhan dan persentil.
    - Kalkulator prediksi tinggi optimal berdasarkan tinggi orangtua.

    ⚠️ Hasil **bukan diagnosis medis**. Selalu rujuk tenaga medis profesional untuk penilaian klinis.
    """)

# ----------------------------- Page: 0-5 tahun -----------------------------
elif page == "Ukuran 0-5 tahun (WHO)":
    st.header("Deteksi Status Gizi Anak 0–5 tahun (WHO)")
    with st.form('form_0_5'):
        col1, col2 = st.columns(2)
        with col1:
            nama = st.text_input('Nama lengkap')
            ttl = st.date_input('Tanggal lahir', max_value=date.today())
            jenis = st.selectbox('Jenis kelamin', ['Laki-laki','Perempuan'])
            kelas = st.text_input('Kelas / Catatan (opsional)')
        with col2:
            tanggal_ukur = st.date_input('Tanggal ukur', value=date.today())
            umur_days = (tanggal_ukur - ttl).days
            umur_months = int(umur_days // 30)
            st.markdown(f"**Usia:** {umur_months} bulan (~{umur_days} hari)")
            berat = st.number_input('Berat (kg)', min_value=0.0, step=0.01)
            tinggi = st.number_input('Tinggi / Panjang (cm)', min_value=10.0, step=0.1)

        submitted = st.form_submit_button('Hitung & Simpan')
    if submitted:
        if lms_0_5.empty:
            st.error('Data WHO 0-5 tahun belum tersedia di folder data/. Silakan unduh dari situs WHO dan letakkan sebagai data/who_lms_0_5.csv')
        else:
            # find closest age row in months, matching sex
            df_sel = lms_0_5[(lms_0_5['age_months']==umur_months) & (lms_0_5['sex'].str.lower().str.startswith(jenis[0].lower()))]
            if df_sel.empty:
                st.warning('Tidak ditemukan baris LMS eksak untuk usia ini. Menggunakan interpolasi dari tabel WHO.')
                # nearest by age
                df_age = lms_0_5[lms_0_5['sex'].str.lower().str.startswith(jenis[0].lower())]
                if df_age.empty:
                    st.error('Data referensi WHO tidak lengkap untuk jenis kelamin ini.')
                else:
                    # linear interpolation on L,M,S by age
                    df_age_sorted = df_age.sort_values('age_months')
                    L = np.interp(umur_months, df_age_sorted['age_months'], df_age_sorted['L'])
                    M = np.interp(umur_months, df_age_sorted['age_months'], df_age_sorted['M'])
                    S = np.interp(umur_months, df_age_sorted['age_months'], df_age_sorted['S'])
                    z = lms_zscore(tinggi, L, M, S)
                    pct = z_to_pct(z)
            else:
                row = df_sel.iloc[0]
                z = lms_zscore(tinggi, float(row['L']), float(row['M']), float(row['S']))
                pct = z_to_pct(z)

            # status by HAZ
            if z < -3:
                status = 'Severe Stunting'
            elif z < -2:
                status = 'Stunting'
            elif z < -1:
                status = 'Risk'
            else:
                status = 'Normal'

            st.success(f"Z-score (HAZ): {z:.2f}  — Persentil global ≈ {pct:.1f}%")
            st.image(avatar_svg_base64(jenis, status))
            st.info('Hasil bersifat edukatif dan non-diagnostik.')

            # store
            new_id = len(st.session_state.children_df) + 1
            st.session_state.children_df.loc[len(st.session_state.children_df)] = [
                new_id, nama, ttl.isoformat(), jenis, kelas, tanggal_ukur.isoformat(), int(umur_months//12), int(umur_months%12), berat, tinggi, z, pct, status
            ]

# ----------------------------- Page: 5-19 tahun -----------------------------
elif page == "Ukuran 5-19 tahun (WHO)":
    st.header("Deteksi Status Gizi Anak & Remaja 5–19 tahun (WHO)")
    with st.form('form_5_19'):
        col1, col2 = st.columns(2)
        with col1:
            nama = st.text_input('Nama lengkap')
            ttl = st.date_input('Tanggal lahir', max_value=date.today())
            jenis = st.selectbox('Jenis kelamin', ['Laki-laki','Perempuan'])
            kelas = st.text_input('Kelas / Catatan (opsional)')
        with col2:
            tanggal_ukur = st.date_input('Tanggal ukur', value=date.today())
            umur_years = (tanggal_ukur - ttl).days / 365.25
            st.markdown(f"**Usia:** {umur_years:.2f} tahun")
            berat = st.number_input('Berat (kg)', min_value=0.0, step=0.01)
            tinggi = st.number_input('Tinggi (cm)', min_value=50.0, step=0.1)
        submitted = st.form_submit_button('Hitung & Simpan')
    if submitted:
        if lms_5_19.empty:
            st.error('Data WHO 5-19 tahun belum tersedia di folder data/. Silakan unduh dari situs WHO dan letakkan sebagai data/who_lms_5_19.csv')
        else:
            # age in years, use nearest interpolation
            df_sel = lms_5_19[(lms_5_19['sex'].str.lower().str.startswith(jenis[0].lower()))]
            if df_sel.empty:
                st.error('Data referensi WHO tidak lengkap untuk jenis kelamin ini.')
            else:
                age_col = 'age_years' if 'age_years' in df_sel.columns else 'age'
                ages = df_sel[age_col].values
                L = np.interp(umur_years, ages, df_sel['L'].values)
                M = np.interp(umur_years, ages, df_sel['M'].values)
                S = np.interp(umur_years, ages, df_sel['S'].values)
                z = lms_zscore(tinggi, L, M, S)
                pct = z_to_pct(z)

                if z < -3:
                    status = 'Severe Stunting'
                elif z < -2:
                    status = 'Stunting'
                elif z < -1:
                    status = 'Risk'
                else:
                    status = 'Normal'

                st.success(f"Z-score (HAZ): {z:.2f}  — Persentil global ≈ {pct:.1f}%")
                st.image(avatar_svg_base64(jenis, status))
                st.info('Hasil bersifat edukatif dan non-diagnostik.')

                new_id = len(st.session_state.children_df) + 1
                umur_y = int(umur_years)
                umur_m = int((umur_years - umur_y)*12)
                st.session_state.children_df.loc[len(st.session_state.children_df)] = [
                    new_id, nama, ttl.isoformat(), jenis, kelas, tanggal_ukur.isoformat(), umur_y, umur_m, berat, tinggi, z, pct, status
                ]

# ----------------------------- Batch Upload / Data -----------------------------
elif page == "Batch Upload / Data":
    st.header("Upload Excel / Lihat & Unduh Data")
    st.markdown("Unggah file Excel berisi kolom: nama, ttl, jenis_kelamin, kelas, tanggal_ukur, berat_kg, tinggi_cm. Aplikasi akan mencoba menghitung usia dan z-score jika WHO data tersedia.")
    uploaded = st.file_uploader('Upload Excel (.xlsx atau .csv)', type=['xlsx','csv'])
    if uploaded:
        try:
            if uploaded.name.lower().endswith('.csv'):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
            st.dataframe(df.head())
            # attempt simple processing
            if 'tanggal_ukur' not in df.columns:
                df['tanggal_ukur'] = pd.to_datetime('today')
            df['ttl'] = pd.to_datetime(df['ttl'])
            df['tanggal_ukur'] = pd.to_datetime(df['tanggal_ukur'])
            df['umur_days'] = (df['tanggal_ukur'] - df['ttl']).dt.days
            df['umur_months'] = (df['umur_days'] // 30).astype(int)
            # attempt zscore only for 0-5 if data available
            if not lms_0_5.empty:
                z_list = [];
                pct_list = [];
                status_list = [];
                for _, r in df.iterrows():
                    try:
                        umur = int(r['umur_months'])
                        sex = r['jenis_kelamin']
                        ht = float(r['tinggi_cm'])
                        df_sel = lms_0_5[(lms_0_5['age_months']==umur) & (lms_0_5['sex'].str.lower().str.startswith(sex[0].lower()))]
                        if df_sel.empty:
                            df_age = lms_0_5[lms_0_5['sex'].str.lower().str.startswith(sex[0].lower())]
                            L = np.interp(umur, df_age['age_months'], df_age['L'])
                            M = np.interp(umur, df_age['age_months'], df_age['M'])
                            S = np.interp(umur, df_age['age_months'], df_age['S'])
                        else:
                            rr = df_sel.iloc[0]
                            L, M, S = rr['L'], rr['M'], rr['S']
                        z = lms_zscore(ht, L, M, S)
                        pct = z_to_pct(z)
                        if z < -3:
                            status = 'Severe Stunting'
                        elif z < -2:
                            status = 'Stunting'
                        elif z < -1:
                            status = 'Risk'
                        else:
                            status = 'Normal'
                    except Exception:
                        z = np.nan; pct = np.nan; status = 'N/A'
                    z_list.append(z); pct_list.append(pct); status_list.append(status)
                df['z_haz'] = z_list
                df['pct_h'] = pct_list
                df['status'] = status_list
            st.session_state.children_df = pd.concat([st.session_state.children_df, df], ignore_index=True, sort=False)
            st.success('Data berhasil diunggah dan disimpan (sementara di session).')
        except Exception as e:
            st.error(f'Gagal memproses file: {e}')
    st.markdown('---')
    st.subheader('Data Hasil Pengukuran (session)')
    st.dataframe(st.session_state.children_df)

    # Download Excel
    if not st.session_state.children_df.empty:
        towrite = BytesIO()
        st.session_state.children_df.to_excel(towrite, index=False, sheet_name='hasil')
        towrite.seek(0)
        st.download_button('Unduh Excel Semua Data', data=towrite, file_name='hasil_pengukuran.xlsx')

# ----------------------------- Visualisasi -----------------------------
elif page == "Visualisasi Data":
    st.header('Visualisasi Data')
    df = st.session_state.children_df.copy()
    if df.empty:
        st.info('Belum ada data. Masukkan minimal 1 anak di halaman ukur.')
    else:
        st.subheader('Distribusi Status Gizi')
        st.bar_chart(df['status'].value_counts())
        st.subheader('Scatter: Tinggi vs Umur (bulan)')
        if 'umur_tahun' in df.columns:
            # convert to months
            df['age_months'] = df['umur_tahun'].fillna(0).astype(int)*12 + df['umur_bulan'].fillna(0).astype(int)
        else:
            df['age_months'] = df.get('umur_months', np.nan)
        st.plotly_chart = None
        try:
            import plotly.express as px
            fig = px.scatter(df, x='age_months', y='tinggi_cm', color='status', hover_data=['nama','jenis_kelamin'])
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.write('Install plotly untuk visual interaktif. Menampilkan tabel sebagai gantinya:')
            st.dataframe(df[['nama','age_months','tinggi_cm','status']])

# ----------------------------- Kalkulator Prediksi Tinggi -----------------------------
elif page == "Kalkulator Prediksi Tinggi":
    st.header('Kalkulator Prediksi Tinggi Anak (Perkiraan)')
    st.markdown('Metode mid-parental height (MPH) — hasil estimasi, bukan jaminan.')
    with st.form('form_mph'):
        col1, col2 = st.columns(2)
        with col1:
            tinggi_ortu_ayah = st.number_input('Tinggi ayah (cm)', min_value=100.0, max_value=250.0, step=0.1)
            tinggi_ortu_ibu = st.number_input('Tinggi ibu (cm)', min_value=100.0, max_value=250.0, step=0.1)
            sex = st.selectbox('Jenis kelamin anak', ['Laki-laki','Perempuan'])
        with col2:
            umur_anak = st.number_input('Usia anak saat ini (tahun)', min_value=0.0, max_value=19.0, step=0.1)
            tinggi_sekarang = st.number_input('Tinggi anak saat ini (cm)', min_value=30.0, max_value=250.0, step=0.1)
        btn = st.form_submit_button('Hitung Perkiraan')
    if btn:
        # MPH formula
        if sex == 'Laki-laki':
            mph = (tinggi_ortu_ayah + (tinggi_ortu_ibu + 13)) / 2
        else:
            mph = ((tinggi_ortu_ayah - 13) + tinggi_ortu_ibu) / 2
        lower = mph - 8.5
        upper = mph + 8.5
        st.success(f'Perkiraan tinggi dewasa anak: {mph:.1f} cm (kisaran {lower:.1f} — {upper:.1f} cm)')
        st.info('Ini perkiraan kasar (mid-parental height). Faktor nutrisi, penyakit kronis, dan lingkungan mempengaruhi hasil nyata.')

# ----------------------------- Tutorial Pengukuran -----------------------------
elif page == "Tutorial Pengukuran":
    st.header('Tutorial: Cara Mengukur Berat & Tinggi yang Benar')
    st.markdown('''
    1. Gunakan timbangan yang terkalibrasi untuk mengukur berat badan. Anak melepas sepatu dan pakaian tebal.
    2. Untuk anak <2 tahun: ukur panjang berbaring (recumbent length) menggunakan infantometer.
    3. Untuk anak ≥2 tahun: ukur tinggi berdiri (stadiometer) tanpa sepatu, tumit rapat, kepala mengikuti plane Frankfort.
    4. Catat tanggal lahir dan tanggal ukur dengan benar.
    5. Ulangi pengukuran 2 kali bila ragu, ambil rata-rata.
    6. Dokumentasikan kondisi (mis. sedang sakit, tanggal imunisasi, dsb.) karena dapat mempengaruhi berat/tinggi.
    ''')
    st.info('Panduan singkat — rujuk pedoman WHO untuk panduan lengkap pengukuran antropometri.')

# ----------------------------- Disclaimer -----------------------------
elif page == "Disclaimer":
    st.header('Disclaimer & Latar Belakang')
    st.markdown('''
    Aplikasi ini dibuat untuk tujuan edukasi dan pemantauan status gizi secara non-diagnostik.

    **Sumber standar:** Aplikasi menggunakan tabel LMS (Lambda-Mu-Sigma) yang disediakan oleh WHO Child Growth Standards untuk menghitung z-score (Height-for-Age Z-score / HAZ) yang biasa dipakai untuk mendeteksi stunting.

    **Catatan penting:**
    - Hasil yang diberikan **bukan pengganti pemeriksaan klinis**.
    - Untuk keputusan medis, rujuk ke petugas kesehatan atau dokter anak.

    ''')
    st.markdown('---')
    st.markdown('**Petunjuk teknis untuk developer / operator:**'
    1. Unduh data LMS WHO dari situs WHO (format CSV) dan simpan di folder `data/` seperti disebut di atas.
    2. Pastikan library `reportlab` (opsional untuk PDF), `plotly` (opsional), dan `scipy` terinstall.
    3. Jalankan: `pip install streamlit pandas numpy scipy reportlab plotly openpyxl`')

# ----------------------------- Extra: Generate PDF per anak -----------------------------
# Provide a small helper in sidebar if single selection exists
st.sidebar.markdown('---')
if not st.session_state.children_df.empty:
    st.sidebar.subheader('Ekspor & Pilih Anak')
    select_id = st.sidebar.selectbox('Pilih ID anak', st.session_state.children_df['id'].tolist())
    selected = st.session_state.children_df[st.session_state.children_df['id']==select_id].iloc[0]
    st.sidebar.text(f"Nama: {selected.get('nama','-')}")
    if REPORTLAB_AVAILABLE:
        if st.sidebar.button('Download PDF Laporan Anak'):
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            c.setFont('Helvetica', 12)
            c.drawString(50, 800, f"Laporan Hasil Pengukuran — {selected.get('nama','-')}")
            c.drawString(50, 780, f"Tanggal ukur: {selected.get('tanggal_ukur','-')}")
            c.drawString(50, 760, f"Jenis kelamin: {selected.get('jenis_kelamin','-')}")
            c.drawString(50, 740, f"Tinggi (cm): {selected.get('tinggi_cm','-')}")
            c.drawString(50, 720, f"Z-score HAZ: {selected.get('z_haz','-')}")
            c.drawString(50, 700, f"Status (non-diagnostik): {selected.get('status','-')}")
            c.drawString(50, 680, "Catatan: Hasil hanya untuk edukasi. Tidak menggantikan penilaian klinis.")
            c.showPage(); c.save()
            buffer.seek(0)
            st.sidebar.download_button('Unduh PDF', data=buffer, file_name=f"laporan_{select_id}.pdf")
    else:
        st.sidebar.info('ReportLab tidak tersedia — install reportlab untuk fitur PDF.')

# End of file
