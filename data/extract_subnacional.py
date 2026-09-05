#!/usr/bin/env python3
"""
Extract ONE's subnacional population projections (Cuadro 5.3) to CSV.

    python extract_subnacional.py --pdf <subnacionales.pdf> --out raw/...csv

Cuadro 5.3 gives, for every province and region, population by calendar
year, sex and five-year age group, 2000-2030 -- the provincial exposure
base the national workbook does not carry. Each entity spans several
pages; a page holds 7-8 year columns and three stacked sex blocks
(Ambos sexos / Hombres / Mujeres), each listing 0-4 through '80 y mas'.

Parsed from the text layer by line shape rather than by geometry: the
rows are 'label + N numbers', which is unambiguous once the year header
fixes N. Rows whose number count disagrees with the header are reported,
never padded.
"""
import argparse, csv, hashlib, os, re, sys

SEXES = {"ambos sexos": "both", "hombres": "male", "mujeres": "female"}

# Region names as ONE prints them here, mapped to the names reference.py
# uses (which follow the Anuario's Cuadro 3.2).
REGION_ALIAS = {"METROPOLITANA": "Region Ozama", "DEL VALLE": "Region El Valle"}
AGE = re.compile(r"^(\d{1,2}\s*-\s*\d{1,2}|\d{2}\s*y\s*m[áa]s)\s+(.*)$", re.I)
YEARS = re.compile(r"^(?:\d{4}\s+){3,}\d{4}$")
# The title line, not the PROVINCIA/REGION word, identifies the entity:
# ONE's own headers are inconsistent. 'DISTRITO NACIONAL:' and
# 'SANTO DOMINGO:' carry no prefix at all (and Santo Domingo omits the
# space before 'Estimaciones'), while 'PROVINCIA CIBAO NORDESTE',
# 'PROVINCIA VALDESIA' and 'REGION BAORUCO' are mislabelled -- the first
# two are regions and the third is a province. Level is therefore
# resolved from the NAME against reference.py, never from the heading.
ENTITY = re.compile(
    r"^(.*?):\s*Estimaciones y proyecciones de la poblaci[óo]n total",
    re.I | re.M)
PREFIX = re.compile(r"^(PROVINCIA|REGI[ÓO]N)\s+", re.I)
NUM = re.compile(r"-?[\d,]+")


def norm_band(b):
    b = re.sub(r"\s+", "", b).lower().replace("ymás", "+").replace("ymas", "+")
    return b


def build_resolver():
    """Name -> (level, canonical name), from reference.py."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import reference as R
    table = {R.fold("Republica Dominicana"): ("national", "Republica Dominicana"),
             R.fold("Total pais"): ("national", "Republica Dominicana")}
    for region, provinces in R.REGIONS.items():
        table[R.fold(region)] = ("region", region)
        bare = R.fold(region.replace("Region ", ""))
        table.setdefault(bare, ("region", region))
        for p in provinces:
            table[R.fold(p)] = ("province", p)
    for printed, canonical in REGION_ALIAS.items():
        table[R.fold(printed)] = ("region", canonical)
    # ONE spells this province BAHORUCO in some documents.
    table[R.fold("Bahoruco")] = ("province", "Baoruco")
    return lambda n: table.get(R.fold(n))


def extract(pdf_path):
    import pdfplumber
    resolve = build_resolver()
    rows, warnings = [], []
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            # Filter on the TITLE line, not the cuadro number: p204 of the
            # 2016 edition heads a San Cristobal page 'Cuadro 3' instead of
            # 'Cuadro 5.3', and filtering on the number silently dropped
            # eight years for that one province.
            if not ENTITY.search(text):
                continue
            entity, years, sex = None, None, None
            for line in text.split("\n"):
                line = line.strip()
                m = ENTITY.match(line)
                if m:
                    entity = resolve(PREFIX.sub("", m.group(1).strip()))
                    if entity is None:
                        warnings.append(f"p{pno}: unrecognised entity "
                                        f"{m.group(1).strip()!r}")
                    continue
                if YEARS.match(line):
                    years = [int(y) for y in line.split()]
                    continue
                low = line.lower()
                for label, s in SEXES.items():
                    if low.startswith(label):
                        sex = s
                        tail = line[len(label):]
                        break
                else:
                    tail = None
                if tail is not None:
                    continue                      # sex header row: total only
                m = AGE.match(line)
                if not (m and entity and years and sex):
                    continue
                band = norm_band(m.group(1))
                vals = [int(v.replace(",", "")) for v in NUM.findall(m.group(2))]
                if len(vals) != len(years):
                    warnings.append(f"p{pno} {entity[1]} {sex} {band}: "
                                    f"{len(vals)} values for {len(years)} years")
                    continue
                for y, v in zip(years, vals):
                    rows.append((entity[0], entity[1], sex, band, y, v))
    return rows, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--year-min", type=int, default=2013)
    ap.add_argument("--year-max", type=int, default=2030)
    a = ap.parse_args()

    print("sha256", hashlib.sha256(open(a.pdf, "rb").read()).hexdigest())
    rows, warnings = extract(a.pdf)
    rows = [r for r in rows if a.year_min <= r[4] <= a.year_max]
    rows = sorted(set(rows))
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["level", "name_es", "sex", "age_band", "year", "persons"])
        w.writerows(rows)
    from collections import Counter
    per = Counter((r[0], r[1]) for r in rows)
    expected = 3 * 17 * (a.year_max - a.year_min + 1)
    short = {k: v for k, v in per.items() if v != expected}
    ents = set(per)
    print(f"{len(rows)} rows -> {a.out}")
    print(f"expected {expected} rows per entity (3 sexes x 17 bands x "
          f"{a.year_max - a.year_min + 1} years)")
    if short:
        print("  INCOMPLETE entities:")
        for k, v in sorted(short.items()):
            print(f"    {k[0]:<9} {k[1]:<26} {v} rows ({expected - v} missing)")
    print(f"entities: {sum(1 for e in ents if e[0]=='province')} provinces, "
          f"{sum(1 for e in ents if e[0]=='region')} regions, "
          f"{sum(1 for e in ents if e[0]=='national')} national")
    print(f"years {min(r[4] for r in rows)}-{max(r[4] for r in rows)}; "
          f"bands {sorted({r[3] for r in rows})}")
    for w_ in warnings[:15]:
        print("  WARN", w_)
    print(f"  ({len(warnings)} warnings)")


if __name__ == "__main__":
    main()
