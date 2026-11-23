#!/usr/bin/env python3
"""Gabungkan anotasi A, B, dan hasil adjudikasi menjadi qrels final.

Aturan:
    - Pasangan yang disepakati A dan B  -> label yang disepakati.
    - Pasangan yang berselisih          -> `label_final` dari berkas adjudikasi.
    - Bila ada perselisihan yang belum diputuskan, skrip berhenti dan melaporkan jumlahnya
      (kecuali `--paksa-model`, yang memakai pendapat model penilai sebagai cadangan).

Pemakaian:
    python3 eksperimen/gabung_qrels.py --adjudikasi data/anotasi/ekspor/adjudikasi_tora.jsonl
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANOT = ROOT / "data" / "anotasi" / "ekspor"


def muat(path: Path, kunci_label: str = "label") -> dict[tuple[str, str], object]:
    if not path.exists():
        raise SystemExit(f"berkas tidak ada: {path}")
    hasil = {}
    for baris in path.read_text(encoding="utf-8").splitlines():
        if not baris.strip():
            continue
        r = json.loads(baris)
        hasil[(r["qid"], r["doc_id"])] = r.get(kunci_label)
    return hasil


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default=str(ANOT / "anotator_a.jsonl"))
    ap.add_argument("--b", default=str(ANOT / "anotator_b.jsonl"))
    ap.add_argument("--adjudikasi", default=str(ANOT / "adjudikasi_tora.jsonl"))
    ap.add_argument("--keluaran", default=str(ROOT / "data" / "qrels_final.jsonl"))
    ap.add_argument("--paksa-model", action="store_true",
                    help="pakai label_model untuk perselisihan yang belum diputuskan")
    a = ap.parse_args()

    A = muat(Path(a.a))
    B = muat(Path(a.b))
    adj = {}
    p = Path(a.adjudikasi)
    if p.exists():
        for baris in p.read_text(encoding="utf-8").splitlines():
            if not baris.strip():
                continue
            r = json.loads(baris)
            adj[(r["qid"], r["doc_id"])] = r
    else:
        print(f"peringatan: berkas adjudikasi belum ada ({p})")

    kunci = sorted(set(A) & set(B))
    if not kunci:
        raise SystemExit("tidak ada pasangan yang beririsan antara A dan B")

    qrels, sumber = {}, Counter()
    belum = []
    for k in kunci:
        if A[k] == B[k]:
            qrels[k] = int(A[k])
            sumber["sepakat"] += 1
            continue
        r = adj.get(k)
        final = None if r is None else r.get("label_final")
        if final is None:
            if a.paksa_model and r is not None and r.get("label_model") is not None:
                qrels[k] = int(r["label_model"])
                sumber["dipaksa-model"] += 1
                continue
            belum.append(k)
            continue
        qrels[k] = int(final)
        sumber["adjudikasi"] += 1

    if belum:
        print(f"GAGAL: {len(belum)} perselisihan belum diputuskan. Contoh: {belum[:3]}")
        print("Lengkapi berkas adjudikasi, atau jalankan dengan --paksa-model.")
        return 2

    out = Path(a.keluaran)
    with out.open("w", encoding="utf-8") as f:
        for k in kunci:
            f.write(json.dumps({"qid": k[0], "doc_id": k[1], "label": qrels[k]}, ensure_ascii=False) + "\n")

    positif = sum(qrels.values())
    print(json.dumps({
        "pasangan": len(kunci),
        "positif": positif,
        "positif_persen": round(100 * positif / len(kunci), 1),
        "asal_label": dict(sumber),
        "keluaran": str(out),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
