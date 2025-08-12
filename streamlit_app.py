# app.py
# Streamlit Stunting / Status Gizi (Non-Diagnostik)
# Pastikan meletakkan file WHO LMS pada folder who_standards/
#  - who_standards/who_0_5.csv  (kolom: age_months, sex (M/F), L, M, S)
#  - who_standards/who_5_19.csv (kolom: age_years, sex (M/F), L, M, S)

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
import base64

# plotting
import plotly.express as px

# stats
from scipy.stats import norm

# PDF (optional)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# ---------------------------
# Config
# ---------------------------
st.set_page_config(page_title='Deteksi Status Gizi Anak (Non-Diagnostik)', layout='wide')

WHO_0_5_PATH = 'who_standards/who_0_5.csv'
WHO_5_19_PATH = 'who_standards/who_5_19.csv'

# ---------------------------
# Utilities
# ---------------------------
@st.cache_data
def load_who(path):
    try:
        df = pd.read_csv(path)
        return df
    except Exception:
        return pd.DataFrame()

def lms_zscore(x, L, M, S):
    # LMS formula to compute z-score
    if abs(L) < 1e-8:
        return np.log(x / M) / S
    return ((x / M) ** L - 1) / (L * S)

def z_to_percentile(z):
    return float(norm.cdf(z) * 100)

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

def make_pdf_from_record(rec):
    """
    Returns BytesIO buffer. If reportlab missing, returns buffer with message.
    """
    buffer = BytesIO()
    if not REPORTLAB_AVAILABLE:
        buffer.write(b'PDF generation requires reportlab. Install reportlab to enable PDF export.')
        buffer.seek(0)
        return buffer
    c = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    c.setFont('Helvetica-Bold', 14)
    c.drawString(50, y, 'Laporan Pengukuran — Edukatif (Non-Diagnostik)')
    y -= 28
    c.setFont('Helvetica', 11)
    for k in ['nama','ttl','jenis_kelamin','kelas','tanggal_ukur','umur_tahun','umur_bulan','berat_kg','tinggi_cm','z_haz','percentile','status']:
        val = rec.get(k, '-')
        c.drawString(50, y, f"{k.replace('_',' ').title()}: {val}")
        y -= 18
    y -= 6
    c.drawString(50, y, "Catatan: Hasil hanya untuk edukasi dan pemantauan. Bukan diagnosis medis.")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ---------------------------
# Load WHO tables
# ---------------------------
who_0_5 = load_who(WHO_0_5_PATH)
who_5_19 = load_who(WHO_5_19_PATH)

# ---------------------------
# Session storage
# ---------------------------
if 'df_children' not in st.session_state:
    st.session_state.df_children = pd.DataFrame(columns=[
        'id','nama','ttl','jenis_kelamin','kelas','tanggal_ukur','umur_tahun','umur_bulan','berat_kg','tinggi_cm','z_haz','percentile','status'
    ])

# ---------------------------
# Sidebar & Navigation
# ---------------------------
st.sidebar.title('Menu')
page = st.sidebar.radio('Pilih Halaman', [
    'Home','Deteksi 0-5 tahun','Deteksi 5-19 tahun','Batch & Data','Visualisasi','Kalkulator Tinggi','Tutorial Pengukuran','Disclaimer'
])

st.sidebar.markdown('---')
if not st.session_state.df_children.empty:
    # prepare excel bytes
    excel_buf = BytesIO()
    with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
        st.session_state.df_children.to_excel(writer, index=False, sheet_name='hasil')
    excel_buf.seek(0)
    st.sidebar.download_button('📥 Unduh Semua Hasil (Excel)', data=excel_buf, file_name='hasil_pengukuran.xlsx')

# ---------------------------
# Home
# ---------------------------
if page == 'Home':
    st.title('📏 Deteksi Status Gizi Anak — Edukatif & Non-Diagnostik')
    st.markdown("""
Aplikasi ini membantu memantau status gizi (tinggi terhadap umur) berdasarkan standar WHO.
Hasil bersifat **edukatif**, **bukan diagnosis medis**.
- Gunakan *Deteksi 0-5 tahun* untuk bayi/balita (WHO Child Growth Standards).
- Gunakan *Deteksi 5-19 tahun* untuk anak & remaja (WHO Growth Reference).
""")
    c1, c2 = st.columns([2,1])
    with c1:
        st.header('Mulai Pemantauan')
        st.write('- Pilih halaman deteksi sesuai usia anak.')
        st.write('- Unggah batch Excel jika ingin memproses banyak anak sekaligus.')
        st.write('- Lihat ringkasan & grafik di halaman Visualisasi.')
    with c2:
        st.image(avatar_svg_base64('M','Normal'), width=140)
        st.image(avatar_svg_base64('F','Risk'), width=140)

# ---------------------------
# Helper: process store
# ---------------------------
def process_and_store(nama, ttl, jenis, kelas, tanggal_ukur, berat, tinggi, who_df, age_mode='months'):
    # date types
    if isinstance(ttl, str):
        ttl = datetime.fromisoformat(ttl).date()
    if isinstance(tanggal_ukur, str):
        tanggal_ukur = datetime.fromisoformat(tanggal_ukur).date()
    days = (tanggal_ukur - ttl).days
    umur_months = int(days // 30)
    umur_years = int(days // 365.25)
    umur_m = umur_months % 12

    sex_code = 'M' if jenis.lower().startswith('l') or jenis.lower().startswith('m') else 'F'

    if who_df.empty:
        return None, 'WHO standard file not available. Taruh CSV pada folder who_standards/'

    # choose interpolation basis
    df_sex = who_df[who_df['sex'].str.upper().str.startswith(sex_code)]
    if df_sex.empty:
        return None, 'WHO data tidak memiliki entri untuk jenis kelamin ini.'

    if age_mode == 'months':
        # column age_months expected
        if 'age_months' not in df_sex.columns:
            # try first column as ages
            ages = df_sex.iloc[:,0].values
        else:
            ages = df_sex['age_months'].values
        L = np.interp(umur_months, ages, df_sex['L'].values)
        M = np.interp(umur_months, ages, df_sex['M'].values)
        S = np.interp(umur_months, ages, df_sex['S'].values)
    else:
        # years (age decimal)
        if 'age_years' not in df_sex.columns:
            ages = df_sex.iloc[:,0].values
        else:
            ages = df_sex['age_years'].values
        age_dec = (tanggal_ukur - ttl).days / 365.25
        L = np.interp(age_dec, ages, df_sex['L'].values)
        M = np.interp(age_dec, ages, df_sex['M'].values)
        S = np.interp(age_dec, ages, df_sex['S'].values)

    z = lms_zscore(tinggi, L, M, S)
    pct = z_to_percentile(z)
    if z < -3:
        status = 'Severe Stunting'
    elif z < -2:
        status = 'Stunting'
    elif z < -1:
        status = 'Risk'
    else:
        status = 'Normal'

    rec = {
        'id': len(st.session_state.df_children) + 1,
        'nama': nama,
        'ttl': ttl.isoformat(),
        'jenis_kelamin': jenis,
        'kelas': kelas,
        'tanggal_ukur': tanggal_ukur.isoformat(),
        'umur_tahun': umur_years,
        'umur_bulan': umur_m,
        'berat_kg': round(float(berat) if not pd.isna(berat) else np.nan,2),
        'tinggi_cm': round(float(tinggi),2),
        'z_haz': round(float(z),2),
        'percentile': round(float(pct),1),
        'status': status
    }
    st.session_state.df_children = pd.concat([st.session_state.df_children, pd.DataFrame([rec])], ignore_index=True, sort=False)
    return rec, None

# ---------------------------
# Deteksi 0-5 tahun
# ---------------------------
if page == 'Deteksi 0-5 tahun':
    st.header('Deteksi 0–5 tahun (WHO Child Growth Standards)')
    st.info('Gunakan standar WHO Child Growth Standards (LMS).')

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
                st.warning('Anak berada di bawah standar tinggi menurut WHO. Pertimbangkan konsultasi dengan tenaga kesehatan, perbaikan nutrisi, dan pemeriksaan lebih lanjut.')
            elif rec['status']=='Risk':
                st.info('Anak sedikit di bawah median. Pantau pertumbuhan dan pastikan asupan gizi seimbang.')
            else:
                st.success('Tinggi anak berada di kisaran normal. Pertahankan pola makan dan aktivitas sehat.')

            if REPORTLAB_AVAILABLE:
                pdf_buf = make_pdf_from_record(rec)
                st.download_button('📄 Unduh Laporan PDF', data=pdf_buf, file_name=f"laporan_{rec['id']}.pdf")

# ---------------------------
# Deteksi 5-19 tahun
# ---------------------------
if page == 'Deteksi 5-19 tahun':
    st.header('Deteksi 5–19 tahun (WHO Growth Reference)')
    st.info('Gunakan WHO Growth Reference (LMS).')

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
                st.warning('Anak berada di bawah standar tinggi menurut WHO. Pertimbangkan konsultasi dengan tenaga kesehatan, perbaikan nutrisi, dan pemeriksaan lebih lanjut.')
            elif rec['status']=='Risk':
                st.info('Anak sedikit di bawah median. Pantau pertumbuhan dan pastikan asupan gizi seimbang.')
            else:
                st.success('Tinggi anak berada di kisaran normal. Pertahankan pola makan dan aktivitas sehat.')

            if REPORTLAB_AVAILABLE:
                pdf_buf = make_pdf_from_record(rec)
                st.download_button('📄 Unduh Laporan PDF', data=pdf_buf, file_name=f"laporan_{rec['id']}.pdf")

# ---------------------------
# Batch & Data
# ---------------------------
if page == 'Batch & Data':
    st.header('Batch Upload & Data')
    st.write('Unggah file Excel/CSV untuk memproses banyak anak sekaligus. Kolom saran: nama, ttl (YYYY-MM-DD), jenis_kelamin, kelas, tanggal_ukur, berat_kg, tinggi_cm')
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
                        kelas = r.get('kelas','')
                        tanggal_ukur = pd.to_datetime(r.get('tanggal_ukur', pd.Timestamp(date.today()))).date()
                        berat = float(r.get('berat_kg', np.nan))
                        tinggi = float(r.get('tinggi_cm', np.nan))
                        days = (tanggal_ukur - ttl).days
                        if days/365.25 < 5:
                            who = who_0_5
                            mode = 'months'
                        else:
                            who = who_5_19
                            mode = 'years'
                        rec, err = process_and_store(nama, ttl, jenis, kelas, tanggal_ukur, berat, tinggi, who, age_mode=('months' if mode=='months' else 'years'))
                        if rec:
                            count += 1
                    except Exception:
                        continue
                st.success(f'Berhasil memproses sekitar {count} baris dan menambah ke session.')
        except Exception as e:
            st.error('Gagal membaca file: ' + str(e))

    st.markdown('---')
    st.subheader('Tabel Hasil (session)')
    st.dataframe(st.session_state.df_children)

# ---------------------------
# Visualisasi
# ---------------------------
if page == 'Visualisasi':
    st.header('Visualisasi Data')
    df = st.session_state.df_children.copy()
    if df.empty:
        st.info('Belum ada data. Masukkan minimal 1 anak di halaman Deteksi atau unggah batch.')
    else:
        with st.expander('Filter'):
            genders = st.multiselect('Jenis kelamin', options=df['jenis_kelamin'].unique(), default=list(df['jenis_kelamin'].unique()))
            statuses = st.multiselect('Status', options=df['status'].unique(), default=list(df['status'].unique()))
            dff = df[df['jenis_kelamin'].isin(genders) & df['status'].isin(statuses)]

        st.subheader('Distribusi Status Gizi')
        bar = px.bar(dff['status'].value_counts().reset_index().rename(columns={'index':'status','status':'count'}), x='status', y='count', color='status')
        st.plotly_chart(bar, use_container_width=True)

        st.subheader('Tinggi vs Usia (bulan)')
        df['age_months'] = df['umur_tahun'].fillna(0).astype(int)*12 + df['umur_bulan'].fillna(0).astype(int)
        scatter = px.scatter(df, x='age_months', y='tinggi_cm', color='status', hover_data=['nama','jenis_kelamin'])
        st.plotly_chart(scatter, use_container_width=True)

        st.subheader('Rata-rata Tinggi per Kelas')
        if 'kelas' in df.columns:
            agg = df.groupby('kelas')['tinggi_cm'].mean().reset_index().sort_values('tinggi_cm',ascending=False)
            st.table(agg)

# ---------------------------
# Kalkulator Tinggi
# ---------------------------
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

# ---------------------------
# Tutorial Pengukuran
# ---------------------------
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

# ---------------------------
# Disclaimer
# ---------------------------
if page == 'Disclaimer':
    st.header('Disclaimer & Latar Belakang')
    st.markdown('''
Aplikasi ini dibuat untuk tujuan edukasi dan pemantauan. Standar yang dipakai:
- WHO Child Growth Standards (0–5 years): LMS tables (Height-for-age, Weight-for-age, etc.)
- WHO Growth Reference (5–19 years): LMS tables (Height-for-age, BMI-for-age, etc.)

Hasil yang diberikan **bukan diagnosis medis**. Untuk keputusan klinis, rujuk tenaga kesehatan.

Teknis: letakkan file LMS WHO pada folder `who_standards/` dengan nama `who_0_5.csv` dan `who_5_19.csv`.
''')

# End of file
