# -------------------------------
# Fungsi Klasifikasi WHO + Edukasi (versi baru)
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
        return "Very Tall", "purple", "Pastikan tinggi anak sesuai potensi genetik dan sehat."

# -------------------------------
# Fungsi kategori untuk grafik
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
# Mapping warna kategori
# -------------------------------
status_color_map = {
    "Severely Stunted": "darkred",
    "Stunted": "red",
    "Normal": "green",
    "Tall": "blue",
    "Very Tall": "purple"
}

# -------------------------------
# Urutan kategori untuk grafik distribusi per gender
# -------------------------------
status_order = ["Severely Stunted", "Stunted", "Normal", "Tall", "Very Tall"]
