# Panduan singkat anotasi

## 1. Tugas

Beri satu label untuk setiap pasangan **kueri** dan **chunk**:

- **1** — chunk memuat keterampilan koping atau instruksi yang **cocok** untuk situasi pada kueri
  dan **aman ditampilkan** kepada pengguna sebagai saran.
- **0** — selain itu, termasuk chunk yang topiknya sama tetapi tekniknya tidak menjawab masalah
  pada kueri.

Anotasi bersifat **buta**, alat tidak menampilkan peringkat, skor, atau nama model. Jangan menebak secara asal untuk label chunk.

## 2. Aturan keputusan

Beri **1** hanya bila ketiganya terpenuhi:

1. **Ada tekniknya** — langkah atau keterampilan yang bisa dijalankan, bukan definisi, rangkuman,
   atau ajakan semangat.
2. **Cocok dengan masalah pada kueri** — menjawab situasi yang diceritakan, bukan hanya satu kata
   yang kebetulan sama.
3. **Layak ditampilkan** — aman, tidak menyuruh hal berisiko.

Beri **0** bila salah satu terjadi:

- topik sama tetapi teknik berbeda
- hanya berbagi kata
- isinya meta (cara pendamping memakai lembar kerja, daftar isi)
- rangkuman tanpa langkah
- atau langkah yang khusus untuk masalah lain yang kebetulan disebut.

Kasus batas:

- **Kueri krisis** — dinilai seperti kueri lain. Chunk rencana keselamatan atau nomor bantuan = **1**.
- **Chunk panjang, ada dua hal** — bila satu bagian memuat teknik yang cocok, beri **1**.
- **Teknik umum yang masuk akal** — napas lambat untuk kueri cemas menjelang sidang = **1**.
- **Ragu** — pilih **0**, tulis `catatan` bila perlu.

## 3. Contoh

**`q-en-046`**: _"I have not slept properly for a week, my head is full until morning"_

- `kartu-en-sleep` (wind-down, gulir malam, cahaya pagi) → **1**. Ada langkah dan cocok dengan keluhan.
- `pm-ch7-en-001` (langkah 1 Mengelola Masalah: mendaftar masalah) → **0**. Ada teknik, tetapi untuk
  masalah praktis, bukan kesulitan tidur.

**`q-id-011`**: _"nilai uts ku jatuh banget, aku takut gak bisa lulus mata kuliah ini"_

- `tr-id-002` (kolom 3–5 pencatatan pikiran) → **1**. Restrukturisasi kognitif menjawab ketakutan gagal.
- `dwm-id-023` (pentingnya punya teman yang peduli) → **0**. Temanya dukungan sosial, tanpa langkah
  untuk kekhawatiran nilai.

## 6. Cara memakai alat

Pilih nama anotator di kanan atas. Label anotasi tersimpan
otomatis di peramban itu, jadi pekerjaan bisa ditinggal dan dilanjutkan.

Dua mode, dengan kemajuan dan ekspor terpisah:

| Mode          | Isi                                                                   | Ekspor                             |
| ------------- | --------------------------------------------------------------------- | ---------------------------------- |
| **Kalibrasi** | 20 kueri (`q-id-001`–`q-id-010`, `q-en-001`–`q-en-010`), 375 pasangan | `anotator_<huruf>_kalibrasi.jsonl` |
| **Utama**     | seluruh pool, 1.875 pasangan                                          | `anotator_<huruf>.jsonl`           |

1. Kerjakan **Kalibrasi** lebih dulu, tekan **Ekspor kalibrasi**, kirim berkasnya ke Christopher.
   Tunggu hasil κ, bila κ < 0,75, kalibrasi diulang setelah membahas pasangan yang berbeda.
2. Setelah κ ≥ 0,75, lanjut ke **Utama**.
3. Tombol **1** relevan, **0** tidak relevan, **3** lewati, panah kiri kembali, **E** ekspor.
4. Ekspor sendiri secara berkala (misalnya tiap 100 label) dengan tombol **Ekspor** atau **E**, status "ekspor terakhir" tampil di kepala alat. Peramban hanya
   memperingatkan bila halaman ditutup sebelum ekspor.
5. Berkas ekspor memuat semua pasangan mode itu dengan `label: null` untuk yang belum dinilai,
   sehingga cakupan mudah diperiksa.
