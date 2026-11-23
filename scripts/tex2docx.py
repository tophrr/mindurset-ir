#!/usr/bin/env python3
"""Konversi naskah LaTeX (IEEE dua kolom) menjadi .docx dengan python-docx.

Menangani: judul+penulis, section/subsection, paragraf dengan \\emph/\\textbf/
\\texttt/\\cite, daftar bernomor RQ, persamaan (PNG hasil render), tabel
(table dan table*), gambar (figure*), serta daftar pustaka.

Badan ditulis dua kolom seperti naskah; tabel/gambar selebar halaman dibuat
dengan section break kontinu supaya tetap penuh.

Pemakaian:
    uv run --quiet --with python-docx --with pillow python eksperimen/tex2docx.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "Paper_Alpha_KK_Kelompok5.tex"
IMG = ROOT / "build" / "docx-img"
OUT = ROOT / "Paper_Alpha_KK_Kelompok5.docx"

FONT = "Times New Roman"
BODY_PT = 12
LINE = 1.12
COL_CM = 8.5            # lebar satu kolom badan (16 mm margin, gutter 18 pt)
FULL_CM = 17.8          # lebar teks penuh

ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]

MATH_MAP = [
    (r"\\mathrm\{([^{}]*)\}", r"\1"),
    (r"\\kappa", "κ"), (r"\\geq", "≥"), (r"\\leq", "≤"), (r"\\times", "×"),
    (r"\\pm", "±"), (r"\\cdot", "·"), (r"\\mid", "|"), (r"\\in", "∈"),
    (r"\\alpha", "α"), (r"\\beta", "β"), (r"\\left", ""), (r"\\right", ""),
    (r"\\,", " "), (r"\\;", " "), (r"\{,\}", ","),
    (r"\\text\{([^{}]*)\}", r"\1"),
]


def math_teks(m: str) -> str:
    for pola, ganti in MATH_MAP:
        m = re.sub(pola, ganti, m)
    return m


def teks_biasa(s: str) -> str:
    s = s.replace("\\,", " ").replace("\\;", " ")
    s = s.replace("---", "—").replace("--", "–")
    s = s.replace("``", "“").replace("''", "”")
    s = s.replace("\\%", "%").replace("\\&", "&").replace("\\_", "_").replace("\\#", "#")
    s = s.replace("\\{", "{").replace("\\}", "}")
    s = s.replace("\\belum{}", "[--]").replace("\\belum", "[--]")
    s = s.replace("\\allowbreak", "").replace("~", " ")
    s = re.sub(r"\\url\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\$([^$]*)\$", lambda m: math_teks(m.group(1)), s)
    s = s.replace("\\justifying", "").replace("\\raggedright", "").replace("\\noindent", "")
    return re.sub(r"[ \t]+", " ", s)


def tambah_runs(par, teks: str, sitasi: dict[str, int], *, italic=False, bold=False,
                mono=False, size=None):
    pola = re.compile(r"\\(emph|textbf|texttt|cite)\{")
    pos = 0
    while True:
        m = pola.search(teks, pos)
        if not m:
            sisa = teks_biasa(teks[pos:])
            if sisa:
                r = par.add_run(sisa)
                r.italic, r.bold = italic, bold
                r.font.name = "Consolas" if mono else FONT
                if size:
                    r.font.size = size
            return
        awal = teks_biasa(teks[pos:m.start()])
        if awal:
            r = par.add_run(awal)
            r.italic, r.bold = italic, bold
            r.font.name = "Consolas" if mono else FONT
            if size:
                r.font.size = size
        i = m.end()
        depth = 1
        while i < len(teks) and depth:
            if teks[i] == "{":
                depth += 1
            elif teks[i] == "}":
                depth -= 1
            i += 1
        isi = teks[m.end():i - 1]
        jenis = m.group(1)
        if jenis == "cite":
            nomor = "[" + ", ".join(str(sitasi[k.strip()]) for k in isi.split(",")
                                    if k.strip() in sitasi) + "]"
            r = par.add_run(nomor)
            r.font.name = FONT
            if size:
                r.font.size = size
        else:
            tambah_runs(par, isi, sitasi, italic=italic or jenis == "emph",
                        bold=bold or jenis == "textbf", mono=mono or jenis == "texttt",
                        size=size)
        pos = i


def ambil_kurung(teks: str, mulai: int) -> tuple[str, int]:
    depth, i = 0, mulai
    while i < len(teks):
        if teks[i] == "{":
            depth += 1
        elif teks[i] == "}":
            depth -= 1
            if depth == 0:
                return teks[mulai + 1:i], i + 1
        i += 1
    return teks[mulai + 1:], len(teks)


def set_kolom(section, n: int):
    cols = section._sectPr.xpath("./w:cols")
    el = cols[0] if cols else OxmlElement("w:cols")
    if not cols:
        section._sectPr.append(el)
    el.set(qn("w:num"), str(n))
    el.set(qn("w:space"), "340" if n == 2 else "0")


def ganti_kolom(doc: Document, n: int):
    s = doc.add_section(WD_SECTION.CONTINUOUS)
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.top_margin, s.bottom_margin = Cm(1.9), Cm(2.1)
    s.left_margin, s.right_margin = Cm(1.6), Cm(1.6)
    set_kolom(s, n)
    return s


def siapkan_dokumen() -> Document:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(BODY_PT)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    pf = st.paragraph_format
    pf.line_spacing = LINE
    pf.space_after = Pt(4)
    pf.space_before = Pt(0)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.top_margin, s.bottom_margin = Cm(1.9), Cm(2.1)
    s.left_margin, s.right_margin = Cm(1.6), Cm(1.6)
    set_kolom(s, 1)

    for nama, tebal, miring in [("Heading 1", True, False), ("Heading 2", False, True)]:
        h = doc.styles[nama]
        h.font.name = FONT
        h.font.size = Pt(BODY_PT)
        h.font.bold = tebal
        h.font.italic = miring
        h.font.color.rgb = RGBColor(0, 0, 0)
        h.paragraph_format.alignment = (WD_ALIGN_PARAGRAPH.CENTER if nama == "Heading 1"
                                        else WD_ALIGN_PARAGRAPH.LEFT)
        h.paragraph_format.space_before = Pt(8 if nama == "Heading 1" else 5)
        h.paragraph_format.space_after = Pt(3)
        h.paragraph_format.keep_with_next = True
    return doc


def blok_judul(doc: Document, preamble: str):
    def nilai(nama):
        m = re.search(r"\\newcommand\{\\" + nama + r"\}\{(.*?)\}\s*\n", preamble, re.S)
        return m.group(1).strip() if m else ""

    judul = re.sub(r"\\emph\{([^{}]*)\}", r"\1", nilai("BarisJudul"))
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(judul)
    r.bold = True
    r.font.size = Pt(17)

    for b in [nilai("BarisAnggotaA"), nilai("BarisAnggotaB"), nilai("BarisProdi"),
              nilai("BarisInstitusi"), nilai("BarisKontak"), nilai("BarisMataKuliah")]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(teks_biasa(b.replace("$\\bullet$", "•")))
        r.font.size = Pt(10.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def set_shading(cell, heks: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), heks)
    tcPr.append(shd)


def set_border(table):
    borders = OxmlElement("w:tblBorders")
    for sisi in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{sisi}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "BFBFBF")
        borders.append(el)
    table._tbl.tblPr.append(borders)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    table._tbl.tblPr.append(layout)


def tabel(doc: Document, blok: str, sitasi, nomor: int):
    mcap = re.search(r"\\caption\{", blok)
    caption = ambil_kurung(blok, mcap.end() - 1)[0] if mcap else ""
    m = re.search(r"\\begin\{tabular\}\{([^\n]*)\}\n(.*?)\\end\{tabular\}", blok, re.S)
    if not m:
        return
    spec, isi = m.group(1), m.group(2)
    lebar = [float(x.replace(",", ".")) for x in re.findall(r"p\{([\d.,]+)cm\}", spec)]
    total = sum(lebar)
    if total < 13.0:                      # tabel kolom dilebarkan agar tampil penuh
        faktor = (FULL_CM - 1.2) / total
        lebar = [round(w * faktor, 2) for w in lebar]

    potong = re.sub(r"\\hline|\\rowcolor\{[^}]*\}", "", isi)
    baris = []
    for b in potong.split("\\\\"):
        b = b.strip()
        if not b:
            continue
        b = re.sub(r"\\multicolumn\{(\d+)\}\{[^}]*\}\{([^{}]*)\}", lambda mm: mm.group(2), b)
        sel = [s.strip() for s in b.split("&")]
        if len(sel) != len(lebar) or (baris and sel == baris[-1]):
            continue
        baris.append(sel)

    if caption:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(f"Tabel {ROMAN[nomor]}. ")
        r.bold = True
        r.font.size = Pt(9)
        tambah_runs(p, caption.strip(), sitasi, size=Pt(9))

    table = doc.add_table(rows=len(baris), cols=len(lebar))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_border(table)
    for i, b in enumerate(baris):
        for j, isi_sel in enumerate(b):
            cell = table.cell(i, j)
            cell.width = Cm(lebar[j])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            par = cell.paragraphs[0]
            par.paragraph_format.space_after = Pt(0)
            par.paragraph_format.space_before = Pt(0)
            par.paragraph_format.line_spacing = 1.0
            tambah_runs(par, isi_sel, sitasi, bold=(i == 0), size=Pt(8))
            if i == 0:
                set_shading(cell, "E7EBEF")
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for row in table.rows:
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def gambar(doc: Document, caption: str, sitasi, lebar_cm: float):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(IMG / "fig-1.png"), width=Cm(lebar_cm))
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_after = Pt(6)
    r = p2.add_run("Gambar 1. ")
    r.bold = True
    r.font.size = Pt(9)
    tambah_runs(p2, caption.strip(), sitasi, size=Pt(9))


def persamaan(doc: Document, path: Path, nomor: int):
    from PIL import Image
    px_w, px_h = Image.open(path).size
    lebar_cm = px_w / 400 * 2.54
    tinggi_cm = px_h / 400 * 2.54
    if lebar_cm > COL_CM - 0.5:
        skala = (COL_CM - 0.5) / lebar_cm
        lebar_cm, tinggi_cm = COL_CM - 0.5, tinggi_cm * skala
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(COL_CM - 0.2), WD_TAB_ALIGNMENT.RIGHT)
    p.add_run().add_picture(str(path), width=Cm(lebar_cm), height=Cm(tinggi_cm))
    p.add_run("\t(" + str(nomor) + ")")


def main() -> int:
    tex = TEX.read_text(encoding="utf-8")
    preamble = tex[:tex.index("\\begin{document}")]
    body = tex[tex.index("\\begin{document}") + len("\\begin{document}"):tex.index("\\end{document}")]
    body = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("%"))

    sitasi: dict[str, int] = {}
    for m in re.finditer(r"\\cite\{([^}]*)\}", body):
        for k in m.group(1).split(","):
            k = k.strip()
            if k and k not in sitasi:
                sitasi[k] = len(sitasi) + 1

    def baris_tata_letak(l: str) -> bool:
        s = l.strip()
        if "\\begin{" in s or "\\end{" in s:
            return False
        return bool(re.fullmatch(
            r"\\(?:vspace|setlength|raggedright|justifying|noindent|centering|small|scriptsize"
            r"|normalsize|Needspace)(?:\{[^{}]*\})*\s*", s))

    body = "\n".join(l for l in body.splitlines() if not baris_tata_letak(l))
    body = "\n".join(l for l in body.splitlines()
                     if not re.search(r"\\(?:setlength|arrayrulecolor|Needspace)"
                                      r"|renewcommand\{\\arraystretch\}", l))
    for pola in (r"\\vspace\{[^{}]*\}",
                 r"\\(?:raggedright|justifying|noindent|scriptsize|small|normalsize)\b"):
        body = re.sub(pola, "", body)

    simpanan: dict[str, tuple[str, str]] = {}
    urutan = 0

    def tarik(pola, jenis, teks):
        nonlocal urutan

        def ganti(m):
            nonlocal urutan
            kunci = f"@@{jenis}{urutan}@@"
            simpanan[kunci] = (jenis, m.group(0))
            urutan += 1
            return "\n\n" + kunci + "\n\n"
        return re.sub(pola, ganti, teks, flags=re.S)

    body = tarik(r"\\begin\{equation\}.*?\\end\{equation\}", "EQ", body)
    body = tarik(r"\\begin\{table\*?\}\[[^\]]*\].*?\\end\{table\*?\}", "TAB", body)
    body = tarik(r"\\begin\{figure\*?\}\[[^\]]*\].*?\\end\{figure\*?\}", "FIG", body)
    body = tarik(r"\\begin\{enumerate\}.*?\\end\{enumerate\}", "LIST", body)
    body = tarik(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", "BIB", body)
    body = body.replace("\\twocolumn[\\BlokJudul]", "@@TITLE@@")
    body = re.sub(r"(?m)^(\\\\(?:sub)?section\*?\{[^\n]*\})\s*$", r"\n\n\1\n\n", body)
    body = re.sub(r"(?m)^(@@\w+@@)\s*$", r"\n\n\1\n\n", body)

    doc = siapkan_dokumen()
    blok_judul(doc, preamble)
    ganti_kolom(doc, 2)

    bagian = sub = n_eq = n_tab = 0
    for blok in [b.strip() for b in re.split(r"\n\s*\n", body)]:
        if not blok or blok == "@@TITLE@@":
            continue
        m = re.fullmatch(r"@@(\w+?)(\d+)@@", blok)
        if m:
            jenis, isi = simpanan[blok]
            if jenis == "EQ":
                n_eq += 1
                persamaan(doc, IMG / f"eq-{n_eq}.png", n_eq)
            elif jenis == "FIG":
                cap = ambil_kurung(isi, re.search(r"\\caption\{", isi).end() - 1)[0]
                ganti_kolom(doc, 1)
                gambar(doc, cap, sitasi, FULL_CM - 1.4)
                ganti_kolom(doc, 2)
            elif jenis == "TAB":
                n_tab += 1
                ganti_kolom(doc, 1)
                tabel(doc, isi, sitasi, n_tab)
                ganti_kolom(doc, 2)
            elif jenis == "LIST":
                for label, teks in re.findall(
                        r"\\item\[([^\]]*)\]\s*(.*?)(?=\\item\[|\\end\{enumerate\})", isi, re.S):
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                    p.paragraph_format.left_indent = Cm(0.9)
                    p.paragraph_format.first_line_indent = Cm(-0.9)
                    p.paragraph_format.space_after = Pt(3)
                    tambah_runs(p, label + " ", sitasi, bold=True)
                    tambah_runs(p, " " + " ".join(teks.split()), sitasi)
            elif jenis == "BIB":
                doc.add_heading("References", level=1)
                isi = isi.replace("\\end{thebibliography}", "")
                for key, isi_bib in re.findall(
                        r"\\bibitem\{([^}]*)\}\s*(.*?)(?=\\bibitem|$)", isi, re.S):
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    p.paragraph_format.left_indent = Cm(0.7)
                    p.paragraph_format.first_line_indent = Cm(-0.7)
                    p.paragraph_format.space_after = Pt(2)
                    p.paragraph_format.line_spacing = 1.0
                    r = p.add_run(f"[{sitasi.get(key.strip(), 0)}] ")
                    r.font.size = Pt(9.5)
                    tambah_runs(p, " ".join(isi_bib.split()), sitasi, size=Pt(9.5))
            continue

        while blok:
            h = re.match(r"\\section(\*?)\{([^{}]*)\}", blok)
            if h:
                bagian += 1
                sub = 0
                teks = (f"{ROMAN[bagian]} " if not h.group(1) else "") + h.group(2)
                doc.add_heading(teks, level=1)
                blok = blok[h.end():].strip()
                continue
            h = re.match(r"\\subsection\{([^{}]*)\}", blok)
            if h:
                sub += 1
                doc.add_heading(f"{chr(64 + sub)} {h.group(1)}", level=2)
                blok = blok[h.end():].strip()
                continue
            break
        if not blok:
            continue

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        tambah_runs(p, " ".join(blok.split()), sitasi)

    doc.save(OUT)
    print("tersimpan:", OUT, "| sitasi:", len(sitasi), "| persamaan:", n_eq, "| tabel:", n_tab)
    return 0


if __name__ == "__main__":
    sys.exit(main())
