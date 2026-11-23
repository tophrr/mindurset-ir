#!/usr/bin/env python3
"""Hitung peringkat M3 (BGE-M3 dense) dan M4 (RRF BM25+dense) untuk kolam anotasi.

Skrip ini dijalankan di mesin ber-GPU. Keluarannya dipakai oleh
eksperimen/bangun_kolam_anotasi.py untuk memperluas kolam kandidat, dan oleh
laporan latensi (mode --device cpu) untuk Tabel IV.

Pemakaian (GPU, untuk kolam):
    python3 eksperimen/dense_pool.py --device cuda --fp16 \
        --keluaran data/anotasi/kandidat_m3_m4.jsonl --ringkasan hasil/dense_gpu.json

Pemakaian (CPU, untuk latensi yang dilaporkan):
    python3 eksperimen/dense_pool.py --device cpu \
        --keluaran hasil/dense_cpu_kandidat.jsonl --ringkasan hasil/dense_cpu.json

Uji pipa tanpa model:
    python3 eksperimen/dense_pool.py --dry-run --keluaran /tmp/uji.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieval_eval import BM25, rrf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
K = 10
RRF_K = 60


def muat(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def vektor_hash(teks: str, dimensi: int = 256) -> list[float]:
    """Pengganti sementara untuk uji pipa: bag-of-words yang diproyeksikan ke dimensi tetap."""
    v = [0.0] * dimensi
    for kata in teks.lower().split():
        v[hash(kata) % dimensi] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--korpus", default=str(ROOT / "data" / "korpus.jsonl"))
    ap.add_argument("--kueri", default=str(ROOT / "data" / "kueri.jsonl"))
    ap.add_argument("--model", default="BAAI/bge-m3")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--fp16", action="store_true")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--threads", type=int, default=0, help="jumlah thread torch intra-op (0 = bawaan)")
    ap.add_argument("--cache", default="", help="folder simpan/muat embedding korpus (mempercepat run ulang)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--k", type=int, default=K)
    ap.add_argument("--keluaran", default=str(ROOT / "data" / "anotasi" / "kandidat_m3_m4.jsonl"))
    ap.add_argument("--ringkasan", default=str(ROOT / "hasil" / "dense_ringkasan.json"))
    a = ap.parse_args()

    korpus = muat(Path(a.korpus))
    kueri = muat(Path(a.kueri))

    t_mulai = time.perf_counter()
    if a.dry_run:
        def kodekan(daftar):
            return [vektor_hash(t) for t in daftar]
        info_model = {"mode": "dry-run", "model": None, "device": "none"}
    else:
        import torch
        from sentence_transformers import SentenceTransformer

        if a.threads:
            torch.set_num_threads(a.threads)

        if a.device == "cuda" and not torch.cuda.is_available():
            print("CUDA tidak tersedia; jatuh ke CPU", file=sys.stderr)
            a.device = "cpu"
        model = SentenceTransformer(a.model, device=a.device)
        if a.fp16 and a.device == "cuda":
            model.half()

        def kodekan(daftar):
            v = model.encode(daftar, batch_size=a.batch, normalize_embeddings=True,
                             convert_to_numpy=True, show_progress_bar=False)
            return v.tolist()

        info_model = {"mode": "sentence-transformers", "model": a.model, "device": a.device,
                      "fp16": bool(a.fp16 and a.device == "cuda"),
                      "gpu": (torch.cuda.get_device_name(0) if a.device == "cuda" else None),
                      "threads_torch": torch.get_num_threads()}

    # indeks: satu ruang vektor, peringkat tetap dibatasi per bahasa
    berkas_cache = None
    if a.cache:
        import hashlib
        kunci = hashlib.sha256((a.model + "|" + Path(a.korpus).read_text(encoding="utf-8")).encode()).hexdigest()[:16]
        Path(a.cache).mkdir(parents=True, exist_ok=True)
        berkas_cache = Path(a.cache) / f"emb_{kunci}.npy"
    if berkas_cache is not None and berkas_cache.exists():
        import numpy as np
        emb_chunk = np.load(berkas_cache).tolist()
        waktu_indeks = 0.0
        dari_cache = True
    else:
        t0 = time.perf_counter()
        emb_chunk = kodekan([d["teks"] for d in korpus])
        waktu_indeks = time.perf_counter() - t0
        dari_cache = False
        if berkas_cache is not None:
            import numpy as np
            np.save(berkas_cache, np.asarray(emb_chunk, dtype="float32"))

    bm25 = {b: BM25([d for d in korpus if d["bahasa"] == b]) for b in ("id", "en")}
    posisi = {b: [i for i, d in enumerate(korpus) if d["bahasa"] == b] for b in ("id", "en")}

    latensi, keluaran = [], []
    for q in kueri:
        t1 = time.perf_counter()
        qv = kodekan([q["teks"]])[0]
        skor = []
        for i in posisi[q["bahasa"]]:
            dv = emb_chunk[i]
            skor.append((korpus[i]["id"], sum(x * y for x, y in zip(qv, dv))))
        skor.sort(key=lambda x: (-x[1], x[0]))
        m3 = skor[:a.k]
        latensi.append((time.perf_counter() - t1) * 1000.0)

        m2 = bm25[q["bahasa"]].cari(q["teks"], a.k)
        m4 = rrf([m2, m3], k=RRF_K)[:a.k]

        rank3 = {d: r for r, (d, _) in enumerate(m3, start=1)}
        rank4 = {d: r for r, (d, _) in enumerate(m4, start=1)}
        for doc_id in sorted(set(rank3) | set(rank4)):
            keluaran.append({"qid": q["qid"], "doc_id": doc_id, "bahasa": q["bahasa"],
                             "rank_m3": rank3.get(doc_id), "rank_m4": rank4.get(doc_id)})

    out = Path(a.keluaran)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for d in keluaran:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    latensi.sort()
    ringkasan = {
        **info_model,
        "chunk": len(korpus),
        "kueri": len(kueri),
        "kandidat": len(keluaran),
        "waktu_indeks_detik": round(waktu_indeks, 2),
        "indeks_dari_cache": dari_cache,
        "waktu_indeks_per_chunk_ms": round(1000 * waktu_indeks / len(korpus), 1),
        "latensi_kueri_ms": {
            "rata": round(statistics.mean(latensi), 2),
            "median": round(statistics.median(latensi), 2),
            "p95": round(latensi[int(0.95 * (len(latensi) - 1))], 2),
            "maks": round(latensi[-1], 2),
        },
        "rrf_k": RRF_K,
        "k": a.k,
    }
    Path(a.ringkasan).parent.mkdir(parents=True, exist_ok=True)
    Path(a.ringkasan).write_text(json.dumps(ringkasan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(ringkasan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
