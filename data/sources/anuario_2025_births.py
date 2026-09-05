"""
ONE -- Anuario de Estadisticas Vitales 2025, birth cuadros with parent
pairings. Extracted by extract_births.py.

  1.2  mother nationality x father nationality   (324 cells, 18x18)
  1.3  mother's marital status, registration timing, month of occurrence
  1.4  mother age band x father age band         (121 cells, 11x11)

These are the two couplings the marriage cuadros cannot give, over a
different population: 85.6% of these mothers are recorded 'soltera', so
parent pairings reach unions that never enter the marriage registry.

Both pairing cuadros reconcile exactly -- every printed row total equals
the sum of its cells -- which is the check Cuadro 3.5 fails.

The row and column label sets are NOT the same: mothers include Ecuador
and Rusia, fathers include Francia and Holanda. A symmetry query must
therefore tolerate a missing counterpart rather than assume a square
matrix.
"""
import csv

# Section of Cuadro 1.3 -> dimension name.
C13_DIMS = {
    "estado civil de la madre": "marital_status",
    "tipo de registro del nacimiento": "registration_timing",
    "mes de ocurrencia": "month",
}


def read(path):
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            yield (r["cuadro"], r["vital_event"], r["dim1_name"],
                   r["dim1_value"], r["dim2_name"], r["dim2_value"],
                   float(r["value"]))
