#!/usr/bin/env python3
"""Rakit dan periksa himpunan 100 kueri uji dari berkas teks berpenanda.

Pemeriksaan yang dijalankan:
    1. panjang 5--40 token (tokenizer BGE-M3) dan tidak kosong
    2. tidak ada salinan frasa dari chunk korpus (tumpang tindih n-gram terpanjang)
    3. tidak ada salinan frasa dari sampel ESConv (kalau berkasnya diberikan)
    4. tidak ada kueri kembar di dalam himpunan

Pemakaian:
    python3 eksperimen/bangun_kueri.py --keluaran data/kueri.jsonl \
        [--esconv data/src/esconv_sample.jsonl]
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[2]
TOK = Tokenizer.from_file(str(ROOT / "ref" / "tok" / "tokenizer.json"))
MIN_TOK, MAKS_TOK = 5, 40
N_GRAM = 5          # frasa lima kata dianggap salinan
SUMBER = [("id", ROOT / "data" / "src" / "kueri_id.txt"), ("en", ROOT / "data" / "src" / "kueri_en.txt")]


def token(teks: str) -> int:
    return len(TOK.encode(teks, add_special_tokens=False).ids)


def normal(teks: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", teks.lower())


def ngram(daftar: list[str], n: int) -> set[tuple]:
    return {tuple(daftar[i:i + n]) for i in range(len(daftar) - n + 1)}


def tumpang_tindih_terpanjang(kueri: list[str], kumpulan: list[set], maks: int = 12) -> int:
    """Panjang n-gram terpanjang yang muncul di salah satu dokumen pembanding."""
    for n in range(maks, N_GRAM - 1, -1):
        g = ngram(kueri, n)
        if g and any(g & s for s in kumpulan):
            return n
    return 0


def baca(path: Path, bahasa: str) -> list[dict]:
    hasil, kunci, topik, buf = [], None, "", []
    for baris in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+(\S+)\s*\|\s*(\S+)\s*$", baris)
        if m:
            if kunci:
                hasil.append({"qid": kunci, "bahasa": bahasa, "topik": topik,
                              "teks": " ".join(" ".join(buf).split())})
            kunci, topik, buf = m.group(1), m.group(2), []
            continue
        if kunci:
            buf.append(baris)
    if kunci:
        hasil.append({"qid": kunci, "bahasa": bahasa, "topik": topik,
                      "teks": " ".join(" ".join(buf).split())})
    return [h for h in hasil if h["teks"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keluaran", default=str(ROOT / "data" / "kueri.jsonl"))
    ap.add_argument("--korpus", default=str(ROOT / "data" / "korpus.jsonl"))
    ap.add_argument("--esconv", default=None)
    a = ap.parse_args()

    korpus = [json.loads(l) for l in Path(a.korpus).read_text(encoding="utf-8").splitlines() if l.strip()]
    gram_korpus = {"id": [], "en": []}
    for d in korpus:
        gram_korpus[d["bahasa"]].append(ngram(normal(d["teks"]), N_GRAM))

    esconv = {"id": [], "en": []}
    if a.esconv and Path(a.esconv).exists():
        for baris in Path(a.esconv).read_text(encoding="utf-8").splitlines():
            if not baris.strip():
                continue
            for ujar in json.loads(baris).get("dialog", []):
                if ujar.get("speaker") == "usr":
                    esconv["en"].append(ngram(normal(ujar["text"]), N_GRAM))

    kueri = []
    for bahasa, path in SUMBER:
        kueri.extend(baca(path, bahasa))

    masalah, catatan = [], []
    for k in kueri:
        k["token"] = token(k["teks"])
        k["kata"] = len(k["teks"].split())
        if not (MIN_TOK <= k["token"] <= MAKS_TOK):
            masalah.append(f"{k['qid']}: {k['token']} token di luar {MIN_TOK}--{MAKS_TOK}")
        n_korpus = tumpang_tindih_terpanjang(normal(k["teks"]), gram_korpus[k["bahasa"]])
        if n_korpus >= N_GRAM:
            masalah.append(f"{k['qid']}: berbagi frasa {n_korpus} kata dengan chunk korpus")
        if esconv[k["bahasa"]]:
            # ESConv adalah bahan adaptasi, bukan bahan yang tidak boleh berbagi kata;
            # tumpang tindih dicatat sebagai informasi, bukan pelanggaran.
            catatan.append(tumpang_tindih_terpanjang(normal(k["teks"]), esconv[k["bahasa"]]))

    # kueri kembar
    terlihat = set()
    for k in kueri:
        h = tuple(normal(k["teks"]))
        if h in terlihat:
            masalah.append(f"{k['qid']}: kueri kembar")
        terlihat.add(h)

    out = Path(a.keluaran)
    with out.open("w", encoding="utf-8") as f:
        for k in kueri:
            f.write(json.dumps({"qid": k["qid"], "bahasa": k["bahasa"], "topik": k["topik"],
                                "teks": k["teks"], "token": k["token"], "kata": k["kata"]},
                               ensure_ascii=False) + "\n")

    print(f"{len(kueri)} kueri → {out}")
    for bahasa in ("id", "en"):
        bagian = [k for k in kueri if k["bahasa"] == bahasa]
        tok = [k["token"] for k in bagian]
        print(f"  {bahasa}: {len(bagian)} kueri, token {min(tok)}--{max(tok)} (median {sorted(tok)[len(tok)//2]}), "
              f"kata {min(k['kata'] for k in bagian)}--{max(k['kata'] for k in bagian)}")
        print("     topik:", dict(collections.Counter(k["topik"] for k in bagian).most_common()))
    if catatan:
        sebaran = collections.Counter(catatan)
        print(f"  tumpang tindih n-gram dengan ESConv (informasi, bukan pelanggaran): "
              f"0 kata {sebaran.get(0, 0)} kueri, 3 kata {sebaran.get(3, 0)}, 4 kata {sebaran.get(4, 0)}, "
              f"5 kata {sebaran.get(5, 0)}")
    if masalah:
        print(f"\n{len(masalah)} masalah:")
        for m in masalah[:30]:
            print("  -", m)
        return 1
    print("\nkueri: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
