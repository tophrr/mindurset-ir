# Kesepakatan antar penilai: κ, PABAK, dan Krippendorff α

Semua dihitung pada 1.875 pasangan yang sama (kolam 1.875, 100 kueri). Data A adalah putaran kedua
(`data/anotasi/anotator_a.jsonl`, 300 positif / 16,0%); B 319 positif / 17,0%.

| Pasangan | n | Kesepakatan mentah (po) | Kebetulan (pe) | κ | CI 95% | PABAK |
|---|---|---|---|---|---|---|
| A–B (dua manusia) | 1.875 | 0,818 | 0,724 | **0,340** | 0,284–0,396 | 0,636 |
| Gemini–A | 1.875 | 0,850 | 0,717 | 0,469 | 0,419–0,524 | 0,699 |
| Gemini–B | 1.875 | 0,765 | 0,710 | 0,188 | 0,137–0,241 | 0,530 |
| Gemini–pplx | 1.875 | 0,889 | 0,681 | **0,653** | 0,608–0,697 | **0,778** |
| pplx–A | 1.875 | 0,856 | 0,693 | 0,531 | 0,481–0,581 | 0,712 |
| pplx–B | 1.875 | 0,764 | 0,687 | 0,245 | 0,195–0,296 | 0,527 |

PABAK = 2·po − 1 (prevalence-adjusted bias-adjusted kappa).

## Krippendorff α (nominal)

| Penilai | α |
|---|---|
| Empat penilai (A, B, Gemini, pplx) | 0,407 |
| Dua manusia (A, B) | 0,340 |
| Dua mesin (Gemini, pplx) | 0,652 |

## Mengapa κ rendah padahal kesepakatan mentah tinggi

Gemini dan pplx sepakat pada 88,9% pasangan, tetapi κ hanya 0,653 karena keduanya
sama-sama ketat: positif 18,1% dan 21,6%. Dengan mayoritas label 0, peluang sepakat
karena kebetulan sudah 0,681, sehingga κ menekan angka. Ini paradoks κ yang lazim pada
data dengan prevalensi tidak seimbang.

Kasus paling ekstrem adalah Gemini–B: kesepakatan mentah 76,5% tetapi κ 0,188, karena
pe 0,710 (keduanya menilai 17–18% positif). PABAK-nya 0,530.

## Di mana ambiguitasnya berada

Dari 208 pasangan yang dinilai berbeda oleh kedua model, A memberi label 1 pada **35,1%**
(di seluruh data 16,0%), sedangkan B pada 22,1% (seluruh data 17,0%). Pada arah pplx=1 dan
Gemini=0, manusia lebih sering menilai 1 (A 41%, B 28%) daripada arah sebaliknya (A 24%, B 10%).

## Implikasi untuk naskah

1. Laporkan κ **bersama** PABAK dan α, dan sebutkan efek prevalensi. Satu angka κ saja
   akan menyesatkan pembaca.
2. Jangan menurunkan ambang 0,75 setelah melihat hasil. Ambang itu ditetapkan sebelum
   anotasi; yang dilaporkan adalah nilai tercapai dan penjelasannya.
3. Landis–Koch menempatkan 0,61–0,80 sebagai *substantial*; pasangan dua mesin (0,653)
   masuk di sana, dan PABAK-nya 0,778 hampir menyentuh ambang.
4. Pasangan manusia (0,340; α 0,340) masih di bawah dua mesin (0,652). Selisih ini
   adalah temuan yang layak dilaporkan di IV.B, bukan sesuatu yang bisa dijelaskan oleh
   ambang.
