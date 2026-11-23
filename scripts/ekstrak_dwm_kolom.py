#!/usr/bin/env python3
"""Ekstraksi ulang korpus DWM dengan urutan baca sadar-kolom (opsi A).

Masalah yang diperbaiki: `pdftotext -layout` mencampur kolom balon percakapan pada 61/132
halaman edisi Inggris dan 49/132 halaman edisi Indonesia, sehingga kalimat saling menyilang.
Skrip ini memakai `pdftotext -bbox-layout`, yang memecah halaman menjadi blok berkoordinat,
lalu menyusun urutan baca dari blok itu dan membuang label gambar serta nomor halaman.

Aturan:
    - blok yang seluruh katanya label gambar (23A, 22.5E) atau nomor halaman dibuang
    - fragmen dekoratif 1--3 huruf kapital dibuang
    - kata di akhir baris yang dipenggal ('-' + lanjutan huruf kecil) digabung
    - halaman dengan dua blok tinggi berdampingan diperlakukan dua kolom (urut x lalu y),
      halaman lain diurutkan (y, x) mengikuti posisi balon
    - segmentasi 300--500 token pada batas kalimat, memakai tokenizer BGE-M3

Keluaran (belum menimpa korpus):
    data/src/dwm_en_v2.txt / dwm_id_v2.txt
    data/src/dwm_en_v2.jsonl / dwm_id_v2.jsonl

Pemakaian:
    python3 eksperimen/ekstrak_dwm_kolom.py
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "ref"
SRC = ROOT / "data" / "src"
TOK = Tokenizer.from_file(str(REF / "tok" / "tokenizer.json"))
MIN_TOK, MAKS_TOK, TARGET_TOK = 300, 500, 310
DOKUMEN = {
    "en": ("who_dwm_eng.pdf", "who-dwm-2020-eng", "CC BY-NC-SA 3.0 IGO (WHO 2020, ISBN 978-92-4-000391-0)"),
    "id": ("who_dwm_id.pdf", "who-dwm-2020-ind", "CC BY-NC-SA 3.0 IGO (WHO SEARO 2020, ISBN 978-92-4-000391-0)"),
}
POLA_LABEL = re.compile(r"^\d{1,2}(?:\.\d{1,2})?[A-F]$")      # label gambar: 23A, 22.5E
POLA_ANGKA = re.compile(r"^\d{1,3}$")                          # nomor halaman (dicek posisinya)
POLA_FRAGMEN = re.compile(r"^[A-Z]{1,3}$")
POLA_JUDUL = re.compile(r"^(?:Part|Bagian)\s+\d+\s*:\s*.+$", re.I)
# Halaman parateks yang tidak masuk korpus (lisensi, daftar isi, pengantar, peninjau, pustaka).
POLA_PARATEKS = re.compile(
    r"(ISBN\s+978-92-4|Daftar isi|Contents|Preface|Pengantar|Acknowledg|Ucapan terima kasih|"
    r"Book review|Peninjauan buku|References|Daftar pustaka|© World Health Organization|"
    r"Some rights reserved|Sebagian hak dilindungi)", re.I)


def token(teks: str) -> int:
    return len(TOK.encode(teks, add_special_tokens=False).ids)


def bbox(pdf: Path) -> str:
    keluaran = Path("/home/chrisg/.hermes/cache/scratch") / (pdf.stem + "_bbox2.html")
    if not keluaran.exists():
        subprocess.run(["pdftotext", "-bbox-layout", str(pdf), str(keluaran)], check=True)
    return keluaran.read_text(encoding="utf-8", errors="replace")


def blok_halaman(xml_halaman: str, tinggi: float, lebar: float) -> list[dict]:
    hasil = []
    for potong in re.findall(r"<block[^>]*>(.*?)</block>", xml_halaman, re.S):
        kepala = re.match(r"<block xMin=\"([\d.]+)\" yMin=\"([\d.]+)\" xMax=\"([\d.]+)\" yMax=\"([\d.]+)\"", potong)
        # atribut bbox ada di tag pembuka blok; ambil dari potongan penuh
        baris = []
        for ln in re.findall(r"<line[^>]*>(.*?)</line>", potong, re.S):
            kata = [html.unescape(w) for w in re.findall(r"<word[^>]*>([^<]*)</word>", ln)]
            kata = [k for k in kata if not POLA_LABEL.match(k) and not POLA_FRAGMEN.match(k)]
            if kata:
                baris.append(kata)
        teks = gabung_baris(baris)
        if not teks.strip():
            continue
        if POLA_JUDUL.match(teks):
            hasil.append({"teks": "", "judul": teks, "y0": 0.0, "y1": 0.0, "x0": 0.0,
                          "tinggi": tinggi, "lebar": lebar})
            continue                                  # header berjalan: label bagian, bukan isi
        ys_atas = min(float(y) for y in re.findall(r'yMin="([\d.]+)"', potong))
        if POLA_ANGKA.match(teks) and (ys_atas < 0.05 * tinggi or ys_atas > 0.90 * tinggi):
            continue                                  # nomor halaman di margin atas/bawah
        kata_teks = teks.split()
        if len(kata_teks) <= 4 and not re.search(r"[a-z]", teks):
            continue                                  # label diagram/huruf dekoratif
        ys = [float(y) for y in re.findall(r'yMin="([\d.]+)"', potong)]
        xs = [float(x) for x in re.findall(r'xMin="([\d.]+)"', potong)]
        if not ys or not xs:
            continue
        hasil.append({"teks": teks, "y0": min(ys), "y1": max(float(v) for v in re.findall(r'yMax="([\d.]+)"', potong)),
                      "x0": min(xs), "tinggi": tinggi, "lebar": lebar})
    return hasil


def gabung_baris(baris: list[list[str]]) -> str:
    teks = ""
    for kata in baris:
        if teks.endswith("-") and kata and kata[0][:1].islower():
            teks = teks[:-1] + kata[0] + " " + " ".join(kata[1:]) + " "
        else:
            teks += " ".join(kata) + " "
    return re.sub(r"\s+", " ", teks).strip()


def urutkan(blok: list[dict], tinggi_halaman: float) -> list[dict]:
    tinggi_blok = [b["y1"] - b["y0"] for b in blok]
    kolom = [b for b in blok if (b["y1"] - b["y0"]) > 0.45 * tinggi_halaman]
    if len(kolom) >= 2:
        # dua kolom teks: urutkan per kolom (x), lalu y
        return sorted(blok, key=lambda b: (round(b["x0"] / 10), b["y0"]))
    return sorted(blok, key=lambda b: (round(b["y0"] / 4), b["x0"]))


HALAMAN_AWAL = 7          # sampul, halaman hak cipta, dan daftar isi tidak masuk korpus


def halaman_ke_teks(xml: str, nama: str) -> list[dict]:
    hasil = []
    for i, halaman in enumerate(re.split(r"<page\b", xml)[1:], start=1):
        if i < HALAMAN_AWAL:
            continue
        dimensi = re.search(r'width="([\d.]+)" height="([\d.]+)"', halaman)
        lebar, tinggi = (float(dimensi.group(1)), float(dimensi.group(2))) if dimensi else (595.0, 842.0)
        blok = blok_halaman(halaman, tinggi, lebar)
        if not blok:
            continue
        bagian = ""
        for b in blok:
            if b.get("judul"):
                bagian = b["judul"]
        isi = [b for b in blok if b["teks"]]
        teks = " ".join(b["teks"] for b in urutkan(isi, tinggi))
        if len(teks.split()) < 15:
            continue
        if POLA_PARATEKS.search(teks):
            continue
        hasil.append({"halaman": i, "bagian": bagian, "teks": teks})
    return hasil


def pecah_panjang(teks: str, batas: int = 380) -> list[str]:
    """Potong teks yang terlalu panjang pada tanda baca, supaya tidak ada unit > batas."""
    if token(teks) <= batas:
        return [teks]
    potong = re.split(r"(?<=[.!?;:])\s+", teks)
    hasil, buf = [], ""
    for p in potong:
        if buf and token(buf + " " + p) > batas:
            hasil.append(buf.strip())
            buf = p
        else:
            buf = (buf + " " + p).strip()
    if buf:
        hasil.append(buf.strip())
    akhir = []
    for h in hasil:                      # sisa yang masih > batas dipotong di koma
        if token(h) <= batas:
            akhir.append(h)
            continue
        buf = ""
        for bagian in re.split(r"(?<=,)\s+", h):
            if buf and token(buf + " " + bagian) > batas:
                akhir.append(buf.strip())
                buf = bagian
            else:
                buf = (buf + " " + bagian).strip()
        if buf:
            akhir.append(buf.strip())
    return akhir


def kalimat(teks: str) -> list[str]:
    kasar = re.split(r"(?<=[.!?])\s+", teks)
    hasil = []
    for k in kasar:
        if hasil and hasil[-1].split()[-1].lstrip("(“\"") in {"e.g.", "i.e.", "etc.", "vs.", "no."}:
            hasil[-1] += " " + k
        else:
            hasil.append(k)
    return [k.strip() for k in hasil if k.strip()]


def rakit(halaman: list[dict], bahasa: str) -> list[dict]:
    unit = []
    bagian = ""
    for h in halaman:
        if h["bagian"]:
            bagian = h["bagian"]
        for kal in kalimat(h["teks"]):
            for s in pecah_panjang(kal):
                unit.append({"halaman": h["halaman"], "bagian": bagian, "teks": s, "token": token(s)})

    chunk, buf, n = [], [], 0
    for i, u in enumerate(unit):
        berikut = unit[i + 1]["token"] if i + 1 < len(unit) else None
        if buf and n + u["token"] > MAKS_TOK and n >= MIN_TOK:
            chunk.append(buf)
            buf, n = [], 0
        buf.append(u)
        n += u["token"]
        if n >= MIN_TOK and (berikut is None or n + berikut > MAKS_TOK or n >= TARGET_TOK):
            chunk.append(buf)
            buf, n = [], 0
    if buf:
        chunk.append(buf)

    def total(c):
        return sum(x["token"] for x in c)

    if len(chunk) > 1:
        while total(chunk[-1]) < MIN_TOK and len(chunk[-2]) > 1 and total(chunk[-2]) - chunk[-2][-1]["token"] >= MIN_TOK:
            chunk[-1].insert(0, chunk[-2].pop())
        # chunk pertama yang terlalu pendek menarik kalimat dari chunk berikutnya
        while (len(chunk) > 1 and total(chunk[0]) < MIN_TOK and len(chunk[1]) > 1
               and total(chunk[0]) + chunk[1][0]["token"] <= MAKS_TOK):
            chunk[0].append(chunk[1].pop(0))
    for i in range(len(chunk) - 1):
        while total(chunk[i]) > MAKS_TOK and len(chunk[i]) > 2:
            chunk[i + 1].insert(0, chunk[i].pop())

    hasil = []
    for i, c in enumerate(chunk, start=1):
        teks = " ".join(x["teks"] for x in c)
        hal = sorted({x["halaman"] for x in c})
        hasil.append({
            "id": f"dwm-{bahasa}-{i:03d}",
            "bahasa": bahasa,
            "sumber": DOKUMEN[bahasa][1],
            "lisensi": DOKUMEN[bahasa][2],
            "halaman": hal if len(hal) > 1 else hal[0],
            "bagian": next((x["bagian"] for x in c if x["bagian"]), ""),
            "teks": teks,
            "token": token(teks),
            "kata": len(teks.split()),
        })
    return hasil


def main() -> int:
    for bahasa, (berkas, sumber, lisensi) in DOKUMEN.items():
        xml = bbox(REF / berkas)
        halaman = halaman_ke_teks(xml, berkas)
        butir = rakit(halaman, bahasa)
        SRC.mkdir(parents=True, exist_ok=True)
        with (SRC / f"dwm_{bahasa}_v2.txt").open("w", encoding="utf-8") as f:
            for d in butir:
                f.write(f"### {d['id']}\n")
                f.write(f"<!-- halaman: {d['halaman']}; token: {d['token']}; bagian: {d['bagian'] or '-'} -->\n")
                f.write(f"{d['teks']}\n\n")
        with (SRC / f"dwm_{bahasa}_v2.jsonl").open("w", encoding="utf-8") as f:
            for d in butir:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        tok = [d["token"] for d in butir]
        kata = sum(d["kata"] for d in butir)
        print(f"{bahasa}: {len(butir)} chunk | token {min(tok)}–{max(tok)} total {sum(tok)} | kata {kata} | "
              f"halaman berisi {len(halaman)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
