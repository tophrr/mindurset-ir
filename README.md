# who-ir — artefak perbandingan konfigurasi retrieval untuk Mind-Ur-Set

Repo ini memuat korpus, himpunan kueri, matriks relevansi, dan skrip evaluasi yang dipakai pada
artikel "Perbandingan Model Retrieval Leksikal, Dense, dan Hibrida pada Korpus Psikoedukasi Mikro
Tertutup untuk Aplikasi Mind-Ur-Set" (Kelompok 5, Kecerdasan Komputasional INF20052, Universitas Pelita Harapan).
Empat konfigurasi dibandingkan: VSM TF-IDF, Okapi BM25, BGE-M3 *dense* (ONNX int8), dan fusi
*Reciprocal Rank Fusion*.

## Hasil utama

| Ukuran | Nilai |
|---|---|
| Korpus | 153 *chunk* (77 Inggris, 76 Indonesia), 56.089 token |
| Kueri | 100 (50 Indonesia, 50 Inggris) |
| Kolam anotasi | 1.875 pasangan kueri-*chunk* |
| Kesepakatan anotator | κ = 0,340; 341 pasangan diadjudikasi |
| *Qrels* final | 281 pasangan positif (15,0%) |
| MRR (qrels final) | M1 0,390 · M2 0,397 · M3 0,420 · **M4 0,500** |

## Reproduksi

Angka pada naskah dapat diproduksi ulang persis dengan vektor yang disertakan:

```bash
pip install -r requirements.txt
python3 scripts/eval/retrieval_eval.py run --korpus data/korpus.jsonl --kueri data/kueri.jsonl \
    --qrels data/qrels_final.jsonl --keluaran hasil/reproduksi --k 1 5 10 \
    --dense-backend berkas --dense-chunk-berkas hasil/embedding/emb_chunk_cls.npy \
    --dense-kueri-berkas hasil/embedding/emb_kueri_cls.npy
```

Hasil yang diharapkan: MRR M1 0,390 · M2 0,397 · M3 0,420 · M4 0,500.

Untuk mengodekan ulang dari model, unduh ONNX int8 BGE-M3 dari
https://huggingface.co/Xenova/bge-m3/tree/main/onnx (`model_int8.onnx`, `tokenizer.json`,
`tokenizer_config.json`, `special_tokens_map.json`, `config.json`) ke `models/bge-m3-onnx/` atau set
`BGE_MODEL_DIR`, lalu:

```bash
python3 scripts/eval/embed_onnx.py --korpus data/korpus.jsonl --kueri data/kueri.jsonl \
    --keluaran-chunk hasil/emb_chunk.npy --keluaran-kueri hasil/emb_kueri.npy
```

**Peringatan reprodusibilitas.** Model int8 dijalankan tanpa penguncian bit-level: pengodean ulang
menghasilkan vektor dengan kosinus sekitar 0,986 terhadap vektor yang disertakan, dan nilai itu
bergeser lagi bila `--batch` diubah (batch 4 dan 8 berbeda sampai 0,019). Karena M4 memakai fusi
peringkat, pergeseran kecil itu mengubah MRR M4 cukup banyak (0,500 menjadi 0,513 pada batch 8).
Karena itu `hasil/embedding/` disertakan sebagai vektor acuan, sedangkan pengodean ulang dipakai
untuk memeriksa kestabilan, bukan untuk menggantikan angka naskah. M1 dan M2 selalu identik karena
tidak memakai embedding.

`python3 scripts/eval/retrieval_eval.py selftest` menguji metrik, RRF, Wilcoxon, dan κ pada data
sintetis.

## Peta berkas

| Jalur | Isi |
|---|---|
| `data/korpus.jsonl` | korpus final, satu *chunk* per baris (`id`, `bahasa`, `sumber`, `halaman`, `teks`) |
| `data/kueri.jsonl` | 100 kueri afektif (`qid`, `bahasa`, `teks`) |
| `data/qrels_final.jsonl` | 1.875 pasangan berlabel (`qid`, `doc_id`, `label`) |
| `data/src/` | teks sumber hasil ekstraksi (DWM, PM+ bab 6–10, modul *thought record*, kartu koping) |
| `data/anotasi/` | kolam kandidat, ekspor dua anotator, putusan adjudikasi, kedua alat HTML, pedoman anotasi |
| `scripts/korpus/` | pembentukan korpus dari teks sumber sampai `korpus.jsonl` |
| `scripts/anotasi/` | pembentukan kolam kandidat, alat anotasi HTML, dan anotasi otomatis pembanding |
| `scripts/eval/` | harness evaluasi, embedding ONNX, pengukuran latensi, uji hibrida *sparse* |
| `scripts/qrels/` | pembentukan himpunan kueri dan penggabungan *qrels* |
| `hasil/` | keluaran evaluasi final per bahasa, latensi, dan ringkasan adjudikasi |
| `ref/tok/` | tokenizer BGE-M3 untuk menghitung panjang *chunk* (300–500 token) |

Urutan pembentukan korpus: `scripts/korpus/susun_sumber.py` → `ekstrak_pm_bab.py` /
`ekstrak_pm_ch7.py` → `gabung_korpus.py` → `bangun_korpus.py` → `validasi_korpus.py`.

## Alat anotasi

`data/anotasi/anotasi.html` dan `data/anotasi/adjudikasi.html` adalah aplikasi satu berkas: buka di
peramban, hasil ekspor berupa JSONL. Anotasi memuat 1.875 pasangan dalam mode kalibrasi (20 kueri)
dan mode penuh; adjudikasi memuat 341 kasus sengketa antara kedua anotator.

## Sumber dan lisensi

- *Doing What Matters in Times of Stress* (WHO, 2020) — https://www.who.int/publications/i/item/9789240003927
- *Hal yang Perlu Dilakukan Saat Stres* (WHO SEARO, 2020, terjemahan resmi) —
  https://www.who.int/docs/default-source/searo/indonesia/hal-yang-perlu-dilakukan-saat-stres.pdf
- *Problem Management Plus* (WHO, 2018, WHO/MSD/MER/18.5) —
  https://www.who.int/publications/i/item/WHO-MSD-MER-18.5 — Bab 6–10 diterjemahkan kelompok,
  bukan terbitan resmi WHO.
- Modul *thought record* dan kartu koping: karya kelompok; kartu dirilis MIT.

Berkas PDF sumber tidak disertakan di repo; gunakan tautan di atas. Teks hasil ekstraksi ada di
`data/src/` agar penomoran halaman dan pemotongan *chunk* dapat diperiksa.

## Batasan yang perlu diketahui pemakai data ini

1. Anotasi menilai 700 karakter pertama setiap *chunk*, bukan teks utuh. Uji ulang dengan teks penuh
   mengubah 250 dari 1.875 label dan menaikkan MRR 0,015–0,064 tanpa mengubah urutan konfigurasi.
2. Kesepakatan dua anotator manusia hanya κ = 0,340; 341 pasangan diselisihkan dan diputuskan satu
   adjudikator. *Qrels* ini lebih ketat daripada label satu anotator tunggal.
3. Korpus mikro: 153 *chunk* membuat satu perubahan peringkat menggeser metrik cukup besar.
4. `hasil/uji_hybrid_sparse.json` menyimpan jalur berkas dari mesin tempat eksperimen dijalankan.
