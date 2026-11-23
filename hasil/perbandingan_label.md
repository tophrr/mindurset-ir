# Perbandingan metrik antar sumber label

Empat konfigurasi retrieval, dihitung dengan harness yang sama; hanya sumber label yang berbeda.

| Label | Konf | MRR | P@1 | P@3 | P@5 | P@10 | R@10 |
|---|---|---|---|---|---|---|---|
| A (manusia, 92 kueri) | M1 | 0,400 | 0,250 | 0,192 | 0,176 | 0,170 | 0,529 |
| A (manusia, 92 kueri) | M2 | 0,400 | 0,261 | 0,192 | 0,183 | 0,157 | 0,493 |
| A (manusia, 92 kueri) | M3 | 0,403 | 0,272 | 0,207 | 0,193 | 0,150 | 0,446 |
| A (manusia, 92 kueri) | M4 | **0,468** | **0,293** | **0,283** | **0,213** | **0,172** | 0,528 |
| B (manusia, 99 kueri) | M1 | 0,394 | 0,232 | 0,222 | 0,196 | 0,171 | 0,527 |
| B (manusia, 99 kueri) | M2 | 0,415 | 0,242 | 0,232 | 0,218 | 0,164 | 0,513 |
| B (manusia, 99 kueri) | M3 | 0,433 | 0,263 | 0,209 | 0,188 | 0,143 | 0,454 |
| B (manusia, 99 kueri) | M4 | **0,502** | **0,313** | **0,253** | 0,202 | **0,182** | **0,556** |
| Gemini Decision 1 (89 kueri) | M1 | 0,489 | 0,303 | 0,243 | 0,227 | 0,203 | **0,579** |
| Gemini Decision 1 (89 kueri) | M2 | 0,467 | 0,270 | 0,243 | 0,213 | 0,192 | 0,556 |
| Gemini Decision 1 (89 kueri) | M3 | 0,377 | 0,213 | 0,199 | 0,196 | 0,143 | 0,380 |
| Gemini Decision 1 (89 kueri) | M4 | **0,522** | **0,360** | **0,258** | 0,211 | 0,184 | 0,519 |
| pplx decider (88 kueri) | M1 | 0,515 | 0,341 | 0,280 | **0,266** | **0,240** | **0,551** |
| pplx decider (88 kueri) | M2 | 0,506 | 0,330 | 0,277 | 0,259 | 0,230 | 0,539 |
| pplx decider (88 kueri) | M3 | 0,418 | 0,250 | 0,220 | 0,225 | 0,189 | 0,409 |
| pplx decider (88 kueri) | M4 | **0,550** | **0,398** | **0,307** | 0,245 | 0,224 | 0,499 |

Catatan: jumlah kueri yang bisa dinilai berbeda karena harness melewati kueri yang tidak punya satu pun
label relevan (A 92, B 99, Gemini 89, pplx 88). Angka antar-baris karena itu tidak sepenuhnya sebanding
dan hanya dipakai untuk memeriksa kestabilan peringkat.

Kesepakatan antar penilai (Cohen's κ, 1.875 pasangan): A–B 0,340 · Gemini–A 0,469 · Gemini–B 0,188 ·
Gemini–pplx 0,653 · pplx–A 0,531 · pplx–B 0,245.

## Kesimpulan

M4 (RRF BM25 + dense) unggul pada MRR dan P@1 di keempat sumber label. M1 menang pada R@10 di tiga
sumber label (A, Gemini, pplx). M3 (dense murni) selalu terakhir kecuali pada label B. Jadi kesimpulan
relatif antar-konfigurasi stabil terhadap perbedaan anotator.
