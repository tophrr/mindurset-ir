# Gemini Decision 1 vs pplx decider sebagai penilai otomatis

Dibandingkan pada kolam yang sama (1.875 pasangan, 100 kueri), dengan data manusia A2 dan B.

## Ketepatan terhadap label konsensus manusia

Konsensus = 1.534 pasangan yang dinilai sama oleh A2 dan B (139 positif).

| Ukuran | Gemini Decision 1 | pplx decider |
|---|---|---|
| Akurasi | 0,875 | **0,879** |
| Presisi | 0,383 | **0,413** |
| Recall | 0,612 | **0,799** |
| F1 (kelas positif) | 0,471 | **0,544** |

## Kesepakatan dengan manusia

| Pasangan | κ Gemini | κ pplx |
|---|---|---|
| vs A2 | 0,394 | **0,434** |
| vs B | 0,188 | **0,245** |
| vs sesama model | 0,653 (Gemini–pplx) | — |
| PABAK vs A2 / B | 0,468 / 0,530 | **0,495 / 0,527** |

Korelasi peringkat per kueri (Spearman proporsi positif): Gemini 0,565, pplx 0,563 — seri.

## Reproduksibilitas

100 pasangan dijalankan dua kali:

| Model | Label identik | Selisih probabilitas | Perubahan label |
|---|---|---|---|
| Gemini | 100/100 | 0,0000 (maks 0,0000) | 0 |
| pplx | 99/100 | median 0,0004 (maks 0,0843) | 1 |

## Biaya dan kecepatan

| Ukuran | Gemini Decision 1 | pplx decider |
|---|---|---|
| Waktu 1.875 pasangan | 30,7 menit (4 pekerja) | **4,5 menit** |
| Biaya | $0 lewat kunci AI Studio; $0,10/M token bila lewat OpenRouter (~$0,11 per run) | **$0** (model gratis) |
| Jalur | SDK Google (`google-genai`), `noul` tanpa `criteria` | endpoint OpenRouter `/api/alpha/decisions` |
| Ketergantungan | kunci AI Studio, kuota Gemini | kredit OpenRouter (akun saat ini minus $0,24) |

## Kesimpulan

- **Sebagai alat bantu anotasi dan adjudikasi**: pplx lebih baik — F1 0,544 vs 0,471 dan recall 0,799
  vs 0,612 terhadap konsensus manusia, serta κ sedikit lebih tinggi dengan kedua anotator.
- **Sebagai instrumen yang harus reproducible di naskah**: Gemini lebih baik — hasilnya identik
  bit-per-bit pada pengulangan, sementara pplx mengubah 1 dari 100 label.
- Keduanya sama-sama lebih dekat ke A2 (κ 0,39–0,43) daripada ke B (0,19–0,25), dan pada 341
  pasangan sengketa keduanya berpihak ke A (Gemini 250, pplx 257). Jadi tidak ada model yang
  "membela" B.
- Karena naskah butuh penilai ketiga yang bisa dipertanggungjawabkan, cara paling aman adalah
  **melaporkan keduanya** dan menyebut bahwa kesepakatan antar-model (κ 0,653) lebih tinggi daripada
  kesepakatan antar-manusia (0,340).
