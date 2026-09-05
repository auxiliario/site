#!/usr/bin/env python3
"""
Extract the vital-statistics cuadros of ONE's 'Dominicana en Cifras 2021'
that carry couple events, to CSV.

  2.1-09  marriages by month of registration, national, 2016-2020
  2.1-10  marriages by province of registration, 2016-2020
  2.1-11  divorces  by month of registration, national, 2016-2020
  2.1-12  divorces  by province of registration, 2016-2020

Why these matter beyond the Anuario: 2.1-12 is the only PROVINCIAL
divorce series available anywhere in this collection -- the 2025 Anuario
tabulates divorce nationally only -- and 2.1-10 extends provincial
marriages back five years, so a provincial rate becomes a trend rather
than one cross-section.

All four are tabulated by REGISTRO. Region subtotals are kept and marked
marginal; they are not summed with provinces.
"""
import argparse, csv, hashlib, re, sys

CUADRO = re.compile(r"Cuadro\s+(2\.1-\d+)\.", re.I)
YEARS = re.compile(r"^(?:20\d{2}\s+){3,}20\d{2}$")
ROW = re.compile(r"^(.+?)\s+((?:[\d,]+\s+){3,}[\d,]+)$")
SPEC = {"2.1-09": ("marriage", "month"), "2.1-10": ("marriage", "geography"),
        "2.1-11": ("divorce", "month"),  "2.1-12": ("divorce", "geography")}
SKIP = re.compile(r"^(a[ñn]o de registro|mes de registro|provincia de registro|"
                  r"fuente|situaci[óo]n)", re.I)


def extract(pdf_path, first, last):
    import pdfplumber
    out, warn = [], []
    with pdfplumber.open(pdf_path) as pdf:
        for pno in range(first, last + 1):
            text = pdf.pages[pno - 1].extract_text() or ""
            cuadro, years = None, None
            for line in text.split("\n"):
                line = line.strip()
                m = CUADRO.search(line)
                if m:
                    cuadro = m.group(1) if m.group(1) in SPEC else None
                    years = None
                    continue
                if YEARS.match(line):
                    years = [int(y) for y in line.split()]
                    continue
                if not (cuadro and years) or SKIP.match(line):
                    continue
                m = ROW.match(line)
                if not m:
                    continue
                label = m.group(1).strip()
                vals = [int(v.replace(",", "")) for v in m.group(2).split()]
                if len(vals) != len(years):
                    warn.append(f"p{pno} {cuadro} {label!r}: {len(vals)} "
                                f"values for {len(years)} years")
                    continue
                event, kind = SPEC[cuadro]
                for y, v in zip(years, vals):
                    out.append((cuadro, event, kind, label, y, v))
    return out, warn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--first-page", type=int, default=53)
    ap.add_argument("--last-page", type=int, default=57)
    a = ap.parse_args()
    print("sha256", hashlib.sha256(open(a.pdf, "rb").read()).hexdigest())
    rows, warn = extract(a.pdf, a.first_page, a.last_page)
    rows = sorted(set(rows))
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cuadro", "vital_event", "kind", "label", "year", "value"])
        w.writerows(rows)
    from collections import Counter
    c = Counter(r[0] for r in rows)
    print(f"{len(rows)} rows -> {a.out}")
    for k in sorted(c):
        labels = {r[3] for r in rows if r[0] == k}
        print(f"  {k}: {c[k]} rows, {len(labels)} labels, "
              f"years {sorted({r[4] for r in rows if r[0]==k})}")
    for w_ in warn[:10]:
        print("  WARN", w_)
    print(f"  ({len(warn)} warnings)")


if __name__ == "__main__":
    main()
