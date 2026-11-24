#!/usr/bin/env python3
"""Bangun kolam kandidat anotasi (G-α3) dari peringkat M1 dan M2.

Untuk setiap kueri, sepuluh teratas M1 (VSM TF-IDF) dan sepuluh teratas M2 (Okapi BM25)
digabung menjadi satu kolam kandidat. Anotator menilai setiap pasangan kueri–chunk secara
biner tanpa melihat model mana yang mengangkat chunk tersebut (anotasi buta peringkat).

Keluaran (folder data/anotasi/):
    kolam_kandidat.jsonl   satu baris per pasangan, lengkap dengan metadata chunk
    anotator_a.jsonl       lembar kerja anotator A (label kosong)
    anotator_b.jsonl       lembar kerja anotator B (label kosong)
    ringkasan_kolam.json   statistik kolam, termasuk tumpang tindih M1 dan M2

Pemakaian:
    python3 eksperimen/bangun_kolam_anotasi.py
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from retrieval_eval import BM25, TFIDF  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = DATA / "anotasi"
K = 10
CUPLIKAN = 700


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--korpus", default=str(DATA / "korpus.jsonl"))
    ap.add_argument("--kueri", default=str(DATA / "kueri.jsonl"))
    ap.add_argument("--keluaran", default=str(OUT))
    ap.add_argument("--seed", type=int, default=20261117)
    ap.add_argument("--tambahan", default=str(DATA / "anotasi" / "kandidat_m3_m4.jsonl"),
                    help="kandidat M3/M4 dari eksperimen/dense_pool.py (opsional)")
    a = ap.parse_args()

    korpus = [json.loads(l) for l in Path(a.korpus).read_text(encoding="utf-8").splitlines() if l.strip()]
    kueri = [json.loads(l) for l in Path(a.kueri).read_text(encoding="utf-8").splitlines() if l.strip()]
    peta = {d["id"]: d for d in korpus}

    model: dict[str, tuple[TFIDF, BM25]] = {}
    for bahasa in ("id", "en"):
        subset = [d for d in korpus if d["bahasa"] == bahasa]
        model[bahasa] = (TFIDF(subset), BM25(subset))

    kolam = []
    ringkas_kueri = []
    for q in kueri:
        m1, m2 = model[q["bahasa"]]
        p1 = m1.cari(q["teks"], K)
        p2 = m2.cari(q["teks"], K)
        posisi = {}
        for peringkat, (doc_id, skor) in enumerate(p1, start=1):
            posisi.setdefault(doc_id, {})["m1"] = (peringkat, skor)
        for peringkat, (doc_id, skor) in enumerate(p2, start=1):
            posisi.setdefault(doc_id, {})["m2"] = (peringkat, skor)
        for doc_id, r in posisi.items():
            d = peta[doc_id]
            kolam.append({
                "qid": q["qid"],
                "doc_id": doc_id,
                "bahasa": q["bahasa"],
                "topik": q["topik"],
                "kueri": q["teks"],
                "sumber": d["sumber"],
                "bagian": d.get("bagian", ""),
                "halaman": d.get("halaman"),
                "cuplikan": d["teks"][:CUPLIKAN] + ("…" if len(d["teks"]) > CUPLIKAN else ""),
                "token_chunk": d["token"],
                "rank_m1": r.get("m1", (None, 0.0))[0],
                "rank_m2": r.get("m2", (None, 0.0))[0],
            })
        ringkas_kueri.append({
            "qid": q["qid"], "bahasa": q["bahasa"], "topik": q["topik"],
            "kandidat": len(posisi),
            "hanya_m1": len({d for d, _ in p1} - {d for d, _ in p2}),
            "hanya_m2": len({d for d, _ in p2} - {d for d, _ in p1}),
            "irisan": len({d for d, _ in p1} & {d for d, _ in p2}),
        })

    # kandidat tambahan dari M3 dan M4 (kalau uji dense sudah dijalankan)
    tambahan = Path(a.tambahan)
    baru: list[dict] = []
    if tambahan.exists():
        peta_kueri = {q["qid"]: q for q in kueri}
        sudah = {(d["qid"], d["doc_id"]) for d in kolam}
        for baris in tambahan.read_text(encoding="utf-8").splitlines():
            if not baris.strip():
                continue
            t = json.loads(baris)
            if (t["qid"], t["doc_id"]) in sudah:
                for d in kolam:
                    if d["qid"] == t["qid"] and d["doc_id"] == t["doc_id"]:
                        d["rank_m3"] = t.get("rank_m3")
                        d["rank_m4"] = t.get("rank_m4")
                continue
            q = peta_kueri[t["qid"]]
            d = peta[t["doc_id"]]
            baru.append({
                "qid": t["qid"], "doc_id": t["doc_id"], "bahasa": q["bahasa"], "topik": q["topik"],
                "kueri": q["teks"], "sumber": d["sumber"], "bagian": d.get("bagian", ""),
                "halaman": d.get("halaman"),
                "cuplikan": d["teks"][:CUPLIKAN] + ("…" if len(d["teks"]) > CUPLIKAN else ""),
                "token_chunk": d["token"],
                "rank_m1": None, "rank_m2": None,
                "rank_m3": t.get("rank_m3"), "rank_m4": t.get("rank_m4"),
            })
        kolam.extend(baru)
    for d in kolam:
        d.setdefault("rank_m3", None)
        d.setdefault("rank_m4", None)

    out = Path(a.keluaran)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "kolam_kandidat.jsonl").exists():
        (out / "kolam_kandidat_sebelum.jsonl").write_text(
            (out / "kolam_kandidat.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    with (out / "kolam_kandidat.jsonl").open("w", encoding="utf-8") as f:
        for d in kolam:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # lembar kerja per anotator: urutan diacak berbeda, kolom label kosong
    for nama, seed in (("a", a.seed), ("b", a.seed + 1)):
        acak = list(kolam)
        random.Random(seed).shuffle(acak)
        with (out / f"anotator_{nama}.jsonl").open("w", encoding="utf-8") as f:
            for d in acak:
                f.write(json.dumps({"qid": d["qid"], "doc_id": d["doc_id"],
                                    "bahasa": d["bahasa"], "label": None}, ensure_ascii=False) + "\n")

    # lembar kerja untuk pasangan tambahan saja (kalau kolam pernah dibangun sebelumnya)
    sebelum = out / "kolam_kandidat_sebelum.jsonl"
    jumlah_tambahan = 0
    if sebelum.exists():
        lama = {(json.loads(l)["qid"], json.loads(l)["doc_id"])
                for l in sebelum.read_text(encoding="utf-8").splitlines() if l.strip()}
        tambah = [d for d in kolam if (d["qid"], d["doc_id"]) not in lama]
        jumlah_tambahan = len(tambah)
        for nama, seed in (("a", a.seed), ("b", a.seed + 1)):
            acak = list(tambah)
            random.Random(seed).shuffle(acak)
            with (out / f"anotator_{nama}_tambahan.jsonl").open("w", encoding="utf-8") as f:
                for d in acak:
                    f.write(json.dumps({"qid": d["qid"], "doc_id": d["doc_id"],
                                        "bahasa": d["bahasa"], "label": None}, ensure_ascii=False) + "\n")

    hitung = {}
    for d in kolam:
        hitung[d["qid"]] = hitung.get(d["qid"], 0) + 1
    for r in ringkas_kueri:
        r["kandidat"] = hitung.get(r["qid"], 0)
    per_kueri = [r["kandidat"] for r in ringkas_kueri]
    ringkasan = {
        "pasangan_total": len(kolam),
        "pasangan_tambahan": jumlah_tambahan,
        "kandidat_dari_dense": sum(1 for d in kolam if d.get("rank_m3") or d.get("rank_m4")),
        "kueri": len(kueri),
        "kandidat_per_kueri": {
            "min": min(per_kueri), "maks": max(per_kueri),
            "median": statistics.median(per_kueri), "rata": round(statistics.mean(per_kueri), 1),
        },
        "irisan_m1_m2": {
            "rata": round(statistics.mean(r["irisan"] for r in ringkas_kueri), 1),
            "min": min(r["irisan"] for r in ringkas_kueri),
            "maks": max(r["irisan"] for r in ringkas_kueri),
        },
        "per_bahasa": {
            b: {
                "pasangan": sum(1 for d in kolam if d["bahasa"] == b),
                "kueri": sum(1 for q in kueri if q["bahasa"] == b),
            } for b in ("id", "en")
        },
        "kalibrasi": ([r["qid"] for r in ringkas_kueri if r["bahasa"] == "id"][:10]
                      + [r["qid"] for r in ringkas_kueri if r["bahasa"] == "en"][:10]),
        "per_kueri": ringkas_kueri,
    }
    (out / "ringkasan_kolam.json").write_text(json.dumps(ringkasan, indent=2, ensure_ascii=False),
                                              encoding="utf-8")
    print(json.dumps({k: v for k, v in ringkasan.items() if k != "per_kueri"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
