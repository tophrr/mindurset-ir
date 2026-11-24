#!/usr/bin/env python3
"""Bobot sparse (lexical) BGE-M3 dihitung dari keluaran ONNX, tanpa torch.

BGE-M3 punya tiga keluaran: dense (CLS), sparse (bobot leksikal per token), dan multi-vector.
ONNX dari `Xenova/bge-m3` hanya mengekspor `last_hidden_state`, jadi kepala sparse dihitung
sendiri: `log(1 + relu(h . w + b))` per token, lalu nilai maksimum diambil per id token.
Bobot `w` dan `b` diambil dari `sparse_linear.pt` milik `BAAI/bge-m3` (3,5 KB) dan disimpan
sebagai `sparse_linear.npy`.

Keluaran: JSONL `{"id", "sparse": {token_id: bobot}}` untuk korpus dan kueri.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _umum import model_dir  # noqa: E402


def baca_pt_sparse(berkas: Path) -> tuple[np.ndarray, np.ndarray]:
    """Baca weight dan bias dari sparse_linear.pt tanpa torch (format zip + pickle)."""
    import io
    import pickle

    z = zipfile.ZipFile(berkas)
    nama_pkl = [n for n in z.namelist() if n.endswith("data.pkl")][0]
    awalan = nama_pkl.rsplit("data.pkl", 1)[0]

    class Gagang:
        def __init__(self, pid=None):
            self.pid = pid

    def rebuild(storage, offset, size, stride, *rest):
        return {"storage": storage, "offset": offset, "size": size, "stride": stride}

    class U(pickle.Unpickler):
        def find_class(self, mod, name):
            if mod == "torch._utils" and name.startswith("_rebuild_tensor"):
                return rebuild
            if name.endswith("Storage"):
                return Gagang
            if mod == "collections" and name == "OrderedDict":
                return dict
            return super().find_class(mod, name)

        def persistent_load(self, pid):
            return Gagang(pid)

    obj = U(io.BytesIO(z.read(nama_pkl))).load()
    hasil = {}
    for nama in ("weight", "bias"):
        t = obj[nama]
        pid = t["storage"].pid
        kunci = pid[2]
        mentah = z.read(f"{awalan}data/{kunci}")
        jum = int(np.prod(t["size"]))
        lebar = len(mentah) // jum if jum else 4
        dtype = {2: np.float16, 4: np.float32, 8: np.float64}.get(lebar, np.float32)
        arr = np.frombuffer(mentah, dtype=dtype).astype(np.float32)
        hasil[nama] = arr[:jum].reshape(t["size"])
    return hasil["weight"].reshape(-1), hasil["bias"].reshape(-1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default=None, help="folder model ONNX; bawaan dari BGE_MODEL_DIR atau models/bge-m3-onnx")
    ap.add_argument("--berkas-model", default="model_int8.onnx")
    ap.add_argument("--bobot-sparse", default=None, help="sparse_linear.pt (bawaan: <model-dir>/sparse_linear.pt)")
    ap.add_argument("--korpus", default="data/korpus.jsonl")
    ap.add_argument("--kueri", default="data/kueri.jsonl")
    ap.add_argument("--keluaran-korpus", default="hasil/sparse_korpus.jsonl")
    ap.add_argument("--keluaran-kueri", default="hasil/sparse_kueri.jsonl")
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--maks-panjang", type=int, default=512)
    ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args()

    md = model_dir(a.model_dir)
    bobot_pt = Path(a.bobot_sparse) if a.bobot_sparse else md / "sparse_linear.pt"
    w, b = baca_pt_sparse(bobot_pt)
    np.save(md / "sparse_linear.npy", np.stack([w, np.full_like(w, b[0] if b.size == 1 else 0.0)]))
    print(f"bobot sparse: {w.shape} | bias {b} | dari {bobot_pt.name}")

    tok = Tokenizer.from_file(str(md / "tokenizer.json"))
    tok.enable_truncation(max_length=a.maks_panjang)
    tok.enable_padding(pad_id=1, pad_token="<pad>")

    so = ort.SessionOptions()
    so.intra_op_num_threads = a.threads
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sesi = ort.InferenceSession(str(md / a.berkas_model), sess_options=so, providers=["CPUExecutionProvider"])
    nama_masuk = [i.name for i in sesi.get_inputs()]

    def kodekan(teks: list[str]) -> list[dict[str, float]]:
        keluar: list[dict[str, float]] = []
        for i in range(0, len(teks), a.batch):
            potong = teks[i:i + a.batch]
            enc = tok.encode_batch(potong)
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            masuk = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in nama_masuk:
                masuk["token_type_ids"] = np.zeros_like(ids)
            h = sesi.run(None, {k: v for k, v in masuk.items() if k in nama_masuk})[0]
            skor = np.log1p(np.maximum(h @ w + b[0], 0.0)) * mask  # [B,L]
            for j in range(len(potong)):
                kumpul: dict[int, float] = {}
                for pos in range(ids.shape[1]):
                    if mask[j, pos] == 0:
                        continue
                    tid = int(ids[j, pos])
                    nilai = float(skor[j, pos])
                    if nilai > kumpul.get(tid, 0.0):
                        kumpul[tid] = nilai
                keluar.append({str(k): round(v, 5) for k, v in kumpul.items() if v > 0})
        return keluar

    korpus = [json.loads(l) for l in Path(a.korpus).read_text(encoding="utf-8").splitlines() if l.strip()]
    kueri = [json.loads(l) for l in Path(a.kueri).read_text(encoding="utf-8").splitlines() if l.strip()]

    t0 = time.perf_counter()
    sp_k = kodekan([d["teks"] for d in korpus])
    t1 = time.perf_counter()
    sp_q = kodekan([d["teks"] for d in kueri])
    t2 = time.perf_counter()

    Path(a.keluaran_korpus).parent.mkdir(parents=True, exist_ok=True)
    with Path(a.keluaran_korpus).open("w", encoding="utf-8") as f:
        for d, s in zip(korpus, sp_k):
            f.write(json.dumps({"id": d["id"], "sparse": s}, ensure_ascii=False) + "\n")
    with Path(a.keluaran_kueri).open("w", encoding="utf-8") as f:
        for d, s in zip(kueri, sp_q):
            f.write(json.dumps({"qid": d["qid"], "sparse": s}, ensure_ascii=False) + "\n")

    print(json.dumps({
        "korpus": len(sp_k), "kueri": len(sp_q),
        "token_unik_median_per_chunk": int(np.median([len(s) for s in sp_k])),
        "token_unik_median_per_kueri": int(np.median([len(s) for s in sp_q])),
        "detik_korpus": round(t1 - t0, 1), "detik_kueri": round(t2 - t1, 1),
        "keluaran": [a.keluaran_korpus, a.keluaran_kueri],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
