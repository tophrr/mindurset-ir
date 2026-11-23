# Perbandingan metrik antar sumber label

| Label | Konf | MRR | P@1 | R@10 |
|---|---|---|---|---|
| A (manusia) | M1 | 0.653 | 0.450 | 0.523 |
| A (manusia) | M2 | 0.640 | 0.460 | 0.506 |
| A (manusia) | M3 | 0.568 | 0.360 | 0.381 |
| A (manusia) | M4 | 0.712 | 0.560 | 0.475 |
| B (manusia) | M1 | 0.394 | 0.232 | 0.527 |
| B (manusia) | M2 | 0.415 | 0.242 | 0.513 |
| B (manusia) | M3 | 0.433 | 0.263 | 0.454 |
| B (manusia) | M4 | 0.502 | 0.313 | 0.556 |
| Gemini Decision 1 | M1 | 0.489 | 0.303 | 0.579 |
| Gemini Decision 1 | M2 | 0.467 | 0.270 | 0.556 |
| Gemini Decision 1 | M3 | 0.377 | 0.213 | 0.380 |
| Gemini Decision 1 | M4 | 0.522 | 0.360 | 0.519 |
| pplx decider | M1 | 0.515 | 0.341 | 0.551 |
| pplx decider | M2 | 0.506 | 0.330 | 0.539 |
| pplx decider | M3 | 0.418 | 0.250 | 0.409 |
| pplx decider | M4 | 0.550 | 0.398 | 0.499 |

Catatan: label pplx memakai 88 kueri (12 kueri tanpa positif), label lain 100 kueri.

Kesepakatan antar penilai (Cohen's κ, 1.875 pasangan):

| Pasangan | κ |
|---|---|
| A–B | 0,227 |
| Gemini–A | 0,394 |
| Gemini–B | 0,188 |
| Gemini–pplx | 0,653 |
| pplx–A | 0,434 |
| pplx–B | 0,245 |
