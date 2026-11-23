#!/usr/bin/env python3
"""Rakit chunk korpus dari berkas teks bertanda `### <id>`.

Dipakai untuk modul yang ditulis sendiri (pencatatan pikiran tujuh kolom). Bagian
dipadatkan berurutan menjadi chunk 300--500 token; batas bagian tidak dilanggar bila
bagian masih muat.

Pemakaian:
    python3 eksperimen/bangun_modul.py --teks data/src/thought_record_en.txt \
        --bahasa en --sumber modul-thought-record --keluaran data/src/thought_record_en.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
TOK = Tokenizer.from_file(str(ROOT / "ref" / "tok" / "tokenizer.json"))
MIN_TOK, MAKS_TOK = 300, 500


def token(teks: str) -> int:
    return len(TOK.encode(teks, add_special_tokens=False).ids)


def baca(path: Path) -> list[dict]:
    bagian, kunci, buf = [], None, []
    for baris in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+(\S+)\s*$", baris)
        if m:
            if kunci:
                bagian.append({"id": kunci, "teks": " ".join(" ".join(buf).split())})
            kunci, buf = m.group(1), []
            continue
        if kunci:
            buf.append(baris)
    if kunci:
        bagian.append({"id": kunci, "teks": " ".join(" ".join(buf).split())})
    return [b for b in bagian if b["teks"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teks", required=True)
    ap.add_argument("--bahasa", required=True)
    ap.add_argument("--sumber", required=True)
    ap.add_argument("--lisensi", default="")
    ap.add_argument("--keluaran", required=True)
    a = ap.parse_args()

    bagian = baca(Path(a.teks))
    for b in bagian:
        b["token"] = token(b["teks"])

    chunk, buf, n = [], [], 0
    for b in bagian:
        if buf and n + b["token"] > MAKS_TOK and n >= MIN_TOK:
            chunk.append(buf)
            buf, n = [], 0
        buf.append(b)
        n += b["token"]
    if buf:
        chunk.append(buf)

    hasil = []
    for i, c in enumerate(chunk, start=1):
        teks = " ".join(b["teks"] for b in c)
        hasil.append({
            "id": f"{a.sumber}-{a.bahasa}-{i:03d}",
            "bahasa": a.bahasa,
            "sumber": a.sumber,
            "lisensi": a.lisensi,
            "halaman": None,
            "bagian": c[0]["id"],
            "teks": teks,
            "token": token(teks),
            "kata": len(teks.split()),
            "hash": hashlib.sha256(re.sub(r"\W+", " ", teks.lower()).encode()).hexdigest()[:16],
        })

    out = Path(a.keluaran)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for d in hasil:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    print(f"{len(hasil)} chunk → {out}")
    for d in hasil:
        tanda = "" if MIN_TOK <= d["token"] <= MAKS_TOK else "  <-- di luar 300--500"
        print(f"  {d['id']:<30} {d['token']:>4} token  bagian {d['bagian']}{tanda}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
