# Ringkasan adjudikasi A2–B

Total pasangan berselisih: **341** dari 1.875 (18.2%).

| Arah | Jumlah |
|---|---|
| A=1, B=0 | 161 |
| A=0, B=1 | 180 |

Sebaran hampir seimbang — berbeda dari putaran pertama A yang berat sebelah (537 vs 97).

## Per sumber

| Sumber | Berselisih | Total | Proporsi |
|---|---|---|---|
| who-dwm-2020-ind | 114 | 458 | 24.9% |
| who-dwm-2020-eng | 69 | 403 | 17.1% |
| who-pm-18-5-id | 54 | 323 | 16.7% |
| mindurset-cards-v1 | 38 | 232 | 16.4% |
| who-pm-18-5-eng | 35 | 339 | 10.3% |
| modul-thought-record | 31 | 120 | 25.8% |

## Cara kerja adjudikasi

1. Buka `data/anotasi/adjudikasi_kosong.jsonl` (341 baris, urut qid/doc_id).
2. Setiap baris memuat `label_a`, `label_b`, dan `label_model` (Gemini) sebagai pendapat ketiga.
3. Isi `label_final` (0/1) dan `alasan` singkat, lalu simpan sebagai `data/anotasi/adjudikasi.jsonl`.
4. Qrels final dibentuk dari: label yang disepakati + `label_final` hasil adjudikasi.

Perkiraan waktu: 341 pasangan × 20–30 detik ≈ 2–3 jam.
