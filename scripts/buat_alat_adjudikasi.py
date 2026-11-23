#!/usr/bin/env python3
"""Buat alat adjudikasi HTML satu berkas untuk G-α3.

Memuat 341 pasangan yang masih berselisih antara anotator A (putaran kedua) dan B.
Setiap pasangan menampilkan kueri, chunk, dan dua label plus pendapat model penilai
sebagai rujukan ketiga. Adjudikator mengisi label final dan alasan singkat, lalu
mengekspor JSONL yang siap digabung menjadi qrels final.

Pemakaian:
    python3 eksperimen/buat_alat_adjudikasi.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANOT = ROOT / "data" / "anotasi"

TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Adjudikasi relevansi — Korpus KK Kelompok 5</title>
<style>
  :root { --bg:#0f1115; --card:#171a21; --line:#262b36; --txt:#e6e8ee; --dim:#9aa3b2;
          --ok:#2f8f5b; --no:#a3423f; --skip:#4a5160; --acc:#7aa2f7; --cal:#e0af68; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font-family: ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif; }
  header { position:sticky; top:0; background:#12151b; border-bottom:1px solid var(--line);
           padding:10px 16px; display:flex; gap:14px; align-items:center; flex-wrap:wrap; z-index:5; }
  header h1 { font-size:15px; margin:0; font-weight:600; }
  .grow { flex:1; }
  button { font:inherit; }
  .bar { height:6px; background:#232833; border-radius:99px; width:180px; overflow:hidden; }
  .bar > i { display:block; height:100%; width:0; background:var(--acc); }
  main { max-width:900px; margin:0 auto; padding:18px 16px 130px; }
  .meta { font-size:12px; color:var(--dim); }
  .q { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }
  .q .tag { display:inline-block; font-size:11px; color:#0f1115; background:var(--acc);
            border-radius:99px; padding:1px 8px; margin-right:6px; }
  .q p { margin:8px 0 0; font-size:19px; line-height:1.45; }
  .c { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin-top:12px; }
  .c .src { font-size:12px; color:var(--dim); margin-bottom:8px; }
  .c .txt { font-size:15px; line-height:1.55; max-height:40vh; overflow:auto; white-space:pre-wrap; }
  .chip { display:inline-flex; gap:6px; align-items:center; font-size:13px; border-radius:8px;
          padding:5px 10px; margin:10px 8px 0 0; background:#1c2028; border:1px solid var(--line); }
  .chip b { font-size:15px; }
  .chip.satu { border-color:#2f6b46; } .chip.nol { border-color:#6b3a38; } .chip.mod { border-color:#3b4d78; }
  textarea { width:100%; margin-top:10px; background:#12151b; color:var(--txt); border:1px solid var(--line);
             border-radius:8px; padding:8px 10px; font:inherit; font-size:14px; min-height:52px; resize:vertical; }
  .keys { position:fixed; left:0; right:0; bottom:0; background:#12151b; border-top:1px solid var(--line);
          padding:12px 16px; display:flex; gap:10px; justify-content:center; flex-wrap:wrap; }
  .keys button { border:none; border-radius:8px; padding:11px 18px; color:#fff; cursor:pointer; font-weight:600; }
  .b1 { background:var(--ok); } .b0 { background:var(--no); } .b4 { background:#2a3040; } .b5 { background:#3b4d78; }
  .keys small { color:var(--dim); align-self:center; }
</style>
</head>
<body>
<header>
  <h1>Adjudikasi relevansi (A vs B)</h1>
  <div class="bar"><i id="bar"></i></div>
  <span class="meta" id="prog">0 / 0</span>
  <div class="grow"></div>
  <span class="meta">Adjudikator: __ADJ__</span>
  <span class="meta" id="status">belum ada ekspor</span>
  <button class="b4" id="export" style="border-radius:8px;padding:8px 12px;color:#fff;border:none;cursor:pointer">Ekspor JSONL</button>
</header>
<main>
  <div class="meta" id="pos"></div>
  <div class="q">
    <span class="tag" id="topik">—</span><span class="meta" id="qid"></span>
    <p id="kueri">—</p>
  </div>
  <div class="c">
    <div class="src" id="src"></div>
    <div class="txt" id="txt"></div>
    <div>
      <span class="chip" id="chip-a">A <b id="la">—</b></span>
      <span class="chip" id="chip-b">B <b id="lb">—</b></span>
      <span class="chip mod" id="chip-m">model <b id="lm">—</b></span>
    </div>
    <textarea id="alasan" placeholder="Alasan singkat (opsional, mis. 'teknik ada tetapi tidak menjawab kueri')"></textarea>
    <div class="meta" id="keputusan">belum diputuskan</div>
  </div>
</main>
<div class="keys">
  <button class="b1" id="b1">1 · Relevan</button>
  <button class="b0" id="b0">0 · Tidak relevan</button>
  <button class="b5" id="ikuta">Ikut A</button>
  <button class="b5" id="ikutb">Ikut B</button>
  <button class="b4" id="prev">← Sebelumnya</button>
  <small>1 / 0 putuskan · A atau B ikut anotator · ← kembali · E ekspor</small>
</div>
<script>
const ITEMS = __ITEMS__;
const KEY = "kk-adjudikasi";
let idx = 0, state = {final:{}, alasan:{}, pos:0, ekspor:-1};

const el = id => document.getElementById(id);
const kunci = it => it.qid + "|" + it.doc_id;

function muat() {
  const raw = localStorage.getItem(KEY);
  if (raw) state = Object.assign(state, JSON.parse(raw));
  idx = Math.min(state.pos || 0, ITEMS.length - 1);
  render();
}
function simpan() {
  state.pos = idx;
  localStorage.setItem(KEY, JSON.stringify(state));
}
function diputuskan() {
  return ITEMS.filter(it => state.final[kunci(it)] !== undefined).length;
}
function render() {
  const it = ITEMS[idx];
  const n = diputuskan();
  el("prog").textContent = n + " / " + ITEMS.length + " diputuskan";
  el("bar").style.width = (100 * n / ITEMS.length).toFixed(1) + "%";
  el("status").textContent = state.ekspor < 0 ? "belum ada ekspor" : "ekspor terakhir: " + state.ekspor + " label";
  if (!it) return;
  el("topik").textContent = it.topik;
  el("qid").textContent = it.qid + " · " + it.bahasa;
  el("kueri").textContent = it.kueri;
  const hlm = it.halaman === null ? "" : " · hlm " + (Array.isArray(it.halaman) ? it.halaman.join(",") : it.halaman);
  el("src").textContent = it.sumber + (it.bagian ? " · " + it.bagian : "") + hlm + " · " + it.doc_id;
  el("txt").textContent = it.cuplikan;
  el("la").textContent = it.label_a;
  el("lb").textContent = it.label_b;
  el("lm").textContent = it.label_model === null ? "-" : it.label_model;
  el("chip-a").className = "chip " + (it.label_a === 1 ? "satu" : "nol");
  el("chip-b").className = "chip " + (it.label_b === 1 ? "satu" : "nol");
  el("pos").textContent = "Perselisihan " + (idx + 1) + " dari " + ITEMS.length;
  el("alasan").value = state.alasan[kunci(it)] || "";
  const f = state.final[kunci(it)];
  el("keputusan").textContent = f === undefined ? "belum diputuskan" : "label final: " + f;
}
function putuskan(v) {
  const it = ITEMS[idx];
  state.final[kunci(it)] = v;
  state.alasan[kunci(it)] = el("alasan").value.trim();
  if (idx < ITEMS.length - 1) idx++;
  simpan(); render();
}
function ekspor() {
  const baris = ITEMS.map(it => JSON.stringify({
    qid: it.qid, doc_id: it.doc_id,
    label_a: it.label_a, label_b: it.label_b, label_model: it.label_model,
    label_final: state.final[kunci(it)] === undefined ? null : state.final[kunci(it)],
    alasan: state.alasan[kunci(it)] || ""
  }));
  const blob = new Blob([baris.join("\\n") + "\\n"], {type:"application/x-ndjson"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "adjudikasi_tora.jsonl";
  a.click();
  state.ekspor = diputuskan();
  simpan(); render();
}
el("b1").addEventListener("click", () => putuskan(1));
el("b0").addEventListener("click", () => putuskan(0));
el("ikuta").addEventListener("click", () => putuskan(ITEMS[idx].label_a));
el("ikutb").addEventListener("click", () => putuskan(ITEMS[idx].label_b));
el("prev").addEventListener("click", () => { if (idx > 0) { idx--; simpan(); render(); } });
el("export").addEventListener("click", ekspor);
document.addEventListener("keydown", e => {
  if (e.target.tagName === "TEXTAREA") return;
  if (e.key === "1") putuskan(1);
  else if (e.key === "0") putuskan(0);
  else if (e.key === "a" || e.key === "A") putuskan(ITEMS[idx].label_a);
  else if (e.key === "b" || e.key === "B") putuskan(ITEMS[idx].label_b);
  else if (e.key === "e" || e.key === "E") ekspor();
  else if (e.key === "ArrowLeft") { if (idx > 0) { idx--; simpan(); render(); } }
});
window.addEventListener("beforeunload", e => {
  if (diputuskan() > state.ekspor) { e.preventDefault(); e.returnValue = "Ada keputusan yang belum diekspor."; }
});
muat();
</script>
</body>
</html>
"""


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--adjudikator", default="Adjudikator")
    ap.add_argument("--a", default=None, help="berkas anotator A; bila diisi, sengketa dihitung ulang")
    ap.add_argument("--b", default=None, help="berkas anotator B")
    ap.add_argument("--sengketa", default=str(ANOT / "adjudikasi_kosong.jsonl"))
    ap.add_argument("--keluaran", default=str(ANOT / "adjudikasi.html"))
    a = ap.parse_args()

    pool = {(d["qid"], d["doc_id"]): d for d in
            (json.loads(l) for l in (ANOT / "kolam_kandidat.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
    if a.a and a.b:
        def baca(p):
            return {(r["qid"], r["doc_id"]): r["label"] for r in
                    (json.loads(l) for l in (ANOT / p).read_text(encoding="utf-8").splitlines() if l.strip())
                    if r.get("label") is not None}
        A, B = baca(a.a), baca(a.b)
        sengketa = []
        for k in sorted(A):
            if k in B and A[k] != B[k]:
                sengketa.append({"qid": k[0], "doc_id": k[1], "label_a": A[k], "label_b": B[k], "label_model": None})
    else:
        sengketa = [json.loads(l) for l in Path(a.sengketa).read_text(encoding="utf-8").splitlines()
                    if l.strip()]
    item = []
    for s in sengketa:
        d = pool.get((s["qid"], s["doc_id"]))
        if not d:
            continue
        item.append({
            "qid": s["qid"], "doc_id": s["doc_id"], "bahasa": d["bahasa"], "topik": d["topik"],
            "kueri": d["kueri"], "sumber": d["sumber"], "bagian": d.get("bagian", ""),
            "halaman": d.get("halaman"), "cuplikan": d["cuplikan"],
            "label_a": s["label_a"], "label_b": s["label_b"], "label_model": s.get("label_model"),
        })
    html = (TEMPLATE.replace("__ITEMS__", json.dumps(item, ensure_ascii=False))
            .replace("__ADJ__", a.adjudikator))
    out = Path(a.keluaran)
    out.write_text(html, encoding="utf-8")
    print(f"{len(item)} pasangan sengketa → {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
