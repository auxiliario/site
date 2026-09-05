"""
ONE -- Anuario de Estadisticas Vitales 2025.

Cells are transcribed EXACTLY as printed. Nothing here is reconciled,
rounded, or repaired: where a published row total disagrees with the row
it heads, both numbers are recorded and the disagreement is resolved (or
not) downstream, in `reconciliation`.

To add another edition, copy this module, change DOCUMENT, and re-transcribe.
Do not parametrize cuadro numbers across editions -- ONE renumbers them.
"""

DOCUMENT = dict(
    source_id=1,
    institution="ONE",
    instrument="anuario",
    publication="Anuario de Estadisticas Vitales 2025",
    edition_year=2025,
    url="https://www.one.gob.do/media/5cjnog0m/"
        "anuario-de-estadisticas-vitales-2025.pdf",
    local_path="sources/anuario-2025.pdf",
    sha256="42ec03d0ef6d7e2e18af0f4555eb8270fae0b624aa89cd74d24fc6880956ef70",
    page_count=103,
)

# ------------------------------------------------- Cuadro 1 (p.37) EMNup
# Synthetic-cohort measure, 2013-2025 as restated by THIS edition.
# (year, both, male, female, difference)
EMNUP = [
    (2013, 35.03, 37.30, 32.77, 4.53), (2014, 34.97, 37.21, 32.72, 4.49),
    (2015, 35.34, 37.50, 33.18, 4.32), (2016, 35.59, 37.64, 33.55, 4.09),
    (2017, 35.84, 37.91, 33.77, 4.14), (2018, 35.88, 37.90, 33.86, 4.03),
    (2019, 36.23, 38.15, 34.30, 3.86), (2020, 35.54, 37.39, 33.69, 3.70),
    (2021, 36.31, 38.13, 34.49, 3.65), (2022, 36.88, 38.75, 35.02, 3.73),
    (2023, 37.58, 39.46, 35.70, 3.77), (2024, 37.66, 39.55, 35.76, 3.78),
    (2025, 38.00, 39.92, 36.08, 3.84),
]

# ------------------------------- Sec. 3.1.3 (p.33) observed mean ages
OBSERVED_MEAN = dict(male=38.10, female=35.22, gap=2.88)

# --------------------------- Cuadro 3.3 (p.84) bride age x groom age
AGE_BANDS = ["15-19", "20-24", "25-29", "30-34", "35-39",
             "40-44", "45-49", "50+", "No declarada"]
C33 = {
    "15-19":        [59,  496,  210,  65,   30,   11,   6,   12,   0],
    "20-24":        [80,  2375, 2359, 909,  372,  152,  80,  117,  3],
    "25-29":        [28,  717,  2723, 2226, 967,  467,  256, 289,  5],
    "30-34":        [9,   210,  821,  1926, 1520, 845,  447, 652,  8],
    "35-39":        [4,   82,   304,  743,  1194, 1083, 704, 935,  1],
    "40-44":        [0,   33,   135,  332,  579,  921,  864, 1179, 0],
    "45-49":        [0,   23,   76,   169,  268,  454,  761, 1680, 4],
    "50+":          [3,   20,   61,   143,  228,  330,  582, 4907, 6],
    "No declarada": [1,   3,    6,    2,    0,    4,    7,   10,   457],
}
C33_ROW_TOTALS = {"15-19": 889, "20-24": 6447, "25-29": 7678, "30-34": 6438,
                  "35-39": 5050, "40-44": 4043, "45-49": 3435, "50+": 6280,
                  "No declarada": 490}

# ------------------- Cuadro 3.5 (p.85) bride nationality x groom nationality
# NOTE: the interior of this cuadro does not reconcile with either set of
# published marginals -- IN THE PDF ITSELF. Verified 2026-09-05 against
# pp.85-86: all 17 printed row totals disagree with the cells printed
# beside them, and the Estados Unidos row total (1,565) is smaller than a
# single cell in that row (1,904), so the Total column cannot be a row
# total at all. The defect is ONE's. Transcribed exactly as printed.
# Column order VERIFIED against the PDF (pp. 85-86, sha256 42ec03d0...).
# The cuadro is printed across two pages: p.85 carries Total + the first 8
# country columns, p.86 the remaining 9 under "continuacion...". Peru and
# Puerto Rico were transposed in the original transcription -- almost
# certainly where the two pages were stitched. Cell VALUES were positionally
# correct; only these two headers were swapped, which mislabelled 8 cells
# and 2 column totals.
C35_COLS = ["Republica Dominicana", "Estados Unidos", "Espana", "Haiti",
            "Italia", "Venezuela", "Canada", "Polonia", "Colombia",
            "Alemania", "Cuba", "Francia", "Mexico", "Puerto Rico", "Peru",
            "Otros paises", "No declarada"]
C35 = {
    "Republica Dominicana": [36358, 1897, 408, 178, 172, 91, 66, 11, 52, 53, 47, 45, 51, 51, 15, 252, 85],
    "Estados Unidos":       [1904, 174, 2, 39, 1, 2, 0, 0, 5, 1, 1, 1, 2, 1, 2, 11, 0],
    "Espana":               [443, 1, 8, 1, 1, 1, 1, 0, 0, 1, 0, 1, 1, 0, 0, 2, 0],
    "Haiti":                [188, 46, 3, 53, 1, 0, 30, 1, 0, 5, 0, 4, 0, 0, 0, 10, 3],
    "Venezuela":            [220, 14, 2, 0, 2, 43, 2, 0, 2, 0, 1, 1, 2, 0, 0, 2, 1],
    "Colombia":             [149, 14, 1, 1, 0, 1, 3, 0, 13, 0, 0, 0, 0, 0, 0, 2, 1],
    "Canada":               [96, 1, 0, 13, 0, 2, 31, 0, 2, 0, 0, 1, 0, 0, 0, 1, 0],
    "Italia":               [78, 0, 0, 2, 6, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
    "Polonia":              [11, 0, 1, 0, 0, 0, 0, 69, 0, 0, 0, 0, 0, 0, 0, 2, 0],
    "Cuba":                 [50, 3, 1, 0, 1, 0, 0, 0, 0, 0, 13, 1, 0, 0, 0, 0, 0],
    "Mexico":               [57, 1, 0, 3, 0, 0, 0, 0, 0, 1, 1, 0, 2, 0, 0, 0, 1],
    "Francia":              [33, 0, 0, 3, 0, 1, 0, 0, 0, 0, 0, 10, 0, 0, 0, 0, 1],
    "Alemania":             [39, 1, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 1, 0, 2],
    "Peru":                 [17, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15, 1, 0],
    "Puerto Rico":          [32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Otros paises":         [211, 8, 2, 4, 0, 2, 3, 1, 3, 0, 1, 0, 0, 0, 0, 66, 4],
    "No declarada":         [72, 1, 0, 1, 0, 5, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 90],
}
C35_ROW_TOTALS = {"Republica Dominicana": 36785, "Estados Unidos": 1565,
                  "Espana": 486, "Haiti": 397, "Venezuela": 273,
                  "Colombia": 151, "Canada": 125, "Italia": 98,
                  "Polonia": 82, "Cuba": 78, "Mexico": 74, "Francia": 74,
                  "Alemania": 41, "Peru": 37, "Puerto Rico": 36,
                  "Otros paises": 413, "No declarada": 35}
C35_COL_TOTALS = [36892, 1737, 401, 325, 181, 128, 122, 104, 77, 73, 72,
                  68, 67, 41, 37, 385, 40]

# ----------------- Cuadro 4.5 (p.96) wife nationality x husband nationality
C45_COLS = ["Republica Dominicana", "Estados Unidos", "Espana", "Italia",
            "Puerto Rico", "Haiti", "Venezuela", "Canada", "Francia", "Cuba",
            "Colombia", "Mexico", "Holanda", "Alemania", "Peru",
            "Otros paises", "No declarada"]
C45 = {
    "Republica Dominicana": [17380, 669, 123, 88, 52, 32, 30, 24, 27, 23, 20, 18, 19, 19, 18, 164, 981],
    "Estados Unidos":       [922, 21, 1, 0, 1, 4, 1, 0, 0, 0, 0, 2, 0, 0, 0, 3, 92],
    "Espana":               [133, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
    "Venezuela":            [73, 2, 0, 1, 0, 0, 13, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4],
    "Puerto Rico":          [64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3],
    "Canada":               [45, 0, 0, 0, 0, 5, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 6],
    "Haiti":                [19, 6, 2, 0, 0, 8, 0, 4, 1, 0, 0, 0, 0, 0, 0, 3, 4],
    "Italia":               [43, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
    "Colombia":             [31, 4, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 1, 2],
    "Alemania":             [18, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    "Mexico":               [16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3],
    "Cuba":                 [14, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0],
    "Holanda":              [14, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1],
    "Francia":              [10, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    "Peru":                 [10, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Otros paises":         [106, 3, 0, 1, 2, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 21, 11],
    "No declarada":         [843, 61, 7, 3, 2, 1, 2, 7, 2, 2, 1, 1, 2, 2, 0, 16, 2293],
}
C45_ROW_TOTALS = {"Republica Dominicana": 19687, "Estados Unidos": 1047,
                  "Espana": 137, "Venezuela": 93, "Puerto Rico": 67,
                  "Canada": 58, "Haiti": 47, "Italia": 47, "Colombia": 40,
                  "Alemania": 19, "Mexico": 19, "Cuba": 18, "Holanda": 16,
                  "Francia": 13, "Peru": 11, "Otros paises": 147,
                  "No declarada": 3245}

# ------------- Cuadro 3.2 (p.83) marriages by type, region and province
# (total, civil, canonico, otros_religiosos)
C32 = {
    'Republica Dominicana'      : (40750, 35635, 3002, 2113),
    'Region Ozama'              : (15434, 13248, 1011, 1175),
    'Distrito Nacional'         : (5574, 4803, 585, 186),
    'Santo Domingo'             : (9860, 8445, 426, 989),
    'Region Cibao Norte'        : (6835, 5948, 676, 211),
    'Espaillat'                 : (1142, 993, 141, 8),
    'Puerto Plata'              : (1507, 1293, 80, 134),
    'Santiago'                  : (4186, 3662, 455, 69),
    'Region Cibao Sur'          : (3303, 2810, 435, 58),
    'La Vega'                   : (1753, 1462, 272, 19),
    'Sanchez Ramirez'           : (558, 497, 51, 10),
    'Monsenor Nouel'            : (992, 851, 112, 29),
    'Region Cibao Nordeste'     : (2652, 2292, 263, 97),
    'Duarte'                    : (1121, 976, 121, 24),
    'Maria Trinidad Sanchez'    : (588, 524, 44, 20),
    'Hermanas Mirabal'          : (473, 423, 50, 0),
    'Samana'                    : (470, 369, 48, 53),
    'Region Cibao Noroeste'     : (1502, 1375, 105, 22),
    'Dajabon'                   : (159, 155, 4, 0),
    'Monte Cristi'              : (432, 395, 17, 20),
    'Santiago Rodriguez'        : (236, 194, 42, 0),
    'Valverde'                  : (675, 631, 42, 2),
    'Region Valdesia'           : (3151, 2780, 125, 246),
    'Peravia'                   : (673, 641, 22, 10),
    'San Cristobal'             : (2270, 1937, 97, 236),
    'San Jose de Ocoa'          : (208, 202, 6, 0),
    'Region Enriquillo'         : (1090, 1080, 8, 2),
    'Baoruco'                   : (311, 311, 0, 0),
    'Barahona'                  : (604, 594, 8, 2),
    'Independencia'             : (137, 137, 0, 0),
    'Pedernales'                : (38, 38, 0, 0),
    'Region El Valle'           : (1237, 1157, 34, 46),
    'Azua'                      : (749, 704, 17, 28),
    'Elias Pina'                : (58, 50, 5, 3),
    'San Juan'                  : (430, 403, 12, 15),
    'Region Yuma'               : (3296, 2851, 243, 202),
    'El Seibo'                  : (206, 149, 12, 45),
    'La Altagracia'             : (1958, 1791, 143, 24),
    'La Romana'                 : (1132, 911, 88, 133),
    'Region Higuamo'            : (2250, 2094, 102, 54),
    'San Pedro de Macoris'      : (1396, 1308, 55, 33),
    'Monte Plata'               : (545, 507, 38, 0),
    'Hato Mayor'                : (309, 279, 9, 21),
}

# ------------------- Cuadro 3.4 (p.85) marriages by type, national
C34 = [("Total", 40750, 100.0), ("Civil", 35635, 87.4),
       ("Canonico", 3002, 7.4), ("Otros religiosos", 2113, 5.2)]

# ------------------------ Cuadro 4.3 (p.95) divorces by legal cause
C43 = [("Total", 24711, 100.00),
       ("Incompatibilidad de caracteres", 8459, 34.23),
       ("Mutuo consentimiento", 16252, 65.77)]
