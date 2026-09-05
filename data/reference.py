"""
Reference data: geography, controlled vocabulary, and the category
lookups the analysis views join against.

Everything here is edition-independent. A new Anuario adds a module under
sources/, not a line in this file -- unless it introduces a genuinely new
category, in which case it is added here FIRST and the build then accepts
it. That ordering is the point: the vocabulary trigger turns an
unannounced new category into a build failure instead of a silent second
spelling of an existing dimension.
"""

# ---------------------------------------------------------------- utils
_FOLD = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")


def fold(s: str) -> str:
    """Accent-fold and upper-case. The geography join key."""
    return s.translate(_FOLD).upper().strip()


# ------------------------------------------------------------ geography
# Regionalization per Decreto 685-00, as used by the Anuario's Cuadro 3.2.
REGIONS = {
    "Region Ozama":           ["Distrito Nacional", "Santo Domingo"],
    "Region Cibao Norte":     ["Espaillat", "Puerto Plata", "Santiago"],
    "Region Cibao Sur":       ["La Vega", "Sanchez Ramirez", "Monsenor Nouel"],
    "Region Cibao Nordeste":  ["Duarte", "Maria Trinidad Sanchez",
                               "Hermanas Mirabal", "Samana"],
    "Region Cibao Noroeste":  ["Dajabon", "Monte Cristi",
                               "Santiago Rodriguez", "Valverde"],
    "Region Valdesia":        ["Peravia", "San Cristobal", "San Jose de Ocoa"],
    "Region Enriquillo":      ["Baoruco", "Barahona", "Independencia",
                               "Pedernales"],
    "Region El Valle":        ["Azua", "Elias Pina", "San Juan"],
    "Region Yuma":            ["El Seibo", "La Altagracia", "La Romana"],
    "Region Higuamo":         ["San Pedro de Macoris", "Monte Plata",
                               "Hato Mayor"],
}

# Names other ONE publications use for the same geographies. The Anuario's
# Cuadro 3.2 calls the capital region "Region Ozama"; Dominicana en Cifras
# and the subnacional projections call it "Region Metropolitana". Same
# place, and a join on the printed string silently drops it.
GEO_ALIASES = {
    "Region Metropolitana": "Region Ozama",
    "Metropolitana": "Region Ozama",
    "Region Del Valle": "Region El Valle",
    "Del Valle": "Region El Valle",
    "Bahoruco": "Baoruco",           # spelled both ways across ONE products
}

# ONE provincia codes. Recorded so census / ENI / proyecciones tables can
# be joined on a code rather than on a hand-folded string.
#
# IMPORTANT: these are stored with code_verified = 0. They were not read
# off the Anuario, and nothing in this repository has checked them against
# ONE's Division Territorial. Verify before using `code` as a join key;
# `name_norm` is the key that is actually verified against the source.
PROVINCE_CODES = {
    "Distrito Nacional": "01", "Azua": "02", "Baoruco": "03",
    "Barahona": "04", "Dajabon": "05", "Duarte": "06",
    "Elias Pina": "07", "El Seibo": "08", "Espaillat": "09",
    "Independencia": "10", "La Altagracia": "11", "La Romana": "12",
    "La Vega": "13", "Maria Trinidad Sanchez": "14", "Monte Cristi": "15",
    "Pedernales": "16", "Peravia": "17", "Puerto Plata": "18",
    "Hermanas Mirabal": "19", "Samana": "20", "San Cristobal": "21",
    "San Juan": "22", "San Pedro de Macoris": "23", "Sanchez Ramirez": "24",
    "Santiago": "25", "Santiago Rodriguez": "26", "Valverde": "27",
    "Monsenor Nouel": "28", "Monte Plata": "29", "Hato Mayor": "30",
    "San Jose de Ocoa": "31", "Santo Domingo": "32",
}

# ------------------------------------------------------------ vocabulary
# (domain, term, label_es, is_residual, sort_order, note)
VOCAB = [
    ("vital_event", "marriage",  "Matrimonios", 0, 1, None),
    ("vital_event", "divorce",   "Divorcios",   0, 2, None),
    ("vital_event", "birth",     "Nacimientos", 0, 3, "slot reserved; not yet loaded"),
    ("vital_event", "death",     "Defunciones", 0, 4, "slot reserved; not yet loaded"),

    ("measure", "count",         "Numero absoluto",        0, 1, None),
    ("measure", "percent",       "Porcentaje",             0, 2, None),
    ("measure", "mean_age",      "Edad media",             0, 3,
     "always paired with a `construct` dimension; see construct_registry"),
    ("measure", "age_gap_years", "Diferencia de edad",     0, 4,
     "derived by ONE within one construct; never across constructs"),
    ("measure", "rate_per_1000", "Tasa por mil",           0, 5, "slot reserved"),
    ("measure", "persons",       "Personas",               0, 6, "population table"),

    ("basis", "registro",   "Por fecha/lugar de registro",   0, 1,
     "inflates destination-wedding provinces; NOT residence"),
    ("basis", "ocurrencia", "Por lugar/fecha de ocurrencia", 0, 2, None),
    ("basis", "residencia", "Por provincia de residencia",   0, 3, None),

    ("dim_name", "construct",           None, 0, 1, None),
    ("dim_name", "sex",                 None, 0, 2, None),
    ("dim_name", "bride_age_band",      None, 0, 3, None),
    ("dim_name", "groom_age_band",      None, 0, 4, None),
    ("dim_name", "bride_nationality",   None, 0, 5, None),
    ("dim_name", "groom_nationality",   None, 0, 6, None),
    ("dim_name", "wife_nationality",    None, 0, 7, None),
    ("dim_name", "husband_nationality", None, 0, 8, None),
    ("dim_name", "marriage_type",       None, 0, 9, None),
    ("dim_name", "divorce_cause",       None, 0, 10, None),
    ("dim_name", "month",               None, 0, 15,
     "month of REGISTRATION, not of the event"),
    # reserved so births extraction does not need a schema change
    ("dim_name", "mother_age_band",     None, 0, 11, "slot reserved"),
    ("dim_name", "father_age_band",     None, 0, 12, "slot reserved"),
    ("dim_name", "mother_nationality",  None, 0, 13, "slot reserved"),
    ("dim_name", "father_nationality",  None, 0, 14, "slot reserved"),

    ("sex", "male",   "Hombres", 0, 1, None),
    ("sex", "female", "Mujeres", 0, 2, None),
    ("sex", "both",   "Ambos sexos", 0, 3, None),
]

# ------------------------------------------------------------- age bands
# (band, lower, upper, is_residual, sort_order)
AGE_BANDS = [
    # Present for population denominators; no marriage cuadro uses it.
    ("0-14", 0, 14, 0, 0),
    ("15-19", 15, 19, 0, 1),
    ("20-24", 20, 24, 0, 2),
    ("25-29", 25, 29, 0, 3),
    ("30-34", 30, 34, 0, 4),
    ("35-39", 35, 39, 0, 5),
    ("40-44", 40, 44, 0, 6),
    ("45-49", 45, 49, 0, 7),
    ("50+",   50, None, 0, 8),
    # Residual. Runs 1-2% of marriages here but 10-20% in other cuadros,
    # and it is not missing at random -- it stays a category, never NULL.
    ("No declarada", None, None, 1, 98),
    ("TOTAL",        None, None, 1, 99),
]

# --------------------------------------------------------- nationalities
# (label as printed, iso3, canonical, is_residual, sort_order)
NATIONALITIES = [
    ("Republica Dominicana", "DOM", "Republica Dominicana", 0, 1),
    ("Estados Unidos",       "USA", "Estados Unidos",       0, 2),
    ("Espana",               "ESP", "Espana",               0, 3),
    ("Haiti",                "HTI", "Haiti",                0, 4),
    ("Italia",               "ITA", "Italia",               0, 5),
    ("Venezuela",            "VEN", "Venezuela",            0, 6),
    ("Canada",               "CAN", "Canada",               0, 7),
    ("Polonia",              "POL", "Polonia",              0, 8),
    ("Colombia",             "COL", "Colombia",             0, 9),
    ("Alemania",             "DEU", "Alemania",             0, 10),
    ("Cuba",                 "CUB", "Cuba",                 0, 11),
    ("Francia",              "FRA", "Francia",              0, 12),
    ("Mexico",               "MEX", "Mexico",               0, 13),
    ("Peru",                 "PER", "Peru",                 0, 14),
    ("Puerto Rico",          "PRI", "Puerto Rico",          0, 15),
    ("Holanda",              "NLD", "Holanda",              0, 16),
    ("Otros paises",         None,  "Otros paises",         1, 97),
    ("No declarada",         None,  "No declarada",         1, 98),
    ("TOTAL",                None,  "TOTAL",                1, 99),
]

# ---------------------------------------------------------- constructs
CONSTRUCTS = [
    ("observed_mean_age_at_marriage",
     "Edad promedio de los contrayentes que se casaron en el anio (Sec. 3.1.3)",
     "2025: H 38.10 / M 35.22, sobreedad 2.88. Observed, not synthetic."),
    ("EMNup",
     "Edad media a la que una generacion ficticia termina siendo alcanzada "
     "por el suceso casarse (glosario)",
     "2025: H 39.92 / M 36.08, diferencia 3.84. Synthetic cohort. "
     "NEVER merge with the observed mean."),
    ("basis_registro",
     "Tabulado por fecha/lugar de registro en la Oficialia",
     "Inflates destination-wedding provinces (La Altagracia). Not residence."),
    ("basis_ocurrencia", "Tabulado por lugar/fecha de ocurrencia del hecho", ""),
    ("basis_residencia", "Tabulado por provincia de residencia habitual", ""),
]
