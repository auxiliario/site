#!/usr/bin/env python3
"""
Extract the Anuario's birth cuadros that carry PARENT PAIRINGS.

  1.2  mother nationality x father nationality  (pp.48-49, three blocks)
  1.3  mother's marital status / registration / month   (p.50)
  1.4  mother age band x father age band        (p.51)

Why these matter more than another Anuario edition: 1.2 and 1.4 are two
additional couplings, and they describe a DIFFERENT POPULATION from the
marriage cuadros. Cuadro 1.3 shows 85.6% of these mothers are 'soltera',
so parent pairings capture overwhelmingly non-marital unions -- the
couples a marriage registry never sees. Loading a second edition of the
Anuario would multiply rows; loading these multiplies pairings.

Column headers here wrap across two or three lines and cannot be parsed
reliably from the text layer, so they are DECLARED below and then
verified two ways: the number of declared columns must equal the number
of values on every row, and each row's printed Total must equal the sum
of that row's cells. The second check is the one that would have caught
the Peru/Puerto Rico transposition in Cuadro 3.5.
"""
import argparse, csv, hashlib, re

NUM = re.compile(r"^-?[\d,]+$")

# Cuadro 1.2 is printed in three blocks with different column sets.
C12_BLOCKS = [
    (48, ["TOTAL", "Republica Dominicana", "Estados Unidos", "Haiti",
          "Venezuela", "Espana", "Colombia"]),
    (48, ["Cuba", "Canada", "Mexico", "China", "Italia", "Peru", "Francia"]),
    (49, ["Argentina", "Holanda", "Otros paises", "No declarada"]),
]
C12_ROWS = ["Total en el pais", "Republica Dominicana", "Haiti", "Venezuela",
            "Colombia", "Estados Unidos", "Cuba", "Mexico", "Espana", "China",
            "Peru", "Argentina", "Ecuador", "Italia", "Rusia", "Canada",
            "Otros paises", "No declarada"]

C14_COLS = ["TOTAL", "0-14", "15-19", "20-24", "25-29", "30-34", "35-39",
            "40-44", "45-49", "50+", "No declarada"]
C14_ROWS = ["Total en el pais", "0-14", "15-19", "20-24", "25-29", "30-34",
            "35-39", "40-44", "45-49", "50+", "No declarada"]

FOLD = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")


def fold(s):
    return s.translate(FOLD).strip()


def numeric_lines(text, want):
    """Lines that are a run of exactly `want` numbers, in page order.

    Row labels on these pages wrap around the numbers ('Menos de 15' /
    numbers / 'anos'), so the labels are matched positionally against the
    declared row list rather than read off the line.
    """
    out = []
    for line in text.split("\n"):
        toks = line.strip().split()
        # Anchor on the LAST `want` tokens rather than counting numeric
        # tokens anywhere on the line: row labels can contain digits
        # ('50 anos y mas'), and counting them swallows the label into the
        # data and silently drops the row.
        if len(toks) < want:
            continue
        tail = toks[-want:]
        if not all(NUM.match(t) for t in tail):
            continue
        if len(toks) > want and NUM.match(toks[-want - 1]):
            continue                      # ambiguous: cannot tell label from data
        out.append([int(n.replace(",", "")) for n in tail])
    return out


def extract(pdf_path):
    import pdfplumber
    rows, warn = [], []
    with pdfplumber.open(pdf_path) as pdf:
        # ---- Cuadro 1.2, stitched across three blocks -------------------
        p48 = pdf.pages[47].extract_text() or ""
        p49 = pdf.pages[48].extract_text() or ""
        halves = p48.split("Continuación")
        blocks = [(halves[0], C12_BLOCKS[0][1]),
                  (halves[1] if len(halves) > 1 else "", C12_BLOCKS[1][1]),
                  (p49, C12_BLOCKS[2][1])]
        grid = {r: {} for r in C12_ROWS}
        for text, cols in blocks:
            got = numeric_lines(text, len(cols))
            if len(got) != len(C12_ROWS):
                warn.append(f"Cuadro 1.2 block {cols[0]!r}: {len(got)} rows, "
                            f"expected {len(C12_ROWS)}")
                continue
            for label, vals in zip(C12_ROWS, got):
                for c, v in zip(cols, vals):
                    grid[label][c] = v
        for label, cells in grid.items():
            for col, v in cells.items():
                rows.append(("1.2", "birth", "mother_nationality", label,
                             "father_nationality", col, v))

        # ---- Cuadro 1.4 -------------------------------------------------
        p51 = pdf.pages[50].extract_text() or ""
        c14 = p51.split("Cuadro 1.5")[0]
        got = numeric_lines(c14, len(C14_COLS))
        if len(got) != len(C14_ROWS):
            warn.append(f"Cuadro 1.4: {len(got)} rows, "
                        f"expected {len(C14_ROWS)}")
        for label, vals in zip(C14_ROWS, got):
            for c, v in zip(C14_COLS, vals):
                rows.append(("1.4", "birth", "mother_age_band", label,
                             "father_age_band", c, v))

        # ---- Cuadro 1.3, a one-way list with section headings -----------
        p50 = pdf.pages[49].extract_text() or ""
        section = None
        for line in p50.split("\n"):
            line = line.strip()
            m = re.match(r"^(.+?)\s+([\d,]+)$", line)
            if re.match(r"^(Estado civil|Tipo de registro|Mes de ocurrencia)",
                        line):
                section = fold(re.match(r"^([^\d]+?)\s+[\d,]", line).group(1)
                               if m else line).lower()
            if not m:
                continue
            label, val = m.group(1).strip(), int(m.group(2).replace(",", ""))
            if label.startswith(("Cuadro", "Fuente", "Nota")):
                continue
            rows.append(("1.3", "birth", "mother_characteristic",
                         section or "total", "", fold(label), val))
    return rows, warn


def verify(rows):
    """Every row's printed TOTAL must equal the sum of that row's cells."""
    bad = []
    for cuadro, dim_a in (("1.2", "mother_nationality"),
                          ("1.4", "mother_age_band")):
        by_row = {}
        for c, _, _, ra, _, cb, v in rows:
            if c == cuadro:
                by_row.setdefault(ra, {})[cb] = v
        for label, cells in by_row.items():
            total = cells.get("TOTAL")
            summed = sum(v for k, v in cells.items() if k != "TOTAL")
            if total is None:
                bad.append(f"Cuadro {cuadro} {label!r}: no TOTAL column")
            elif total != summed:
                bad.append(f"Cuadro {cuadro} {label!r}: printed total {total}, "
                           f"cells sum to {summed} (delta {total - summed:+})")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    print("sha256", hashlib.sha256(open(a.pdf, "rb").read()).hexdigest())
    rows, warn = extract(a.pdf)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cuadro", "vital_event", "dim1_name", "dim1_value",
                    "dim2_name", "dim2_value", "value"])
        w.writerows(rows)
    from collections import Counter
    c = Counter(r[0] for r in rows)
    print(f"{len(rows)} rows -> {a.out}")
    for k in sorted(c):
        print(f"  Cuadro {k}: {c[k]} rows")
    for w_ in warn:
        print("  WARN", w_)
    bad = verify(rows)
    print(f"  row-total verification: {len(bad)} failure(s)")
    for b in bad[:10]:
        print("    ", b)


if __name__ == "__main__":
    main()
