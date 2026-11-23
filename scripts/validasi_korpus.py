#!/usr/bin/env python3
"""Validasi korpus: rentang token, provenans halaman, kemurnian bahasa, duplikat.

Pemakaian:
    python3 validasi_korpus.py --korpus data/korpus.jsonl [--tokenizer ref/tok/tokenizer.json]

Keluaran berupa laporan ringkas dan kode keluar bukan nol bila ada pelanggaran.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ID_KATA = {"dan", "yang", "untuk", "dengan", "tidak", "anda", "ini", "itu", "dari", "pada",
           "adalah", "akan", "bisa", "kita", "saya", "dalam", "atau", "juga", "jika", "saat"}
EN_KATA = {"the", "and", "your", "you", "that", "this", "with", "for", "are", "not",
           "have", "what", "when", "can", "will", "from", "they", "how", "but", "about"}


def cek(korpus: list[dict], tokenizer: str | None) -> int:
    masalah: list[str] = []
    pendek: list[tuple[str, int]] = []
    tanpa_halaman: list[str] = []
    tok = None
    if tokenizer and Path(tokenizer).exists():
        from tokenizers import Tokenizer  # type: ignore
        tok = Tokenizer.from_file(tokenizer)

    ids = [d["id"] for d in korpus]
    if len(ids) != len(set(ids)):
        masalah.append("ada id ganda")
    if len({d["hash"] for d in korpus}) != len(korpus):
        masalah.append("ada teks duplikat")

    for d in korpus:
        kata = re.findall(r"[^\W_]+", d["teks"].lower())
        if tok is not None:
            n = len(tok.encode(d["teks"], add_special_tokens=False).ids)
            if abs(n - d["token"]) > 2:
                masalah.append(f"{d['id']}: token tercatat {d['token']} tetapi terhitung {n}")
        else:
            n = d["token"]
        if n > 500:
            masalah.append(f"{d['id']}: {n} token melebihi 500")
        if n < 250 and d.get("catatan") != "pendek-batas-bagian":
            masalah.append(f"{d['id']}: {n} token di bawah toleransi 250")
        elif 250 <= n < 300:
            pendek.append((d["id"], n))

        hal = d.get("halaman")
        if hal is None:
            tanpa_halaman.append(d["id"])
        else:
            daftar = hal if isinstance(hal, list) else [hal]
            batas = 133 if str(d.get("sumber", "")).startswith("who-dwm") else 140
            if any(not (1 <= h <= batas) for h in daftar):
                masalah.append(f"{d['id']}: nomor halaman di luar 1-{batas}: {daftar}")

        n_id = sum(1 for w in kata if w in ID_KATA)
        n_en = sum(1 for w in kata if w in EN_KATA)
        if d["bahasa"] == "id" and n_en > n_id:
            masalah.append(f"{d['id']}: ditandai id tetapi lebih banyak kata Inggris ({n_en} vs {n_id})")
        if d["bahasa"] == "en" and n_id > n_en:
            masalah.append(f"{d['id']}: ditandai en tetapi lebih banyak kata Indonesia ({n_id} vs {n_en})")

    print("chunk:", len(korpus))
    for bahasa in sorted({d["bahasa"] for d in korpus}):
        k = [d for d in korpus if d["bahasa"] == bahasa]
        t = [d["token"] for d in k]
        hal = {h for d in k if d.get("halaman") is not None
               for h in ([d["halaman"]] if isinstance(d["halaman"], int) else d["halaman"])}
        print(f"  {bahasa}: {len(k)} chunk, token {min(t)}-{max(t)} (median {sorted(t)[len(t)//2]}), "
              f"{len(hal)} halaman tercakup, bagian {len({d['bagian'] for d in k})}")
    print("bagian terbanyak:", Counter(d["bagian"] for d in korpus).most_common(3))
    print("sumber:", Counter(d["sumber"] for d in korpus).most_common())
    if pendek:
        print(f"chunk 250-299 token (di bawah sasaran 300, masih di atas toleransi 250): {len(pendek)}")
        for i, n in pendek:
            print(f"  - {i}: {n}")
    if tanpa_halaman:
        print(f"chunk tanpa nomor halaman (karya sendiri, tanpa paginasi sumber): {len(tanpa_halaman)}")

    if masalah:
        print(f"\n{len(masalah)} pelanggaran:")
        for m in masalah[:25]:
            print("  -", m)
        return 1
    print("\nvalidasi: OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--korpus", default="data/korpus.jsonl")
    ap.add_argument("--tokenizer", default="ref/tok/tokenizer.json")
    a = ap.parse_args()
    korpus = [json.loads(l) for l in Path(a.korpus).read_text(encoding="utf-8").splitlines() if l.strip()]
    return cek(korpus, a.tokenizer)


if __name__ == "__main__":
    sys.exit(main())
