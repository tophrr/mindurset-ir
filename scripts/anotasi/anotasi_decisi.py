#!/usr/bin/env python3
"""Anotasi otomatis lewat OpenRouter Decision API (model penilai, bukan chat generatif).

Endpoint: POST https://openrouter.ai/api/alpha/decisions
Model   : perplexity/pplx-decider-v1.3:free (dikenali sebagai ...-20261112)

Setiap pasangan kueri–chunk dikirim sebagai satu `state` teks, lalu model menjawab pertanyaan
bertipe: tiga `noul` (probabilitas 0--1) untuk syarat relevansi dan satu `choice` untuk jenis
kegagalan. Label biner diturunkan dari ambang pada probabilitas `relevan`.

Hasil dipakai sebagai penilai ketiga dan qrels sementara, **bukan** pengganti dua anotator
manusia pada naskah.

Pemakaian:
    python3 scripts/anotasi/anotasi_decisi.py --dry-run --batas 5
    python3 scripts/anotasi/anotasi_decisi.py --batas 20              # uji kecil
    python3 scripts/anotasi/anotasi_decisi.py --pekerja 4             # seluruh kolam
    python3 scripts/anotasi/anotasi_decisi.py --bandingkan data/anotasi/anotator_a.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from retrieval_eval import hitung_kappa  # noqa: E402

KOLAM = ROOT / "data" / "anotasi" / "kolam_kandidat.jsonl"
KELUARAN = ROOT / "hasil" / "label_model" / "anotasi_decisi.jsonl"
QRELS = ROOT / "hasil" / "label_model" / "qrels_decisi.jsonl"
CACHE = ROOT / "data" / "anotasi" / "cache_decisi.jsonl"
URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "perplexity/pplx-decider-v1.3:free"
VERSI_STATE = "s1"
MAKS_KARAKTER_CHUNK = 2600
AMBANG = 0.5


def muat_kunci(nama: str = "OPENROUTER_API_KEY") -> str:
    """Kunci dari lingkungan atau ~/.hermes/.env (tidak pernah dicetak)."""
    kunci = os.environ.get(nama, "").strip()
    if kunci:
        return kunci
    env = Path.home() / ".hermes" / ".env"
    if env.exists():
        for baris in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if baris.strip().startswith(nama + "="):
                return baris.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def muat_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def kunci_cache(model: str, qid: str, doc_id: str) -> str:
    return hashlib.sha256(f"{VERSI_STATE}|{model}|{qid}|{doc_id}".encode()).hexdigest()[:24]


def susun_state(b: dict) -> str:
    hal = b.get("halaman")
    hal = ",".join(map(str, hal)) if isinstance(hal, list) else hal
    return (
        "Anda menilai relevansi potongan dokumen psikoedukasi untuk satu kueri pengguna.\n"
        "Korpus diambil dari panduan WHO dan kartu koping aplikasi kesehatan mental mahasiswa.\n\n"
        f"KUERI PENGGUNA\n{b['kueri']}\n\n"
        f"POTONGAN DOKUMEN\n{b['cuplikan'][:MAKS_KARAKTER_CHUNK]}\n\n"
        f"ASAL POTONGAN\nsumber {b.get('sumber','')} | bagian {b.get('bagian','') or '-'} | halaman {hal}\n\n"
        "ATURAN RELEVANSI\n"
        "1. Potongan dinilai relevan hanya bila memuat langkah atau teknik koping yang bisa dijalankan, "
        "bukan sekadar penjelasan atau ajakan semangat.\n"
        "2. Teknik itu harus menjawab masalah yang diceritakan pada kueri, bukan hanya berbagi satu kata.\n"
        "3. Isinya harus aman ditampilkan kepada pengguna.\n"
        "4. Untuk kueri krisis, potongan tentang rencana keselamatan atau bantuan darurat dinilai relevan.\n"
        "5. Bila ragu, nilai tidak relevan."
    )


PERTANYAAN = {
    "relevan": {
        "type": "noul",
        "instructions": "Apakah potongan ini layak ditampilkan sebagai saran untuk kueri tersebut?",
        "criteria": {
            "true": "memuat teknik koping yang cocok dengan masalah pada kueri dan dapat dijalankan",
            "false": "tidak cocok, hanya penjelasan umum, topik sama tetapi teknik berbeda, atau membahas masalah lain",
        },
    },
    "ada_teknik": {
        "type": "noul",
        "instructions": "Apakah potongan memuat langkah atau teknik konkret, bukan hanya penjelasan?",
        "criteria": {"true": "ada langkah atau teknik yang bisa dijalankan",
                     "false": "hanya penjelasan, definisi, atau ajakan umum"},
    },
    "cocok_masalah": {
        "type": "noul",
        "instructions": "Apakah teknik itu menjawab masalah spesifik yang diceritakan pada kueri?",
        "criteria": {"true": "menjawab masalah pada kueri",
                     "false": "tidak menjawab masalah pada kueri"},
    },
    "jenis": {
        "type": "choice",
        "instructions": "Apa jenis hubungan antara potongan dan kueri?",
        "criteria": {
            "relevan": "potongan memuat teknik yang cocok",
            "topik_sama": "topik sama tetapi teknik berbeda",
            "umum": "hanya penjelasan umum tanpa langkah",
            "masalah_lain": "membahas masalah lain",
        },
    },
}


_lokal = threading.local()


def panggil_google(state: str, model: str, kunci: str) -> dict:
    """Decision API lewat SDK Google (kunci AI Studio).

    Berbeda dari endpoint OpenRouter: pertanyaan `noul` tidak menerima `criteria`,
    dan teks masukan dikirim sebagai `input`, bukan `state`.
    """
    from google import genai  # type: ignore

    # klien SDK tidak aman dipakai lintas thread, jadi satu klien per thread
    if getattr(_lokal, "klien", None) is None:
        _lokal.klien = genai.Client(api_key=kunci, http_options={"api_version": "v1beta"})
    klien = _lokal.klien
    tanya = {}
    for nama, isi in PERTANYAAN.items():
        bersih = dict(isi)
        if bersih.get("type") == "noul":
            bersih.pop("criteria", None)
        tanya[nama] = bersih
    h = klien.decisions.create(model=model, input=state, questions=tanya)
    jawab = {}
    for nama, ans in h.answers.items():
        jawab[nama] = {"type": getattr(ans, "type", None),
                       "noul": getattr(ans, "noul", None),
                       "choice": getattr(ans, "choice", None),
                       "probabilities": getattr(ans, "probabilities", None),
                       "confidence": getattr(ans, "confidence", None)}
    return {"model": model, "answers": jawab, "usage": {}}


def panggil(state: str, model: str, kunci: str) -> dict:
    badan = {"model": model, "state": [state], "questions": PERTANYAAN}
    req = urllib.request.Request(URL, data=json.dumps(badan).encode(), method="POST", headers={
        "Authorization": f"Bearer {kunci}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/chrisg/kk-uas",
        "X-OpenRouter-Title": "Anotasi KK Kelompok 5",
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kolam", default=str(KOLAM))
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--penyedia", default="openrouter", choices=["openrouter", "google"],
                    help="openrouter = endpoint alpha/decisions; google = SDK genai dengan kunci AI Studio")
    ap.add_argument("--keluaran", default=str(KELUARAN))
    ap.add_argument("--qrels", default=str(QRELS), help="qrels sementara yang ditulis dari label")
    ap.add_argument("--cache", default=str(CACHE))
    ap.add_argument("--ambang", type=float, default=AMBANG)
    ap.add_argument("--batas", type=int, default=0)
    ap.add_argument("--pekerja", type=int, default=4)
    ap.add_argument("--jeda", type=float, default=0.0)
    ap.add_argument("--ulang", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bandingkan", default="")
    ap.add_argument("--sapu-ambang", action="store_true", help="hitung kappa pada beberapa ambang")
    a = ap.parse_args()

    if a.bandingkan:
        otomatis = {(d["qid"], d["doc_id"]): d for d in muat_jsonl(Path(a.keluaran))}
        manusia = {(d["qid"], d["doc_id"]): d["label"] for d in muat_jsonl(Path(a.bandingkan)) if d.get("label") is not None}
        sama = [k for k in otomatis if k in manusia]
        if not sama:
            print("tidak ada pasangan yang bisa dibandingkan")
            return 1
        hasil = []
        ambang = [0.3, 0.4, 0.5, 0.6, 0.7] if a.sapu_ambang else [a.ambang]
        for t in ambang:
            auto = {k: int(otomatis[k]["noul_relevan"] >= t) for k in sama}
            man = {k: manusia[k] for k in sama}
            k = hitung_kappa(auto, man)
            hasil.append({"ambang": t, "n": k["n"], "setuju": k["setuju"], "kappa": round(k["kappa"], 3)})
        print(json.dumps({"pasangan": len(sama), "hasil": hasil}, indent=2, ensure_ascii=False))
        return 0

    kolam = muat_jsonl(Path(a.kolam))
    if not kolam:
        print(f"kolam kosong: {a.kolam}", file=sys.stderr)
        return 1
    if a.batas:
        kolam = kolam[: a.batas]

    cache = {d["kunci"]: d for d in muat_jsonl(Path(a.cache))}
    belum = [b for b in kolam if kunci_cache(a.model, b["qid"], b["doc_id"]) not in cache]
    print(f"kolam {len(kolam)} pasangan | sudah di cache {len(kolam) - len(belum)} | akan dinilai {len(belum)}")

    if a.dry_run:
        out = Path(a.keluaran)
        with out.open("w", encoding="utf-8") as f:
            for b in kolam:
                f.write(json.dumps({"qid": b["qid"], "doc_id": b["doc_id"], "bahasa": b["bahasa"],
                                    "noul_relevan": 0.0, "label": 0, "model": a.model,
                                    "versi_state": VERSI_STATE}, ensure_ascii=False) + "\n")
        print(f"dry-run: {len(kolam)} baris ke {out}")
        return 0

    kunci = muat_kunci("GOOGLE_API_KEY" if a.penyedia == "google" else "OPENROUTER_API_KEY")
    if not kunci:
        print("kunci API tidak ditemukan (OPENROUTER_API_KEY atau GOOGLE_API_KEY)", file=sys.stderr)
        return 1

    kunci_lock = threading.Lock()
    selesai, gagal = [], 0
    t0 = time.perf_counter()

    def kerja(b: dict) -> dict:
        kc = kunci_cache(a.model, b["qid"], b["doc_id"])
        for percobaan in range(a.ulang):
            try:
                if a.penyedia == "google":
                    jawab = panggil_google(susun_state(b), a.model, kunci)
                else:
                    jawab = panggil(susun_state(b), a.model, kunci)
                ans = jawab["answers"]
                noul = float(ans["relevan"]["noul"])
                return {
                    "kunci": kc,
                    "qid": b["qid"], "doc_id": b["doc_id"], "bahasa": b["bahasa"],
                    "noul_relevan": round(noul, 4),
                    "noul_ada_teknik": round(float(ans["ada_teknik"]["noul"]), 4),
                    "noul_cocok_masalah": round(float(ans["cocok_masalah"]["noul"]), 4),
                    "jenis": ans["jenis"]["choice"],
                    "keyakinan_jenis": round(float(ans["jenis"].get("confidence", 0.0)), 4),
                    "label": int(noul >= a.ambang),
                    "model": jawab.get("model", a.model),
                    "versi_state": VERSI_STATE,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "token": (jawab.get("usage") or {}).get("input_tokens"),
                    "biaya": (jawab.get("usage") or {}).get("cost"),
                }
            except (urllib.error.HTTPError, urllib.error.URLError, KeyError, ValueError, TimeoutError):
                if percobaan == a.ulang - 1:
                    raise
                time.sleep(2 ** percobaan + random.random())
        raise RuntimeError("tidak tercapai")

    with ThreadPoolExecutor(max_workers=max(1, a.pekerja)) as pool:
        futs = {pool.submit(kerja, b): b for b in belum}
        for i, f in enumerate(as_completed(futs), start=1):
            try:
                hasil = f.result()
                with kunci_lock:
                    selesai.append(hasil)
                    with Path(a.cache).open("a", encoding="utf-8") as fc:
                        fc.write(json.dumps(hasil, ensure_ascii=False) + "\n")
                if a.jeda:
                    time.sleep(a.jeda)
            except Exception as e:
                gagal += 1
                print(f"  gagal: {e}", file=sys.stderr)
            if i % 50 == 0 or i == len(belum):
                print(f"  {i}/{len(belum)} ({gagal} gagal)")

    gabung = dict(cache)
    for d in selesai:
        gabung[d["kunci"]] = d
    terpilih = [gabung[kunci_cache(a.model, b["qid"], b["doc_id"])]
                for b in kolam if kunci_cache(a.model, b["qid"], b["doc_id"]) in gabung]
    with Path(a.keluaran).open("w", encoding="utf-8") as f:
        for d in terpilih:
            f.write(json.dumps({k: v for k, v in d.items() if k != "kunci"}, ensure_ascii=False) + "\n")
    with Path(a.qrels).open("w", encoding="utf-8") as f:
        for d in terpilih:
            f.write(json.dumps({"qid": d["qid"], "doc_id": d["doc_id"],
                                "label": d["label"]}, ensure_ascii=False) + "\n")

    label = [d["label"] for d in terpilih]
    jenis = {}
    for d in terpilih:
        jenis[d["jenis"]] = jenis.get(d["jenis"], 0) + 1
    print(json.dumps({
        "model": terpilih[0]["model"] if terpilih else a.model,
        "pasangan": len(terpilih),
        "label_1": sum(label), "label_0": len(label) - sum(label),
        "ambang": a.ambang,
        "jenis": jenis,
        "gagal": gagal,
        "detik": round(time.perf_counter() - t0, 1),
        "keluaran": str(a.keluaran), "qrels": str(a.qrels),
    }, indent=2, ensure_ascii=False))
    return 0 if gagal == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
