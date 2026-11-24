#!/usr/bin/env python3
"""Harness anotasi otomatis (LLM sebagai penilai) lewat OpenRouter.

Menilai setiap pasangan kueri–chunk pada kolam anotasi dengan label biner mengikuti
`data/anotasi/PEDOMAN_ANOTASI.md`, lalu menulis qrels berprovenans (model, versi prompt,
waktu, alasan singkat). Hasil ini **bukan** pengganti dua anotator manusia yang diminta
naskah: dipakai sebagai pra-anotasi, pembanding, atau penilai ketiga, dan harus dilabeli
sebagai anotator otomatis di naskah.

Pemakaian:
    # uji tanpa jaringan
    python3 eksperimen/anotasi_otomatis.py --dry-run --batas 5

    # 20 pasangan pertama dengan model tertentu
    python3 eksperimen/anotasi_otomatis.py --model <model-id> --batas 20

    # seluruh kolam, 4 pekerja paralel, lanjutkan dari cache
    python3 eksperimen/anotasi_otomatis.py --model <model-id> --pekerja 4

    # bandingkan dengan ekspor anotator manusia
    python3 eksperimen/anotasi_otomatis.py --bandingkan data/anotasi/ekspor/anotator_a.jsonl

Kunci API dibaca dari OPENROUTER_API_KEY, atau dari baris OPENROUTER_API_KEY= di
~/.hermes/.env bila variabel lingkungan tidak diset. Kunci tidak pernah dicetak.
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
KELUARAN = ROOT / "data" / "anotasi" / "anotasi_otomatis.jsonl"
CACHE = ROOT / "data" / "anotasi" / "cache_otomatis.jsonl"
URL = "https://openrouter.ai/api/v1/chat/completions"
VERSI_PROMPT = "v1"
MAKS_KARAKTER_CHUNK = 2600

SISTEM = """Anda penilai relevansi untuk korpus psikoedukasi kesehatan mental berbahasa Indonesia dan Inggris.

Tugas: beri label biner untuk satu pasangan kueri dan chunk.
- 1 = chunk memuat keterampilan koping atau instruksi yang cocok untuk situasi pada kueri DAN dapat ditampilkan kepada pengguna sebagai saran.
- 0 = selain itu, termasuk chunk yang topiknya sama tetapi tekniknya tidak menjawab masalah pada kueri, chunk yang hanya berisi penjelasan umum, rangkuman tanpa langkah, atau potongan yang membahas masalah lain.

Beri 1 hanya bila ketiga syarat terpenuhi: (a) ada langkah atau teknik yang bisa dijalankan, (b) cocok dengan masalah pada kueri, (c) isinya aman ditampilkan.
Untuk kueri krisis, chunk rencana keselamatan atau nomor bantuan dinilai 1.
Bila ragu, pilih 0.

Jangan menulis proses berpikir, penjelasan, atau kalimat pembuka. Balas tepat satu objek JSON:
{"label": 0 atau 1, "alasan": "maksimal 20 kata"}"""

CONTOH = [
    {"kueri": "I have not slept properly for a week, my head is full until morning",
     "chunk": "Wind-down. Sleep starts before you lie down. A short wind-down gives the body a repeated signal that the day is ending: dim the lights, put the phone out of reach, and do one low-effort thing such as stretching or reading.",
     "label": 1, "alasan": "Memberi langkah tidur yang cocok dengan keluhan insomnia"},
    {"kueri": "I have not slept properly for a week, my head is full until morning",
     "chunk": "The first step of Managing Problems involves reviewing concerns and deciding whether they are solvable problems, unsolvable problems or unimportant problems.",
     "label": 0, "alasan": "Teknik penyelesaian masalah praktis, bukan kesulitan tidur"},
]


def muat_kunci() -> str:
    kunci = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if kunci:
        return kunci
    env = Path.home() / ".hermes" / ".env"
    if env.exists():
        for baris in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if baris.strip().startswith("OPENROUTER_API_KEY="):
                return baris.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def muat_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def kunci_cache(model: str, qid: str, doc_id: str) -> str:
    return hashlib.sha256(f"{VERSI_PROMPT}|{model}|{qid}|{doc_id}".encode()).hexdigest()[:24]


def susun_pesan(baris: dict) -> list[dict]:
    kueri = baris["kueri"]
    chunk = baris["cuplikan"][:MAKS_KARAKTER_CHUNK]
    sumber = f"{baris.get('sumber','')} | {baris.get('bagian','')} | hlm {baris.get('halaman')}"
    isi = [
        {"role": "system", "content": SISTEM},
    ]
    for c in CONTOH:
        isi.append({"role": "user", "content": f"Kueri: {c['kueri']}\n\nChunk: {c['chunk']}"})
        isi.append({"role": "assistant", "content": json.dumps({"label": c["label"], "alasan": c["alasan"]})})
    isi.append({"role": "user", "content": f"Kueri: {kueri}\n\nChunk (sumber: {sumber}):\n{chunk}"})
    return isi


def panggil(pesan: list[dict], model: str, kunci: str, suhu: float = 0.0,
            maks_token: int = 300, tanpa_nalar: bool = False) -> dict:
    badan = {
        "model": model,
        "messages": pesan,
        "temperature": suhu,
        "max_tokens": maks_token,
        "response_format": {"type": "json_object"},
    }
    if tanpa_nalar:
        badan["reasoning"] = {"enabled": False}
    data = json.dumps(badan).encode()
    req = urllib.request.Request(URL, data=data, method="POST", headers={
        "Authorization": f"Bearer {kunci}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/chrisg/kk-uas",
        "X-Title": "Anotasi otomatis paper alpha",
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def teks_jawaban(jawab: dict) -> str:
    """Ambil teks dari content; model penalar bisa menaruh isi di field reasoning."""
    pesan = (((jawab.get("choices") or [{}])[0] or {}).get("message") or {})
    isi = pesan.get("content") or ""
    if isinstance(isi, list):
        isi = " ".join(b.get("text", "") for b in isi if isinstance(b, dict))
    if not isi.strip():
        isi = pesan.get("reasoning") or ""
    if not isi.strip():
        detail = pesan.get("reasoning_details") or []
        isi = " ".join(d.get("text", "") for d in detail if isinstance(d, dict))
    return isi or ""


def ambil_label(teks: str) -> tuple[int | None, str]:
    try:
        obj = json.loads(teks)
        label = obj.get("label")
        if isinstance(label, bool):
            label = int(label)
        if label in (0, 1):
            return int(label), str(obj.get("alasan", ""))[:200]
    except Exception:
        pass
    # cadangan: ambil objek JSON terakhir yang memuat "label"
    import re
    for potong in reversed(re.findall(r"\{[^{}]*\}", teks)):
        try:
            obj = json.loads(potong)
        except Exception:
            continue
        label = obj.get("label")
        if label in (0, 1, True, False):
            return int(bool(label)), str(obj.get("alasan", ""))[:200]
    # tidak ada JSON sah: jangan menebak label dari teks penalaran
    return None, teks[:200]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kolam", default=str(KOLAM))
    ap.add_argument("--model", default="", help="id model OpenRouter, mis. vendor/model:free")
    ap.add_argument("--keluaran", default=str(KELUARAN))
    ap.add_argument("--cache", default=str(CACHE))
    ap.add_argument("--batas", type=int, default=0, help="hanya N pasangan pertama (0 = semua)")
    ap.add_argument("--pekerja", type=int, default=2)
    ap.add_argument("--jeda", type=float, default=0.0, help="jeda detik antar permintaan per pekerja")
    ap.add_argument("--ulang", type=int, default=3, help="percobaan ulang saat gagal")
    ap.add_argument("--maks-token", dest="maks_token", type=int, default=300)
    ap.add_argument("--tanpa-nalar", dest="tanpa_nalar", action="store_true",
                    help="minta model tidak memakai penalaran panjang (didukung sebagian provider)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bandingkan", default="", help="berkas ekspor anotator manusia untuk dihitung kappa")
    a = ap.parse_args()

    if a.bandingkan:
        otomatis = {(d["qid"], d["doc_id"]): d["label"] for d in muat_jsonl(Path(a.keluaran)) if d.get("label") is not None}
        manusia = {(d["qid"], d["doc_id"]): d["label"] for d in muat_jsonl(Path(a.bandingkan)) if d.get("label") is not None}
        sama = set(otomatis) & set(manusia)
        if not sama:
            print("tidak ada pasangan yang bisa dibandingkan (cek qid/doc_id dan label)")
            return 1
        hasil = hitung_kappa({k: otomatis[k] for k in sama}, {k: manusia[k] for k in sama})
        print(json.dumps({"pasangan": len(sama), **hasil}, indent=2, ensure_ascii=False))
        return 0

    kolam = muat_jsonl(Path(a.kolam))
    if not kolam:
        print(f"kolam kosong: {a.kolam}", file=sys.stderr)
        return 1
    if a.batas:
        kolam = kolam[: a.batas]

    cache = {d["kunci"]: d for d in muat_jsonl(Path(a.cache))}
    belum = [b for b in kolam if kunci_cache(a.model, b["qid"], b["doc_id"]) not in cache]
    print(f"kolam {len(kolam)} pasangan | sudah ada di cache {len(kolam) - len(belum)} | akan dinilai {len(belum)}")

    if a.dry_run:
        tulis = Path(a.keluaran)
        with tulis.open("w", encoding="utf-8") as f:
            for b in kolam:
                f.write(json.dumps({"qid": b["qid"], "doc_id": b["doc_id"], "bahasa": b["bahasa"],
                                    "label": 0, "alasan": "dry-run", "model": a.model or "dry-run",
                                    "versi_prompt": VERSI_PROMPT}, ensure_ascii=False) + "\n")
        print(f"dry-run: {len(kolam)} baris ditulis ke {tulis}")
        return 0

    kunci = muat_kunci()
    if not kunci:
        print("OPENROUTER_API_KEY tidak ditemukan (env atau ~/.hermes/.env)", file=sys.stderr)
        return 1
    if not a.model:
        print("--model wajib diisi di luar --dry-run", file=sys.stderr)
        return 1

    kunci_lock = threading.Lock()
    selesai, gagal = [], 0
    t_mulai = time.perf_counter()

    def kerja(b: dict) -> dict:
        kc = kunci_cache(a.model, b["qid"], b["doc_id"])
        pesan = susun_pesan(b)
        for percobaan in range(a.ulang):
            try:
                jawab = panggil(pesan, a.model, kunci, maks_token=a.maks_token,
                                tanpa_nalar=a.tanpa_nalar)
                teks = teks_jawaban(jawab)
                label, alasan = ambil_label(teks)
                if label is None:
                    raise ValueError(f"label tidak terbaca: {teks[:120]}")
                return {"kunci": kc, "qid": b["qid"], "doc_id": b["doc_id"], "bahasa": b["bahasa"],
                        "label": label, "alasan": alasan, "model": a.model,
                        "versi_prompt": VERSI_PROMPT,
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "token": (jawab.get("usage") or {}).get("total_tokens")}
            except (urllib.error.HTTPError, urllib.error.URLError, ValueError, TimeoutError) as e:
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
            if i % 25 == 0 or i == len(belum):
                print(f"  {i}/{len(belum)} selesai ({gagal} gagal)")

    # tulis keluaran: gabungan cache (lama + baru), urut qid/doc_id
    gabung = dict(cache)
    for d in selesai:
        gabung[d["kunci"]] = d
    terpilih = [gabung[kunci_cache(a.model, b["qid"], b["doc_id"])]
                for b in kolam if kunci_cache(a.model, b["qid"], b["doc_id"]) in gabung]
    with Path(a.keluaran).open("w", encoding="utf-8") as f:
        for d in terpilih:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    label = [d["label"] for d in terpilih]
    print(json.dumps({
        "model": a.model,
        "pasangan_dinilai": len(terpilih),
        "label_1": sum(label), "label_0": len(label) - sum(label),
        "gagal": gagal,
        "detik": round(time.perf_counter() - t_mulai, 1),
        "keluaran": str(a.keluaran),
    }, indent=2, ensure_ascii=False))
    return 0 if gagal == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
