# -------------------------------
# Visualisasi distribusi Z-score (versi lebih informatif)
# -------------------------------
if st.session_state.data_anak:
    st.subheader("📈 Distribusi Z-score Anak")

    df_all = pd.DataFrame(st.session_state.data_anak)

    # Histogram Z-score dengan warna sesuai kategori
    fig, ax = plt.subplots(figsize=(8, 5))

    # Definisikan kategori WHO dan warnanya
    kategori_ranges = [
        ("Severe Stunted", -np.inf, -3, "darkred"),
        ("Stunted", -3, -2, "red"),
        ("Perlu Perhatian", -2, -1, "orange"),
        ("Normal", -1, 3, "green"),
        ("Tall", 3, np.inf, "blue")
    ]

    for label, low, high, color in kategori_ranges:
        subset = df_all[(df_all["Z-score"] > low) & (df_all["Z-score"] <= high)]
        ax.hist(subset["Z-score"], bins=10, color=color, edgecolor="black", alpha=0.7, label=label)

    # Garis batas WHO
    ax.axvline(x=-3, color="darkred", linestyle="--")
    ax.axvline(x=-2, color="red", linestyle="--")
    ax.axvline(x=-1, color="orange", linestyle="--")
    ax.axvline(x=3, color="blue", linestyle="--")

    # Garis rata-rata
    mean_z = df_all["Z-score"].mean()
    ax.axvline(mean_z, color="black", linestyle=":", label=f"Rata-rata: {mean_z:.2f}")

    # Anotasi batas kategori
    batas_kategori = { -3: "Severe Stunted", -2: "Stunted", -1: "Perlu Perhatian", 3: "Tall" }
    for batas, teks in batas_kategori.items():
        ax.text(batas, ax.get_ylim()[1]*0.9, teks, rotation=90, va='top', ha='center', fontsize=9, color="black")

    ax.set_title("Distribusi Status Gizi (Z-score HFA) Anak Usia Sekolah", fontsize=14, weight='bold')
    ax.set_xlabel("Z-score Tinggi terhadap Umur (HFA)")
    ax.set_ylabel("Jumlah Anak")
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    ax.legend()
    st.pyplot(fig)

    # -------------------------------
    # Grafik tambahan: jumlah anak per kategori
    # -------------------------------
    st.subheader("📊 Jumlah Anak per Kategori Status Gizi")

    kategori_order = ["Severe Stunted", "Stunted", "Perlu Perhatian", "Normal", "Tall"]
    warna_map = {
        "Severe Stunted": "darkred",
        "Stunted": "red",
        "Perlu Perhatian": "orange",
        "Normal": "green",
        "Tall": "blue"
    }

    kategori_count = df_all["Status"].value_counts().reindex(kategori_order).fillna(0)

    fig2, ax2 = plt.subplots(figsize=(6, 4))
    ax2.bar(kategori_count.index, kategori_count.values,
            color=[warna_map[k] for k in kategori_count.index], edgecolor="black")

    for i, val in enumerate(kategori_count.values):
        ax2.text(i, val + 0.1, str(int(val)), ha='center', fontsize=10)

    ax2.set_title("Jumlah Anak per Kategori WHO", fontsize=14, weight='bold')
    ax2.set_ylabel("Jumlah Anak")
    ax2.set_xlabel("Kategori Status Gizi")
    ax2.grid(axis="y", linestyle=":", alpha=0.6)
    st.pyplot(fig2)
