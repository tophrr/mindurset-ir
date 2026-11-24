#!/usr/bin/env python3
"""Bangun berkas sumber korpus dari pustaka kartu coping skills Mind-Ur-Set.

Kartu berbahasa Inggris diambil dari aplikasi (worker/src/corpus/<topik>.md), kartu
berbahasa Indonesia dari data/src/kartu_id.txt. Satu kartu menjadi satu chunk, sesuai
aturan "satu chunk memuat satu instruksi utuh".

Pemakaian:
    python3 eksperimen/bangun_kartu.py --bahasa en --keluaran data/src/kartu_en.jsonl
    python3 eksperimen/bangun_kartu.py --bahasa id --keluaran data/src/kartu_id.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[2]
TOK = Tokenizer.from_file(str(ROOT / "ref" / "tok" / "tokenizer.json"))
KARTU_EN = ROOT / "data" / "src" / "kartu_en"
TOPIK = ["action", "all-or-nothing", "rumination", "safety-plan", "self-compassion", "sleep", "stress"]
SUMBER = "mindurset-cards-v1"
LISENSI = "karya sendiri (MIT)"


def token(teks: str) -> int:
    return len(TOK.encode(teks, add_special_tokens=False).ids)


def baca_tambahan(path: Path, awalan: str) -> dict[str, str]:
    """Kalimat "kapan kartu ini dipakai" yang ditambahkan pada ujung setiap kartu."""
    hasil, kunci, buf = {}, None, []
    if not path.exists():
        return hasil
    for baris in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+" + awalan + r"(\S+)\s*$", baris)
        if m:
            if kunci:
                hasil[kunci] = " ".join(" ".join(buf).split())
            kunci, buf = m.group(1), []
            continue
        if kunci:
            buf.append(baris)
    if kunci:
        hasil[kunci] = " ".join(" ".join(buf).split())
    return {k: v for k, v in hasil.items() if v}


def kartu_inggris() -> dict[str, str]:
    hasil = {}
    for topik in TOPIK:
        isi = (KARTU_EN / f"{topik}.md").read_text(encoding="utf-8")
        isi = re.sub(r"<!--[\s\S]*?-->", "", isi)          # komentar kata kunci
        isi = re.sub(r"^#\s+.*$", "", isi, flags=re.M)      # judul berkas
        bagian = []
        for blok in re.split(r"^##\s+", isi, flags=re.M)[1:]:
            baris = blok.splitlines()
            judul = baris[0].strip()
            teks = " ".join(" ".join(baris[1:]).split())
            if teks:
                bagian.append(f"{judul}. {teks}")
        hasil[topik] = " ".join(bagian)
    return hasil


def kartu_indonesia() -> dict[str, str]:
    teks = (ROOT / "data" / "src" / "kartu_id.txt").read_text(encoding="utf-8")
    hasil, kunci, buf = {}, None, []
    for baris in teks.splitlines():
        m = re.match(r"^###\s+kartu-(\S+)\s*$", baris)
        if m:
            if kunci:
                hasil[kunci] = " ".join(" ".join(buf).split())
            kunci, buf = m.group(1), []
            continue
        if kunci:
            buf.append(baris)
    if kunci:
        hasil[kunci] = " ".join(" ".join(buf).split())
    return {k: v for k, v in hasil.items() if v}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bahasa", choices=["en", "id"], required=True)
    ap.add_argument("--keluaran", required=True)
    a = ap.parse_args()

    kartu = kartu_inggris() if a.bahasa == "en" else kartu_indonesia()
    tambahan = baca_tambahan(ROOT / "data" / "src" / ("kartu_en_extra.txt" if a.bahasa == "en"
                                                       else "kartu_id_extra.txt"), "kartu-")
    out = Path(a.keluaran)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for topik in TOPIK:
            teks = kartu.get(topik)
            if teks and tambahan.get(topik):
                teks = f"{teks} {tambahan[topik]}"
            if not teks:
                print(f"kartu hilang: {topik}", file=sys.stderr)
                continue
            f.write(json.dumps({
                "id": f"kartu-{a.bahasa}-{topik}",
                "bahasa": a.bahasa,
                "sumber": SUMBER,
                "lisensi": LISENSI,
                "halaman": None,
                "bagian": topik,
                "teks": teks,
                "token": token(teks),
                "kata": len(teks.split()),
                "hash": hashlib.sha256(re.sub(r"\W+", " ", teks.lower()).encode()).hexdigest()[:16],
            }, ensure_ascii=False) + "\n")

    data = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"{len(data)} kartu → {out}")
    for d in data:
        print(f"  {d['id']:<28} {d['token']:>4} token")
    return 0


if __name__ == "__main__":
    sys.exit(main())
