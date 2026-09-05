"""
ONE -- Proyecciones subnacionales de poblacion 2000-2030 (2016 revision).

Provincial and regional population by calendar year, sex and five-year
age group, extracted from Cuadro 5.3 by extract_subnacional.py into
raw/one-proyecciones-subnacionales-2000-2030.csv.

This is the provincial exposure base. Without it a provincial marriage
count cannot be turned into a rate, and La Altagracia -- a
destination-wedding province tabulated by place of REGISTRO -- cannot be
interpreted at all.

Three source defects were found and are handled in the extractor, not
patched here:
  * 'DISTRITO NACIONAL:' and 'SANTO DOMINGO:' carry no PROVINCIA prefix
    (and Santo Domingo omits the space before 'Estimaciones'),
  * 'PROVINCIA CIBAO NORDESTE', 'PROVINCIA VALDESIA' and 'REGION BAORUCO'
    are mislabelled -- the first two are regions, the third a province,
  * one San Cristobal page is headed 'Cuadro 3' instead of 'Cuadro 5.3'.
Level is resolved from the entity NAME against reference.py rather than
from ONE's heading, and pages are found by title line rather than by
cuadro number.

Percentage tables printed under the same title are rejected structurally:
their decimals split into two integer tokens, so the row's value count
never matches the year header and the row is reported, never padded.
"""
import csv

DOCUMENT = dict(
    source_id=3,
    institution="ONE",
    instrument="proyecciones",
    publication="Estimaciones y proyecciones de poblacion. Proyecciones "
                "subnacionales 2000-2030 (Volumen IV, abril 2016)",
    edition_year=2016,
    url=None,
    local_path="data/raw/one-proyecciones-subnacionales-2000-2030.csv",
    sha256="af6e4cb4513e050530d3530e252983695f8127c466f76a020df09aa0b220946c",
    page_count=614,
)

# Five-year source bands -> the Anuario's marriage bands.
FOLD = {"0-4": "0-14", "5-9": "0-14", "10-14": "0-14"}
for b in ("15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"):
    FOLD[b] = b
for b in ("50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80+"):
    FOLD[b] = "50+"


def read(path, years):
    """Yield (level, name_es, sex, band, year, persons) in Anuario bands,
    plus a TOTAL band summed across every source band."""
    agg, total = {}, {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            y = int(r["year"])
            if y not in years:
                continue
            band = FOLD.get(r["age_band"])
            if band is None:
                continue
            key = (r["level"], r["name_es"], r["sex"], y)
            agg[key + (band,)] = agg.get(key + (band,), 0) + int(r["persons"])
            total[key] = total.get(key, 0) + int(r["persons"])
    for (lvl, name, sex, y, band), v in agg.items():
        yield lvl, name, sex, band, y, float(v)
    for (lvl, name, sex, y), v in total.items():
        yield lvl, name, sex, "TOTAL", y, float(v)
