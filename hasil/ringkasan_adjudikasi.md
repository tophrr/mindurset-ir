# Ringkasan adjudikasi A–B

Data A adalah putaran kedua (`data/anotasi/anotator_a.jsonl`, 300 positif / 16,0%); B 319 positif /
17,0%.

Total pasangan berselisih: **341** dari 1.875 (18,2%).

| Arah | Jumlah |
|---|---|
| A=0, B=1 | 180 |
| A=1, B=0 | 161 |

Sebaran hampir seimbang, jadi tidak ada anotator yang sistematis lebih longgar.

## Per sumber

| Sumber | Berselisih | Total | Proporsi |
|---|---|---|---|
| modul thought record | 31 | 120 | 25,8% |
| who-dwm-2020-ind | 114 | 458 | 24,9% |
| who-dwm-2020-eng | 69 | 403 | 17,1% |
| who-pm-18-5-id | 54 | 323 | 16,7% |
| mindurset-cards-v1 | 38 | 232 | 16,4% |
| who-pm-18-5-eng | 35 | 339 | 10,3% |

Delapan kueri sudah sepakat penuh.

## Cara kerja adjudikasi

1. Buka `data/anotasi/adjudikasi.html` (341 pasangan; tiap baris memuat `label_a`, `label_b`, dan
   `label_model` sebagai pendapat ketiga).
2. Putuskan dengan tombol **1** / **0**, atau ikuti salah satu anotator (**A** / **B**); kotak alasan
   opsional.
3. Ekspor `adjudikasi_tora.jsonl`, simpan ke `data/anotasi/`.
4. Qrels final dibentuk dengan
   `python3 scripts/gabung_qrels.py --adjudikasi data/anotasi/adjudikasi_tora.jsonl`.
   Skrip memakai 1.534 pasangan yang disepakati plus 341 hasil adjudikasi, dan berhenti bila masih ada
   perselisihan yang belum diputuskan.

Perkiraan waktu: 341 pasangan × 20–30 detik ≈ 2–3 jam.
