#!/usr/bin/env python3
"""Berkas sumber korpus DWM: pisahkan versi 1, dan simpan sebagai teks yang bisa disunting.

Dua arah:

1. Default — `data/korpus_dwm_v1.jsonl` (keluaran eksperimen/bangun_korpus.py atas
   `ref/who_*_pages.txt`) dipecah menjadi berkas per bahasa:
       data/src/dwm_en.txt, dwm_id.txt      teks sumber yang disunting manusia
       data/src/dwm_en.jsonl, dwm_id.jsonl  artefak siap pakai untuk penggabung

2. `--dari-txt` — setelah teks disunting, bangun ulang JSONL dari berkas `.txt`.
   Metadata halaman dan bagian diambil dari JSONL yang ada, sedangkan token, kata, dan
   hash dihitung ulang dari teks terbaru.

Pemakaian:
    python3 eksperimen/pisahkan_dwm.py             # v1 → txt + jsonl
    python3 eksperimen/pisahkan_dwm.py --dari-txt  # txt → jsonl (setelah suntingan)
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
DATA = ROOT / "data"
SRC = DATA / "src"
TOK = Tokenizer.from_file(str(ROOT / "ref" / "tok" / "tokenizer.json"))
BAHASA = ("en", "id")
SUMBER = {"en": "who-dwm-2020-eng", "id": "who-dwm-2020-ind"}
LISENSI = {
    "en": "CC BY-NC-SA 3.0 IGO (WHO 2020, ISBN 978-92-4-000391-0)",
    "id": "CC BY-NC-SA 3.0 IGO (WHO SEARO 2020, ISBN 978-92-4-000391-0)",
}


def token(teks: str) -> int:
    return len(TOK.encode(teks, add_special_tokens=False).ids)


def sidik(teks: str) -> str:
    return hashlib.sha256(re.sub(r"\W+", " ", teks.lower()).encode()).hexdigest()[:16]


def butir(nomor: str, bahasa: str, teks: str, halaman, bagian: str, catatan: str | None) -> dict:
    return {
        "id": f"dwm-{bahasa}-{nomor}",
        "bahasa": bahasa,
        "sumber": SUMBER[bahasa],
        "lisensi": LISENSI[bahasa],
        "halaman": halaman,
        "bagian": bagian,
        "teks": teks,
        "token": token(teks),
        "kata": len(teks.split()),
        "hash": sidik(teks),
        **({"catatan": catatan} if catatan else {}),
    }


def tulis(isi: list[dict], bahasa: str, tulis_txt: bool = True) -> None:
    SRC.mkdir(parents=True, exist_ok=True)
    if tulis_txt:
        with (SRC / f"dwm_{bahasa}.txt").open("w", encoding="utf-8") as f:
            for d in isi:
                hal = d.get("halaman")
                hal = ",".join(map(str, hal)) if isinstance(hal, list) else hal
                f.write(f"### {d['id']}\n")
                f.write(f"<!-- halaman: {hal}; token: {d['token']}; "
                        f"bagian: {d.get('bagian') or '-'} -->\n")
                f.write(f"{d['teks']}\n\n")
    out = SRC / f"dwm_{bahasa}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for d in isi:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    tok = [d["token"] for d in isi]
    print(f"{len(isi)} chunk → {out} (token {min(tok)}–{max(tok)}, total {sum(tok)})")


def dari_v1() -> int:
    lama = DATA / "korpus_dwm_v1.jsonl"
    if not lama.exists():
        print(f"{lama} tidak ada; jalankan eksperimen/bangun_korpus.py lebih dahulu", file=sys.stderr)
        return 1
    baris = [json.loads(l) for l in lama.read_text(encoding="utf-8").splitlines() if l.strip()]
    per_bahasa: dict[str, list[dict]] = {b: [] for b in BAHASA}
    for d in baris:
        bahasa = d["bahasa"]
        per_bahasa[bahasa].append(butir(d["id"].split("-")[-1], bahasa, d["teks"],
                                        d.get("halaman"), d.get("bagian", ""), d.get("catatan")))
    for bahasa, isi in per_bahasa.items():
        tulis(isi, bahasa)
    return 0


def dari_txt() -> int:
    for bahasa in BAHASA:
        txt = SRC / f"dwm_{bahasa}.txt"
        jika = SRC / f"dwm_{bahasa}.jsonl"
        if not txt.exists():
            print(f"{txt} tidak ada", file=sys.stderr)
            return 1
        meta = {}
        if jika.exists():
            for l in jika.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    d = json.loads(l)
                    meta[d["id"]] = d
        isi, kunci, buf = [], None, []
        for baris in txt.read_text(encoding="utf-8").splitlines():
            if baris.lstrip().startswith("<!--"):
                continue                      # baris komentar metadata tidak ikut jadi teks
            m = re.match(r"^###\s+(\S+)\s*$", baris)
            if m:
                if kunci:
                    isi.append((kunci, " ".join(" ".join(buf).split())))
                kunci, buf = m.group(1), []
                continue
            if kunci:
                buf.append(baris)
        if kunci:
            isi.append((kunci, " ".join(" ".join(buf).split())))
        hasil = []
        for kunci, teks in isi:
            asal = meta.get(kunci, {})
            baru = butir(kunci.split("-")[-1], bahasa, teks, asal.get("halaman"),
                         asal.get("bagian", ""), asal.get("catatan"))
            if asal and asal.get("token") != baru["token"]:
                print(f"  {kunci}: token {asal.get('token')} → {baru['token']}")
            hasil.append(baru)
        tulis(hasil, bahasa, tulis_txt=False)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dari-txt", action="store_true", help="bangun JSONL dari dwm_*.txt")
    a = ap.parse_args()
    return dari_txt() if a.dari_txt else dari_v1()


if __name__ == "__main__":
    sys.exit(main())
