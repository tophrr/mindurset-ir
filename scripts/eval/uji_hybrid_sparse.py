#!/usr/bin/env python3
"""Uji konfigurasi tambahan M3.1/M3.2: BGE-M3 hibrida dense + sparse.

M3.1 = Reciprocal Rank Fusion atas peringkat dense (M3) dan peringkat sparse BGE-M3,
       dengan k = 60, sama seperti M4 yang memadukan BM25 dan dense.
M3.2 = gabungan skor berbobot 0,5 dense + 0,5 sparse setelah min-max normalisasi per kueri.
M3s  = sparse BGE-M3 saja (pembanding, untuk melihat sumbangan tiap komponen).

M1, M2, M3, M4 dihitung ulang di skrip ini dengan pustaka yang sama seperti
`retrieval_eval.py`, supaya tabelnya sebanding dan angkanya bisa dicocokkan.

Pemakaian:
    python3 scripts/eval/uji_hybrid_sparse.py --qrels data/qrels_final.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics as st
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_eval import BM25, TFIDF, muat_jsonl, muat_qrels, p_at_k, r_at_k, rr, rrf, wilcoxon  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def minmax(skor: dict[str, float]) -> dict[str, float]:
    if not skor:
        return {}
    lo, hi = min(skor.values()), max(skor.values())
    if hi - lo < 1e-12:
        return {k: 0.0 for k in skor}
    return {k: (v - lo) / (hi - lo) for k, v in skor.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--korpus", default=str(ROOT / "data/korpus.jsonl"))
    ap.add_argument("--kueri", default=str(ROOT / "data/kueri.jsonl"))
    ap.add_argument("--qrels", default=str(ROOT / "data/qrels_final.jsonl"))
    ap.add_argument("--dense-chunk", default=str(ROOT / "hasil/emb_chunk_cls.npy"))
    ap.add_argument("--dense-kueri", default=str(ROOT / "hasil/emb_kueri_cls.npy"))
    ap.add_argument("--sparse-korpus", default=str(ROOT / "hasil/sparse_korpus.jsonl"))
    ap.add_argument("--sparse-kueri", default=str(ROOT / "hasil/sparse_kueri.jsonl"))
    ap.add_argument("--k", type=int, nargs="+", default=[1, 3, 5, 10])
    ap.add_argument("--rrf-k", type=int, default=60)
    ap.add_argument("--bobot-dense", type=float, default=0.5)
    a = ap.parse_args()

    korpus = muat_jsonl(a.korpus)
    kueri = [q for q in muat_jsonl(a.kueri)]
    qrels = muat_qrels(a.qrels)
    ids = [d["id"] for d in korpus]
    id_sah = set(ids)

    m1 = TFIDF(korpus)
    m2 = BM25(korpus, k1=1.2, b=0.75)

    mat = np.load(a.dense_chunk).astype("float32")
    qmat = np.load(a.dense_kueri).astype("float32")
    peta_q = {q["qid"]: i for i, q in enumerate(muat_jsonl(a.kueri))}

    sp_k = {d["id"]: {int(k): float(v) for k, v in d["sparse"].items()}
            for d in muat_jsonl(a.sparse_korpus)}
    sp_q = {d["qid"]: {int(k): float(v) for k, v in d["sparse"].items()}
            for d in muat_jsonl(a.sparse_kueri)}

    K = max(a.k)
    hasil = {n: {"MRR": [], **{f"P@{k}": [] for k in a.k}, **{f"R@{k}": [] for k in a.k}}
             for n in ("M1", "M2", "M3", "M3s", "M4", "M3.1", "M3.2")}

    for q in kueri:
        relevan = {d for d in qrels.get(q["qid"], set()) if d in id_sah}
        if not relevan:
            continue
        qid = q["qid"]

        d1 = m1.cari(q["teks"], K)
        d2 = m2.cari(q["teks"], K)

        iv = qmat[peta_q[qid]]
        iv = iv / (np.linalg.norm(iv) or 1.0)
        skor_d = mat @ iv
        urut_d = [(ids[i], float(skor_d[i])) for i in np.argsort(-skor_d)]
        d3 = urut_d[:K]

        sq = sp_q[qid]
        skor_s = {cid: sum(w * sp_k[cid].get(t, 0.0) for t, w in sq.items()) for cid in ids}
        d3s = sorted(skor_s.items(), key=lambda x: (-x[1], x[0]))[:K]

        d4 = rrf([d2, d3], k=a.rrf_k)
        d31 = rrf([d3, d3s], k=a.rrf_k)

        nd, ns = minmax(skor_s), minmax({i: float(skor_d[j]) for j, i in enumerate(ids)})
        gab = {i: a.bobot_dense * nd[i] + (1 - a.bobot_dense) * ns[i] for i in ids}
        d32 = sorted(gab.items(), key=lambda x: (-x[1], x[0]))[:K]

        for nama, urutan in (("M1", d1), ("M2", d2), ("M3", d3), ("M3s", d3s),
                             ("M4", d4), ("M3.1", d31), ("M3.2", d32)):
            daftar = [d for d, _ in urutan]
            for k in a.k:
                hasil[nama][f"P@{k}"].append(p_at_k(daftar, relevan, k))
                hasil[nama][f"R@{k}"].append(r_at_k(daftar, relevan, k))
            hasil[nama]["MRR"].append(rr(daftar, relevan))

    kolom = [f"P@{k}" for k in a.k] + [f"R@{max(a.k)}", "MRR"]
    baris = ["| Konfigurasi | " + " | ".join(kolom) + " |", "|---" * (len(kolom) + 1) + "|"]
    for nama in ("M1", "M2", "M3", "M3s", "M4", "M3.1", "M3.2"):
        b = hasil[nama]
        if not b["MRR"]:
            continue
        baris.append("| " + nama + " | " + " | ".join(
            f"{st.mean(b[c]):.3f}" for c in kolom) + " |")
    print("\n".join(baris))

    print(f"\nkueri dinilai: {len(hasil['M1']['MRR'])}")
    for lawan in ("M3", "M4", "M1", "M3s"):
        x, y = hasil["M3.1"]["MRR"], hasil[lawan]["MRR"]
        if len(x) == len(y) and x:
            stat, p = wilcoxon(x, y)
            print(f"M3.1 vs {lawan}: selisih MRR {st.mean(x) - st.mean(y):+.3f}, W={stat:.1f}, p={p:.4f}")

    ringkas = {n: {"MRR": round(st.mean(v["MRR"]), 4),
                   **{c: round(st.mean(v[c]), 4) for c in kolom if c != "MRR"}}
               for n, v in hasil.items() if v["MRR"]}
    keluar = ROOT / "hasil" / "uji_hybrid_sparse.json"
    keluar.write_text(json.dumps({
        "konfigurasi": ringkas,
        "kueri": len(hasil["M1"]["MRR"]),
        "rrf_k": a.rrf_k, "bobot_dense": a.bobot_dense,
        "embedding": {"dense": str(a.dense_chunk), "pooling": "cls", "presisi": "onnx int8"},
        "catatan": "sparse BGE-M3 dihitung dari last_hidden_state ONNX + sparse_linear.pt",
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\ntersimpan: {keluar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
