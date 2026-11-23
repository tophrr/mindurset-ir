#!/usr/bin/env python3
"""Rapikan ekor bab PM+ yang tercampur kotak ringkasan atau lembar kerja bab berikutnya.

Ekstraksi pdftotext menyeret kotak "In this chapter you learned" (dan kadang awal bab
berikutnya) ke ujung chunk terakhir sebuah bab. Skrip ini memotong ekor itu dan
menggantinya dengan satu kalimat ringkas yang setia pada isi kotak aslinya.

Pemakaian:
    python3 eksperimen/rapikan_batas_bab.py [--uji]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "src"
TOK = Tokenizer.from_file(str(ROOT / "ref" / "tok" / "tokenizer.json"))

# (berkas, akhiran id, penanda awal ekor, kalimat pengganti)
PERBAIKAN = [
    ("pm_ch8_en", "008", "• What types of problems",
     "This chapter covered the types of problems that Get Going, Keep Doing helps with, "
     "how to introduce the strategy to clients, and how to break bigger activities down with clients."),
    ("pm_ch9_en", "005", "What Strengthening Social Support means",
     "This chapter covered what Strengthening Social Support means, how to introduce the strategy, "
     "and how to encourage clients to strengthen their social support networks."),
    ("pm_ch9_id", "005", "Apa yang Anda pelajari tentang makna",
     "Bab ini membahas makna Memperkuat Dukungan Sosial, cara memperkenalkan strategi ini, "
     "dan cara mendorong klien memperkuat jaringan dukungan sosialnya."),
    ("pm_ch10_en", "004", "• What emotional recovery will look like",
     "This chapter covered what emotional recovery will look like for most clients, how clients can "
     "stay well and prevent a full return of emotional problems, and how to complete the "
     "post-intervention assessment."),
]


def main() -> int:
    uji = "--uji" in sys.argv
    for berkas, akhiran, penanda, pengganti in PERBAIKAN:
        path = SRC / f"{berkas}.jsonl"
        baris = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        berubah = False
        for d in baris:
            if not d["id"].endswith(akhiran):
                continue
            pos = d["teks"].find(penanda)
            if pos < 0:
                print(f"  {d['id']}: penanda tidak ditemukan, dilewati")
                continue
            baru = d["teks"][:pos].rstrip() + " " + pengganti
            n_lama = len(TOK.encode(d["teks"], add_special_tokens=False).ids)
            n_baru = len(TOK.encode(baru, add_special_tokens=False).ids)
            print(f"  {d['id']}: {n_lama} → {n_baru} token")
            d["teks"] = baru
            d["token"] = n_baru
            d["kata"] = len(baru.split())
            berubah = True
        if berubah and not uji:
            path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in baris) + "\n",
                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
