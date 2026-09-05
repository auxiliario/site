"""
ONE -- Dominicana en Cifras 2021, vital statistics section.

Extracted by extract_cifras.py to raw/one-cifras-2021-vitales.csv.

What this adds that nothing else here has:
  * PROVINCIAL DIVORCE counts. The 2025 Anuario tabulates divorce
    nationally only, so without this there is no provincial divorce rate
    at any price.
  * Provincial marriages 2016-2020, turning the single 2025 cross-section
    into a trend.
  * Month of registration for both events -- a seasonality dimension the
    Anuario cuadros loaded here do not carry.

Everything is basis=registro. Region rows are kept and flagged marginal.
"""
import csv

DOCUMENT = dict(
    source_id=4, institution="ONE", instrument="anuario",
    publication="Dominicana en Cifras 2021",
    edition_year=2021, url=None,
    local_path="data/raw/one-cifras-2021-vitales.csv",
    sha256="1bc0891f6c6e147d84eb2b00e98b59f3fb87e6bf61a86543b2653ed3efe80ced",
    page_count=502,
)

CUADROS = {
    "2.1-09": ("Matrimonios registrados por ano, segun mes de registro, "
               "2016-2020", 53, "marriage", "month"),
    "2.1-10": ("Matrimonios registrados por ano, segun provincia de "
               "registro, 2016-2020", 53, "marriage", "geography"),
    "2.1-11": ("Divorcios registrados por ano, segun mes de registro, "
               "2016-2020", 54, "divorce", "month"),
    "2.1-12": ("Divorcios registrados por ano, segun provincia de "
               "registro, 2016-2020", 55, "divorce", "geography"),
}


def read(path):
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            yield (r["cuadro"], r["vital_event"], r["kind"], r["label"],
                   int(r["year"]), float(r["value"]))
