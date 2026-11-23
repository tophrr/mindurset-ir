#!/usr/bin/env python3
"""Ekstrak satu bab PM+ 18.5 menjadi chunk korpus (Inggris).

Generalisasi dari eksperimen/ekstrak_pm_ch7.py: halaman, nomor bab, dan judul bab
diberikan lewat argumen, aturan pembersihan dan segmentasi sama.

Pemakaian:
    python3 eksperimen/ekstrak_pm_bab.py --halaman 45-48 --bab 6 --judul "MANAGING STRESS" \
        --keluaran data/src/pm_ch6_en.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
TOK = Tokenizer.from_file(str(ROOT / "ref" / "tok" / "tokenizer.json"))
MIN_TOK, MAKS_TOK = 300, 500
SINGKATAN = {"e.g.", "i.e.", "etc.", "vs.", "cf.", "no.", "Dr.", "Mr.", "Mrs.", "Ms."}
HALAMAN_LEWATI: set[int] = set()


def token(teks: str) -> int:
    return len(TOK.encode(teks, add_special_tokens=False).ids)


def pola_buang(judul: str) -> list[re.Pattern]:
    return [
        re.compile(r"^\s*PM\+: INDIVIDUAL PSYCHOLOGICAL HELP.*$"),
        re.compile(r"^\s*CHAPTER \d+\s*$"),
        re.compile(r"^\s*" + re.escape(judul) + r"\s*$"),
        re.compile(r"^\s*\d{1,3}\s*$"),
        re.compile(r"^\s*(?:\d{1,2}\s+)?Source:.*$"),
        re.compile(r"^\s*\(After the plan has been.*$"),
        re.compile(r"^\s*completed\)\s*$"),
        re.compile(r"^\s*REVIEW\s*$"),
        re.compile(r"^\s*•\s*$"),
    ]


def kalimat(teks: str) -> list[str]:
    kasar = re.split(r"(?<=[.!?])\s+", teks)
    hasil: list[str] = []
    for k in kasar:
        if hasil and hasil[-1].split()[-1].lstrip("(“\"") in SINGKATAN:
            hasil[-1] = hasil[-1] + " " + k
        else:
            hasil.append(k)
    return [k for k in hasil if k.strip()]


def blok_halaman(teks_halaman: str, halaman: int, buang: list[re.Pattern]) -> list[dict]:
    if halaman in HALAMAN_LEWATI:
        return []
    blok, buf = [], []
    sub = ""

    def tutup():
        nonlocal buf
        if buf:
            t = " ".join(" ".join(buf).split())
            t = re.sub(r"([a-z])\.(\d{1,2})(?=\s)", r"\1.", t)
            if len(t) >= 20:
                blok.append({"halaman": halaman, "bagian": sub, "teks": t})
            buf = []

    for b in teks_halaman.splitlines():
        if any(p.match(b) for p in buang):
            continue
        if not b.strip():
            tutup()
            continue
        if not buf:
            m = re.match(r"^\s*(\d)\.\s+(.+?)\s*$", b)
            if m and len(b) < 60:
                sub = m.group(0).strip()
        buf.append(b.rstrip())
    tutup()
    return blok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--halaman", required=True, help="rentang, mis. 45-48")
    ap.add_argument("--bab", required=True)
    ap.add_argument("--judul", required=True)
    ap.add_argument("--sumber", default="who-pm-18-5")
    ap.add_argument("--keluaran", required=True)
    ap.add_argument("--lewati", default="", help="halaman yang dilewati, mis. 46,52")
    a = ap.parse_args()

    awal, akhir = (int(x) for x in a.halaman.split("-"))
    if a.lewati:
        HALAMAN_LEWATI.update(int(x) for x in a.lewati.split(","))

    buang = pola_buang(a.judul)
    halaman = (ROOT / "ref" / "pm_18-5_eng.txt").read_text(encoding="utf-8").split("\f")
    blok: list[dict] = []
    for no in range(awal, akhir + 1):
        blok.extend(blok_halaman(halaman[no - 1], no, buang))

    gabung: list[dict] = []
    for b in blok:
        if gabung and b["teks"][:1].islower():
            gabung[-1]["teks"] += " " + b["teks"]
            gabung[-1]["halaman"] = sorted(set(gabung[-1]["halaman"] + [b["halaman"]]))
            continue
        gabung.append({"halaman": [b["halaman"]], "bagian": b["bagian"], "teks": b["teks"]})

    unit = []
    for b in gabung:
        for s in kalimat(b["teks"]):
            unit.append({"halaman": b["halaman"], "bagian": b["bagian"], "teks": s, "token": token(s)})

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

    if len(chunk) > 1:
        while total(chunk[-1]) < MIN_TOK and len(chunk[-2]) > 1 and total(chunk[-2]) - chunk[-2][-1]["token"] >= MIN_TOK:
            chunk[-1].insert(0, chunk[-2].pop())
    for i in range(len(chunk) - 1):
        while total(chunk[i]) > MAKS_TOK and len(chunk[i]) > 2:
            chunk[i + 1].insert(0, chunk[i].pop())

    out = Path(a.keluaran)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for i, c in enumerate(chunk, start=1):
            teks = " ".join(u["teks"] for u in c)
            hal = sorted({h for u in c for h in u["halaman"]})
            f.write(json.dumps({
                "id": f"pm-ch{a.bab}-en-{i:03d}",
                "bahasa": "en",
                "sumber": a.sumber,
                "halaman": hal if len(hal) > 1 else hal[0],
                "bagian": next((u["bagian"] for u in c if u["bagian"]), ""),
                "teks": teks,
                "token": token(teks),
                "kata": len(teks.split()),
            }, ensure_ascii=False) + "\n")

    data = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"Bab {a.bab}: {len(data)} chunk, token {sum(d['token'] for d in data)} "
          f"(min {min(d['token'] for d in data)}, maks {max(d['token'] for d in data)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
