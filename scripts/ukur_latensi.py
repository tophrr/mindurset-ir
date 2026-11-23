#!/usr/bin/env python3
"""Ukur latensi empat konfigurasi pada satu lingkungan CPU.

M1 dan M2: pencarian murni. M3: pengodean kueri dengan ONNX (BGE-M3 int8) ditambah pencarian
kosinus. M4: M2 + M3 + RRF. Semua dijalankan pada kueri yang sama, berulang, lalu dilaporkan
mean, median, p95, dan maks.

Pemakaian:
    python3 eksperimen/ukur_latensi.py --ulang 3
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_eval import BM25, TFIDF, rrf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--korpus", default=str(ROOT / "data/korpus.jsonl"))
    ap.add_argument("--kueri", default=str(ROOT / "data/kueri.jsonl"))
    ap.add_argument("--emb-chunk", default=str(ROOT / "hasil/emb_chunk_cls.npy"))
    ap.add_argument("--model-dir", default="/home/chrisg/.hermes/cache/scratch/bge-m3-onnx")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--ulang", type=int, default=3)
    ap.add_argument("--k", type=int, default=10)
    a = ap.parse_args()

    korpus = [json.loads(l) for l in Path(a.korpus).read_text(encoding="utf-8").splitlines() if l.strip()]
    kueri = [json.loads(l) for l in Path(a.kueri).read_text(encoding="utf-8").splitlines() if l.strip()]
    ids = [d["id"] for d in korpus]

    t0 = time.perf_counter()
    m1 = TFIDF(korpus)
    t_m1 = time.perf_counter() - t0
    t0 = time.perf_counter()
    m2 = BM25(korpus, k1=1.2, b=0.75)
    t_m2 = time.perf_counter() - t0

    mat = np.load(a.emb_chunk).astype("float32")
    tok = Tokenizer.from_file(str(Path(a.model_dir) / "tokenizer.json"))
    tok.enable_truncation(max_length=512)
    so = ort.SessionOptions()
    so.intra_op_num_threads = a.threads
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sesi = ort.InferenceSession(str(Path(a.model_dir) / "model_int8.onnx"), sess_options=so,
                               providers=["CPUExecutionProvider"])
    nama_masuk = [i.name for i in sesi.get_inputs()]

    def kodekan(teks: str) -> np.ndarray:
        e = tok.encode(teks)
        ids_ = np.array([e.ids], dtype=np.int64)
        mask = np.array([e.attention_mask], dtype=np.int64)
        masuk = {"input_ids": ids_, "attention_mask": mask}
        if "token_type_ids" in nama_masuk:
            masuk["token_type_ids"] = np.zeros_like(ids_)
        h = sesi.run(None, {k: v for k, v in masuk.items() if k in nama_masuk})[0]
        v = h[:, 0, :][0]
        return v / (np.linalg.norm(v) or 1.0)

    waktu = {n: [] for n in ("M1", "M2", "M3", "M4")}
    for _ in range(a.ulang):
        for q in kueri:
            t = time.perf_counter(); d1 = m1.cari(q["teks"], a.k); waktu["M1"].append((time.perf_counter() - t) * 1000)
            t = time.perf_counter(); d2 = m2.cari(q["teks"], a.k); lama2 = (time.perf_counter() - t) * 1000
            waktu["M2"].append(lama2)
            t = time.perf_counter()
            v = kodekan(q["teks"])
            skor = mat @ v
            urut = np.argsort(-skor)[:a.k]
            d3 = [(ids[i], float(skor[i])) for i in urut]
            lama3 = (time.perf_counter() - t) * 1000
            waktu["M3"].append(lama3)
            t = time.perf_counter(); _ = rrf([d2, d3], k=60); lama_rrf = (time.perf_counter() - t) * 1000
            waktu["M4"].append(lama2 + lama3 + lama_rrf)

    ringkas = {}
    for n, v in waktu.items():
        v2 = sorted(v)
        ringkas[n] = {"mean": round(st.mean(v), 2), "median": round(st.median(v), 2),
                      "p95": round(v2[int(0.95 * len(v2)) - 1], 2), "maks": round(max(v), 2),
                      "n": len(v)}
    keluar = {"lingkungan": {"threads": a.threads, "ulang": a.ulang, "kueri": len(kueri)},
              "bangun_indeks_detik": {"M1_M2": round(t_m1 + t_m2, 3)}, "latensi_ms": ringkas}
    p = ROOT / "hasil/latensi_cpu.json"
    p.write_text(json.dumps(keluar, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(keluar, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
