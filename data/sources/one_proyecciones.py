"""
ONE -- Estimaciones y Proyecciones de Poblacion, single years of age.

Source: raw/one-proyecciones-edades-simples-1950-2100.xlsx
Sheets: Total / Hombres / Mujeres; rows = single ages 0..100 (100 is the
open interval); columns = calendar years 1950..2100.

Why the single-age file and not the grouped one: ONE's
"...segun sexo y grupos de edades..." workbook has its 5-9 and 10-14 row
labels corrupted into Excel dates (2026-09-05 and 2014-10-01) in all
three sex blocks. Single ages are integers, cannot be date-coerced, and
let the Anuario's own bands -- including the open-ended 50+ -- be built
exactly rather than approximated.

These are NATIONAL figures. Provincial denominators are not in this
workbook; they are in ONE's subnacional projection reports, which are
PDFs. Until those are extracted, no provincial rate is computable, and
`geo_id` here is always 1.
"""
import openpyxl

DOCUMENT = dict(
    source_id=2,
    institution="ONE",
    instrument="proyecciones",
    publication="Estimaciones y Proyecciones de Poblacion, edades simples, "
                "1950-2100",
    edition_year=2025,
    url=None,
    local_path="data/raw/one-proyecciones-edades-simples-1950-2100.xlsx",
    sha256="ae7783bf5ab23af539f20f8b4f1049444439737e666d318cc068b12746af8b10",
    page_count=None,
)

SHEET_SEX = {"Total": "both", "Hombres": "male", "Mujeres": "female"}

# Anuario marriage bands, built from single ages. 50+ is open-ended and
# absorbs everything to the top of the table.
BANDS = [("0-14", 0, 14), ("15-19", 15, 19), ("20-24", 20, 24),
         ("25-29", 25, 29), ("30-34", 30, 34), ("35-39", 35, 39),
         ("40-44", 40, 44), ("45-49", 45, 49), ("50+", 50, 200)]


def _header_row(rows):
    for i, r in enumerate(rows):
        if len([c for c in r if isinstance(c, int) and 1900 < c < 2200]) > 50:
            return i
    raise ValueError("no year header row found")


def read(path, years):
    """Yield (year, sex, band, persons), aggregated from single ages.

    Also yields band 'TOTAL' from the sheet's own published Total row --
    NOT from summing the ages -- so the two can be compared rather than
    assumed equal.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet, sex in SHEET_SEX.items():
            rows = list(wb[sheet].iter_rows(values_only=True))
            h = _header_row(rows)
            col = {c: j for j, c in enumerate(rows[h])
                   if isinstance(c, int) and 1900 < c < 2200}
            by_age, published_total = {}, {}
            for r in rows[h + 1:]:
                lab = r[0]
                if isinstance(lab, int):
                    by_age[lab] = r
                elif isinstance(lab, str) and lab.strip().lower() == "total":
                    published_total = r
            for y in years:
                if y not in col:
                    continue
                j = col[y]
                for band, lo, hi in BANDS:
                    v = sum(by_age[a][j] for a in by_age
                            if lo <= a <= hi and by_age[a][j] is not None)
                    yield y, sex, band, float(v)
                if published_total and published_total[j] is not None:
                    yield y, sex, "TOTAL", float(published_total[j])
    finally:
        wb.close()
