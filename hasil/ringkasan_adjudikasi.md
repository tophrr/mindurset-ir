# Ringkasan adjudikasi A–B

Data A adalah putaran kedua (`data/anotasi/anotator_a.jsonl`, 300 positif / 16,0%); B 319 positif /
17,0%. **Adjudikasi selesai** oleh Tora; hasilnya di `data/anotasi/adjudikasi_tora.jsonl`.

## Hasil

| Ukuran | Nilai |
|---|---|
| Pasangan berselisih | **341** dari 1.875 (18,2%) |
| Putusan mengikuti A | 238 (70%) |
| Putusan mengikuti B | 103 (30%) |
| Putusan yang tidak mengikuti keduanya | 0 |
| Positif hasil adjudikasi | 142 dari 341 |
| Qrels final | 1.875 pasangan, **281 positif (15,0%)** |

Arah perselisihan sebelum adjudikasi: A=0/B=1 sebanyak 180, A=1/B=0 sebanyak 161.

## Per sumber

| Sumber | Berselisih | Total | Proporsi |
|---|---|---|---|
| modul thought record | 31 | 120 | 25,8% |
| who-dwm-2020-ind | 114 | 458 | 24,9% |
| who-dwm-2020-eng | 69 | 403 | 17,1% |
| who-pm-18-5-id | 54 | 323 | 16,7% |
| mindurset-cards-v1 | 38 | 232 | 16,4% |
| who-pm-18-5-eng | 35 | 339 | 10,3% |

Delapan kueri sudah sepakat penuh sebelum adjudikasi.

## Qrels final

`data/qrels_final.jsonl` dibentuk dari 1.534 pasangan yang disepakati plus 341 hasil adjudikasi dengan
`python3 scripts/gabung_qrels.py --adjudikasi data/anotasi/adjudikasi_tora.jsonl`.

## Metrik dengan qrels final (88 kueri berlabel)

| Konfigurasi | P@1 | P@5 | R@10 | MRR |
|---|---|---|---|---|
| M1 VSM TF-IDF | 0,239 | 0,189 | 0,533 | 0,390 |
| M2 Okapi BM25 | 0,239 | 0,200 | 0,535 | 0,397 |
| M3 BGE-M3 dense | 0,261 | 0,211 | 0,488 | 0,420 |
| M4 RRF hibrida | **0,341** | **0,216** | **0,581** | **0,500** |

Wilcoxon pada MRR: M4 vs M1 p = 0,014; M4 vs M2 p = 0,026; M4 vs M3 p = 0,024 — semua perbandingan
dengan M4 kini signifikan. Urutan MRR: **M4 > M3 > M2 > M1**, jadi dense tidak lagi terakhir.
