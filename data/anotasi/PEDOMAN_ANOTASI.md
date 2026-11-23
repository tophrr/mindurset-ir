# Pedoman anotasi relevansi (G-α3)

Dokumen ini dipakai dua anotator independen, Christian (A) dan Evan (B), untuk mengisi matriks
`qrels` pada 100 kueri × kolam kandidat. Pedoman ditulis sebelum anotasi dimulai dan tidak diubah
di tengah jalan.

## 1. Tugas

Untuk setiap pasangan **kueri** dan **chunk**, beri satu label:

| Label | Arti |
|---|---|
| **1** | Chunk memuat keterampilan koping atau instruksi yang **cocok** untuk situasi pada kueri dan **dapat ditampilkan** kepada pengguna sebagai saran. |
| **0** | Selain itu, termasuk chunk yang topiknya sama tetapi tekniknya tidak menjawab masalah pada kueri. |

Anotasi bersifat **buta peringkat**: alat tidak menampilkan skor, peringkat, atau nama model.
Jangan menebak chunk ini berasal dari model mana.

## 2. Aturan keputusan

Beri **1** hanya bila ketiga syarat ini terpenuhi.

1. **Ada tekniknya.** Chunk memuat langkah atau keterampilan yang bisa dijalankan, bukan hanya
   penjelasan umum, ajakan semangat, atau definisi.
2. **Cocok dengan masalah pada kueri.** Teknik itu menjawab situasi yang diceritakan, bukan hanya
   satu kata yang kebetulan sama.
3. **Layak ditampilkan.** Isinya aman dan tidak menyuruh pengguna melakukan hal yang berisiko.

Beri **0** bila salah satu terjadi.

- Topik sama, teknik berbeda. Kueri tentang nilai ujian, chunk tentang sulit tidur.
- Hanya berbagi kata. Kueri memuat kata "nilai", chunk memuat kata "nilai" dalam arti lain.
- Isinya meta. Potongan yang menjelaskan cara pendamping memakai lembar kerja, atau daftar isi bab,
  tidak dipakai sebagai saran kepada pengguna.
- Isinya rangkuman tanpa langkah. "Mengelola Masalah adalah strategi terstruktur" bukan saran.
- Isinya khusus untuk masalah lain yang kebetulan disebut. Contoh lembar kerja tentang pertengkaran
  suami istri tidak relevan untuk kueri tentang ujian, meskipun strukturnya berupa langkah.

Kasus batas dan keputusannya.

- **Kueri krisis.** Kueri yang menyebut keinginan menyakiti diri tetap dinilai seperti kueri lain.
  Chunk rencana keselamatan dan nomor bantuan diberi **1** karena itulah saran yang tepat.
- **Chunk panjang yang memuat dua hal.** Bila satu bagian chunk memuat teknik yang cocok, beri **1**.
  Anotator tidak menilai porsi, hanya ada atau tidak ada.
- **Teknik umum yang tetap masuk akal.** Napas lambat untuk kueri cemas menjelang sidang tetap **1**,
  karena tekniknya menjawab gejala yang diceritakan.
- **Ragu.** Pilih **0** dan tulis catatan singkat di kolom `catatan` pada berkas ekspor bila perlu.
  Aturan ini menjaga agar label 1 benar-benar berarti "layak ditampilkan".

## 3. Contoh dari kolam kandidat

**Kueri `q-en-046`**: *"I have not slept properly for a week, my head is full until morning"*

- `kartu-en-sleep` (kartu tidur: wind-down, gulir malam, cahaya pagi) → **1**. Ada teknik yang bisa
  dijalankan dan cocok dengan keluhan tidur.
- `pm-ch7-en-001` (langkah 1 Mengelola Masalah: mendaftar masalah) → **0**. Ada teknik, tetapi
  menyelesaikan masalah praktis, bukan kesulitan tidur yang diceritakan.

**Kueri `q-id-011`**: *"nilai uts ku jatuh banget, aku takut gak bisa lulus mata kuliah ini"*

- `tr-id-002` (kolom 3–5 pencatatan pikiran: menulis pikiran otomatis, bukti mendukung, bukti
  menentang) → **1**. Teknik restrukturisasi kognitif langsung menjawab ketakutan akan gagal.
- `dwm-id-023` (pentingnya punya teman yang peduli) → **0**. Temanya dukungan sosial, tetapi tidak
  memberi langkah untuk kekhawatiran nilai. Ini contoh chunk yang terangkat karena kedekatan tema.

## 4. Prosedur kalibrasi

1. Setiap anotator menilai **20 kueri kalibrasi** (375 pasangan): `q-id-001`–`q-id-010` dan
   `q-en-001`–`q-en-010`. Buka tab **Kalibrasi** pada alat — badge kuning "kalibrasi" menandai
   kuerinya, dan ekspornya terpisah dari anotasi penuh.
2. Ekspor lewat tombol mode Kalibrasi (`anotator_a_kalibrasi.jsonl`, `anotator_b_kalibrasi.jsonl`),
   lalu hitung kesepakatan:
   ```bash
   cd /home/chrisg/Hermes/kec-ko-paper-uas
   python3 eksperimen/retrieval_eval.py kappa \
       --anotator-a data/anotasi/ekspor/anotator_a_kalibrasi.jsonl \
       --anotator-b data/anotasi/ekspor/anotator_b_kalibrasi.jsonl
   ```
3. Bila κ < 0,75, bahas pasangan yang berbeda (biasanya 10–20 pasangan), sepakati tafsiran aturan
   di atas, lalu **ulangi kalibrasi**. Hasil kalibrasi tidak dipakai sebagai data akhir.
4. Setelah κ ≥ 0,75, lanjutkan anotasi penuh 100 kueri dengan pedoman yang sama.

## 5. Adjudikasi

Data A yang dipakai adalah **putaran kedua** (`ekspor/anotator_a.jsonl`, 300 positif / 16,0%);
putaran pertama diarsipkan sebagai `ekspor/anotator_a1_prakalibrasi.jsonl`.

Setelah kalibrasi, A dan B masih berselisih pada **341 pasangan** (18,2%). Semua diselesaikan pihak
ketiga (Tora) dengan melihat kedua label, isi chunk, dan pendapat model penilai:

```bash
xdg-open data/anotasi/adjudikasi.html      # 341 pasangan, progress + ekspor sendiri
```

Alat menampilkan `label_a`, `label_b`, dan `label_model`; tombol **1**/**0** untuk putusan bebas,
**A**/**B** untuk mengikuti salah satu anotator, kotak alasan opsional, dan ekspor
`adjudikasi_christopher.jsonl`. Simpan ke `data/anotasi/ekspor/`.

Qrels final dibentuk dengan:

```bash
python3 eksperimen/gabung_qrels.py --adjudikasi data/anotasi/ekspor/adjudikasi_christopher.jsonl
```

Skrip memakai label yang disepakati (1.534 pasangan) dan `label_final` hasil adjudikasi (341
pasangan), lalu menulis `data/qrels_final.jsonl`. Bila masih ada perselisihan yang belum diputuskan,
skrip berhenti dan melaporkan jumlahnya. Jumlah kasus yang diadjudikasi dilaporkan di Subbagian IV.B.

## 6. Cara memakai alat

Versi ringkas untuk anotator ada di `PANDUAN_SINGKAT.md` (Bagian 1–3 dan 6 saja).

```bash
xdg-open /home/chrisg/Hermes/kec-ko-paper-uas/data/anotasi/anotasi.html
```

Alat punya **dua mode** dengan kemajuan, total, dan ekspor terpisah:

| Mode | Isi | Ekspor |
|---|---|---|
| Kalibrasi | 20 kueri (`q-id-001`–`010`, `q-en-001`–`010`), **375 pasangan** | `anotator_<huruf>_kalibrasi.jsonl` |
| Utama | seluruh kolam, **1.875 pasangan** | `anotator_<huruf>.jsonl` |

1. Pilih nama anotator di kanan atas. Label tersimpan otomatis di peramban (localStorage) dan
   dipakai bersama kedua mode, jadi pasangan yang sudah dinilai di kalibrasi tidak perlu diulang.
2. Dua meter di kepala alat menunjukkan kemajuan masing-masing mode (`x / 375` dan `x / 1875`).
3. Tombol **1** relevan, **0** tidak relevan, **3** lewati, panah kiri kembali, **E** ekspor.
4. Tidak ada modal pengingat. Anotator mengekspor sendiri secara berkala (disarankan tiap 100
   label) lewat tombol **Ekspor** atau tombol **E**; status "ekspor terakhir" tampil di kepala alat.
   Peramban memperingatkan bila halaman ditutup sebelum ekspor.
5. Berkas ekspor memuat semua pasangan mode itu dengan `label: null` untuk yang belum dinilai,
   sehingga cakupan anotasi mudah diperiksa.

Perkiraan waktu: 375 pasangan kalibrasi ±35 menit, 1.875 pasangan utama 2,5–3 jam per anotator
(4–6 detik per pasangan).

## 7. Berkas terkait

| Berkas | Isi |
|---|---|
| `kolam_kandidat.jsonl` | 1.161 pasangan, lengkap dengan peringkat M1/M2 untuk keperluan analisis (jangan dibuka saat menilai) |
| `anotator_a.jsonl`, `anotator_b.jsonl` | lembar kerja kosong, urutan diacak berbeda per anotator |
| `ringkasan_kolam.json` | statistik kolam per kueri, termasuk irisan M1 dan M2, serta daftar kueri kalibrasi |
| `anotasi.html` | alat anotasi satu berkas, data disematkan, tanpa server |
| `ekspor/` | tempat menyimpan hasil ekspor JSONL (dibuat manual) |

## 8. Catatan metodologis yang harus masuk naskah

Kolam kandidat dibentuk dari 10 teratas **keempat** konfigurasi: M1 (VSM TF-IDF), M2 (Okapi BM25),
M3 (BGE-M3 *dense*), dan M4 (RRF BM25+dense). Uji *dense* dijalankan ulang pada mesin GPU
terpisah (fp16) pada 18 November 2026 setelah korpus DWM dibangun ulang dengan ekstraksi
sadar-kolom, lalu kolam dirakit dari nol menjadi **1.875 pasangan** (936 Indonesia, 939 Inggris;
15–24 kandidat per kueri). Karena keempat konfigurasi ikut menyumbang kandidat, skor M3 dan M4 tidak
lagi bersifat batas bawah seperti pada rencana awal dengan dua model leksikal saja.

Dua hal tetap perlu dinyatakan di IV.F. Pertama, kolam tetap tidak memuat dokumen yang tidak
diangkat sepuluh teratas oleh konfigurasi mana pun, sehingga relevansi di luar kolam tidak terukur.
Kedua, latensi M3 dan M4 diukur pada satu lingkungan CPU yang dispesifikasikan (16 thread,
torch fp32), bukan pada perangkat Android tempat aplikasi berjalan.
