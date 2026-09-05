"""
ONE -- Anuario 2025 cuadros printed on ROTATED pages.

Extracted by extract_rotated.py. These were invisible to every earlier
extractor: the pages carry /Rotate 0, the table is drawn rotated 90
degrees, and each word's characters are stored reversed, so ordinary text
extraction returns mirrored nonsense. Ten of the Anuario's 26 cuadros
are laid out this way.

Loaded here:
  1.10  mother's marital status x mother age band
  3.6   marriages by month x region/province
  3.7   marriages by BRIDE AGE BAND x region/province
  4.6   divorces by month x region/province

3.7 is the reason this was worth doing: with the provincial population by
sex and age already loaded, it gives provincial AGE-SPECIFIC marriage
rates. Nothing else in the collection supports them.

1.10 is the only union-status-by-age data held. It is not a substitute
for a census marital-status distribution -- it describes women who gave
birth in 2025, not the whole female population -- but it is the first
direct evidence here on how union status varies with age.
"""
import csv

DIM_FOR_GEO_ROWS = {"3.6": "month", "3.7": "bride_age_band", "4.6": "month"}
EVENT = {"1.10": "birth", "3.6": "marriage", "3.7": "marriage",
         "4.6": "divorce"}
BASIS = {"1.10": "ocurrencia", "3.6": "registro", "3.7": "registro",
         "4.6": "registro"}
TITLES = {
    "1.10": ("Nacimientos por estado civil de la madre, segun grupos de "
             "edades de la madre al momento del nacimiento, 2025", 57),
    "3.6": ("Matrimonios registrados por mes, segun region y provincia de "
            "registro, 2025", 87),
    "3.7": ("Matrimonios registrados por grupos de edades de la "
            "contrayente, segun region y provincia de registro, 2025", 89),
    "4.6": ("Divorcios registrados por mes de registro, segun region y "
            "provincia de registro, 2025", 98),
}


# Cuadro 1.10 prints its age bands in words. Map them onto the bands the
# rest of the database uses, so a join to population or to Cuadro 3.3 does
# not silently miss the youngest and oldest mothers.
BAND_ALIAS = {
    "Menos de 15 anos": "0-14", "Menos de 15 años": "0-14",
    "50 anos y mas": "50+", "50 años y más": "50+",
}


def read(path):
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            d1v = r["dim1_value"]
            if r["dim1_name"].endswith("age_band"):
                d1v = BAND_ALIAS.get(d1v, d1v)
            yield (r["cuadro"], r["dim1_name"], d1v,
                   r["dim2_name"], r["dim2_value"], float(r["value"]))
