#!/usr/bin/env python3
"""Susun berkas sumber korpus dari teks mentah menjadi JSONL berskema.

Dipakai untuk terjemahan Indonesia Bab 7 PM+ (data/src/pm_ch7_id_a.txt dan _b.txt).
Setiap bagian dalam berkas teks diawali penanda `### <id>`; metadata (halaman, bagian)
diambil dari pasangan bahasa Inggrisnya di data/src/pm_ch7_en.jsonl.

Pemakaian:
    python3 eksperimen/susun_sumber.py --en data/src/pm_ch7_en.jsonl \
        --teks data/src/pm_ch7_id_a.txt data/src/pm_ch7_id_b.txt \
        --keluaran data/src/pm_ch7_id.jsonl --bahasa id --sumber who-pm-18-5-id
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


def token(teks: str) -> int:
    return len(TOK.encode(teks, add_special_tokens=False).ids)


def baca_bagian(paths: list[str]) -> dict[str, str]:
    bagian: dict[str, str] = {}
    for p in paths:
        kunci = None
        buf: list[str] = []
        for baris in Path(p).read_text(encoding="utf-8").splitlines():
            m = re.match(r"^###\s+(\S+)\s*$", baris)
            if m:
                if kunci:
                    bagian[kunci] = " ".join(" ".join(buf).split())
                kunci, buf = m.group(1), []
                continue
            if kunci:
                buf.append(baris)
        if kunci:
            bagian[kunci] = " ".join(" ".join(buf).split())
    return {k: v for k, v in bagian.items() if v}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--en", required=True, help="JSONL pasangan bahasa Inggris")
    ap.add_argument("--teks", nargs="+", required=True)
    ap.add_argument("--keluaran", required=True)
    ap.add_argument("--bahasa", default="id")
    ap.add_argument("--sumber", required=True)
    a = ap.parse_args()

    pasangan = {json.loads(l)["id"]: json.loads(l)
                for l in Path(a.en).read_text(encoding="utf-8").splitlines() if l.strip()}
    teks = baca_bagian(a.teks)

    hasil, kurang = [], []
    for id_teks, isi in teks.items():
        id_en = id_teks.replace("-id-", "-en-")
        id_id = id_teks
        asal = pasangan.get(id_en)
        if asal is None:
            kurang.append(id_en)
            continue
        n = token(isi)
        hasil.append({
            "id": id_id,
            "bahasa": a.bahasa,
            "sumber": a.sumber,
            "halaman": asal["halaman"],
            "bagian": asal["bagian"],
            "teks": isi,
            "token": n,
            "kata": len(isi.split()),
            "hash": hashlib.sha256(re.sub(r"\W+", " ", isi.lower()).encode()).hexdigest()[:16],
        })

    out = Path(a.keluaran)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for d in hasil:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    di_luar = [(d["id"], d["token"]) for d in hasil if not 300 <= d["token"] <= 500]
    print(f"{len(hasil)} chunk → {out}")
    print(f"token: min {min(d['token'] for d in hasil)}, maks {max(d['token'] for d in hasil)}, "
          f"total {sum(d['token'] for d in hasil)}")
    if di_luar:
        print("di luar 300--500:", di_luar)
    if kurang:
        print("tanpa pasangan EN:", kurang)
    return 0


if __name__ == "__main__":
    sys.exit(main())
