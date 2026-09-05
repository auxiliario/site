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

DIM_FOR_GEO_ROWS = {
    "3.6": "month", "3.7": "bride_age_band", "4.6": "month",
    "1.1": "mother_nationality", "1.9": "mother_birth_country",
    "1.11": "month", "2.2": "month", "2.5": "deceased_nationality",
}
EVENT = {"1.10": "birth", "3.6": "marriage", "3.7": "marriage",
         "4.6": "divorce", "1.1": "birth", "1.9": "birth", "1.11": "birth",
         "1.12": "birth", "2.2": "death", "2.5": "death"}
BASIS = {"1.10": "ocurrencia", "3.6": "registro", "3.7": "registro",
         "4.6": "registro", "1.1": "registro", "1.9": "registro",
         "1.11": "ocurrencia", "1.12": "registro", "2.2": "ocurrencia",
         "2.5": "registro"}
TITLES = {
    "1.1": ("Nacimientos registrados por pais de nacionalidad de la madre, "
            "segun region y provincia de registro, 2025", 46),
    "1.9": ("Nacimientos ocurridos por pais de nacimiento de la madre, "
            "segun region y provincia de registro, 2025", 56),
    "1.11": ("Nacimientos ocurridos por mes de ocurrencia, segun region y "
             "provincia de ocurrencia, 2025", 58),
    "1.12": ("Nacimientos registrados por ano de registro, segun ano de "
             "ocurrencia del nacimiento, 2015-2025", 60),
    "2.2": ("Defunciones ocurridas por mes, segun region y provincia de "
            "ocurrencia, 2025", 66),
    "2.5": ("Defunciones ocurridas por pais de nacionalidad del fallecido(a), "
            "segun region y provincia de registro, 2025", 70),
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
            yield (r["cuadro"], r["dim1_name"], d1v, r["dim2_name"],
                   r["dim2_value"], float(r["value"]),
                   r.get("anomaly") or None)
