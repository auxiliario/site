#!/usr/bin/env python3
"""
Extract the Anuario cuadros printed on ROTATED pages.

Ten of the 2025 Anuario's cuadros are laid out landscape, and the PDF
stores them in a way no ordinary text extraction reaches: the page
carries /Rotate 0, the table content is drawn rotated 90 degrees, and
every word's characters are stored in REVERSE order. `extract_text()`
returns mirrored nonsense ('ortsiger' for 'registro', '033' for '330'),
so these pages looked empty to every extractor in this repository and
their cuadros were silently absent from the database.

De-rotation: group words into visual lines by x-position, order each
line by descending `top`, and reverse each word's characters.

Extracted here (the couple-relevant ones):
  1.10  mother's marital status x mother age band   -- union status BY AGE
  3.6   marriages by month x region/province
  3.7   marriages by BRIDE AGE BAND x region/province
  4.6   divorces by month x region/province

3.7 is the one that matters most: combined with the provincial
population by sex and age already loaded, it yields provincial
AGE-SPECIFIC marriage rates, which no other table here supports.
"""
import argparse, csv, hashlib, re
from collections import defaultdict

NUM = re.compile(r"^-?[\d,]+$")

SPEC = {
    "1.10": dict(pages=[57], event="birth", row_dim="mother_age_band",
                 col_dim="marital_status",
                 cols=["TOTAL", "Soltera", "Casada", "No declarado"],
                 rows_are_geo=False),
    "3.6":  dict(pages=[87, 88], event="marriage", row_dim=None,
                 col_dim="month", rows_are_geo=True,
                 cols=["TOTAL", "Enero", "Febrero", "Marzo", "Abril", "Mayo",
                       "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
                       "Noviembre", "Diciembre"]),
    "3.7":  dict(pages=[89, 90], event="marriage", row_dim=None,
                 col_dim="bride_age_band", rows_are_geo=True,
                 cols=["TOTAL", "0-14", "15-19", "20-24", "25-29", "30-34",
                       "35-39", "40-44", "45-49", "50+", "No declarada"]),
    "4.6":  dict(pages=[98, 99], event="divorce", row_dim=None,
                 col_dim="month", rows_are_geo=True,
                 cols=["TOTAL", "Enero", "Febrero", "Marzo", "Abril", "Mayo",
                       "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
                       "Noviembre", "Diciembre"]),
}


def derotate(page, band=3.0):
    # The running header and folio are UPRIGHT normal text on these pages;
    # only the table is rotated. Reversing an upright word corrupts it, and
    # leaving one in a line breaks the trailing-numbers test, which was
    # dropping whole provinces (Valverde, Baoruco, Independencia). The
    # `upright` flag separates the two cleanly: on p89, 389 rotated words
    # against 11 upright ones.
    words = [w for w in page.extract_words(use_text_flow=False)
             if not w["upright"]]
    lines = defaultdict(list)
    for w in words:
        lines[round(w["x0"] / band)].append(w)
    return [" ".join(w["text"][::-1]
                     for w in sorted(lines[k], key=lambda w: -w["top"]))
            for k in sorted(lines, reverse=True)]


def parse_rows(lines, ncols):
    """Label + exactly `ncols` trailing numbers, never padded.

    A long row label ('Region Cibao Noroeste', 'Maria Trinidad Sanchez')
    wraps AROUND its own numbers once the page is de-rotated: the tail of
    the label lands on the line above the numbers and the head on the
    line below. A numeric-only line is therefore reassembled as
    following-line + preceding-line, which is what the vertical reading
    order of a rotated page produces. Without this, six of the 43
    geographies were dropped -- silently, and they were the ones with the
    longest names.
    """
    toks_of = [ln.strip().split() for ln in lines]

    def is_label(t):
        return t and not all(NUM.match(x) for x in t) \
            and not t[0].lower().startswith(("fuente", "cuadro"))

    out = []
    for i, toks in enumerate(toks_of):
        if len(toks) < ncols:
            continue
        tail = toks[-ncols:]
        if not all(NUM.match(t) for t in tail):
            continue

        if len(toks) == ncols:                       # numbers only: wrapped
            before = toks_of[i - 1] if i else []
            after = toks_of[i + 1] if i + 1 < len(toks_of) else []
            parts = [" ".join(p) for p in (after, before) if is_label(p)]
            label = " ".join(parts).strip()
        else:
            if NUM.match(toks[-ncols - 1]):
                continue
            label = " ".join(toks[:-ncols]).strip()

        if not label or label.lower().startswith(("fuente", "cuadro")):
            continue
        out.append((label, [int(t.replace(",", "")) for t in tail]))
    return out


def extract(pdf_path, only=None):
    import pdfplumber
    rows, warn = [], []
    with pdfplumber.open(pdf_path) as pdf:
        for cuadro, spec in SPEC.items():
            if only and cuadro not in only:
                continue
            seen = set()
            for p in spec["pages"]:
                lines = derotate(pdf.pages[p - 1])
                for label, vals in parse_rows(lines, len(spec["cols"])):
                    if label in seen:
                        continue
                    seen.add(label)
                    total = vals[0]
                    summed = sum(vals[1:])
                    if total != summed:
                        warn.append(f"Cuadro {cuadro} {label!r}: printed total "
                                    f"{total}, cells sum to {summed} "
                                    f"({total - summed:+})")
                        continue
                    for col, v in zip(spec["cols"], vals):
                        rows.append((cuadro, spec["event"],
                                     "geography" if spec["rows_are_geo"]
                                     else spec["row_dim"],
                                     label, spec["col_dim"], col, v))
    return rows, warn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    print("sha256", hashlib.sha256(open(a.pdf, "rb").read()).hexdigest())
    rows, warn = extract(a.pdf, a.only)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cuadro", "vital_event", "dim1_name", "dim1_value",
                    "dim2_name", "dim2_value", "value"])
        w.writerows(rows)
    from collections import Counter
    c = Counter(r[0] for r in rows)
    print(f"{len(rows)} rows -> {a.out}")
    for k in sorted(c):
        labels = len({r[3] for r in rows if r[0] == k})
        print(f"  Cuadro {k:<5} {c[k]:>4} rows, {labels} row labels "
              f"(row totals verified)")
    for w_ in warn[:12]:
        print("  WARN", w_)
    print(f"  ({len(warn)} rows rejected on the total check)")


if __name__ == "__main__":
    main()
