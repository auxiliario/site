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

    # ---- remaining rotated cuadros --------------------------------------
    "1.1":  dict(pages=[46, 47], event="birth", row_dim=None,
                 col_dim="mother_nationality", rows_are_geo=True,
                 cols=["TOTAL", "Republica Dominicana", "Haiti", "Venezuela",
                       "Colombia", "Cuba", "Espana", "Estados Unidos",
                       "Otros paises", "No declarada"]),

    # NESTED: Total = Dominicana + (subtotal of foreign mothers) + No
    # declarada, and the subtotal itself equals the seven country columns.
    # A flat 'total equals the rest' check fails on this shape, and padding
    # or dropping the row would lose a whole cuadro.
    "1.9":  dict(pages=[56, 57], event="birth", row_dim=None,
                 col_dim="mother_birth_country", rows_are_geo=True,
                 verify="nested",
                 cols=["TOTAL", "Republica Dominicana", "TOTAL extranjeras",
                       "Haiti", "Venezuela", "Colombia", "Mexico", "Espana",
                       "Estados Unidos", "Otros paises", "No declarada"]),

    "1.11": dict(pages=[58, 59], event="birth", row_dim=None,
                 col_dim="month", rows_are_geo=True, cols=["TOTAL", "Enero", "Febrero", "Marzo", "Abril", "Mayo",
                       "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
                       "Noviembre", "Diciembre"]),

    # No total column at all: every column is a year of registration and
    # every row a year of occurrence, so there is nothing to check a row
    # against. Recorded as verify='none' rather than silently skipped.
    "1.12": dict(pages=[60], event="birth", row_dim="year_of_occurrence",
                 col_dim="year_of_registration", rows_are_geo=False,
                 verify="none", numeric_labels=True,
                 cols=[str(y) for y in range(2015, 2026)]),

    "2.2":  dict(pages=[66, 67], event="death", row_dim=None,
                 col_dim="month", rows_are_geo=True, cols=["TOTAL", "Enero", "Febrero", "Marzo", "Abril", "Mayo",
                       "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
                       "Noviembre", "Diciembre"]),

    "2.5":  dict(pages=[70, 71], event="death", row_dim=None,
                 col_dim="deceased_nationality", rows_are_geo=True,
                 cols=["TOTAL", "Republica Dominicana", "Haiti", "Italia",
                       "Espana", "Venezuela", "Canada", "Alemania",
                       "Estados Unidos", "Otros paises", "No declarada"]),
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


def parse_rows(lines, ncols, numeric_labels=False):
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

        if numeric_labels:
            # A table whose row labels are themselves numbers (years) gives
            # no way to tell a wrapped label from the column header, which
            # is also a bare run of years. Require the label as a distinct
            # extra token instead; the header row has exactly ncols tokens
            # and is correctly ignored.
            # Any line with MORE than ncols tokens is a data row and the
            # extra tokens are its label, however many they are ('1995' but
            # also 'Antes de 1995', 'No declarado'). A line with exactly
            # ncols tokens is the column header and is skipped -- which is
            # the only thing the wrapped-label reassembly must not do here.
            if len(toks) <= ncols:
                continue
            label = " ".join(toks[:-ncols]).strip()
            if not label or label.lower().startswith(("fuente", "cuadro")):
                continue
            out.append((label, [int(t.replace(",", "")) for t in tail]))
            continue

        if len(toks) == ncols:                       # numbers only: wrapped
            before = toks_of[i - 1] if i else []
            after = toks_of[i + 1] if i + 1 < len(toks_of) else []
            parts = [" ".join(p) for p in (after, before) if is_label(p)]
            label = " ".join(parts).strip()
        else:
            if NUM.match(toks[-ncols - 1]) and not numeric_labels:
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
                for label, vals in parse_rows(lines, len(spec["cols"]),
                                             spec.get("numeric_labels", False)):
                    if label in seen:
                        continue
                    seen.add(label)
                    mode = spec.get("verify", "total_first")
                    problem = None
                    if mode == "total_first":
                        if vals[0] != sum(vals[1:]):
                            problem = (f"printed total {vals[0]}, cells sum to "
                                       f"{sum(vals[1:])} "
                                       f"({vals[0] - sum(vals[1:]):+})")
                    elif mode == "nested":
                        # Total = Dominicana + foreign subtotal + No declarada
                        if vals[0] != vals[1] + vals[2] + vals[-1]:
                            problem = (f"total {vals[0]} != dominicana "
                                       f"{vals[1]} + extranjeras {vals[2]} + "
                                       f"no declarada {vals[-1]}")
                        elif vals[2] != sum(vals[3:-1]):
                            problem = (f"foreign subtotal {vals[2]} != sum of "
                                       f"countries {sum(vals[3:-1])}")
                    # Preserve and flag; never drop. A row that fails its
                    # own arithmetic is a finding about the source, and
                    # discarding it would hide that the source disagrees
                    # with itself -- the same rule the rest of this
                    # database follows for Cuadro 3.5.
                    if problem:
                        warn.append(f"Cuadro {cuadro} {label!r}: {problem}")
                    for col, v in zip(spec["cols"], vals):
                        rows.append((cuadro, spec["event"],
                                     "geography" if spec["rows_are_geo"]
                                     else spec["row_dim"],
                                     label, spec["col_dim"], col, v,
                                     problem or ""))
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
                    "dim2_name", "dim2_value", "value", "anomaly"])
        w.writerows(rows)
    from collections import Counter
    c = Counter(r[0] for r in rows)
    print(f"{len(rows)} rows -> {a.out}")
    for k in sorted(c):
        labels = len({r[3] for r in rows if r[0] == k})
        fl = len({r[3] for r in rows if r[0] == k and r[7]})
        print(f"  Cuadro {k:<5} {c[k]:>4} rows, {labels:>2} row labels"
              + (f", {fl} FLAGGED" if fl else ", all verified"))
    for w_ in warn[:12]:
        print("  WARN", w_)
    flagged = len({(r[0], r[3]) for r in rows if r[7]})
    print(f"  ({flagged} rows flagged by the total check, 0 dropped)")


if __name__ == "__main__":
    main()
