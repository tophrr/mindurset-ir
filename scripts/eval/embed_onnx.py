#!/usr/bin/env python3
"""Embedding BGE-M3 dengan ONNX Runtime, tanpa torch.

Dipakai bila mesin tidak punya `sentence-transformers`/torch: model ONNX int8 dari
`Xenova/bge-m3` dijalankan di CPU, mean pooling dengan attention mask, lalu L2 normalisasi.
Keluaran berupa dua berkas .npy yang bisa dibaca `retrieval_eval.py --dense-backend berkas`.

Pemakaian:
    python3 eksperimen/embed_onnx.py \
        --korpus data/korpus.jsonl --kueri data/kueri.jsonl \
        --keluaran-chunk hasil/emb_chunk.npy --keluaran-kueri hasil/emb_kueri.npy
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _umum import model_dir  # noqa: E402


def muat_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default=None, help="folder model ONNX; bawaan dari BGE_MODEL_DIR atau models/bge-m3-onnx")
    ap.add_argument("--berkas-model", default="model_int8.onnx")
    ap.add_argument("--korpus", default="data/korpus.jsonl")
    ap.add_argument("--kueri", default="data/kueri.jsonl")
    ap.add_argument("--keluaran-chunk", default="hasil/emb_chunk.npy")
    ap.add_argument("--keluaran-kueri", default="hasil/emb_kueri.npy")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--maks-panjang", type=int, default=512)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--pooling", default="cls", choices=["cls", "mean"],
                    help="bge-m3 memakai CLS (bawaan); mean hanya untuk pembanding")
    a = ap.parse_args()

    md = model_dir(a.model_dir)
    tok = Tokenizer.from_file(str(md / "tokenizer.json"))
    tok.enable_truncation(max_length=a.maks_panjang)
    tok.enable_padding(pad_id=1, pad_token="<pad>")

    so = ort.SessionOptions()
    so.intra_op_num_threads = a.threads
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sesi = ort.InferenceSession(str(md / a.berkas_model), sess_options=so,
                                providers=["CPUExecutionProvider"])
    nama_masuk = [i.name for i in sesi.get_inputs()]
    nama_keluar = [o.name for o in sesi.get_outputs()]

    def kodekan(teks: list[str]) -> np.ndarray:
        keluar = []
        for i in range(0, len(teks), a.batch):
            potong = teks[i:i + a.batch]
            enc = tok.encode_batch(potong)
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            masuk = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in nama_masuk:
                masuk["token_type_ids"] = np.zeros_like(ids)
            hasil = sesi.run(nama_keluar, {k: v for k, v in masuk.items() if k in nama_masuk})
            h = hasil[0]
            if h.ndim == 3:
                if a.pooling == "cls":
                    v = h[:, 0, :]
                else:
                    m = mask[..., None].astype(np.float32)
                    v = (h * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
            else:
                v = h
            v = v / np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-12, None)
            keluar.append(v.astype(np.float32))
        return np.vstack(keluar)

    korpus = muat_jsonl(Path(a.korpus))
    kueri = muat_jsonl(Path(a.kueri))
    print(f"model {a.berkas_model} | masukan {nama_masuk} | keluaran {nama_keluar} | thread {a.threads}")

    t0 = time.perf_counter()
    emb_k = kodekan([d["teks"] for d in korpus])
    t1 = time.perf_counter()
    emb_q = kodekan([d["teks"] for d in kueri])
    t2 = time.perf_counter()

    Path(a.keluaran_chunk).parent.mkdir(parents=True, exist_ok=True)
    np.save(a.keluaran_chunk, emb_k)
    np.save(a.keluaran_kueri, emb_q)
    peta = Path(str(a.keluaran_kueri) + ".idx.json")
    peta.write_text(json.dumps({q["qid"]: i for i, q in enumerate(kueri)}), encoding="utf-8")

    print(json.dumps({
        "dimensi": int(emb_k.shape[1]),
        "chunk": int(emb_k.shape[0]),
        "kueri": int(emb_q.shape[0]),
        "detik_chunk": round(t1 - t0, 1),
        "detik_kueri": round(t2 - t1, 1),
        "ms_per_chunk": round((t1 - t0) * 1000 / max(1, emb_k.shape[0]), 1),
        "norma_chunk_median": float(np.median(np.linalg.norm(emb_k, axis=1))),
        "keluaran": [a.keluaran_chunk, a.keluaran_kueri],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
