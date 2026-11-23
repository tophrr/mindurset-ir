#!/usr/bin/env python3
"""Render persamaan dan diagram dari naskah LaTeX menjadi PNG untuk versi .docx.

Keluaran: build/docx-img/eq-1.png ... eq-8.png dan build/docx-img/fig-1.png
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "Paper_Alpha_KK_Kelompok5.tex"
OUT = ROOT / "build" / "docx-img"
WORK = OUT / "src"

PREAMBLE = r"""\documentclass[12pt]{article}
\usepackage{fontspec}
\setmainfont{Times New Roman}[Ligatures=TeX]
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{xcolor}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,positioning}
\usepackage[active,tightpage]{preview}
\setlength{\PreviewBorder}{3pt}
\pagestyle{empty}
\definecolor{KepalaTabel}{HTML}{E7EBEF}
\begin{document}
"""


def ambil_persamaan(tex: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"\\begin\{equation\}(.*?)\\end\{equation\}", tex, re.S)]


def ambil_gambar(tex: str) -> str:
    i = tex.index("\\begin{tikzpicture}")
    j = tex.index("\\end{tikzpicture}") + len("\\end{tikzpicture}")
    return tex[i:j]


def kompilasi(sumber: Path, keluar: Path) -> None:
    subprocess.run(
        ["tectonic", "-X", "compile", str(sumber), "--outdir", str(keluar)],
        check=True, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin:/home/chrisg/.local/bin",
             "TECTONIC_CACHE_DIR": "/home/chrisg/.hermes/cache/scratch/tectonic",
             "HOME": "/home/chrisg"})


def ke_png(pdf: Path, awalan: str, dpi: int = 400) -> list[Path]:
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(pdf.with_suffix(""))], check=True)
    return sorted(pdf.parent.glob(f"{pdf.stem}-*.png"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    tex = TEX.read_text(encoding="utf-8")

    # ---- persamaan ----
    eqs = ambil_persamaan(tex)
    isi = []
    for e in eqs:
        e = e.replace("\\footnotesize", "").strip()
        isi.append("\\begin{preview}$\\displaystyle " + e + "$\\end{preview}\n")
    (WORK / "eq.tex").write_text(PREAMBLE + "\n".join(isi) + "\n\\end{document}\n", encoding="utf-8")
    kompilasi(WORK / "eq.tex", WORK)
    for n, png in enumerate(ke_png(WORK / "eq.pdf", "eq"), start=1):
        target = OUT / f"eq-{n}.png"
        png.replace(target)
    print("persamaan:", len(eqs))

    # ---- gambar ----
    fig = ambil_gambar(tex)
    (WORK / "fig.tex").write_text(
        PREAMBLE + "\\begin{preview}" + fig + "\\end{preview}\n\\end{document}\n", encoding="utf-8")
    kompilasi(WORK / "fig.tex", WORK)
    for png in ke_png(WORK / "fig.pdf", "fig"):
        (OUT / "fig-1.png").unlink(missing_ok=True)
        png.replace(OUT / "fig-1.png")
    print("gambar: 1")


if __name__ == "__main__":
    main()
