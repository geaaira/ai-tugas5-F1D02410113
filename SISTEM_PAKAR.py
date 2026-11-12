"""
Sistem Pakar Kondisi Tanaman dan Buah Nanas
Metode   : Certainty Factor (CF) dengan penelusuran maju (forward chaining)
Mesin    : ditulis sendiri, hanya memakai library bawaan Python (json, sys)
Jalankan : python sistem_pakar_nanas.py [file_aturan.json]
"""
import json
import sys

# Skala keyakinan user, mengikuti Tabel 4 makalah S1.
# nomor jawaban -> (label, nilai CF[E])
SKALA = {
    "0": ("tidak", 0.0),
    "1": ("ragu-ragu", 0.2),
    "2": ("mungkin", 0.4),
    "3": ("sangat mungkin", 0.6),
    "4": ("hampir pasti", 0.8),
    "5": ("pasti", 1.0),
}


def muat_kb(path):
    """Baca file aturan JSON dan periksa isinya."""
    with open(path, encoding="utf-8") as f:
        kb = json.load(f)
    for r in kb["aturan"]:
        if r["sumber"] not in kb["sumber"]:
            raise ValueError(f"{r['id']}: sumber '{r['sumber']}' tidak ada di daftar sumber")
        if r["mode"] not in ("dan", "atau"):
            raise ValueError(f"{r['id']}: mode harus 'dan' atau 'atau'")
        if not 0 < r["cf"] <= 1:
            raise ValueError(f"{r['id']}: cf harus lebih dari 0 dan paling besar 1")
    return kb


def fakta_untuk_ditanya(aturan):
    """Fakta yang tidak pernah menjadi hasil aturan (tidak ada di 'maka') ditanyakan ke user."""
    hasil_aturan = {r["maka"] for r in aturan}
    urut = []
    for r in aturan:
        for f in r["jika"]:
            if f not in hasil_aturan and f not in urut:
                urut.append(f)
    return urut


# ------------------------------------------------------------------ input user
def tanya(daftar_fakta):
    """Tanya tiap fakta dengan skala 0-5. Hanya fakta ber-CF > 0 masuk memori."""
    print("Skala jawaban: " + ", ".join(f"{n} = {lab}" for n, (lab, _) in SKALA.items()))
    memori = {}
    for i, fakta in enumerate(daftar_fakta, 1):
        while True:
            jawab = input(f"{i}. Apakah {fakta}? (0-5) > ").strip()
            if not sys.stdin.isatty():
                print(jawab)  # kalau input dari pipa/file, tampilkan jawabannya supaya terbaca
            if jawab in SKALA:
                break
            print("   Masukkan angka 0 sampai 5.")
        cf = SKALA[jawab][1]
        if cf > 0:
            memori[fakta] = cf
    return memori


# ------------------------------------------------------------- rumus CF
def cf_premis(aturan, memori):
    """Mode 'dan' -> nilai terkecil (min), mode 'atau' -> nilai terbesar (maks)."""
    nilai = [memori.get(f, 0.0) for f in aturan["jika"]]
    return min(nilai) if aturan["mode"] == "dan" else max(nilai)


def gabung(cf1, cf2):
    """CFcombine untuk dua bukti positif pada kesimpulan yang sama."""
    return cf1 + cf2 * (1 - cf1)


# ------------------------------------------------------ mesin penelusuran maju
def inferensi(aturan, memori):
    """
    Forward chaining dengan CF. Tiap aturan diperiksa tepat satu kali.
    Aturan baru boleh diperiksa kalau SEMUA aturan yang menghasilkan premisnya
    sudah diperiksa, supaya CF fakta turunan sudah final sebelum dipakai.
    Mengembalikan kontribusi: fakta -> daftar aturan yang menghasilkannya.
    """
    penghasil = {}  # fakta -> id aturan yang bisa menghasilkannya
    for r in aturan:
        penghasil.setdefault(r["maka"], set()).add(r["id"])

    diperiksa = set()
    kontribusi = {}
    siklus = 0
    print("\n--- Penelusuran maju ---")
    while len(diperiksa) < len(aturan):
        siap = [r for r in aturan
                if r["id"] not in diperiksa
                and all(pid in diperiksa for f in r["jika"] for pid in penghasil.get(f, ()))]
        if not siap:
            raise ValueError("Aturan saling bergantung secara melingkar, periksa file aturan.")

        baris = []
        for r in siap:
            diperiksa.add(r["id"])
            cfp = cf_premis(r, memori)
            if cfp <= 0:
                continue  # syarat tidak terpenuhi, aturan tidak dijalankan
            cf_baru = cfp * r["cf"]
            catatan = ""
            if r["maka"] in memori:  # kesimpulan sudah punya CF -> gabungkan
                lama = memori[r["maka"]]
                memori[r["maka"]] = gabung(lama, cf_baru)
                catatan = f" | digabung dengan CF lama {lama:.2f} -> {memori[r['maka']]:.2f}"
            else:
                memori[r["maka"]] = cf_baru
            kontribusi.setdefault(r["maka"], []).append({"aturan": r, "cfp": cfp, "cf": cf_baru})
            syarat = (" DAN " if r["mode"] == "dan" else " ATAU ").join(r["jika"])
            baris.append(f"  {r['id']}: {syarat} -> {r['maka']} | "
                         f"{cfp:.2f} x {r['cf']:.2f} = {cf_baru:.2f}{catatan}")
        if baris:
            siklus += 1
            print(f"Siklus {siklus}:")
            print("\n".join(baris))
    print(f"Siklus {siklus + 1}: tidak ada aturan baru, berhenti")
    return kontribusi


# --------------------------------------------------------------------- alasan
def jelaskan(fakta, memori, kontribusi, tingkat=1):
    """Cetak alasan sebuah kesimpulan; premis hasil aturan lain ditelusuri ke belakang."""
    sp = "  " * tingkat
    print(f"{sp}{fakta} (CF {memori[fakta]:.2f} = {memori[fakta] * 100:.0f}%)")
    berjalan = None
    for k in kontribusi[fakta]:
        r = k["aturan"]
        sambung = " DAN " if r["mode"] == "dan" else " ATAU "
        syarat = sambung.join(f"{f} ({memori.get(f, 0):.2f})" for f in r["jika"])
        op = "CF premis" if len(r["jika"]) == 1 else ("min" if r["mode"] == "dan" else "maks")
        print(f"{sp}  <- {r['id']} [{r['sumber']}]: {syarat}")
        print(f"{sp}     {op} = {k['cfp']:.2f}; {k['cfp']:.2f} x CF aturan {r['cf']:.2f} = {k['cf']:.2f}")
        for f in r["jika"]:
            if f in kontribusi:  # premis ini hasil aturan lain
                jelaskan(f, memori, kontribusi, tingkat + 3)
        if berjalan is None:
            berjalan = k["cf"]
        else:
            baru = gabung(berjalan, k["cf"])
            print(f"{sp}     gabung: {berjalan:.2f} + {k['cf']:.2f} x (1 - {berjalan:.2f}) = {baru:.2f}")
            berjalan = baru


# ---------------------------------------------------------------------- utama
def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "kb_nanas.json"
    kb = muat_kb(path)
    aturan = kb["aturan"]

    print(kb["judul"])
    memori = tanya(fakta_untuk_ditanya(aturan))

    print()
    if memori:
        print("Fakta awal: " + ", ".join(f"{f} ({cf:.2f})" for f, cf in memori.items()))
    else:
        print("Fakta awal: tidak ada")

    kontribusi = inferensi(aturan, memori)

    # kesimpulan akhir = hasil aturan yang tidak dipakai lagi sebagai premis aturan lain
    dipakai_sebagai_premis = {f for r in aturan for f in r["jika"]}
    akhir = sorted((f for f in kontribusi if f not in dipakai_sebagai_premis),
                   key=lambda f: -memori[f])

    print("\nKesimpulan:")
    if not akhir:
        print("  Tidak ada kesimpulan: tidak ada aturan yang syaratnya terpenuhi.")
    else:
        for i, f in enumerate(akhir, 1):
            print(f"  {i}. {f} (CF {memori[f]:.2f} = {memori[f] * 100:.0f}%)")
        print("\nAlasan:")
        for f in akhir:
            jelaskan(f, memori, kontribusi)
        dipakai = sorted({k["aturan"]["sumber"] for ks in kontribusi.values() for k in ks})
        print("\nSumber yang dipakai:")
        for s in dipakai:
            print(f"  {s}: {kb['sumber'][s]}")

    print("\nCatatan: " + kb["batas"])


if __name__ == "__main__":
    main()