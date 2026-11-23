#!/usr/bin/env python3
"""Bangun korpus mikro tertutup (bilingual ID/EN) untuk artikel versi alpha.

Sumber resmi:
    WHO, Doing What Matters in Times of Stress (2020), ISBN 978-92-4-000392-7
      - edisi Inggris : ref/who_dwm_eng.pdf
      - edisi Indonesia: ref/who_dwm_id.pdf  (WHO SEARO, ISBN sama)
    Keduanya CC BY-NC-SA 3.0 IGO.

Masukan teks per halaman dihasilkan lebih dulu:
    pdftotext -layout ref/who_dwm_eng.pdf ref/who_eng_pages.txt
    pdftotext -layout ref/who_dwm_id.pdf  ref/who_id_pages.txt

Keluaran:
    data/korpus.jsonl   {"id","bahasa","sumber","halaman","bagian","teks","token","kata"}
    data/korpus_stats.json

Aturan segmentasi (sesuai Bagian III.B naskah):
    - panjang sasaran 300--500 token, dihitung dengan tokenizer BGE-M3
    - batas paragraf tidak dipotong
    - paragraf tidak pernah digabung melewati 500 token
    - label bagian diambil dari header halaman (mis. "Part 2: UNHOOKING")

Pemakaian:
    python3 bangun_korpus.py --out data/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

HALAMAN_MIN, HALAMAN_MAX = 300, 500

# Baris yang berulang di setiap halaman dan bukan isi.
POLA_HEADER = [
    re.compile(r"^\s*(?:Part|Bagian)\s+\d+\s*:?\s*[A-Z ]+\s*\d*\s*$", re.I),
    re.compile(r"^\s*Doing [Ww]hat [Mm]atters.*$"),
    re.compile(r"^\s*Hal yang Perlu.*$"),
    re.compile(r"^\s*\d{1,3}\s*$"),
    re.compile(r"^\s*[.·\u2026\s]{6,}$"),
    re.compile(r"^\s*Bagian\s+\d+", re.I),
]
# Halaman parateks yang dikeluarkan dari korpus.
POLA_TOLAK = re.compile(
    r"(ISBN\s+978-92-4|Daftar isi|Contents|Preface|Pengantar|Acknowledg|Ucapan terima kasih|"
    r"Book review|Peninjauan buku|References|Daftar pustaka|© World Health Organization|"
    r"Some rights reserved|Sebagian hak dilindung)", re.I)


def dapat_tokenizer(path: str | None):
    if not path:
        return None
    from tokenizers import Tokenizer  # type: ignore
    return Tokenizer.from_file(path)


def hitung_token(teks: str, tok) -> int:
    if tok is None:
        return max(1, round(len(teks.split()) * 1.45))
    return len(tok.encode(teks, add_special_tokens=False).ids)


def bersihkan_halaman(teks: str) -> tuple[str, str]:
    """Kembalikan (bagian, isi) untuk satu halaman."""
    bagian = ""
    baris_isi = []
    for baris in teks.splitlines():
        b = baris.rstrip()
        if not b.strip():
            baris_isi.append("")
            continue
        m = re.match(r"^\s*((?:Part|Bagian)\s+\d+\s*:?\s*[A-Za-z ]+?)\s*\d*\s*$", b)
        if m and not bagian:
            bagian = " ".join(m.group(1).split())
        if any(p.match(b) for p in POLA_HEADER):
            continue
        baris_isi.append(b.strip())
    return bagian, "\n".join(baris_isi)


def paragraf(isi: str) -> list[str]:
    blok = re.split(r"\n\s*\n", isi)
    hasil = []
    for b in blok:
        t = " ".join(b.split())
        if len(t) < 25:          # potongan label gambar, bukan prosa
            continue
        huruf = [k for k in t if k.isalpha()]
        if huruf and sum(1 for k in huruf if k.isupper()) / len(huruf) > 0.5:
            continue              # daftar nama alat pada halaman sampul
        hasil.append(t)
    return hasil


def bangun_bahasa(path: str, bahasa: str, sumber: str, tok, verbose: bool) -> list[dict]:
    halaman = Path(path).read_text(encoding="utf-8").split("\f")
    butir: list[dict] = []
    bagian_aktif = ""
    for no, teks in enumerate(halaman, start=1):
        if no <= 3 or not teks.strip():
            continue
        if POLA_TOLAK.search(teks):
            if verbose:
                print(f"  lewati halaman {no}: parateks", file=sys.stderr)
            continue
        bagian, isi = bersihkan_halaman(teks)
        if bagian:
            bagian_aktif = bagian
        for p in paragraf(isi):
            butir.append({"halaman": no, "bagian": bagian or bagian_aktif, "teks": p})

    # gabung paragraf berurutan sampai token >= HALAMAN_MIN
    potongan: list[dict] = []
    buf: list[dict] = []
    n_buf = 0
    for b in butir:
        n = hitung_token(b["teks"], tok)
        # jangan gabungkan paragraf dari bagian berbeda
        if buf and b["bagian"] and buf[-1]["bagian"] and b["bagian"] != buf[-1]["bagian"]:
            potongan.append(buf)
            buf, n_buf = [], 0
        if buf and n_buf + n > HALAMAN_MAX:
            potongan.append(buf)
            buf, n_buf = [], 0
        buf.append({**b, "token": n})
        n_buf += n
        if n_buf >= HALAMAN_MIN:
            potongan.append(buf)
            buf, n_buf = [], 0
    if buf:
        if potongan and n_buf < 120:
            potongan[-1].extend(buf)      # ekor pendek digabung ke potongan terakhir
        else:
            potongan.append(buf)

    # gabungkan potongan ekor yang terlalu pendek (dua arah, batas 500 token)
    def n_tok(blok):
        return sum(b["token"] for b in blok)

    gabung: list[list[dict]] = []
    for blok in potongan:
        if gabung and n_tok(blok) < 250 and n_tok(gabung[-1]) + n_tok(blok) <= HALAMAN_MAX:
            gabung[-1].extend(blok)
        else:
            gabung.append(blok)

    akhir: list[list[dict]] = []
    i = 0
    while i < len(gabung):
        blok = gabung[i]
        if (n_tok(blok) < 250 and i + 1 < len(gabung)
                and n_tok(blok) + n_tok(gabung[i + 1]) <= HALAMAN_MAX):
            gabung[i + 1] = blok + gabung[i + 1]
        else:
            akhir.append(blok)
        i += 1
    potongan = akhir

    hasil = []
    for i, blok in enumerate(potongan, start=1):
        teks = " ".join(b["teks"] for b in blok).strip()
        if len(teks.split()) < 40:
            continue
        hal = sorted({b["halaman"] for b in blok})
        bagian = next((b["bagian"] for b in blok if b["bagian"]), "")
        n_tok_chunk = hitung_token(teks, tok)
        hasil.append({
            "id": f"{bahasa}-{i:03d}",
            "bahasa": bahasa,
            "sumber": sumber,
            "halaman": hal[0] if len(hal) == 1 else hal,
            "bagian": bagian,
            "teks": teks,
            "token": n_tok_chunk,
            "kata": len(teks.split()),
            **({"catatan": "pendek-batas-bagian"} if n_tok_chunk < 250 else {}),
        })
    return hasil


def statistik(korpus: list[dict]) -> dict:
    hasil = {}
    for bahasa in sorted({d["bahasa"] for d in korpus}):
        k = [d for d in korpus if d["bahasa"] == bahasa]
        tok = [d["token"] for d in k]
        hasil[bahasa] = {
            "chunk": len(k),
            "kata": sum(d["kata"] for d in k),
            "token": sum(tok),
            "token_median": statistics.median(tok),
            "token_min": min(tok),
            "token_maks": max(tok),
            "di_bawah_300": sum(1 for t in tok if t < HALAMAN_MIN),
            "di_atas_500": sum(1 for t in tok if t > HALAMAN_MAX),
            "halaman_tercakup": len({h for d in k for h in ([d["halaman"]] if isinstance(d["halaman"], int) else d["halaman"])}),
        }
    return hasil


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--en", default="ref/who_eng_pages.txt")
    ap.add_argument("--id", default="ref/who_id_pages.txt")
    ap.add_argument("--tokenizer", default="ref/tok/tokenizer.json")
    ap.add_argument("--out", default="data")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    tok = dapat_tokenizer(a.tokenizer)
    if tok is None:
        print("peringatan: tokenizer tidak ditemukan, token diperkirakan dari kata", file=sys.stderr)

    en = bangun_bahasa(a.en, "en", "who-dwm-2020-eng", tok, a.verbose)
    idn = bangun_bahasa(a.id, "id", "who-dwm-2020-ind", tok, a.verbose)

    # buang duplikat teks persis
    terlihat, unik = set(), []
    for d in en + idn:
        h = hashlib.sha256(re.sub(r"\W+", " ", d["teks"].lower()).encode()).hexdigest()
        if h in terlihat:
            continue
        terlihat.add(h)
        d["hash"] = h[:16]
        unik.append(d)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "korpus.jsonl").open("w", encoding="utf-8") as f:
        for d in unik:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    st = statistik(unik)
    st["total_chunk"] = len(unik)
    st["sumber"] = {"en": "who-dwm-2020-eng", "id": "who-dwm-2020-ind"}
    (out / "korpus_stats.json").write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(st, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
