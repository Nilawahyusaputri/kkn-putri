# -------------------------------
# Grafik Distribusi Z-score dengan Warna Kategori (versi baru)
# -------------------------------
st.subheader("📈 Distribusi Z-score dengan Kategori Warna")

# Fungsi untuk menentukan kategori (versi baru)
def kategori_zscore(z):
    if z < -3:
        return "Severely Stunted (sangat pendek)"
    elif -3 <= z < -2:
        return "Stunted (pendek)"
    elif -2 <= z <= 2:
        return "Normal"
    elif 2 < z <= 3:
        return "Tall (tinggi)"
    else:
        return "Very Tall (sangat tinggi)"

# Mapping warna baru
color_map = {
    "Severely Stunted (sangat pendek)": "darkred",
    "Stunted (pendek)": "red",
    "Normal": "green",
    "Tall (tinggi)": "blue",
    "Very Tall (sangat tinggi)": "purple"
}

# Tambahkan kolom kategori di dataframe
df_all["Kategori Z-score"] = df_all["Z-score"].apply(kategori_zscore)

# Hitung jumlah anak per Z-score dan kategori
df_zscore_counts = df_all.groupby(["Z-score", "Kategori Z-score"]).size().reset_index(name="Jumlah")

# Plot
fig, ax = plt.subplots(figsize=(8, 5))
for idx, row in df_zscore_counts.iterrows():
    ax.bar(row["Z-score"], row["Jumlah"], color=color_map[row["Kategori Z-score"]], width=0.15)

# Garis batas kategori WHO baru
ax.axvline(x=-3, color="darkred", linestyle="--", label="Batas Severely Stunted (-3)")
ax.axvline(x=-2, color="red", linestyle="--", label="Batas Stunted (-2)")
ax.axvline(x=2, color="blue", linestyle="--", label="Batas Tall (2)")
ax.axvline(x=3, color="purple", linestyle="--", label="Batas Very Tall (3)")

# Label dan judul
ax.set_xlabel("Z-score")
ax.set_ylabel("Jumlah Anak")
ax.set_title("Distribusi Z-score Anak Berdasarkan Kategori")
ax.legend()

st.pyplot(fig)
