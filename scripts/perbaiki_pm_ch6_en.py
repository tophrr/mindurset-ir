#!/usr/bin/env python3
"""Ganti dua chunk Inggris Bab 6 PM+ yang rusak karena tabel dua kolom.

Pada halaman 47–48 `pdftotext` menyisipkan dua lajur tabel sehingga kalimat saling
bertukar tempat. Isi chunk Indonesia (hasil terjemahan tim) sudah tersusun benar, jadi
versi Inggris ditulis ulang agar sejajar dengan versi Indonesia dan tetap setia pada
kalimat aslinya.

Pemakaian:
    python3 eksperimen/perbaiki_pm_ch6_en.py
"""

from __future__ import annotations

import json
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
TOK = Tokenizer.from_file(str(ROOT / "ref" / "tok" / "tokenizer.json"))

BARU = {
    "pm-ch6-en-004": (
        "Once they have mastered how to slow their breathing down, they can try to use the counting or "
        "breathe from their stomach. The client cannot slow their breathing down when they are at the peak "
        "of their anxiety or stress. Say to the client that this would be very hard for anyone to do "
        "straight away, even a helper. Spend some time helping the client to identify early signs that they "
        "are beginning to feel anxious or stressed so they can start slow breathing earlier. If this is too "
        "difficult, help them to schedule specific times throughout the day to practise slow breathing so "
        "they learn how to use it before they get too anxious. Focusing on breathing makes the client speed "
        "up their breathing and feel more anxious. They might also experience feelings of light-headedness "
        "or dizziness, or feel they are losing control. Help them to focus on a ticking clock and breathe to "
        "the count of the clock rather than focus only on the breathing, or on a musical beat in a song. "
        "Remind them that these sensations are safe and they are not losing control. Encourage them to focus "
        "just on blowing all the air out, that is just the breathing out, and letting the in-breath come "
        "naturally. Then they can return to focusing on the whole process of breathing, in and out. Why "
        "Managing Stress is an important strategy. In this chapter you learned who will benefit from this "
        "strategy, how to give information about slow breathing to your clients, and how to teach Managing "
        "Stress to your clients."
    ),
    "pm-ch6-en-005": (
        "Learn session worksheets. What will you learn in this chapter, what session does this chapter link "
        "to, and what worksheets link to this chapter? This chapter covers the types of problem the strategy "
        "is used for, which are sessions 2 to 4, with the Managing Problems handout in Appendix E as the "
        "worksheet. It also covers the steps of Managing Problems with a case example, allowing 70 minutes of "
        "Session 2 to introduce the strategy, and the activities calendar in Appendix E. In addition, the "
        "chapter covers working with difficulties, such as clients who suggest unhelpful solutions or clients "
        "who feel hopeless, and avoiding giving advice, allowing between 20 and 35 minutes for review in "
        "following sessions, see the flowchart for specific times. Adversity can reduce a person's ability "
        "to respond well to practical problems. They may feel helpless or lack confidence in managing their "
        "problems, or possibly their feelings of anxiety or grief will get in the way of managing practical "
        "problems effectively. Managing Problems is a structured strategy that aims to improve clients' "
        "ability to solve and manage practical problems. You will spend about 70 minutes of Session 2 teaching "
        "this strategy to your client while applying it to their chosen problem, that is usually the one "
        "causing them the most distress. Steps to Managing Problems. Managing Problems follows several steps, "
        "explained in detail below. Explain each step in detail to clients while working through an identified "
        "problem in the session. Showing clients the Managing Problems handout can aid this discussion. "
        "Chapter 7 Managing Problems."
    ),
}


def main() -> int:
    path = ROOT / "data" / "src" / "pm_ch6_en.jsonl"
    baris = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for d in baris:
        if d["id"] in BARU:
            lama = len(TOK.encode(d["teks"], add_special_tokens=False).ids)
            d["teks"] = BARU[d["id"]]
            d["token"] = len(TOK.encode(d["teks"], add_special_tokens=False).ids)
            d["kata"] = len(d["teks"].split())
            print(f"  {d['id']}: {lama} → {d['token']} token")
    path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in baris) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
