#!/usr/bin/env python3
"""Gabungkan semua berkas sumber menjadi korpus akhir (bilingual, berprovenans).

Sumber:
    who-dwm-2020        : data/korpus_dwm_v1.jsonl (hasil eksperimen/bangun_korpus.py)
    who-pm-18-5         : data/src/pm_ch{7,6,8,9,10}_*.jsonl + data/src/pm_ringkas_*.jsonl
    modul-thought-record: data/src/thought_record_*.jsonl
    mindurset-cards-v1  : data/src/kartu_*.jsonl

Keluaran:
    data/korpus.jsonl        satu baris per chunk, urut sumber → bahasa → id
    data/korpus_stats.json   ringkasan per bahasa + per sumber
    data/korpus_tabel.md     angka siap pakai untuk Tabel II naskah

Pemakaian:
    python3 eksperimen/gabung_korpus.py
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SRC = DATA / "src"
from tokenizers import Tokenizer  # noqa: E402

TOK = Tokenizer.from_file(str(ROOT / "ref" / "tok" / "tokenizer.json"))


def hitung_token(teks: str) -> int:
    return len(TOK.encode(teks, add_special_tokens=False).ids)

LISENSI = {
    "who-dwm-2020-eng": "CC BY-NC-SA 3.0 IGO (WHO 2020, ISBN 978-92-4-000391-0)",
    "who-dwm-2020-ind": "CC BY-NC-SA 3.0 IGO (WHO SEARO 2020, ISBN 978-92-4-000391-0)",
    "who-pm-18-5-eng": "CC BY-NC-SA 3.0 IGO (WHO/MSD/MER/18.5, versi 1.1)",
    "who-pm-18-5-id": "CC BY-NC-SA 3.0 IGO (terjemahan tidak resmi, WHO/MSD/MER/18.5)",
    "modul-thought-record": "karya sendiri (kerangka Beck 1979, ditulis ulang)",
    "mindurset-cards-v1": "karya sendiri (MIT, pustaka kartu Mind-Ur-Set)",
}
SUMBER_EN = [
    ("who-pm-18-5-eng", ["pm_ch7_en", "pm_ch6_en", "pm_ch8_en", "pm_ch9_en", "pm_ch10_en", "pm_ringkas_en"]),
    ("modul-thought-record", ["thought_record_en"]),
    ("mindurset-cards-v1", ["kartu_en"]),
]
SUMBER_ID = [
    ("who-pm-18-5-id", ["pm_ch7_id", "pm_ch6_id", "pm_ch8_id", "pm_ch9_id", "pm_ch10_id", "pm_ringkas_id"]),
    ("modul-thought-record", ["thought_record_id"]),
    ("mindurset-cards-v1", ["kartu_id"]),
]


def muat(path: Path) -> list[dict]:
    if not path.exists():
        print(f"  (lewat) {path.name} belum ada")
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def normal(d: dict, sumber: str, bahasa: str | None = None) -> dict:
    # garis isian pada lembar kerja dipendekkan agar tidak memakan token
    teks = re.sub(r"_{4,}", "____", d["teks"].strip())
    return {
        "id": d["id"],
        "bahasa": d.get("bahasa") or bahasa or ("en" if d["id"].endswith(("_en",)) else "id"),
        "sumber": sumber,
        "lisensi": LISENSI[sumber],
        "halaman": d.get("halaman"),
        "bagian": d.get("bagian", ""),
        "teks": teks,
        "token": hitung_token(teks),
        "kata": len(teks.split()),
        "hash": hashlib.sha256(re.sub(r"\W+", " ", teks.lower()).encode()).hexdigest()[:16],
        **({"catatan": "pendek-batas-bagian"} if hitung_token(teks) < 300 else {}),
    }


def dwm() -> list[dict]:
    """Korpus DWM masuk lewat data/src/dwm_{en,id}.jsonl.

    Berkas itu dibuat oleh eksperimen/pisahkan_dwm.py dari data/korpus_dwm_v1.jsonl, yaitu
    keluaran eksperimen/bangun_korpus.py atas `ref/who_*_pages.txt`. Kalau berkas per bahasa
    belum ada, fungsi ini jatuh ke berkas gabungan versi 1.
    """
    per_bahasa = [SRC / "dwm_en.jsonl", SRC / "dwm_id.jsonl"]
    if all(p.exists() for p in per_bahasa):
        hasil = []
        for p in per_bahasa:
            for d in muat(p):
                hasil.append(normal(d, d["sumber"]))
        return hasil

    lama = DATA / "korpus_dwm_v1.jsonl"
    if not lama.exists():
        print("  (lewat) dwm_en/dwm_id dan korpus_dwm_v1.jsonl belum ada")
        return []
    print("  catatan: data/src/dwm_*.jsonl belum ada, memakai korpus_dwm_v1.jsonl "
          "(jalankan eksperimen/pisahkan_dwm.py)")
    hasil = []
    for d in muat(lama):
        akhiran = {"en": "eng", "id": "ind"}[d["bahasa"]]
        sumber = f"who-dwm-2020-{akhiran}"
        d = dict(d)
        nomor = d["id"].split("-")[-1]
        d["id"] = f"dwm-{d['bahasa']}-{nomor}"
        hasil.append(normal(d, sumber))
    return hasil


def statistik(korpus: list[dict]) -> dict:
    def blok(k: list[dict]) -> dict:
        tok = [d["token"] for d in k]
        hal = set()
        for d in k:
            h = d.get("halaman")
            if isinstance(h, int):
                hal.add(h)
            elif isinstance(h, list):
                hal.update(h)
        return {
            "chunk": len(k),
            "kata": sum(d["kata"] for d in k),
            "token": sum(tok),
            "token_median": statistics.median(tok),
            "token_min": min(tok),
            "token_maks": max(tok),
            "di_bawah_300": sum(1 for t in tok if t < 300),
            "di_atas_500": sum(1 for t in tok if t > 500),
            "halaman_tercakup": len(hal) if hal else None,
        }

    per_bahasa = {b: blok([d for d in korpus if d["bahasa"] == b])
                  for b in sorted({d["bahasa"] for d in korpus})}
    per_sumber: dict[str, dict] = {}
    for d in korpus:
        kunci = f"{d['sumber']}"
        per_sumber.setdefault(kunci, {"en": [], "id": []})[d["bahasa"]].append(d)
    sumber_ringkas = {
        s: {b: blok(v[b]) for b in ("en", "id") if v[b]}
        for s, v in sorted(per_sumber.items())
    }
    return {
        "per_bahasa": per_bahasa,
        "per_sumber": sumber_ringkas,
        "total_chunk": len(korpus),
        "total_token": sum(d["token"] for d in korpus),
    }


def main() -> int:
    lama = DATA / "korpus.jsonl"
    cadangan = DATA / "korpus_dwm_v1.jsonl"
    if lama.exists() and not cadangan.exists():
        cadangan.write_text(lama.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"cadangan korpus lama → {cadangan.name}")

    korpus = dwm()
    for daftar in (SUMBER_EN, SUMBER_ID):
        for sumber, berkas in daftar:
            for nama in berkas:
                bahasa = "en" if nama.endswith("_en") else "id"
                for d in muat(SRC / f"{nama}.jsonl"):
                    korpus.append(normal(d, sumber, bahasa))

    # buang duplikat teks persis
    terlihat, unik = set(), []
    for d in korpus:
        if d["hash"] in terlihat:
            print(f"  duplikat dibuang: {d['id']}")
            continue
        terlihat.add(d["hash"])
        unik.append(d)
    korpus = unik

    urutan_sumber = ["who-dwm-2020-eng", "who-dwm-2020-ind", "who-pm-18-5-eng", "who-pm-18-5-id",
                     "modul-thought-record", "mindurset-cards-v1"]
    korpus.sort(key=lambda d: (d["bahasa"], urutan_sumber.index(d["sumber"]), d["id"]))

    with lama.open("w", encoding="utf-8") as f:
        for d in korpus:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    st = statistik(korpus)
    (DATA / "korpus_stats.json").write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")

    # angka untuk Tabel II
    baris = ["| Sumber | Bahasa | Chunk | Kata | Token | Token/chunk (median, min–maks) | Di bawah 300 | Di atas 500 |",
             "|---|---|---|---|---|---|---|---|"]
    for sumber, per_b in st["per_sumber"].items():
        for b, v in per_b.items():
            baris.append(f"| {sumber} | {b} | {v['chunk']} | {v['kata']} | {v['token']} | "
                         f"{v['token_median']:.0f} ({v['token_min']}–{v['token_maks']}) | "
                         f"{v['di_bawah_300']} | {v['di_atas_500']} |")
    for b, v in st["per_bahasa"].items():
        baris.append(f"| **total {b}** | {b} | {v['chunk']} | {v['kata']} | {v['token']} | "
                     f"{v['token_median']:.0f} ({v['token_min']}–{v['token_maks']}) | "
                     f"{v['di_bawah_300']} | {v['di_atas_500']} |")
    (DATA / "korpus_tabel.md").write_text("\n".join(baris) + "\n", encoding="utf-8")

    print(json.dumps({"total_chunk": st["total_chunk"], "total_token": st["total_token"],
                      "per_bahasa": {b: v["chunk"] for b, v in st["per_bahasa"].items()}}, indent=2,
                     ensure_ascii=False))
    for b, v in st["per_bahasa"].items():
        if v["di_bawah_300"] or v["di_atas_500"]:
            print(f"  perhatian {b}: {v['di_bawah_300']} chunk <300 token, {v['di_atas_500']} chunk >500 token")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
