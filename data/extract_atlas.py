#!/usr/bin/env python3
"""
Extract the violence dimension of ONE's Atlas de Genero 2020 to CSV.

Cuadros 13-22, pp.61-79 of the PDF. Two shapes:

  13-20  'Desagregacion | Porcentaje (%)' -- one year (2018), rows for
         the national total, urban/rural, and four MACRO-REGIONS.
         Source: ENESIM 2018, a sample survey.
  21-22  'Desagregacion | Total | 2009..2018' -- counts by year, by
         perpetrator relationship, and by the ten planning regions.
         Source: administrative records.

Each cuadro sits on a page whose FIRST table is the indicator metadata
(Indicador / Definicion / Fuente ...) and whose SECOND table is the data.
`partner_specific` is derived from whether the indicator text names
'pareja' -- read off the source, not assumed -- so a caller can separate
intimate-partner measures from the public, school, work and community
spheres that are measured on the same population and make the natural
contrast.

Note the two geographies are NOT the same: cuadros 13-20 use four
macro-regions (Gran Santo Domingo / Sur / Este / Norte o Cibao) which do
not nest into the ten planning regions used by 21-22 and by every other
source in this database.
"""
import argparse, csv, hashlib, re, unicodedata

PAGES = {61: 13, 63: 14, 65: 15, 67: 16, 69: 17,
         71: 18, 73: 19, 75: 20, 77: 21, 79: 22}
SECTION = re.compile(r"^(zona de residencia|macro\s*regi[oó]n geogr[aá]fica|"
                     r"macrorregi[oó]n geogr[aá]fica|regi[oó]n|"
                     r"clasificaci[oó]n)", re.I)
TOTALS = {"total", "pais", "país"}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def num(s):
    s = (s or "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def extract(pdf_path):
    import pdfplumber
    rows, warn = [], []
    with pdfplumber.open(pdf_path) as pdf:
        for pno, cuadro in PAGES.items():
            tbs = pdf.pages[pno - 1].extract_tables()
            if len(tbs) < 2:
                warn.append(f"p{pno} cuadro {cuadro}: {len(tbs)} tables")
                continue
            meta = {(r[0] or "").strip().lower(): (r[1] or "").replace("\n", " ")
                    for r in tbs[0] if r and len(r) > 1}
            indicator = meta.get("indicador", "")
            source = meta.get("fuente", "")
            # 'feminicidio intimo' is partner violence by definition even
            # though the indicator text never says 'pareja'.
            ind_l = strip_accents(indicator).lower()
            partner = int("pareja" in ind_l or "feminicidio intimo" in ind_l)
            data = tbs[1]
            header = [(c or "").strip() for c in data[0]]
            years = [h for h in header[1:] if re.fullmatch(r"20\d{2}", h)]
            section = None
            for r in data[1:]:
                label = (r[0] or "").replace("\n", " ").strip()
                if not label or label.lower().startswith("fuente"):
                    continue
                if SECTION.match(label) and not any(num(c) is not None
                                                    for c in r[1:]):
                    section = strip_accents(label).lower()
                    continue
                if years:                      # shape B: a column per year
                    for h, cell in zip(header[1:], r[1:]):
                        v = num(cell)
                        if v is None:
                            continue
                        yr = int(h) if re.fullmatch(r"20\d{2}", h) else None
                        rows.append((cuadro, indicator, source, partner,
                                     section or "", label,
                                     yr, "count" if yr else "count_total", v))
                else:                          # shape A: a single percentage
                    v = num(r[1] if len(r) > 1 else None)
                    if v is None:
                        continue
                    rows.append((cuadro, indicator, source, partner,
                                 section or "", label, 2018, "percent", v))
            if not any(x[0] == cuadro for x in rows):
                warn.append(f"p{pno} cuadro {cuadro}: no data rows parsed")
    return rows, warn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    print("sha256", hashlib.sha256(open(a.pdf, "rb").read()).hexdigest())
    rows, warn = extract(a.pdf)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cuadro", "indicator", "source_note", "partner_specific",
                    "section", "label", "year", "measure", "value"])
        w.writerows(rows)
    from collections import Counter
    c = Counter(r[0] for r in rows)
    print(f"{len(rows)} rows -> {a.out}")
    for k in sorted(c):
        p = {r[3] for r in rows if r[0] == k}
        print(f"  Cuadro {k:<3} {c[k]:>4} rows  partner_specific={p.pop()}")
    for w_ in warn:
        print("  WARN", w_)


if __name__ == "__main__":
    main()
