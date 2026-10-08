#!/usr/bin/env python3
"""
Harga Sembako Scraper
=====================
Mengambil harga rata-rata komoditas barang kebutuhan pokok (sembako) dari
SP2KP Kemendag (api-sp2kp.kemendag.go.id, endpoint publik tanpa login),
lalu memperbarui tabel harga di README.md dengan kategori per komoditas.

Cara pakai:
    python3 scrape_harga.py            # update README.md
    python3 scrape_harga.py --print    # hanya tampilkan hasil di terminal

Tidak butuh API key / dependensi eksternal (stdlib murni, Python 3.8+).
"""
import json
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta

API = "https://api-sp2kp.kemendag.go.id/report/api/average-price-komoditas-public"
README = "README.md"

# Kategori & satuan standar komoditas Bapokingu (per untung/SP2KP)
KATEGORI = {
    "Sem Bahan Pokok": [
        ("Beras", "kg"), ("Jagung", "kg"), ("Kedelai", "kg"),
        ("Tepung Terigu", "kg"), ("Mie Instan", "pcs"),
    ],
    "Daging & Telur": [
        ("Daging Ayam", "kg"), ("Daging Ruminansia", "kg"),
        ("Telur Ayam", "kg"), ("Ikan", "kg"), ("Udang", "kg"),
    ],
    "Sayur & Buah": [
        ("Bawang", "kg"), ("Cabai", "kg"), ("Tomat", "kg"),
        ("Kentang", "kg"), ("Kacang Panjang", "kg"), ("Kangkung", "kg"),
        ("Sawi Hijau", "kg"), ("Kacang-Kacangan", "kg"), ("Ketimun", "kg"),
        ("Ketela Pohon", "kg"), ("Jeruk", "kg"), ("Pisang", "kg"),
    ],
    "Lainnya": [
        ("Gula", "kg"), ("Minyak Sawit", "liter"), ("Garam", "kg"), ("Susu", "liter"),
    ],
}

WIB = timezone(timedelta(hours=7))


def fetch(tanggal):
    """Ambil harga level-1 (rata-rata per provinsi) untuk satu tanggal."""
    url = f"{API}?tipe_komoditas_id=1&tanggal={tanggal}&take=5000&level=1"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["data"]


def latest_dates():
    url = "https://api-sp2kp.kemendag.go.id/report/api/latest-price-dates?tipe_komoditas_id=1"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)["data"]
    return d["tanggal"], d["tanggal_pembanding"]


def agg(data):
    """Agregasi: nama komoditas -> (rata-rata nasional, min, max, #provinsi)."""
    buckets = defaultdict(list)
    for x in data:
        buckets[x["komoditas"]["nama"]].append(x["harga"])
    out = {}
    for nama, vals in buckets.items():
        out[nama] = {
            "avg": sum(vals) / len(vals),
            "min": min(vals),
            "max": max(vals),
            "n": len(vals),
        }
    return out


BULAN_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
            "Agustus", "September", "Oktober", "November", "Desember"]


def tgl_id(iso):
    d = datetime.fromisoformat(iso)
    return f"{d.day} {BULAN_ID[d.month - 1]} {d.year}"


def rupiah(v):
    return f"Rp{v:,.0f}".replace(",", ".")


def pct(a, b):
    if not b:
        return "–"
    p = (a - b) / b * 100
    if p > 0.05:
        return f"▲ {p:.2f}%"
    if p < -0.05:
        return f"▼ {abs(p):.2f}%"
    return "▬ 0.00%"


def build_table(cur, prev):
    lines = []
    lines.append("| Komoditas | Satuan | Harga Rata-rata | Terendah | Tertinggi | Perubahan |")
    lines.append("|---|---|---|---|---|---|")
    used = set()
    for kategori, items in KATEGORI.items():
        lines.append(f"| **{kategori}** | | | | | |")
        for nama, unit in items:
            if nama not in cur:
                continue
            used.add(nama)
            c = cur[nama]
            p = prev.get(nama)
            change = pct(c["avg"], p["avg"] if p else None)
            lines.append(
                f"| {nama} | {unit} | **{rupiah(c['avg'])}** | {rupiah(c['min'])} "
                f"| {rupiah(c['max'])} | {change} |"
            )
    extra = sorted(set(cur) - used)
    if extra:
        lines.append("| **Komoditas Lainnya** | | | | | |")
        for nama in extra:
            c = cur[nama]
            p = prev.get(nama)
            change = pct(c["avg"], p["avg"] if p else None)
            lines.append(
                f"| {nama} | kg | **{rupiah(c['avg'])}** | {rupiah(c['min'])} "
                f"| {rupiah(c['max'])} | {change} |"
            )
    return "\n".join(lines)


def main():
    show_only = "--print" in sys.argv
    tgl, tgl_prev = latest_dates()
    print(f"Tanggal data : {tgl} (pembanding: {tgl_prev})")
    cur = agg(fetch(tgl))
    prev = agg(fetch(tgl_prev))
    table = build_table(cur, prev)

    if show_only:
        print(table)
        return

    now = datetime.now(WIB)
    updated = now.strftime(f"%d {BULAN_ID[now.month - 1]} %Y, %H:%M WIB")
    tgl_id_str = tgl_id(tgl)

    header = f"""# 🛒 Harga Sembako Terbaru

Pantauan harga rata-rata **26 komoditas barang kebutuhan pokok (sembako)** tingkat provinsi di seluruh Indonesia, dikelompokkan per kategori agar mudah dibaca. Data diperbarui otomatis **setiap 6 jam** oleh script scraper di repo ini.

> 📅 **Data per tanggal: {tgl_id_str}** — terakhir diperbarui: {updated}

## 📊 Tabel Harga Sembako

{table}
"""
    footer = """
## 📈 Keterangan

- **Harga Rata-rata** — rata-rata harga di seluruh provinsi Indonesia
- **Terendah / Tertinggi** — harga termurah & termahal antar provinsi
- **Perubahan** — dibanding hari sebelumnya: ▲ naik · ▼ turun · ▬ stabil

## ⚙️ Cara Kerja

Script `scrape_harga.py` mengambil data harga dari sistem pemantauan pasar kebutuhan pokok Kemendag (SP2KP), mengagregasinya per komoditas, lalu memperbarui tabel di halaman ini secara otomatis. Berjalan setiap 6 jam via cron.

Jalankan sendiri:

```bash
python3 scrape_harga.py          # update README.md
python3 scrape_harga.py --print  # lihat hasil di terminal
```

Tanpa dependensi eksternal — cukup Python 3.8+.

---

*by PT. Pastiin Siber Indonesia*
"""

    # Sisipkan tabel antara header dan footer
    content = header + "\n" + table + "\n" + footer
    with open(README, "w") as f:
        f.write(content)
    print(f"README.md diperbarui ({len(cur)} komoditas, tanggal {tgl})")


if __name__ == "__main__":
    main()
