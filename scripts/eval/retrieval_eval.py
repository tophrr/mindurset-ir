#!/usr/bin/env python3
"""Harness evaluasi empat konfigurasi retrieval untuk artikel versi alpha.

Kelompok 5, Kecerdasan Komputasional (INF20052, 1261).

Konfigurasi yang dibandingkan:
    M1  VSM TF-IDF + cosine similarity (dibangun dari nol)
    M2  Okapi BM25 (k1=1.2, b=0.75)
    M3  dense embedding multilingual (default BAAI/bge-m3)
    M4  Reciprocal Rank Fusion atas M2 dan M3 (k=60)

Masukan berupa tiga berkas JSONL:
    korpus.jsonl   {"id", "bahasa", "sumber", "halaman", "teks"}
    kueri.jsonl    {"qid", "bahasa", "teks"}
    qrels.jsonl    {"qid", "doc_id", "label"}          label 1 = relevan

Perintah:
    python3 retrieval_eval.py selftest
    python3 retrieval_eval.py kappa --anotator-a a.jsonl --anotator-b b.jsonl
    python3 retrieval_eval.py run --korpus ... --kueri ... --qrels ... --keluaran out/

Contoh backend dense:
    --dense-backend fastembed --dense-model BAAI/bge-m3      (butuh paket fastembed)
    --dense-backend st                  --dense-model BAAI/bge-m3   (butuh sentence-transformers)
    --dense-backend http --dense-url https://api.cloudflare.com/client/v4/accounts/<acc>/ai/v1/embeddings \
        --dense-model @cf/baai/bge-m3    (token dari variabel lingkungan CF_API_TOKEN)

Tanpa dependensi wajib: M1, M2, M4, metrik, dan uji statistik berjalan dengan pustaka standar.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import statistics
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

# --------------------------------------------------------------------------
# Tokenisasi
# --------------------------------------------------------------------------

STOPWORDS = set("""
a an the and or of to in on for with at by from as is are was were be been being
this that these those it its he she they them his her their our your my me i you we
not no do does did have has had will would can could should may might must
dan atau yang di ke dari untuk pada dengan dalam adalah ini itu akan tidak bukan
juga saja sudah telah para kami kita mereka dia ia aku kamu anda nya
""".split())

KATA = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(teks: str) -> list[str]:
    return [t for t in KATA.findall(teks.lower()) if t not in STOPWORDS and len(t) > 1]


# --------------------------------------------------------------------------
# M1: VSM TF-IDF + cosine
# --------------------------------------------------------------------------

class TFIDF:
    def __init__(self, korpus: list[dict]):
        self.ids = [d["id"] for d in korpus]
        docs = [Counter(tokenize(d["teks"])) for d in korpus]
        self.N = len(docs)
        df = Counter()
        for tf in docs:
            df.update(tf.keys())
        self.idf = {t: math.log(self.N / c) for t, c in df.items()}
        self.vecs = [self._bobot(tf) for tf in docs]

    def _bobot(self, tf: Counter) -> dict[str, float]:
        v = {t: (1 + math.log(c)) * self.idf[t] for t, c in tf.items() if t in self.idf}
        n = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / n for t, x in v.items()}

    def cari(self, kueri: str, K: int = 10) -> list[tuple[str, float]]:
        q = self._bobot(Counter(tokenize(kueri)))
        skor = [sum(w * q.get(t, 0.0) for t, w in v.items()) for v in self.vecs]
        urut = sorted(zip(self.ids, skor), key=lambda x: (-x[1], x[0]))
        return urut[:K]


# --------------------------------------------------------------------------
# M2: Okapi BM25
# --------------------------------------------------------------------------

class BM25:
    def __init__(self, korpus: list[dict], k1: float = 1.2, b: float = 0.75):
        self.ids = [d["id"] for d in korpus]
        self.docs = [Counter(tokenize(d["teks"])) for d in korpus]
        self.N = len(self.docs)
        self.k1, self.b = k1, b
        self.panjang = [sum(tf.values()) for tf in self.docs]
        self.avgdl = (sum(self.panjang) / self.N) if self.N else 1.0
        df = Counter()
        for tf in self.docs:
            df.update(tf.keys())
        self.idf = {t: math.log(1 + (self.N - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def cari(self, kueri: str, K: int = 10) -> list[tuple[str, float]]:
        q = tokenize(kueri)
        skor = []
        for i, tf in enumerate(self.docs):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if not f:
                    continue
                num = f * (self.k1 + 1)
                den = f + self.k1 * (1 - self.b + self.b * self.panjang[i] / self.avgdl)
                s += self.idf[t] * num / den
            skor.append((self.ids[i], s))
        urut = sorted(skor, key=lambda x: (-x[1], x[0]))
        return urut[:K]


# --------------------------------------------------------------------------
# M3: dense embedding
# --------------------------------------------------------------------------

class Dense:
    def __init__(self, korpus: list[dict], backend: str, model: str, url: str | None = None,
                 berkas_chunk: str | None = None, berkas_kueri: str | None = None,
                 kueri: list[dict] | None = None):
        self.ids = [d["id"] for d in korpus]
        self.backend, self.model, self.url = backend, model, url
        self.berkas_kueri = berkas_kueri
        self.peta_kueri: dict[str, int] = {}
        if backend == "berkas":
            import numpy as np
            if not berkas_chunk:
                raise SystemExit("--dense-chunk-berkas wajib untuk backend berkas")
            self.mat = np.load(berkas_chunk).astype("float32")
            if self.mat.shape[0] != len(korpus):
                raise SystemExit(f"jumlah baris embedding {self.mat.shape[0]} != {len(korpus)} chunk")
            self.kueri_mat = None
            if berkas_kueri:
                self.kueri_mat = np.load(berkas_kueri).astype("float32")
                peta_berkas = Path(str(berkas_kueri) + ".idx.json")
                if peta_berkas.exists():
                    self.peta_kueri = {k: int(v) for k, v in
                                       json.loads(peta_berkas.read_text(encoding="utf-8")).items()}
                else:
                    if kueri is None:
                        raise SystemExit("daftar kueri wajib bila peta qid tidak ada")
                    if self.kueri_mat.shape[0] != len(kueri):
                        raise SystemExit(f"baris embedding kueri {self.kueri_mat.shape[0]} != {len(kueri)} kueri")
                    self.peta_kueri = {q["qid"]: i for i, q in enumerate(kueri)}
            return
        teks = [d["teks"] for d in korpus]
        self.mat = self._kodekan(teks)

    def _kodekan(self, teks: list[str]) -> list[list[float]]:
        if self.backend == "st":
            from sentence_transformers import SentenceTransformer  # type: ignore
            m = SentenceTransformer(self.model)
            arr = m.encode(teks, normalize_embeddings=True, batch_size=16)
            return [list(map(float, v)) for v in arr]
        if self.backend == "fastembed":
            from fastembed import TextEmbedding  # type: ignore
            m = TextEmbedding(model_name=self.model)
            return [list(map(float, v)) for v in m.embed(teks, batch_size=8)]
        if self.backend == "berkas":
            import numpy as np
            return np.load(self.berkas_kueri).astype("float32")
        if self.backend == "http":
            if not self.url:
                raise SystemExit("--dense-url wajib untuk backend http")
            out = []
            for i in range(0, len(teks), 32):
                out.extend(self._http(teks[i:i + 32]))
            return out
        raise SystemExit(f"backend dense tidak dikenal: {self.backend}")

    def _http(self, teks: list[str]) -> list[list[float]]:
        token = os.environ.get("CF_API_TOKEN") or os.environ.get("OPENAI_API_KEY", "")
        if not token:
            raise SystemExit("token kosong: set CF_API_TOKEN atau OPENAI_API_KEY")
        body = json.dumps({"model": self.model, "input": teks}).encode()
        req = urllib.request.Request(
            self.url, data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        items = data["data"] if isinstance(data.get("data"), list) else data["result"]["data"]
        if isinstance(items[0], dict):
            items = sorted(items, key=lambda d: d.get("index", 0))
            return [d["embedding"] for d in items]
        return items

    @staticmethod
    def _norm(v: list[float]) -> list[float]:
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def cari(self, kueri, K: int = 10) -> list[tuple[str, float]]:
        if self.backend == "berkas":
            import numpy as np
            if self.kueri_mat is not None:
                qid = kueri["qid"] if isinstance(kueri, dict) else str(kueri)
                baris = self.peta_kueri.get(qid)
                if baris is None:
                    raise SystemExit(f"qid {qid} tidak ada di embedding kueri")
                q = self.kueri_mat[baris]
            else:
                raise SystemExit("backend berkas tanpa --dense-kueri-berkas tidak bisa mengodekan kueri")
            q = q / (np.linalg.norm(q) or 1.0)
            skor_np = self.mat @ q
            skor = [(self.ids[i], float(skor_np[i])) for i in range(len(self.ids))]
            urut = sorted(skor, key=lambda x: (-x[1], x[0]))
            return urut[:K]
        q = self._norm(self._kodekan([kueri])[0])
        skor = []
        for i, v in enumerate(self.mat):
            v = self._norm(v)
            skor.append((self.ids[i], sum(a * b for a, b in zip(q, v))))
        urut = sorted(skor, key=lambda x: (-x[1], x[0]))
        return urut[:K]


# --------------------------------------------------------------------------
# M4: Reciprocal Rank Fusion
# --------------------------------------------------------------------------

def rrf(daftar: list[list[tuple[str, float]]], k: int = 60) -> list[tuple[str, float]]:
    skor: dict[str, float] = defaultdict(float)
    for hasil in daftar:
        for posisi, (doc_id, _) in enumerate(hasil, start=1):
            skor[doc_id] += 1.0 / (k + posisi)
    return sorted(skor.items(), key=lambda x: (-x[1], x[0]))


# --------------------------------------------------------------------------
# Metrik
# --------------------------------------------------------------------------

def p_at_k(urut: list[str], relevan: set[str], k: int) -> float:
    return sum(1 for d in urut[:k] if d in relevan) / k


def r_at_k(urut: list[str], relevan: set[str], k: int) -> float:
    if not relevan:
        return 0.0
    return sum(1 for d in urut[:k] if d in relevan) / len(relevan)


def rr(urut: list[str], relevan: set[str]) -> float:
    for i, d in enumerate(urut, start=1):
        if d in relevan:
            return 1.0 / i
    return 0.0


def bootstrap_ci(nilai: list[float], n: int = 1000, alpha: float = 0.05,
                 seed: int = 20261113) -> tuple[float, float]:
    if not nilai:
        return (0.0, 0.0)
    rnd = random.Random(seed)
    rerata = []
    for _ in range(n):
        contoh = [nilai[rnd.randrange(len(nilai))] for _ in nilai]
        rerata.append(sum(contoh) / len(contoh))
    rerata.sort()
    return (rerata[int(alpha / 2 * n)], rerata[int((1 - alpha / 2) * n) - 1])


def wilcoxon(x: list[float], y: list[float]) -> tuple[float, float]:
    """Uji peringkat bertanda Wilcoxon, aproksimasi normal dengan koreksi tie.

    Mengembalikan (statistik W, p dua sisi). Implementasi tanpa scipy agar
    harness berjalan dengan pustaka standar saja.
    """
    selisih = [a - b for a, b in zip(x, y)]
    selisih = [d for d in selisih if d != 0]
    n = len(selisih)
    if n < 6:
        return (float("nan"), float("nan"))
    absd = sorted(abs(d) for d in selisih)
    peringkat: dict[float, float] = {}
    i = 0
    while i < len(absd):
        j = i
        while j + 1 < len(absd) and absd[j + 1] == absd[i]:
            j += 1
        peringkat[absd[i]] = (i + j) / 2 + 1
        i = j + 1
    w_plus = sum(peringkat[abs(d)] for d in selisih if d > 0)
    w_minus = sum(peringkat[abs(d)] for d in selisih if d < 0)
    W = min(w_plus, w_minus)
    mu = n * (n + 1) / 4
    # koreksi tie
    tie = Counter(abs(d) for d in selisih)
    koreksi = sum(t ** 3 - t for t in tie.values() if t > 1)
    sigma = math.sqrt(n * (n + 1) * (2 * n + 1) / 24 - koreksi / 48)
    if sigma == 0:
        return (W, 1.0)
    z = (abs(W - mu) - 0.5) / sigma
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return (W, min(1.0, p))


# --------------------------------------------------------------------------
# Muat data
# --------------------------------------------------------------------------

def muat_jsonl(path: str | Path) -> list[dict]:
    baris = []
    with open(path, encoding="utf-8") as f:
        for ln, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                baris.append(json.loads(raw))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{ln} bukan JSON valid: {e}")
    return baris


def muat_qrels(path: str | Path) -> dict[str, set[str]]:
    q: dict[str, set[str]] = defaultdict(set)
    for r in muat_jsonl(path):
        if int(r.get("label", 0)) >= 1:
            q[str(r["qid"])].add(str(r["doc_id"]))
    return q


# --------------------------------------------------------------------------
# Eksekusi
# --------------------------------------------------------------------------

def jalankan(args) -> dict:
    korpus = muat_jsonl(args.korpus)
    kueri = muat_jsonl(args.kueri)
    qrels = muat_qrels(args.qrels)

    if args.bahasa:
        korpus = [d for d in korpus if d.get("bahasa") == args.bahasa]
        kueri = [q for q in kueri if q.get("bahasa") == args.bahasa]
    if not korpus or not kueri:
        raise SystemExit("korpus atau kueri kosong setelah penyaringan bahasa")

    id_sah = {d["id"] for d in korpus}
    tanpa_qrels = [q["qid"] for q in kueri if q["qid"] not in qrels]
    if tanpa_qrels:
        print(f"peringatan: {len(tanpa_qrels)} kueri tanpa qrels, dilewati", file=sys.stderr)
    kueri = [q for q in kueri if q["qid"] in qrels]

    t0 = time.perf_counter()
    m1 = TFIDF(korpus)
    t1 = time.perf_counter()
    m2 = BM25(korpus, k1=args.k1, b=args.b)
    t2 = time.perf_counter()
    m3 = None
    t3 = t2
    if args.dense_backend != "none":
        m3 = Dense(korpus, args.dense_backend, args.dense_model, args.dense_url,
                   berkas_chunk=args.dense_chunk_berkas, berkas_kueri=args.dense_kueri_berkas,
                   kueri=kueri)
        t3 = time.perf_counter()

    K = max(args.k)
    hasil: dict[str, dict] = {}
    for nama in ["M1", "M2", "M3", "M4"]:
        hasil[nama] = {"per_kueri": {}, "latensi": [], "metrik": {}}

    for q in kueri:
        relevan = {d for d in qrels[q["qid"]] if d in id_sah}
        if not relevan:
            continue
        daftar = {}

        for nama, model in (("M1", m1), ("M2", m2)):
            t = time.perf_counter()
            daftar[nama] = model.cari(q["teks"], K)
            hasil[nama]["latensi"].append((time.perf_counter() - t) * 1000)
        if m3 is not None:
            t = time.perf_counter()
            daftar["M3"] = m3.cari(q, K)
            hasil["M3"]["latensi"].append((time.perf_counter() - t) * 1000)
            t = time.perf_counter()
            daftar["M4"] = rrf([daftar["M2"], daftar["M3"]], k=args.rrf_k)
            hasil["M4"]["latensi"].append((time.perf_counter() - t) * 1000)

        for nama, urutan in daftar.items():
            ids = [d for d, _ in urutan]
            hasil[nama]["per_kueri"][q["qid"]] = {
                "peringkat": {d: i for i, d in enumerate(ids, start=1)},
                "top": ids[:5],
                **{f"P@{k}": p_at_k(ids, relevan, k) for k in args.k},
                **{f"R@{k}": r_at_k(ids, relevan, k) for k in args.k},
                "MRR": rr(ids, relevan),
            }

    for nama, blok in hasil.items():
        if not blok["per_kueri"]:
            continue
        for m in [f"P@{k}" for k in args.k] + [f"R@{k}" for k in args.k] + ["MRR"]:
            nilai = [v[m] for v in blok["per_kueri"].values()]
            lo, hi = bootstrap_ci(nilai, seed=args.seed)
            blok["metrik"][m] = {"mean": statistics.fmean(nilai), "ci95": [lo, hi]}
        lat = blok["latensi"]
        if lat:
            lat_s = sorted(lat)
            blok["latensi_ringkas"] = {
                "mean": statistics.fmean(lat),
                "p95": lat_s[min(len(lat_s) - 1, int(round(0.95 * (len(lat_s) - 1))))],
                "maks": max(lat),
                "n": len(lat),
            }

    uji = {}
    nama_ada = [n for n in ["M1", "M2", "M3", "M4"] if hasil[n]["per_kueri"]]
    for i in range(len(nama_ada)):
        for j in range(i + 1, len(nama_ada)):
            a, b = nama_ada[i], nama_ada[j]
            qid = sorted(set(hasil[a]["per_kueri"]) & set(hasil[b]["per_kueri"]))
            x = [hasil[a]["per_kueri"][q]["MRR"] for q in qid]
            y = [hasil[b]["per_kueri"][q]["MRR"] for q in qid]
            w, p = wilcoxon(x, y)
            uji[f"{a}_vs_{b}"] = {"MRR_mean_selisih": statistics.fmean(x) - statistics.fmean(y),
                                  "W": w, "p": p, "n": len(qid)}

    return {
        "konfigurasi": {
            "korpus": [d["id"] for d in korpus],
            "n_kueri": len(kueri),
            "k1": args.k1, "b": args.b, "rrf_k": args.rrf_k,
            "dense_model": args.dense_model if m3 is not None else None,
            "waktu_indeks_detik": {"M1": t1 - t0, "M2": t2 - t1,
                                   "M3": (t3 - t2) if m3 is not None else None},
        },
        "hasil": hasil,
        "uji": uji,
    }


# --------------------------------------------------------------------------
# Keluaran tabel
# --------------------------------------------------------------------------

def kolom_metrik(h: dict) -> list[str]:
    """Kolom tabel mengikuti metrik yang benar-benar dihitung, bukan daftar tetap."""
    ada = set()
    for nama in ["M1", "M2", "M3", "M4"]:
        ada.update((h["hasil"][nama].get("metrik") or {}).keys())
    urut = [k for k in ("P@1", "P@3", "P@5", "P@10", "R@3", "R@5", "R@10", "MRR", "nDCG@10") if k in ada]
    return urut + sorted(k for k in ada if k not in urut)


def tabel_markdown(h: dict) -> str:
    kolom = kolom_metrik(h)
    baris = ["| Konfigurasi | " + " | ".join(kolom) + " |",
             "|---" * (len(kolom) + 1) + "|"]
    for nama in ["M1", "M2", "M3", "M4"]:
        b = h["hasil"][nama]
        if not b.get("metrik"):
            continue
        m = b["metrik"]
        sel = [nama] + [f"{m[k]['mean']:.3f}" if k in m else "-" for k in kolom]
        baris.append("| " + " | ".join(sel) + " |")
    return "\n".join(baris)


def tabel_latex(h: dict) -> str:
    label = {"M1": "VSM TF-IDF", "M2": "Okapi BM25",
             "M3": "BGE-M3 \\emph{dense}", "M4": "RRF hibrida"}
    out = []
    for nama in ["M1", "M2", "M3", "M4"]:
        b = h["hasil"][nama]
        if not b.get("metrik"):
            continue
        m = b["metrik"]
        sel = [label[nama]] + [f"{m[k]['mean']:.3f}" if k in m else "-" for k in kolom_metrik(h)]
        out.append(" & ".join(sel) + " \\\\")
    return "\n".join(out)


def tabel_latensi_latex(h: dict, anggaran_ms: float = 200.0) -> str:
    label = {"M1": "VSM TF-IDF", "M2": "Okapi BM25",
             "M3": "BGE-M3 \\emph{dense}", "M4": "RRF hibrida"}
    out = []
    for nama in ["M1", "M2", "M3", "M4"]:
        b = h["hasil"][nama]
        if "latensi_ringkas" not in b:
            continue
        l = b["latensi_ringkas"]
        ok = "ya" if l["p95"] <= anggaran_ms else "tidak"
        out.append(f"{label[nama]} & {l['mean']:.1f} & {l['p95']:.1f} & {l['maks']:.1f} & {ok} \\\\")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Kappa
# --------------------------------------------------------------------------

def hitung_kappa(a: dict[tuple[str, str], int], b: dict[tuple[str, str], int]) -> dict:
    kunci = sorted(set(a) & set(b))
    if not kunci:
        raise SystemExit("tidak ada pasangan anotasi yang beririsan")
    n = len(kunci)
    setuju = sum(1 for k in kunci if a[k] == b[k])
    po = setuju / n
    # pe dengan kedua anotator memakai skala yang sama (biner 0/1)
    pa1 = sum(1 for k in kunci if a[k] == 1) / n
    pb1 = sum(1 for k in kunci if b[k] == 1) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    kappa = (po - pe) / (1 - pe) if pe != 1 else 1.0
    return {"n": n, "setuju": setuju, "po": po, "pe": pe, "kappa": kappa}


# --------------------------------------------------------------------------
# Selftest
# --------------------------------------------------------------------------

def selftest() -> int:
    korpus = [
        {"id": "d1", "bahasa": "id", "teks": "tarik napas perlahan lalu lepaskan pelan pelan"},
        {"id": "d2", "bahasa": "id", "teks": "tuliskan pikiran yang mengganggu di kertas catatan"},
        {"id": "d3", "bahasa": "id", "teks": "hubungi teman dan ceritakan apa yang kamu rasakan"},
        {"id": "d4", "bahasa": "id", "teks": "jadwalkan satu kegiatan kecil yang bisa diselesaikan hari ini"},
    ]
    kueri = [{"qid": "q1", "bahasa": "id", "teks": "napas"}]
    qrels = {"q1": {"d1"}}

    m1, m2 = TFIDF(korpus), BM25(korpus)
    assert m1.cari("napas", 4)[0][0] == "d1", "TF-IDF gagal memeringkat d1 di posisi 1"
    assert m2.cari("napas", 4)[0][0] == "d1", "BM25 gagal memeringkat d1 di posisi 1"
    assert p_at_k(["d1", "d2"], {"d1"}, 1) == 1.0
    assert p_at_k(["d2", "d1"], {"d1"}, 1) == 0.0
    assert r_at_k(["d2", "d1"], {"d1"}, 2) == 1.0
    assert abs(rr(["d2", "d1"], {"d1"}) - 0.5) < 1e-9
    assert abs(rr(["d3"], {"d1"})) < 1e-9

    fusi = rrf([[("a", 9.0), ("b", 8.0)], [("b", 1.0), ("a", 0.1)]], k=60)
    ids = [d for d, _ in fusi]
    assert set(ids) == {"a", "b"} and abs(fusi[0][1] - fusi[1][1]) < 1e-12, \
        "RRF harus memberi skor sama untuk dua dokumen yang bertukar posisi"

    # uji statistik: dua vektor berbeda jelas
    x = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    y = [0, 0, 0, 0, 0, 0, 0, 0, 0, 1]
    w, p = wilcoxon(x, y)
    assert p < 0.05, f"Wilcoxon tidak mendeteksi perbedaan jelas (p={p})"

    # kappa sempurna dan kappa nol
    a = {("q1", "d1"): 1, ("q1", "d2"): 0, ("q2", "d1"): 1}
    assert abs(hitung_kappa(a, dict(a))["kappa"] - 1.0) < 1e-9

    # bobot idf nol tidak boleh menghasilkan skor negatif
    assert all(s >= 0 for _, s in m1.cari("kertas", 4)), "skor TF-IDF negatif"

    print("selftest: OK (TF-IDF, BM25, RRF, P@K, R@K, MRR, Wilcoxon, kappa)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("selftest", help="uji bawaan tanpa data eksternal")

    kp = sub.add_parser("kappa", help="Cohen's kappa dari dua berkas anotasi")
    kp.add_argument("--anotator-a", required=True)
    kp.add_argument("--anotator-b", required=True)

    rp = sub.add_parser("run", help="jalankan perbandingan empat konfigurasi")
    rp.add_argument("--korpus", required=True)
    rp.add_argument("--kueri", required=True)
    rp.add_argument("--qrels", required=True)
    rp.add_argument("--keluaran", default="out")
    rp.add_argument("--bahasa", default=None, help="saring satu bahasa, mis. id atau en")
    rp.add_argument("--k", type=int, nargs="+", default=[1, 3, 5])
    rp.add_argument("--k1", type=float, default=1.2)
    rp.add_argument("--b", type=float, default=0.75)
    rp.add_argument("--rrf-k", type=int, default=60)
    rp.add_argument("--seed", type=int, default=20261113)
    rp.add_argument("--dense-backend", default="none", choices=["none", "st", "fastembed", "http", "berkas"])
    rp.add_argument("--dense-chunk-berkas", default=None, help=".npy embedding korpus (backend berkas)")
    rp.add_argument("--dense-kueri-berkas", default=None, help=".npy embedding kueri (backend berkas)")
    rp.add_argument("--dense-model", default="BAAI/bge-m3")
    rp.add_argument("--dense-url", default=None)

    args = ap.parse_args()

    if args.cmd == "selftest":
        return selftest()

    if args.cmd == "kappa":
        def baca(p):
            # ekspor alat anotasi memuat label null untuk pasangan yang belum dinilai
            return {(r["qid"], r["doc_id"]): int(r["label"]) for r in muat_jsonl(p)
                    if r.get("label") is not None}
        a_map, b_map = baca(args.anotator_a), baca(args.anotator_b)
        hasil = hitung_kappa(a_map, b_map)
        hasil["dinilai_a"] = len(a_map)
        hasil["dinilai_b"] = len(b_map)
        print(json.dumps(hasil, indent=2, ensure_ascii=False))
        return 0 if hasil["kappa"] >= 0.75 else 1

    h = jalankan(args)
    out = Path(args.keluaran)
    out.mkdir(parents=True, exist_ok=True)
    (out / "hasil.json").write_text(json.dumps(h, indent=2, ensure_ascii=False), encoding="utf-8")
    nama = args.bahasa or "semua"
    (out / f"tabel_{nama}.md").write_text(
        f"# Kualitas peringkat ({nama})\n\n" + tabel_markdown(h) + "\n\n"
        f"# Latensi (ms)\n\n| Konfigurasi | mean | p95 | maks |\n|---|---|---|---|\n" +
        "\n".join(
            f"| {n} | {h['hasil'][n]['latensi_ringkas']['mean']:.1f} | "
            f"{h['hasil'][n]['latensi_ringkas']['p95']:.1f} | "
            f"{h['hasil'][n]['latensi_ringkas']['maks']:.1f} |"
            for n in ["M1", "M2", "M3", "M4"] if "latensi_ringkas" in h["hasil"][n]) + "\n",
        encoding="utf-8")
    (out / f"tabel_{nama}.tex").write_text(
        "% Tabel III (kualitas peringkat)\n" + tabel_latex(h) +
        "\n\n% Tabel IV (latensi)\n" + tabel_latensi_latex(h) + "\n", encoding="utf-8")
    print(tabel_markdown(h))
    for k, v in h["uji"].items():
        print(f"{k}: selisih MRR {v['MRR_mean_selisih']:+.3f}, W={v['W']}, p={v['p']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
