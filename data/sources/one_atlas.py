"""
ONE -- Atlas de Genero de la Republica Dominicana 2020, violence dimension.

Cuadros 13-22, extracted by extract_atlas.py.

This is couple-RELATED data that yields no couplings: it measures women,
not dyads, so neither partner's attributes are cross-tabulated and
nothing here can enter the `dyad` layer. It is loaded into `fact` as
context for the pairing work, and the non-partner spheres (public,
school, work, community) are loaded alongside the partner ones precisely
so the contrast is available -- an intimate-partner figure means little
without the other spheres measured on the same population.

Two cautions that must travel with these numbers:

1. TWO INCOMPATIBLE GEOGRAPHIES. Cuadros 13-20 use four macro-regions
   (Gran Santo Domingo / Sur / Este / Norte o Cibao) that do NOT nest
   into the ten planning regions used by Cuadros 21-22 and by every
   other source in this database. They are stored at level
   'macroregion', deliberately unlinked to the region tree, so a join
   cannot silently mix them.

2. TWO DIFFERENT KINDS OF NUMBER. Cuadros 13-20 are ENESIM 2018 survey
   estimates and carry sampling error the Atlas does not publish;
   Cuadros 21-22 are administrative counts. Do not put them on one axis.
"""
import csv

DOCUMENT = dict(
    source_id=5, institution="ONE", instrument="other",
    publication="Atlas de Genero de la Republica Dominicana 2020",
    edition_year=2020, url=None,
    local_path="data/raw/one-atlas-genero-2020-violencia.csv",
    sha256="e1c058ab60e8f7f3fa1e140328982ad54cf93e90c78999d1b5bd42162df3b3b9",
    page_count=85,
)

MACROREGIONS = ["Gran Santo Domingo", "Sur", "Este", "Norte o Cibao"]

# Short scope labels for the survey cuadros, from their indicator text.
SCOPE = {
    13: "publico_y_o_privado_o_pareja",
    14: "publico",
    15: "privado_familiar_o_pareja",
    16: "familiar",
    17: "pareja_intima",
    18: "escolar",
    19: "laboral",
    20: "comunitario",
}
SURVEY = set(SCOPE)
ADMIN = {21: "death_classification", 22: "perpetrator_relation"}


def read(path):
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            yield dict(cuadro=int(r["cuadro"]), indicator=r["indicator"],
                       source_note=r["source_note"],
                       partner=int(r["partner_specific"]),
                       section=r["section"], label=r["label"],
                       year=int(r["year"]) if r["year"] else None,
                       measure=r["measure"], value=float(r["value"]))
