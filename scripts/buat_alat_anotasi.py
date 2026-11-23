#!/usr/bin/env python3
"""Buat alat anotasi HTML satu berkas untuk G-α3.

Kolam kandidat disematkan langsung ke dalam HTML (tanpa server, tanpa peringkat model,
tanpa nama model) sehingga anotator menilai secara buta.

Dua mode dengan kemajuan, total, dan ekspor terpisah:
    Kalibrasi  20 kueri (375 pasangan), ekspor `anotator_<huruf>_kalibrasi.jsonl`
    Utama      seluruh kolam (1.875 pasangan), ekspor `anotator_<huruf>.jsonl`

Tidak ada modal pengingat; status "ekspor terakhir" tampil di kepala alat dan peramban hanya
memperingatkan bila halaman ditutup sebelum ekspor. Label disimpan di localStorage, jadi
pekerjaan bisa ditinggal dan dilanjutkan.

Pemakaian:
    python3 eksperimen/buat_alat_anotasi.py
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
<title>Anotasi relevansi — Korpus KK Kelompok 5</title>
<style>
  :root { --bg:#0f1115; --card:#171a21; --line:#262b36; --txt:#e6e8ee; --dim:#9aa3b2;
          --ok:#2f8f5b; --no:#a3423f; --skip:#4a5160; --acc:#7aa2f7; --cal:#e0af68; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font-family: ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif; }
  header { position:sticky; top:0; background:#12151b; border-bottom:1px solid var(--line);
           padding:10px 16px; display:flex; gap:16px; align-items:center; flex-wrap:wrap; z-index:5; }
  header h1 { font-size:15px; margin:0; font-weight:600; }
  .grow { flex:1; }
  select, button { font:inherit; }
  select { background:#1c2028; color:var(--txt); border:1px solid var(--line); border-radius:6px; padding:5px 8px; }
  .tabs { display:flex; gap:6px; }
  .tabs button { background:#1c2028; color:var(--dim); border:1px solid var(--line); border-radius:8px;
                 padding:7px 12px; cursor:pointer; font-weight:600; font-size:13px; }
  .tabs button.aktif { background:#243049; color:#dfe7ff; border-color:#3b4d78; }
  .meter { display:flex; flex-direction:column; gap:3px; min-width:170px; }
  .meter .lbl { font-size:11px; color:var(--dim); display:flex; justify-content:space-between; gap:8px; }
  .bar { height:6px; background:#232833; border-radius:99px; overflow:hidden; }
  .bar > i { display:block; height:100%; width:0; background:var(--acc); }
  .bar.cal > i { background:var(--cal); }
  main { max-width:900px; margin:0 auto; padding:18px 16px 130px; }
  .meta { font-size:12px; color:var(--dim); margin-bottom:6px; }
  .q { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }
  .q .tag { display:inline-block; font-size:11px; color:#0f1115; background:var(--acc);
            border-radius:99px; padding:1px 8px; margin-right:6px; }
  .q .tag.cal { background:var(--cal); }
  .q p { margin:8px 0 0; font-size:19px; line-height:1.45; }
  .c { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin-top:12px; }
  .c .src { font-size:12px; color:var(--dim); margin-bottom:8px; }
  .c .txt { font-size:15px; line-height:1.55; max-height:42vh; overflow:auto; white-space:pre-wrap; }
  .keys { position:fixed; left:0; right:0; bottom:0; background:#12151b; border-top:1px solid var(--line);
          padding:12px 16px; display:flex; gap:10px; justify-content:center; flex-wrap:wrap; }
  .keys button { border:none; border-radius:8px; padding:11px 18px; color:#fff; cursor:pointer; font-weight:600; }
  .keys button:disabled { opacity:.35; cursor:not-allowed; }
  .b1 { background:var(--ok); } .b0 { background:var(--no); } .b3 { background:var(--skip); }
  .b4 { background:#2a3040; }
  .keys small { color:var(--dim); align-self:center; }
  .hint { font-size:12px; color:var(--dim); margin-top:10px; line-height:1.5; }
  .status { font-size:12px; color:var(--dim); }
  .status b { color:#cfd6e4; }
</style>
</head>
<body>
<header>
  <h1>Anotasi relevansi kueri–chunk</h1>
  <div class="tabs">
    <button id="tab-kal" data-mode="kalibrasi">Kalibrasi</button>
    <button id="tab-utama" data-mode="utama">Utama</button>
  </div>
  <div class="meter">
    <div class="lbl"><span>Kalibrasi</span><span id="prog-kal">0 / 0</span></div>
    <div class="bar cal"><i id="bar-kal"></i></div>
  </div>
  <div class="meter">
    <div class="lbl"><span>Utama</span><span id="prog-utama">0 / 0</span></div>
    <div class="bar"><i id="bar-utama"></i></div>
  </div>
  <div class="grow"></div>
  <label class="meta">Anotator
    <select id="who">
      <option value="a">A — Christian</option>
      <option value="b">B — Evan</option>
    </select>
  </label>
  <span class="status" id="status">belum pernah ekspor</span>
  <button class="b4" id="export" style="border-radius:8px;padding:8px 12px;color:#fff;border:none;cursor:pointer">Ekspor</button>
</header>
<main>
  <div class="meta" id="pos"></div>
  <div class="q">
    <span class="tag" id="topik">—</span><span class="tag cal" id="cal" style="display:none">kalibrasi</span>
    <span class="meta" id="qid"></span>
    <p id="kueri">—</p>
  </div>
  <div class="c">
    <div class="src" id="src"></div>
    <div class="txt" id="txt"></div>
  </div>
  <div class="hint">
    <b>1</b> relevan bila chunk memuat keterampilan koping yang cocok dan dapat dipakai untuk situasi pada kueri.
    <b>0</b> bila tidak, termasuk chunk yang topiknya sama tetapi tekniknya tidak menjawab masalah kueri.
    <b>E</b> ekspor. Peringkat model tidak ditampilkan; label tersimpan otomatis di peramban ini.
  </div>
</main>
<div class="keys">
  <button class="b1" id="b1">1 · Relevan</button>
  <button class="b0" id="b0">0 · Tidak relevan</button>
  <button class="b3" id="b3">3 · Lewati</button>
  <button class="b4" id="prev">← Sebelumnya</button>
  <small>panah kiri = kembali · E = ekspor</small>
</div>

<script>
const ITEMS = __ITEMS__;
const CALQ = new Set(__CAL__);
const MODE = {
  kalibrasi: ITEMS.filter(it => CALQ.has(it.qid)),
  utama: ITEMS
};
const KEY = w => "kk-anotasi-" + w;
let who = "a", mode = "kalibrasi", idx = 0;
let state = { labels:{}, pos:{kalibrasi:0, utama:0}, ekspor:{kalibrasi:-1, utama:-1} };

const el = id => document.getElementById(id);
const items = () => MODE[mode];
const kunci = it => it.qid + "|" + it.doc_id;

function muat() {
  who = el("who").value;
  const raw = localStorage.getItem(KEY(who));
  const awal = { labels:{}, pos:{kalibrasi:0, utama:0}, ekspor:{kalibrasi:-1, utama:-1} };
  state = raw ? Object.assign(awal, JSON.parse(raw)) : awal;
  state.pos = Object.assign({kalibrasi:0, utama:0}, state.pos);
  state.ekspor = Object.assign({kalibrasi:-1, utama:-1}, state.ekspor);
  idx = Math.min(state.pos[mode] || 0, items().length - 1);
  render();
}
function simpan() {
  state.pos[mode] = idx;
  localStorage.setItem(KEY(who), JSON.stringify(state));
}
function dinilai(m) {
  const daftar = MODE[m];
  return daftar.filter(it => state.labels[kunci(it)] !== undefined).length;
}
function render() {
  const daftar = items();
  const it = daftar[idx];
  el("tab-kal").className = mode === "kalibrasi" ? "aktif" : "";
  el("tab-utama").className = mode === "utama" ? "aktif" : "";
  const nKal = dinilai("kalibrasi"), nUtama = dinilai("utama");
  el("prog-kal").textContent = nKal + " / " + MODE.kalibrasi.length;
  el("prog-utama").textContent = nUtama + " / " + MODE.utama.length;
  el("bar-kal").style.width = (100 * nKal / MODE.kalibrasi.length).toFixed(1) + "%";
  el("bar-utama").style.width = (100 * nUtama / MODE.utama.length).toFixed(1) + "%";
  const lewat = state.ekspor[mode];
  el("status").textContent = lewat < 0
    ? "belum pernah ekspor"
    : "ekspor terakhir: " + lewat + " label (" + mode + ")";
  if (!it) return;
  el("topik").textContent = it.topik;
  el("cal").style.display = CALQ.has(it.qid) ? "inline-block" : "none";
  el("qid").textContent = it.qid + " · " + it.bahasa;
  el("kueri").textContent = it.kueri;
  const hlm = it.halaman === null ? "" : " · hlm " + (Array.isArray(it.halaman) ? it.halaman.join(",") : it.halaman);
  el("src").textContent = it.sumber + (it.bagian ? " · " + it.bagian : "") + hlm + " · " + it.doc_id;
  el("txt").textContent = it.cuplikan;
  el("pos").textContent = "Pasangan " + (idx + 1) + " dari " + daftar.length + " · mode " + mode;
  const cur = state.labels[kunci(it)];
  el("b1").style.opacity = cur === 1 ? 1 : 0.85;
  el("b0").style.opacity = cur === 0 ? 1 : 0.85;
}
function nilai(v) {
  const it = items()[idx];
  if (!it) return;
  if (v === null) delete state.labels[kunci(it)]; else state.labels[kunci(it)] = v;
  if (idx < items().length - 1) idx++;
  simpan(); render();
}
function ekspor() {
  const daftar = items();
  const baris = daftar.map(it => {
    const l = state.labels[kunci(it)];
    return JSON.stringify({qid: it.qid, doc_id: it.doc_id, bahasa: it.bahasa,
                           label: l === undefined ? null : l});
  });
  const blob = new Blob([baris.join("\\n") + "\\n"], {type:"application/x-ndjson"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "anotator_" + who + (mode === "kalibrasi" ? "_kalibrasi" : "") + ".jsonl";
  a.click();
  state.ekspor[mode] = dinilai(mode);
  simpan(); render();
}
function gantiMode(m) {
  simpan();
  mode = m;
  idx = Math.min(state.pos[mode] || 0, items().length - 1);
  render();
}

el("who").addEventListener("change", () => { simpan(); muat(); });
el("tab-kal").addEventListener("click", () => gantiMode("kalibrasi"));
el("tab-utama").addEventListener("click", () => gantiMode("utama"));
el("b1").addEventListener("click", () => nilai(1));
el("b0").addEventListener("click", () => nilai(0));
el("b3").addEventListener("click", () => nilai(null));
el("prev").addEventListener("click", () => { if (idx > 0) { idx--; simpan(); render(); } });
el("export").addEventListener("click", ekspor);
document.addEventListener("keydown", e => {
  if (e.key === "1") nilai(1);
  else if (e.key === "0") nilai(0);
  else if (e.key === "3") nilai(null);
  else if (e.key === "e" || e.key === "E") ekspor();
  else if (e.key === "ArrowLeft") { if (idx > 0) { idx--; simpan(); render(); } }
});
window.addEventListener("beforeunload", e => {
  if (dinilai(mode) > (state.ekspor[mode] || 0)) {
    e.preventDefault();
    e.returnValue = "Ada label yang belum diekspor. Ekspor dulu?";
  }
});
muat();
</script>
</body>
</html>
"""


def main() -> int:
    kolam = [json.loads(l) for l in (ANOT / "kolam_kandidat.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    ringkas = json.loads((ANOT / "ringkasan_kolam.json").read_text(encoding="utf-8"))
    # anotasi buta: peringkat model dan nama model tidak ikut disematkan
    item = [{
        "qid": d["qid"], "doc_id": d["doc_id"], "bahasa": d["bahasa"], "topik": d["topik"],
        "kueri": d["kueri"], "sumber": d["sumber"], "bagian": d.get("bagian", ""),
        "halaman": d.get("halaman"), "cuplikan": d["cuplikan"],
    } for d in kolam]
    kalibrasi = ringkas["kalibrasi"]
    jumlah_kal = sum(1 for d in kolam if d["qid"] in set(kalibrasi))
    html = (TEMPLATE
            .replace("__ITEMS__", json.dumps(item, ensure_ascii=False))
            .replace("__CAL__", json.dumps(kalibrasi, ensure_ascii=False)))
    out = ANOT / "anotasi.html"
    out.write_text(html, encoding="utf-8")
    print(f"{len(item)} pasangan (kalibrasi {jumlah_kal}, {len(kalibrasi)} kueri) → {out} "
          f"({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
