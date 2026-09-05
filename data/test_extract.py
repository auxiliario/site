#!/usr/bin/env python3
"""
Round-trip test for extract_crosstab.py.

The real Anuario PDF is not in this repository (ONE's host is blocked by
this environment's egress policy), so the extractor is validated against a
synthetic PDF laid out like a wide ONE cuadro: a text stub column, 17
right-aligned numeric columns with thousands separators, and a Total
column. Two cases:

  1. faithful render      -> extractor must recover every cell exactly
  2. one cell rendered blank -> extractor must report a HOLE in that
     column, not shift the rest of the row left

Case 2 is the property that matters. Shifting-left is precisely the
corruption suspected in Cuadro 3.5, and an extractor that pads silently
would reproduce it instead of catching it.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "sources"))
import anuario_2025 as A                                        # noqa: E402
import extract_crosstab as X                                    # noqa: E402

from reportlab.lib.pagesizes import landscape, A3               # noqa: E402
from reportlab.pdfgen import canvas                             # noqa: E402

OUT = os.environ.get("TMPDIR", "/tmp")


def render(path, blank=None):
    """blank = (row_label, col_index) rendered as empty space."""
    c = canvas.Canvas(path, pagesize=landscape(A3))
    W, H = landscape(A3)
    c.setFont("Helvetica", 9)
    c.drawString(40, H - 40, "Cuadro 3.5")
    c.drawString(40, H - 55, "Matrimonios registrados por pais de nacionalidad "
                             "del contrayente, segun pais de la contrayente, 2025")
    x0, colw, y = 40, 62, H - 90
    for j, col in enumerate(A.C35_COLS):
        c.saveState(); c.translate(x0 + 150 + j * colw + 30, y); c.rotate(90)
        c.setFont("Helvetica", 6); c.drawString(0, 0, col[:14]); c.restoreState()
    c.setFont("Helvetica", 8)
    y -= 60
    for label in A.C35:
        c.drawString(x0, y, label)
        for j, v in enumerate(A.C35[label]):
            if blank and label == blank[0] and j == blank[1]:
                continue
            s = f"{v:,}"
            c.drawRightString(x0 + 150 + j * colw + 55, y, s)
        c.drawRightString(x0 + 150 + len(A.C35_COLS) * colw + 55, y,
                          f"{A.C35_ROW_TOTALS[label]:,}")
        y -= 16
    c.save()


def run(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        pages = X.find_pages(pdf, "Cuadro 3.5")
        assert pages == [1], f"caption search returned {pages}"
        rows, centres, tol, warns = X.extract_grid(pdf.pages[0], len(A.C35_COLS) + 1)
    return rows, centres, tol, warns


fails = 0
print("== case 1: faithful render ==")
p1 = os.path.join(OUT, "c35_ok.pdf"); render(p1)
rows, centres, tol, warns = run(p1)
print(f"  column positions recovered: {len(centres)} "
      f"(expected {len(A.C35_COLS)+1})")
diffs, missing = X.diff_grid(list(A.C35), A.C35_COLS, A.C35, rows)
print(f"  rows located: {len(A.C35)-len(missing)}/{len(A.C35)}   "
      f"cell diffs: {len(diffs)}   warnings: {len(warns)}")
if diffs or missing or len(centres) != len(A.C35_COLS) + 1:
    fails += 1
    print("  FAIL", diffs[:5], missing)
    for w in warns[:5]: print("   ", w)
else:
    print("  ok  every one of the 17x17 cells round-tripped exactly")

print("\n== case 2: Peru row, Peru column rendered blank ==")
p2 = os.path.join(OUT, "c35_hole.pdf")
render(p2, blank=("Peru", 13))
rows2, centres2, tol2, warns2 = run(p2)
peru = [c for stub, c in rows2 if stub.startswith("Peru")][0]
print(f"  Peru row as recovered: {peru}")
hole_ok = peru[13] is None and peru[14] == 15
print(f"  hole left at column 13, value 15 still under column 14: {hole_ok}")
d2, _ = X.diff_grid(["Peru"], A.C35_COLS, {"Peru": A.C35["Peru"]}, rows2)
print(f"  diff reported against the transcription: {len(d2)} cell(s)")
if not hole_ok:
    fails += 1
    print("  FAIL the extractor shifted the row instead of leaving a hole")
else:
    print("  ok  a missing cell does NOT shift its neighbours left")

print(f"\n{'PASS' if not fails else 'FAIL'} -- {fails} failure(s)")
sys.exit(1 if fails else 0)
