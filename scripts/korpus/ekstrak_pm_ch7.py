#!/usr/bin/env python3
"""Ekstrak Bab 7 (Managing Problems) PM+ 18.5 menjadi chunk korpus.

Keluaran: data/src/pm_ch7_en.jsonl (chunk EN, 300--500 token, provenans halaman + bagian).

Aturan:
    - hanya halaman 49--57 (Bab 7) pada ref/pm_18-5_eng.txt
    - header/footer berulang, nomor halaman, dan catatan kaki dibuang
    - blok yang dimulai huruf kecil digabung ke blok sebelumnya (kelanjutan kalimat)
    - chunk dirakit dari kalimat utuh: tidak pernah memotong di tengah kalimat
    - label bagian = langkah (1--7) atau subjudul yang sedang berlaku saat blok dimulai
    - panjang 300--500 token memakai tokenizer BGE-M3 (ref/tok/tokenizer.json)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[2]
TOK = Tokenizer.from_file(str(ROOT / "ref" / "tok" / "tokenizer.json"))
HALAMAN_AWAL, HALAMAN_AKHIR = 49, 57
MIN_TOK, MAKS_TOK = 300, 500

BUANG = [
    re.compile(r"^\s*PM\+: INDIVIDUAL PSYCHOLOGICAL HELP.*$"),
    re.compile(r"^\s*CHAPTER 7\s*$"),
    re.compile(r"^\s*MANAGING PROBLEMS\s*$"),
    re.compile(r"^\s*\d{1,3}\s*$"),
    re.compile(r"^\s*(?:\d{1,2}\s+)?Source: Bowman.*$"),
    re.compile(r"^\s*The efficacy of self-examination therapy.*$"),
    re.compile(r"^\s*treatment of mild to moderate depression.*$"),
    re.compile(r"^\s*Psychotherapy Research, 5, 131.*$"),
    # potongan tabel lembar kerja dan kotak ringkasan bab yang rusak saat diekstrak
    re.compile(r"^\s*\(After the plan has been.*$"),
    re.compile(r"^\s*completed\)\s*$"),
    re.compile(r"^\s*REVIEW\s*$"),
    re.compile(r"^\s*•\s*$"),
    re.compile(r"^\s*•\s*(?:What types of problems|How to|The steps of Managing Problems)\s*$"),
    re.compile(r"^\s*In this chapter\s*$"),
    re.compile(r"^\s*you learned\s*$"),
]
LANGKAH = re.compile(r"^\s*(\d)\.\s+(Listing problems|Choose a problem|Define the problem|Brainstorm|"
                     r"Decide and choose|Action plan|Review)\s*$")
SUBJUDUL = [
    ("Overview of the steps in Managing Problems", "Ringkasan langkah"),
    ("Introducing Managing Problems", "Memperkenalkan Managing Problems"),
    ("Ongoing adversity or threat", "Kesulitan yang berlanjut"),
    ("Case example", "Contoh kasus"),
]
SINGKATAN = {"e.g.", "i.e.", "etc.", "vs.", "cf.", "no.", "Dr.", "Mr.", "Mrs.", "Ms."}


def token(teks: str) -> int:
    return len(TOK.encode(teks, add_special_tokens=False).ids)


def kalimat(teks: str) -> list[str]:
    kasar = re.split(r"(?<=[.!?])\s+", teks)
    hasil: list[str] = []
    for k in kasar:
        if hasil and hasil[-1].split()[-1].lstrip("(“\"") in SINGKATAN:
            hasil[-1] = hasil[-1] + " " + k
        else:
            hasil.append(k)
    return [k for k in hasil if k.strip()]


# Halaman yang dilewati: tabel lembar kerja Loma (grid dua kolom, rusak saat diekstrak)
# dan tabel ringkasan langkah (direkonstruksi sebagai teks tersendiri).
HALAMAN_LEWATI = {56}
BERHENTI = "Overview of the steps in Managing Problems"


def blok_halaman(teks_halaman: str, halaman: int) -> list[dict]:
    if halaman in HALAMAN_LEWATI:
        return []
    blok: list[dict] = []
    langkah, buf, buf_label = "", [], ""
    lompat = False

    def tutup():
        nonlocal buf
        if buf:
            t = " ".join(" ".join(buf).split())
            t = re.sub(r"([a-z])\.(\d{1,2})(?=\s)", r"\1.", t)   # penanda catatan kaki
            if len(t) >= 20:
                blok.append({"halaman": halaman, "bagian": buf_label, "teks": t})
            buf = []

    for b in teks_halaman.splitlines():
        if any(p.match(b) for p in BUANG):
            continue
        if not b.strip():
            tutup()
            continue
        if not buf:
            if b.strip().startswith(BERHENTI):
                lompat = True
            if lompat:
                continue
            m = LANGKAH.match(b)
            if m:
                langkah = m.group(0).strip()
            label = langkah
            for judul, nama in SUBJUDUL:
                if b.strip().startswith(judul):
                    label = nama
            buf_label = label
        buf.append(b.rstrip())
    tutup()
    return blok


def main() -> int:
    halaman = (ROOT / "ref" / "pm_18-5_eng.txt").read_text(encoding="utf-8").split("\f")
    blok: list[dict] = []
    for no in range(HALAMAN_AWAL, HALAMAN_AKHIR + 1):
        blok.extend(blok_halaman(halaman[no - 1], no))

    # gabung blok kelanjutan (dimulai huruf kecil) ke blok sebelumnya
    gabung: list[dict] = []
    for b in blok:
        if gabung and b["teks"][:1].islower():
            gabung[-1]["teks"] += " " + b["teks"]
            gabung[-1]["halaman"] = sorted(set(gabung[-1]["halaman"] + [b["halaman"]]))
            continue
        gabung.append({"halaman": [b["halaman"]], "bagian": b["bagian"], "teks": b["teks"]})

    unit: list[dict] = []
    for b in gabung:
        for s in kalimat(b["teks"]):
            unit.append({"halaman": b["halaman"], "bagian": b["bagian"], "teks": s,
                         "token": token(s)})

    chunk, buf, n = [], [], 0
    for i, u in enumerate(unit):
        berikut = unit[i + 1]["token"] if i + 1 < len(unit) else None
        if buf and n + u["token"] > MAKS_TOK and n >= MIN_TOK:
            chunk.append(buf)
            buf, n = [], 0
        buf.append(u)
        n += u["token"]
        if n >= MIN_TOK and (berikut is None or n + berikut > MAKS_TOK):
            chunk.append(buf)
            buf, n = [], 0
    if buf:
        chunk.append(buf)

    def total(c):
        return sum(u["token"] for u in c)

    # reimbang: chunk terakhir yang terlalu pendek menarik kalimat dari sebelumnya
    if len(chunk) > 1:
        while total(chunk[-1]) < MIN_TOK and len(chunk[-2]) > 1 and total(chunk[-2]) - chunk[-2][-1]["token"] >= MIN_TOK:
            chunk[-1].insert(0, chunk[-2].pop())
    # reimbang: chunk yang melampaui batas atas menumpahkan kalimat terakhirnya ke berikutnya
    for i in range(len(chunk) - 1):
        while total(chunk[i]) > MAKS_TOK and len(chunk[i]) > 2:
            chunk[i + 1].insert(0, chunk[i].pop())

    out = ROOT / "data" / "src"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "pm_ch7_en.jsonl").open("w", encoding="utf-8") as f:
        for i, c in enumerate(chunk, start=1):
            teks = " ".join(u["teks"] for u in c)
            hal = sorted({h for u in c for h in u["halaman"]})
            f.write(json.dumps({
                "id": f"pm-ch7-en-{i:03d}",
                "halaman": hal if len(hal) > 1 else hal[0],
                "bagian": next((u["bagian"] for u in c if u["bagian"]), ""),
                "teks": teks,
                "token": token(teks),
                "kata": len(teks.split()),
            }, ensure_ascii=False) + "\n")
    hasil = [json.loads(l)["token"] for l in (out / "pm_ch7_en.jsonl").open(encoding="utf-8")]
    print(f"{len(hasil)} chunk, token {sum(hasil)} (min {min(hasil)}, maks {max(hasil)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
