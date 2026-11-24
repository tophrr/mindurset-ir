#!/usr/bin/env python3
"""Utilitas bersama untuk seluruh skrip repo artefak IR Mind-Ur-Set.

Isi:
    ROOT        akar repo (dua tingkat di atas berkas ini)
    baca_jsonl  baca satu berkas JSONL menjadi daftar dict
    tulis_jsonl tulis daftar dict menjadi JSONL (UTF-8, satu baris per dict)
    model_dir   tentukan direktori model BGE-M3 ONNX

Urutan penentuan model: argumen --model-dir, lalu variabel lingkungan
BGE_MODEL_DIR, lalu ``models/bge-m3-onnx`` di dalam repo.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKRIP = Path(__file__).resolve().parent
EVAL = SKRIP / "eval"


def baca_jsonl(jalur: str | Path) -> list[dict]:
    """Baca JSONL; baris kosong dilewati."""
    return [json.loads(b) for b in Path(jalur).read_text(encoding="utf-8").splitlines() if b.strip()]


def tulis_jsonl(jalur: str | Path, baris: list[dict]) -> None:
    """Tulis JSONL; direktori induk dibuat bila belum ada."""
    p = Path(jalur)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for b in baris:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")


def model_dir(nilai: str | None = None) -> Path:
    """Kembalikan direktori model BGE-M3 ONNX, atau hentikan dengan pesan jelas."""
    kandidat = Path(nilai) if nilai else Path(os.environ.get("BGE_MODEL_DIR", ROOT / "models" / "bge-m3-onnx"))
    if not (kandidat / "model_int8.onnx").exists():
        sys.exit(
            f"model BGE-M3 tidak ditemukan di {kandidat}\n"
            "unduh: https://huggingface.co/Xenova/bge-m3/tree/main/onnx (model_int8.onnx,\n"
            "tokenizer.json, tokenizer_config.json, special_tokens_map.json, config.json)\n"
            "lalu jalankan ulang dengan --model-dir <folder> atau set BGE_MODEL_DIR"
        )
    return kandidat


if __name__ == "__main__":
    print("ROOT :", ROOT)
    print("EVAL :", EVAL)
    print("model:", os.environ.get("BGE_MODEL_DIR", ROOT / "models" / "bge-m3-onnx"))
