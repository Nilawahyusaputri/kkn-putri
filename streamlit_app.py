# Streamlit Stunting App
# File: streamlit_stunting_app.py
# Deskripsi: Aplikasi edukatif untuk memantau status gizi anak menggunakan standar WHO.
# Fitur:
# - Halaman Home
# - Halaman deteksi 0-5 tahun (WHO Child Growth Standards - LMS)
# - Halaman deteksi 5-19 tahun (WHO Growth Reference - LMS)\# - Input identitas anak: Nama, TTL, Jenis Kelamin, Kelas
# - Menampilkan usia, z-score, persentil global, avatar sesuai jenis kelamin & status
# - Saran non-diagnostik, download PDF per anak, download Excel semua data
# - Visualisasi data (grafik interaktif), batch upload
# - Tutorial pengukuran & Disclaimer
# - Kalkulator prediksi tinggi berdasarkan mid-parental height

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from math import isnan
import base64

# Plotting
import plotly.express as px
import plotly.graph_objects as go

# PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# ------------------------------- Configuration -------------------------------
st.set_page_config(page_title='Deteksi Status Gizi (Non-Diagnostik)', layout='wide')

WHO_0_5_PATH = 'who_standards/who_0_5.csv'   # LMS table: age_months, sex (M/F), L, M, S
WHO_5_19_PATH = 'who_standards/who_5_19.csv' # LMS table: age_years, sex (M/F), L, M, S

# ------------------------------- Utilities -------------------------------
@st.cache_data
def load_who(path):
    try:
        df = pd.read_csv(path)
        return df
    except Exception:
        return pd.DataFrame()

# LMS to Z-score
def lms_zscore(x, L, M, S):
    # Handle L close to zero
    if abs(L) < 1e-8:
        return np.log(x / M) / S
    return ((x / M) ** L - 1) / (L * S)

from scipy.stats import norm

def z_to_percentile(z):
    return float(norm.cdf(z) * 100)

# Avatar generator fallback (SVG encoded)
def avatar_svg_base64(sex='M', status='Normal'):
    colors = {'Normal':'#2ecc71','Risk':'#f1c40f','Stunting':'#e67e22','Severe Stunting':'#c0392b'}
    color = colors.get(status, '#95a5a6')
    label = 'L' if sex=='M' else 'P'
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'>
    <rect width='100%' height='100%' rx='20' fill='#f7f9f9'/>
    <circle cx='90' cy='50' r='36' fill='{color}' stroke='#2c3e50' stroke-width='2'/>
    <rect x='46' y='96' width='88' height='56' rx='12' fill='{color}' opacity='0.9'/>
    <text x='90' y='154' text-anchor='middle' font-size='12' fill='#2c3e50'>{label} | {status}</text>
    </svg>"""
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()

# PDF helper
def make_pdf_record(row):
    buffer = BytesIO()
    if not REPORTLAB_AVAILABLE:
        buffer.write(b'PDF generation requires reportlab. Install reportlab to enable this feature.')
        buffer.seek(0)
        return buffer
    c = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    c.setFont('Helvetica-Bold', 14)
    c.drawString(50, y, 'Laporan Pengukuran — Hasil Edukatif (Non-Diagnostik)')
    y -= 30
    c.setFont('Helvetica', 11)
    for k in ['nama','ttl','jenis_kelamin','kelas','tanggal_ukur','umur_tahun','umur_bulan','berat_kg','tinggi_cm','z_haz','percentile','status']:
        val = row.get(k,'-')
        c.drawString(50, y, f"{k.replace('_',' ').title()}: {val}")
        y -= 18
    c.drawString(50, y-6, 'Catatan: Hasil hanya untuk edukasi dan pemantauan. Bukan diagnosis medis.')
    c.showPage(); c.save()
    buffer.seek(0)
    return buffer

# ------------------------------- Load WHO Data -------------------------------
who_0_5 = load_who(WHO_0_5_PATH)
who_5_19 = load_who(WHO_5_19_PATH)

# ------------------------------- Session State -------------------------------
if 'df_children' not in st.session_state:
    st.session_state.df_children = pd.DataFrame(columns=[
        'id','nama','ttl','jenis_kelamin','kelas','tanggal_ukur','umur_tahun','umur_bulan','berat_kg','tinggi_cm','z_haz','percentile','status'
    ])

# ------------------------------- Layout: Sidebar -------------------------------
st.sidebar.title('Menu')
page = st.sidebar.radio('Pilih halaman', [
    'Home', 'Deteksi 0-5 tahun', 'Deteksi 5-19 tahun', 'Batch & Data', 'Visualisasi', 'Kalkulator Tinggi', 'Tutorial Pengukuran', 'Disclaimer'
])

# Quick export in sidebar
st.sidebar.markdown('---')
if not st.session_state.df_children.empty:
    st.sidebar.download_button('📥 Unduh Semua Hasil (Excel)', data=st.session_state.df_children.to_excel(index=False, engine='openpyxl', sheet_name='hasil'), file_name='hasil_pengukuran.xlsx')

# ------------------------------- Page: Home -------------------------------
if page == 'Home':
    st.title('📏 Deteksi Status Gizi Anak — Edukatif & Non-Diagnostik')
    st.markdown(
        'Aplikasi ini memanfaatkan standar WHO (LMS) untuk memetakan posisi tinggi anak terhadap referensi internasional. Hasil hanya untuk edukasi dan pemantauan; bukan diagnosis medis.'
    )
    c1, c2 = st.columns([2,1])
    with c1:
        st.header('Mulai pemantauan')
        st.write('- Pilih halaman **Deteksi 0-5 tahun** atau **Deteksi 5-19 tahun** untuk menginput data.
- Unggah batch Excel di halaman **Batch & Data** untuk input banyak anak.
- Lihat ringkasan dan grafik di halaman **Visualisasi**.')
    with c2:
        st.image(avatar_svg_base64('M','Normal'), width=160)
        st.image(avatar_svg_base64('F','Risk'), width=160)

# ------------------------------- Helper: compute and store -------------------------------
def process_and_store(nama, ttl, jenis, kelas, tanggal_ukur, berat, tinggi, who_df, age_mode='months'):
    # compute age
    if isinstance(ttl, str):
        ttl = datetime.fromisoformat(ttl).date()
    if isinstance(tanggal_ukur, str):
        tanggal_ukur = datetime.fromisoformat(tanggal_ukur).date()
    days = (tanggal_ukur - ttl).days
    umur_months = int(days // 30)
    umur_years = int(days // 365.25)
    umur_m = umur_months % 12

    sex_code = 'M' if jenis.lower().startswith('l') or jenis.lower().startswith('m') else 'F'

    # select LMS
    if who_df.empty:
        return None, 'WHO data not available'
    if age_mode == 'months':
        # interpolate L M S by age in months
        df_sex = who_df[who_df['sex'].str.upper().str.startswith(sex_code)]
        if 'age_months' in df_sex.columns:
            ages = df_sex['age_months'].values
        else:
            ages = df_sex.iloc[:,0].values
        L = np.interp(umur_months, ages, df_sex['L'].values)
        M = np.interp(umur_months, ages, df_sex['M'].values)
        S = np.interp(umur_months, ages, df_sex['S'].values)
    else:
        # years
        df_sex = who_df[who_df['sex'].str.upper().str.startswith(sex_code)]
        if 'age_years' in df_sex.columns:
            ages = df_sex['age_years'].values
        else:
            ages = df_sex.iloc[:,0].values
        age_dec = (tanggal_ukur - ttl).days / 365.25
        L = np.interp(age_dec, ages, df_sex['L'].values)
        M = np.interp(age_dec, ages, df_sex['M'].values)
        S = np.interp(age_dec, ages, df_sex['S'].values)

    z = lms_zscore(tinggi, L, M, S)
    pct = z_to_percentile(z)
    # classify HAZ (height-for-age)
    if z < -3:
        status = 'Severe Stunting'
    elif z < -2:
        status = 'Stunting'
    elif z < -1:
        status = 'Risk'
    else:
        status = 'Normal'

    record = {
        'id': len(st.session_state.df_children) + 1,
        'nama': nama,
        'ttl': ttl.isoformat(),
        'jenis_kelamin': jenis,
        'kelas': kelas,
        'tanggal_ukur': tanggal_ukur.isoformat(),
        'umur_tahun': umur_years,
        'umur_bulan': umur_m,
        'berat_kg': berat,
        'tinggi_cm': tinggi,
        'z_haz': round(float(z),2),
        'percentile': round(float(pct),1),
        'status': status
    }
    st.session_state.df_children = pd.concat([st.session_state.df_children, pd.DataFrame([record])], ignore_index=True, sort=False)
    return record, None

# ------------------------------- Page: Deteksi 0-5 tahun -------------------------------
if page == 'Deteksi 0-5 tahun':
    st.header('Deteksi 0–5 tahun (WHO Child Growth Standards)')
    st.info('Standar WHO Child Growth Standards (0-5y) — dihitung dengan metode LMS (L, M, S).')
    with st.form('form_0_5'):
        col1, col2 = st.columns(2)
        with col1:
            nama = st.text_input('Nama lengkap')
            ttl = st.date_input('Tanggal lahir', max_value=date.today())
            jenis = st.selectbox('Jenis kelamin', ['Laki-laki','Perempuan'])
            kelas = st.text_input('Kelas / Catatan (opsional)')
        with col2:
            tanggal_ukur = st.date_input('Tanggal ukur', value=date.today())
            berat = st.number_input('Berat (kg)', min_value=0.0, step=0.01)
            tinggi = st.number_input('Panjang / Tinggi (cm)', min_value=10.0, step=0.1)
            st.write('Catatan: untuk <24 bulan gunakan panjang berbaring (recumbent length).')
        submitted = st.form_submit_button('Hitung & Simpan')
    if submitted:
        rec, err = process_and_store(nama, ttl, jenis, kelas, tanggal_ukur, berat, tinggi, who_0_5, age_mode='months')
        if err:
            st.error(err)
        else:
            st.success(f"Z-score (HAZ): {rec['z_haz']}  — Persentil global ≈ {rec['percentile']}%")
            st.image(avatar_svg_base64('M' if jenis.startswith('L') else 'F', rec['status']), width=160)
            st.subheader('Saran singkat (non-diagnostik)')
            if rec['status'] in ['Severe Stunting','Stunting']:
                st.warning('Anak berada di bawah standar tinggi menurut WHO. Pertimbangkan konsultasi dengan tenaga kesehatan, perbaikan nutrisi dan pemeriksaan lebih lanjut.')
            elif rec['status']=='Risk':
                st.info('Anak sedikit di bawah median. Pantau pertumbuhan dan pastikan asupan gizi seimbang.')
            else:
                st.success('Tinggi anak berada di kisaran normal. Pertahankan pola makan dan aktivitas sehat.')
            if REPORTLAB_AVAILABLE:
                pdf = make_pdf_record(rec)
                st.download_button('📄 Unduh Laporan PDF', data=pdf, file_name=f"laporan_{rec['id']}.pdf")

# ------------------------------- Page: Deteksi 5-19 tahun -------------------------------
if page == 'Deteksi 5-19 tahun':
    st.header('Deteksi 5–19 tahun (WHO Growth Reference)')
    st.info('Standar WHO Growth Reference 5-19 tahun — dihitung dengan metode LMS (L, M, S).')
    with st.form('form_5_19'):
        col1, col2 = st.columns(2)
        with col1:
            nama = st.text_input('Nama lengkap')
            ttl = st.date_input('Tanggal lahir', max_value=date.today())
            jenis = st.selectbox('Jenis kelamin', ['Laki-laki','Perempuan'])
            kelas = st.text_input('Kelas / Catatan (opsional)')
        with col2:
            tanggal_ukur = st.date_input('Tanggal ukur', value=date.today())
            berat = st.number_input('Berat (kg)', min_value=0.0, step=0.01)
            tinggi = st.number_input('Tinggi (cm)', min_value=50.0, step=0.1)
        submitted = st.form_submit_button('Hitung & Simpan')
    if submitted:
        rec, err = process_and_store(nama, ttl, jenis, kelas, tanggal_ukur, berat, tinggi, who_5_19, age_mode='years')
        if err:
            st.error(err)
        else:
            st.success(f"Z-score (HAZ): {rec['z_haz']}  — Persentil global ≈ {rec['percentile']}%")
            st.image(avatar_svg_base64('M' if jenis.startswith('L') else 'F', rec['status']), width=160)
            st.subheader('Saran singkat (non-diagnostik)')
            if rec['status'] in ['Severe Stunting','Stunting']:
                st.warning('Anak berada di bawah standar tinggi menurut WHO. Pertimbangkan konsultasi dengan tenaga kesehatan, perbaikan nutrisi dan pemeriksaan lebih lanjut.')
            elif rec['status']=='Risk':
                st.info('Anak sedikit di bawah median. Pantau pertumbuhan dan pastikan asupan gizi seimbang.')
            else:
                st.success('Tinggi anak berada di kisaran normal. Pertahankan pola makan dan aktivitas sehat.')
            if REPORTLAB_AVAILABLE:
                pdf = make_pdf_record(rec)
                st.download_button('📄 Unduh Laporan PDF', data=pdf, file_name=f"laporan_{rec['id']}.pdf")

# ------------------------------- Page: Batch & Data -------------------------------
if page == 'Batch & Data':
    st.header('Batch Upload & Data')
    st.write('Unggah file Excel/CSV untuk memproses banyak anak sekaligus. Kolom yang disarankan: nama, ttl (YYYY-MM-DD), jenis_kelamin, kelas, tanggal_ukur, berat_kg, tinggi_cm')
    uploaded = st.file_uploader('Upload .xlsx / .csv', type=['xlsx','csv'])
    if uploaded:
        try:
            if uploaded.name.lower().endswith('.csv'):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
            st.dataframe(df.head())
            if st.button('Proses file dan simpan ke session'):
                count = 0
                for _, r in df.iterrows():
                    try:
                        nama = r.get('nama')
                        ttl = pd.to_datetime(r.get('ttl')).date()
                        jenis = r.get('jenis_kelamin')
                        kelas = r.get('kelas', '')
                        tanggal_ukur = pd.to_datetime(r.get('tanggal_ukur', pd.Timestamp(date.today()))).date()
                        berat = float(r.get('berat_kg', np.nan))
                        tinggi = float(r.get('tinggi_cm', np.nan))
                        # choose who table by age
                        days = (tanggal_ukur - ttl).days
                        if days/365.25 < 5:
                            who = who_0_5
                            mode='months'
                        else:
                            who = who_5_19
                            mode='years'
                        rec, err = process_and_store(nama, ttl, jenis, kelas, tanggal_ukur, berat, tinggi, who, age_mode='months' if mode=='months' else 'years')
                        if rec:
                            count += 1
                    except Exception:
                        continue
                st.success(f'Berhasil memproses ~{count} baris dan menambah ke session.')
        except Exception as e:
            st.error('Gagal membaca file: ' + str(e))
    st.markdown('---')
    st.subheader('Tabel Hasil (session)')
    st.dataframe(st.session_state.df_children)

# ------------------------------- Page: Visualisasi -------------------------------
if page == 'Visualisasi':
    st.header('Visualisasi Data')
    df = st.session_state.df_children.copy()
    if df.empty:
        st.info('Belum ada data. Masukkan minimal 1 anak di halaman Deteksi atau unggah batch.')
    else:
        # filters
        with st.expander('Filter'):
            genders = st.multiselect('Jenis kelamin', options=df['jenis_kelamin'].unique(), default=df['jenis_kelamin'].unique())
            statuses = st.multiselect('Status', options=df['status'].unique(), default=df['status'].unique())
            dff = df[df['jenis_kelamin'].isin(genders) & df['status'].isin(statuses)]
        st.subheader('Distribusi Status Gizi')
        fig = px.bar(dff['status'].value_counts().reset_index().rename(columns={'index':'status','status':'count'}), x='status', y='count', color='status')
        st.plotly_chart(fig, use_container_width=True)

        st.subheader('Tinggi vs Usia')
        # compute total months
        df['age_months'] = df['umur_tahun'].fillna(0).astype(int)*12 + df['umur_bulan'].fillna(0).astype(int)
        fig2 = px.scatter(df, x='age_months', y='tinggi_cm', color='status', hover_data=['nama','jenis_kelamin'])
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader('Rata-rata Tinggi per Kelas')
        if 'kelas' in df.columns:
            agg = df.groupby('kelas')['tinggi_cm'].mean().reset_index().sort_values('tinggi_cm',ascending=False)
            st.table(agg)

# ------------------------------- Page: Kalkulator Tinggi -------------------------------
if page == 'Kalkulator Tinggi':
    st.header('Kalkulator Prediksi Tinggi Dewasa (Perkiraan)')
    st.write('Metode: Mid-Parental Height (MPH). Hanya estimasi kasar.')
    col1, col2 = st.columns(2)
    with col1:
        tinggi_ayah = st.number_input('Tinggi Ayah (cm)', value=170.0)
        tinggi_ibu = st.number_input('Tinggi Ibu (cm)', value=160.0)
    with col2:
        jenis = st.selectbox('Jenis kelamin anak', ['Laki-laki','Perempuan'])
        tinggi_saat_ini = st.number_input('Tinggi anak saat ini (cm)', value=100.0)
    if st.button('Hitung Prediksi'):
        if jenis.startswith('L'):
            mph = (tinggi_ayah + (tinggi_ibu + 13)) / 2
        else:
            mph = ((tinggi_ayah - 13) + tinggi_ibu) / 2
        lower = mph - 8.5
        upper = mph + 8.5
        st.success(f'Perkiraan tinggi dewasa: {mph:.1f} cm (kisaran {lower:.1f} — {upper:.1f} cm)')
        st.info('Faktor nutrisi, penyakit, dan lingkungan mempengaruhi realisasi tinggi.')

# ------------------------------- Page: Tutorial Pengukuran -------------------------------
if page == 'Tutorial Pengukuran':
    st.header('Tutorial: Cara Mengukur Berat & Tinggi yang Benar')
    st.markdown('''
1. Berat: gunakan timbangan terkalibrasi, anak melepas pakaian tebal dan sepatu.
2. Panjang (<2 tahun): ukur berbaring (recumbent length) dengan infantometer.
3. Tinggi (>=2 tahun): ukur berdiri tanpa sepatu, tumit rapat, kepala pada plane Frankfort.
4. Catat tanggal lahir & tanggal ukur dengan benar.
5. Ulangi 2 kali bila perlu, catat kondisi anak.
''')
    st.info('Rujuk pedoman WHO untuk panduan pengukuran antropometri lengkap.')

# ------------------------------- Page: Disclaimer -------------------------------
if page == 'Disclaimer':
    st.header('Disclaimer & Latar Belakang')
    st.markdown('''
Aplikasi ini dibuat untuk tujuan edukasi dan pemantauan. Standar yang dipakai:
- WHO Child Growth Standards (0–5 years): LMS tables (Height-for-age, Weight-for-age, etc.)
- WHO Growth Reference (5–19 years): LMS tables (Height-for-age, BMI-for-age, etc.)

Hasil yang diberikan **bukan diagnosis medis**. Untuk keputusan klinis, rujuk tenaga kesehatan.

Teknis: untuk akurasi, letakkan file LMS WHO pada folder `who_standards/` dengan nama `who_0_5.csv` dan `who_5_19.csv`.
''')

# ------------------------------- End -------------------------------

# Note: Developer should provide WHO LMS CSV files with columns: age_months or age_years, sex, L, M, S
# Example columns (0-5): age_months, sex, L, M, S
# Example columns (5-19): age_years, sex, L, M, S
