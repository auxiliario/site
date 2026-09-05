#!/usr/bin/env python3
"""
Build dr_stats.db.

    python build.py                  # full rebuild
    python build.py --views-only     # reapply views.sql to an existing db
    python build.py --db path.db

The build is idempotent: `fact` carries a stored natural key with a unique
index, so re-running a loader updates rows instead of doubling the table.
That is what makes it safe to point this at one database and add editions
one at a time.

Order matters and is enforced: vocabulary -> geography -> facts. A fact
whose measure, basis, vital_event or dimension name is not in `vocab` is
rejected by a trigger, so an unannounced category in a new edition stops
the build rather than forking a dimension.
"""
import argparse, datetime, os, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "sources"))

import reference as R                      # noqa: E402
import acquisition as ACQ                  # noqa: E402
import anuario_2025 as A25                 # noqa: E402
import anuario_2025_births as BIRTHS       # noqa: E402
import anuario_2025_rotated as ROT         # noqa: E402
import one_proyecciones as PROJ            # noqa: E402
import one_subnacional as SUBNAC           # noqa: E402
import one_cifras as CIFRAS                # noqa: E402
import one_atlas as ATLAS                  # noqa: E402

SCHEMA_VERSION = "2.0"


# =====================================================================
# loader context
# =====================================================================
class Build:
    def __init__(self, con):
        self.con = con
        self.c = con.cursor()
        self._tid = 0
        self.tables = {}          # cuadro -> table_id

    # ---------------------------------------------------------- reference
    def load_reference(self):
        c = self.c
        c.executemany("INSERT INTO vocab VALUES (?,?,?,?,?,?)",
                      [(d, t, l, r, s, n) for d, t, l, r, s, n in R.VOCAB])
        c.executemany(
            "INSERT INTO age_band_ref VALUES (?,?,?,?,?,?)",
            [(b, lo, hi,
              None if lo is None else (lo + hi) / 2 if hi is not None else lo + 2.5,
              res, order) for b, lo, hi, res, order in R.AGE_BANDS])
        c.executemany("INSERT INTO nationality_ref VALUES (?,?,?,?,?)",
                      R.NATIONALITIES)
        c.executemany("INSERT INTO construct_registry VALUES (?,?,?)",
                      R.CONSTRUCTS)

        # geography: national -> region -> province
        self.geo = {}
        self.macro = {}
        c.execute("INSERT INTO geography VALUES (1,'national',NULL,NULL,0,?,?,NULL)",
                  ("Republica Dominicana", R.fold("Republica Dominicana")))
        self.geo[R.fold("Republica Dominicana")] = 1
        for alias in ("Total en el pais", "Total pais", "Total"):
            self.geo[R.fold(alias)] = 1
        gid = 2
        for region, provinces in R.REGIONS.items():
            c.execute("INSERT INTO geography VALUES (?,'region',NULL,NULL,0,?,?,1)",
                      (gid, region, R.fold(region)))
            self.geo[R.fold(region)] = gid
            rid, gid = gid, gid + 1
            for p in provinces:
                c.execute(
                    "INSERT INTO geography VALUES (?,'province',?,?,0,?,?,?)",
                    (gid, R.PROVINCE_CODES.get(p), "ONE_provincia",
                     p, R.fold(p), rid))
                self.geo[R.fold(p)] = gid
                gid += 1

    def load_macroregions(self, names, start_id=1000):
        """The Atlas's four macro-regions. Deliberately parentless: they do
        not nest into the ten planning regions, and giving them a parent
        would invite a rollup that is simply wrong."""
        for i, n in enumerate(names):
            gid = start_id + i
            self.c.execute(
                "INSERT INTO geography VALUES (?,'macroregion',NULL,NULL,0,?,?,NULL)",
                (gid, n, R.fold(n)))
            self.macro[R.fold(n)] = gid

    def geo_id(self, name):
        key = R.fold(name)
        if key in self.geo:
            return self.geo[key]
        for printed, canonical in R.GEO_ALIASES.items():
            if R.fold(printed) == key:
                return self.geo.get(R.fold(canonical))
        # bare region name, e.g. "Cibao Norte" for "Region Cibao Norte"
        return self.geo.get(R.fold("Region " + name.strip()))

    # ------------------------------------------------------------- tables
    def table(self, source_id, cuadro, title, page, event, method,
              verified=1, notes=None):
        self._tid += 1
        self.c.execute(
            "INSERT INTO source_table (table_id,source_id,cuadro,title_es,"
            "page_number,vital_event,extraction_method,verified_visually,"
            "trust,trust_note,notes) VALUES (?,?,?,?,?,?,?,?, 'unverified',NULL,?)",
            (self._tid, source_id, cuadro, title, page, event, method,
             verified, notes))
        self.tables[cuadro] = self._tid
        return self._tid

    # -------------------------------------------------------------- facts
    def fact(self, table_id, measure, value, event=None, *, year, basis=None,
             geo=None, dims=(), marginal=0, symbol=None, note=None,
             edition=None):
        d = list(dims) + [None] * (8 - len(dims))
        self.c.execute(
            """INSERT INTO fact
               (table_id,reference_year,edition_year,vital_event,measure,value,
                value_symbol,basis,geo_id,dim1_name,dim1_value,dim2_name,
                dim2_value,dim3_name,dim3_value,dim4_name,dim4_value,
                is_marginal,anomaly_flag,note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?)
               ON CONFLICT(nk) DO UPDATE SET
                 value=excluded.value, value_symbol=excluded.value_symbol,
                 is_marginal=excluded.is_marginal, note=excluded.note""",
            (table_id, year, edition or self.edition, event, measure, value,
             symbol, basis, geo, *d, marginal, note))


# =====================================================================
# generic loaders
# =====================================================================
def load_crosstab(b, tid, event, rows, cols, row_dim, col_dim,
                  row_totals=None, col_totals=None, year=2025, basis="registro"):
    """Two-way cuadro. Cells and published marginals both stored; the
    marginals are never used to correct the cells."""
    for row_key, values in rows.items():
        for col_key, v in zip(cols, values):
            b.fact(tid, "count", v, event, year=year, basis=basis, geo=1,
                   dims=(row_dim, row_key, col_dim, col_key))
        if row_totals is not None:
            b.fact(tid, "count", row_totals[row_key], event, year=year,
                   basis=basis, geo=1,
                   dims=(row_dim, row_key, col_dim, "TOTAL"), marginal=1)
    if col_totals is not None:
        for col_key, v in zip(cols, col_totals):
            b.fact(tid, "count", v, event, year=year, basis=basis, geo=1,
                   dims=(row_dim, "TOTAL", col_dim, col_key), marginal=1)


# =====================================================================
# edition ingest: Anuario 2025
# =====================================================================
def ingest_anuario_2025(b):
    d = A25.DOCUMENT
    b.edition = d["edition_year"]
    b.c.execute(
        "INSERT INTO source_document (source_id,institution,instrument,"
        "publication,edition_year,url,local_path,sha256,retrieved_at,"
        "page_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (d["source_id"], d["institution"], d["instrument"], d["publication"],
         d["edition_year"], d["url"], d["local_path"], d["sha256"],
         datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         d["page_count"]))
    sid = d["source_id"]

    # ---- Cuadro 1: EMNup series, 2013-2025 -----------------------------
    t = b.table(sid, "Cuadro 1",
                "Edad Media a la Nupcialidad, por ano, segun sexo, 2013-2025",
                37, "marriage", "pdftotext -layout",
                notes="Synthetic-cohort measure. Restated between editions; "
                      "compare via v_series_restatement, never by overwriting.")
    for year, both, male, female, diff in A25.EMNUP:
        b.fact(t, "mean_age", both, "marriage", year=year, geo=1,
               dims=("construct", "EMNup", "sex", "both"))
        b.fact(t, "mean_age", male, "marriage", year=year, geo=1,
               dims=("construct", "EMNup", "sex", "male"))
        b.fact(t, "mean_age", female, "marriage", year=year, geo=1,
               dims=("construct", "EMNup", "sex", "female"))
        b.fact(t, "age_gap_years", diff, "marriage", year=year, geo=1,
               dims=("construct", "EMNup"))

    # ---- Sec. 3.1.3: observed means -- the OTHER construct --------------
    t = b.table(sid, "Sec. 3.1.3", "Edad promedio de los contrayentes, 2025",
                33, "marriage", "narrative text",
                notes="Observed mean of those who married in the year. "
                      "Distinct from EMNup; see construct_registry.")
    b.fact(t, "mean_age", A25.OBSERVED_MEAN["male"], "marriage", year=2025,
           basis="registro", geo=1,
           dims=("construct", "observed_mean_age_at_marriage", "sex", "male"))
    b.fact(t, "mean_age", A25.OBSERVED_MEAN["female"], "marriage", year=2025,
           basis="registro", geo=1,
           dims=("construct", "observed_mean_age_at_marriage", "sex", "female"))
    b.fact(t, "age_gap_years", A25.OBSERVED_MEAN["gap"], "marriage", year=2025,
           basis="registro", geo=1,
           dims=("construct", "observed_mean_age_at_marriage"))

    # ---- Cuadro 3.3: bride age x groom age ------------------------------
    t = b.table(sid, "Cuadro 3.3",
                "Matrimonios registrados por grupos de edades del contrayente, "
                "segun grupos de edades de la contrayente, 2025",
                84, "marriage", "pdftotext -layout")
    load_crosstab(b, t, "marriage", A25.C33, A25.AGE_BANDS,
                  "bride_age_band", "groom_age_band",
                  row_totals=A25.C33_ROW_TOTALS)

    # ---- Cuadro 3.5: bride nationality x groom nationality --------------
    t = b.table(sid, "Cuadro 3.5",
                "Matrimonios registrados por pais de nacionalidad del "
                "contrayente, segun pais de nacionalidad de la contrayente, 2025",
                85, "marriage",
                "text layer, pp.85-86 stitched; verified by extract_crosstab.py",
                notes="Printed across pp.85-86 ('continuacion'). Interior "
                      "cells do not reconcile with either set of published "
                      "marginals IN THE SOURCE. See known_issue 1.")
    load_crosstab(b, t, "marriage", A25.C35, A25.C35_COLS,
                  "bride_nationality", "groom_nationality",
                  row_totals=A25.C35_ROW_TOTALS, col_totals=A25.C35_COL_TOTALS)

    # ---- Cuadro 4.5: wife nationality x husband nationality -------------
    t = b.table(sid, "Cuadro 4.5",
                "Divorcios registrados segun el pais de nacionalidad del "
                "divorciado y de la divorciada, 2025",
                96, "divorce", "pdftotext -layout",
                notes="Foreign-pair dissolutions occurring abroad never enter "
                      "this table; it is not a denominator for anything.")
    load_crosstab(b, t, "divorce", A25.C45, A25.C45_COLS,
                  "wife_nationality", "husband_nationality",
                  row_totals=A25.C45_ROW_TOTALS)

    # ---- Cuadro 3.2: marriages by type, region and province -------------
    t = b.table(sid, "Cuadro 3.2",
                "Matrimonios registrados por tipo, segun region y provincia, 2025",
                83, "marriage", "pdftotext -layout regex",
                notes="Basis is REGISTRO, not residence: destination-wedding "
                      "provinces (La Altagracia) are inflated.")
    for name, (total, civil, canon, otros) in A25.C32.items():
        g = b.geo_id(name)
        if g is None:
            raise SystemExit(f"Cuadro 3.2: unmapped geography {name!r}")
        b.fact(t, "count", total, "marriage", year=2025, basis="registro",
               geo=g, dims=("marriage_type", "Total"), marginal=1)
        for label, v in (("Civil", civil), ("Canonico", canon),
                         ("Otros religiosos", otros)):
            b.fact(t, "count", v, "marriage", year=2025, basis="registro",
                   geo=g, dims=("marriage_type", label))

    # ---- Cuadro 3.4 / 4.3 ----------------------------------------------
    t = b.table(sid, "Cuadro 3.4",
                "Matrimonios registrados y porcentaje, segun tipo de "
                "matrimonio, 2025", 85, "marriage", "pdftotext -layout")
    for label, cnt, pct in A25.C34:
        m = 1 if label == "Total" else 0
        b.fact(t, "count", cnt, "marriage", year=2025, basis="registro", geo=1,
               dims=("marriage_type", label), marginal=m)
        b.fact(t, "percent", pct, "marriage", year=2025, basis="registro", geo=1,
               dims=("marriage_type", label), marginal=m)

    t = b.table(sid, "Cuadro 4.3", "Divorcios registrados segun la causa, 2025",
                95, "divorce", "pdftotext -layout")
    for label, cnt, pct in A25.C43:
        m = 1 if label == "Total" else 0
        b.fact(t, "count", cnt, "divorce", year=2025, basis="registro", geo=1,
               dims=("divorce_cause", label), marginal=m)
        b.fact(t, "percent", pct, "divorce", year=2025, basis="registro", geo=1,
               dims=("divorce_cause", label), marginal=m)


# =====================================================================
# reconciliation -- computed from the facts, stored as data
# =====================================================================
def reconcile(con):
    """Recompute `reconciliation` from the facts and derive source_table.trust.

    Two tolerances, because the sources round differently: counts must
    agree exactly, published means and differences are allowed one unit in
    the last printed decimal (ONE rounds each column independently, so a
    published `both` can sit 0.01 off the midpoint of the two it averages).
    """
    TOL_COUNT = 1e-6
    TOL_ROUND = 0.011

    c = con.cursor()
    c.execute("DELETE FROM reconciliation")
    rows = []

    def add(tid, axis, key, pub, summed, tol=TOL_COUNT):
        delta = None if pub is None else round(pub - summed, 6)
        pct = None if not pub else round(100.0 * delta / pub, 4)
        verdict = ("no_published_total" if pub is None
                   else "ok" if abs(delta) <= tol else "mismatch")
        rows.append((tid, axis, str(key), pub, summed, delta, pct, verdict))

    tids = [r[0] for r in con.execute("SELECT table_id FROM source_table")]
    for tid in tids:
        two_way = con.execute(
            "SELECT COUNT(*) FROM fact WHERE table_id=? AND dim2_name IS NOT NULL"
            "  AND dim1_name <> 'construct'", (tid,)).fetchone()[0]

        if two_way:
            for axis, cell_col, marg_col in (("row", "dim1_value", "dim2_value"),
                                             ("column", "dim2_value", "dim1_value")):
                cells = con.execute(
                    f"SELECT {cell_col}, SUM(value) FROM fact "
                    f"WHERE table_id=? AND is_marginal=0 GROUP BY 1",
                    (tid,)).fetchall()
                for key, summed in cells:
                    pub = con.execute(
                        f"SELECT value FROM fact WHERE table_id=? AND is_marginal=1"
                        f" AND {cell_col}=? AND {marg_col}='TOTAL'",
                        (tid, key)).fetchone()
                    add(tid, axis, key, pub[0] if pub else None, summed)
        else:
            # one-way cuadro: published Total vs its own components,
            # per geography and per measure
            # reference_year MUST be in the grouping: a cuadro covering
            # five years otherwise sums all of them against a single
            # published total and reports a spurious mismatch.
            # dim1_name MUST be in the grouping alongside geo, measure and
            # year. A cuadro can stack several independent distributions of
            # the same universe -- Cuadro 1.3 gives births by marital
            # status, by registration timing AND by month -- and summing
            # them together counts every birth once per distribution.
            groups = con.execute(
                "SELECT geo_id, measure, reference_year, "
                "       COALESCE(dim1_name,''), SUM(value) FROM fact "
                "WHERE table_id=? AND is_marginal=0 AND measure IN "
                "('count','percent') GROUP BY 1,2,3,4", (tid,)).fetchall()
            for geo, meas, yr, d1, summed in groups:
                pub = con.execute(
                    "SELECT value FROM fact WHERE table_id=? AND is_marginal=1 "
                    "AND measure=? AND reference_year=? "
                    "AND COALESCE(dim1_name,'')=? "
                    "AND COALESCE(geo_id,-1)=COALESCE(?,-1)",
                    (tid, meas, yr, d1, geo)).fetchone()
                if pub:
                    tol = TOL_ROUND if meas == "percent" else TOL_COUNT
                    add(tid, "row", f"{yr} geo={geo};{meas};{d1}",
                        pub[0], summed, tol)

            # Geography cuadros carry the dimension in geo_id rather than in
            # a dim slot, so the grouping above finds nothing to compare.
            # Check the provinces against the national total, per year.
            for yr, summed in con.execute(
                    "SELECT reference_year, SUM(value) FROM fact f "
                    "JOIN geography g USING(geo_id) "
                    "WHERE f.table_id=? AND g.level='province' "
                    "AND f.dim1_name IS NULL GROUP BY 1", (tid,)).fetchall():
                pub = con.execute(
                    "SELECT value FROM fact WHERE table_id=? AND geo_id=1 "
                    "AND reference_year=? AND dim1_name IS NULL",
                    (tid, yr)).fetchone()
                if pub:
                    add(tid, "column", f"{yr} sum of 32 provinces",
                        pub[0], summed)

    # Mean-age cuadros carry their own arithmetic check: the published
    # difference must equal male - female, and `both` their midpoint.
    for tid, year, construct, male, female, both, diff in con.execute("""
            SELECT table_id, reference_year, dim1_value,
                   MAX(CASE WHEN dim2_value='male'   THEN value END),
                   MAX(CASE WHEN dim2_value='female' THEN value END),
                   MAX(CASE WHEN dim2_value='both'   THEN value END),
                   MAX(CASE WHEN measure='age_gap_years' THEN value END)
            FROM fact WHERE dim1_name='construct'
            GROUP BY table_id, reference_year, dim1_value""").fetchall():
        if None not in (male, female, diff):
            add(tid, "row", f"{year} {construct}:gap", diff,
                round(male - female, 2), TOL_ROUND)
        if None not in (male, female, both):
            add(tid, "row", f"{year} {construct}:midpoint", both,
                round((male + female) / 2, 2), TOL_ROUND)

    # Cross-cuadro control totals: independent cuadros describing the same
    # universe must agree. This is the check v1 never ran, and the one that
    # located the Cuadro 3.5 defect.
    control = {
        "marriage": con.execute(
            "SELECT value FROM fact f JOIN source_table st USING(table_id) "
            "WHERE st.cuadro='Cuadro 3.4' AND f.measure='count' "
            "AND f.dim1_value='Total'").fetchone()[0],
        "divorce": con.execute(
            "SELECT value FROM fact f JOIN source_table st USING(table_id) "
            "WHERE st.cuadro='Cuadro 4.3' AND f.measure='count' "
            "AND f.dim1_value='Total'").fetchone()[0],
    }
    CROSS = (
        ("Cuadro 3.3", "marriage", "cells",         "is_marginal=0"),
        ("Cuadro 3.3", "marriage", "marginals(row)", "is_marginal=1"),
        ("Cuadro 3.5", "marriage", "cells",         "is_marginal=0"),
        ("Cuadro 3.5", "marriage", "marginals(row)",
         "is_marginal=1 AND dim2_value='TOTAL'"),
        ("Cuadro 3.5", "marriage", "marginals(col)",
         "is_marginal=1 AND dim1_value='TOTAL'"),
        ("Cuadro 3.2", "marriage", "marginals(national)",
         "is_marginal=1 AND geo_id=1"),
        ("Cuadro 3.2", "marriage", "cells(national)",
         "is_marginal=0 AND geo_id=1"),
        ("Cuadro 3.2", "marriage", "marginals(sum of 32 provinces)",
         "is_marginal=1 AND geo_id IN (SELECT geo_id FROM geography "
         "WHERE level='province')"),
        ("Cuadro 3.2", "marriage", "marginals(sum of 10 regions)",
         "is_marginal=1 AND geo_id IN (SELECT geo_id FROM geography "
         "WHERE level='region')"),
        ("Cuadro 4.5", "divorce",  "cells",         "is_marginal=0"),
        ("Cuadro 4.5", "divorce",  "marginals(row)", "is_marginal=1"),
    )
    for cuadro, event, label, expr in CROSS:
        tid = con.execute("SELECT table_id FROM source_table WHERE cuadro=?",
                          (cuadro,)).fetchone()[0]
        summed = con.execute(
            f"SELECT SUM(value) FROM fact WHERE table_id=? AND measure='count' "
            f"AND {expr}", (tid,)).fetchone()[0]
        add(tid, "cross_table", f"{label} vs {event} control total",
            control[event], summed)

    c.executemany("INSERT INTO reconciliation (table_id,axis,key_value,"
                  "published_total,summed_cells,delta,pct_delta,verdict) "
                  "VALUES (?,?,?,?,?,?,?,?)", rows)

    # --- trust, derived from the above ---------------------------------
    # verified        nothing mismatches
    # marginals_only  marginals agree with the independent control total
    #                 but the interior cells do not: quote the margins only
    # disputed        the marginals themselves disagree
    # unverified      no arithmetic check exists for this cuadro
    for tid in tids:
        checks = con.execute(
            "SELECT axis,key_value,verdict,delta FROM reconciliation "
            "WHERE table_id=?", (tid,)).fetchall()
        real = [x for x in checks if x[2] != "no_published_total"]
        if not real:
            trust, note = "unverified", "no arithmetic check available"
        elif all(v == "ok" for _, _, v, _ in real):
            trust, note = "verified", None
        else:
            cross = [x for x in real if x[0] == "cross_table"]
            marg_ok = bool(cross) and all(
                v == "ok" for _, k, v, _ in cross if "marginals" in k)
            cell_bad = any(v == "mismatch" for _, k, v, _ in cross
                           if "cells" in k)
            bad = sum(1 for _, _, v, _ in real if v == "mismatch")
            worst = max((abs(d) for _, _, v, d in real
                         if v == "mismatch" and d is not None), default=0)
            if marg_ok and cell_bad:
                trust = "marginals_only"
                note = (f"{bad} of {len(real)} checks fail (largest |delta| "
                        f"{worst:g}). Published marginals agree with the "
                        f"independent control total; the interior cells do "
                        f"not. Use the marginals; do not quote single cells.")
            else:
                trust = "disputed"
                note = (f"{bad} of {len(real)} checks fail "
                        f"(largest |delta| {worst:g}).")
        con.execute("UPDATE source_table SET trust=?, trust_note=? "
                    "WHERE table_id=?", (trust, note, tid))

    # Backward-compatible per-fact flag: v1 queries select on it.
    con.execute("UPDATE fact SET anomaly_flag=NULL")
    con.execute("""
        UPDATE fact SET anomaly_flag='row_total_mismatch'
        WHERE EXISTS (SELECT 1 FROM reconciliation r
                      WHERE r.table_id = fact.table_id
                        AND r.axis     = 'row'
                        AND r.verdict  = 'mismatch'
                        AND r.key_value = fact.dim1_value)""")
    con.commit()


# =====================================================================
# denominators
# =====================================================================
PROJ_YEARS = range(2013, 2031)


def ingest_proyecciones(b):
    """National population by sex and age band -- the exposure base.

    Skipped with a warning rather than failing if the workbook is absent,
    so the build still runs for anyone who has only the Anuario.
    """
    d = PROJ.DOCUMENT
    path = os.path.join(HERE, "raw",
                        "one-proyecciones-edades-simples-1950-2100.xlsx")
    if not os.path.exists(path):
        print(f"  note: {path} absent; population left empty")
        return
    b.c.execute(
        "INSERT INTO source_document (source_id,institution,instrument,"
        "publication,edition_year,url,local_path,sha256,retrieved_at,"
        "page_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (d["source_id"], d["institution"], d["instrument"], d["publication"],
         d["edition_year"], d["url"], d["local_path"], d["sha256"],
         datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         d["page_count"]))
    rows = [(d["source_id"], year, d["edition_year"], 1, sex, band, None, None,
             "persons", persons)
            for year, sex, band, persons in PROJ.read(path, PROJ_YEARS)]
    b.c.executemany(
        "INSERT INTO population (source_id,reference_year,edition_year,geo_id,"
        "sex,age_band,nationality,marital_status,measure,value) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    print(f"  population: {len(rows)} rows, "
          f"{min(PROJ_YEARS)}-{max(PROJ_YEARS)}, national only")


def ingest_births_2025(b):
    """Cuadros 1.2 / 1.3 / 1.4 -- parent pairings and maternal status."""
    path = os.path.join(HERE, "raw", "anuario-2025-births.csv")
    if not os.path.exists(path):
        print(f"  note: {path} absent; birth cuadros skipped")
        return
    b.edition = 2025
    META = {
        "1.2": ("Cuadro 1.2", "Nacimientos ocurridos segun pais de "
                "nacionalidad del padre y de la madre, 2025", 48,
                "Printed across pp.48-49 in three column blocks. Row and "
                "column label sets differ: mothers include Ecuador and "
                "Rusia, fathers Francia and Holanda."),
        "1.3": ("Cuadro 1.3", "Nacimientos ocurridos, segun estado civil de "
                "la madre, tipo de registro y mes de ocurrencia, 2025", 50,
                "The only union-status data in the database."),
        "1.4": ("Cuadro 1.4", "Nacimientos ocurridos segun los grupos de "
                "edades del padre y la madre al momento del nacimiento, 2025",
                51, None),
    }
    tids, n = {}, 0
    for cuadro, event, d1n, d1v, d2n, d2v, value in BIRTHS.read(path):
        if cuadro not in tids:
            c, title, page, note = META[cuadro]
            tids[cuadro] = b.table(1, c, title, page, event,
                                   "text layer via extract_births.py",
                                   notes=note)
        t = tids[cuadro]
        if cuadro == "1.3":
            dim = BIRTHS.C13_DIMS.get(d1v)
            if dim is None:                       # the cuadro's own grand total
                b.fact(t, "count", value, "birth", year=2025, basis="ocurrencia",
                       geo=1, dims=("marital_status", "TOTAL"), marginal=1)
            else:
                marg = 1 if d2v.lower().startswith(("estado civil",
                                                    "tipo de registro",
                                                    "mes de ocurrencia")) else 0
                b.fact(t, "count", value, "birth", year=2025,
                       basis="ocurrencia", geo=1,
                       dims=(dim, "TOTAL" if marg else d2v), marginal=marg)
        else:
            row = "TOTAL" if d1v.lower().startswith("total") else d1v
            marg = 1 if (row == "TOTAL" or d2v == "TOTAL") else 0
            b.fact(t, "count", value, "birth", year=2025, basis="ocurrencia",
                   geo=1, dims=(d1n, row, d2n, d2v), marginal=marg)
        n += 1
    print(f"  Anuario 2025 births: {n} facts across {len(tids)} cuadros")


def ingest_rotated_2025(b):
    """Cuadros on rotated pages -- see anuario_2025_rotated for why they
    were invisible until now."""
    path = os.path.join(HERE, "raw", "anuario-2025-rotated.csv")
    if not os.path.exists(path):
        print(f"  note: {path} absent; rotated cuadros skipped")
        return
    b.edition = 2025
    tids, n, unmapped = {}, 0, set()
    for cuadro, d1n, d1v, d2n, d2v, value, anomaly, sex in ROT.read(path):
        if cuadro not in tids:
            title, page = ROT.TITLES[cuadro]
            tids[cuadro] = b.table(
                1, f"Cuadro {cuadro}", title, page, ROT.EVENT[cuadro],
                "rotated-page de-rotation via extract_rotated.py",
                notes="Printed on a rotated page with character-reversed "
                      "word storage; invisible to plain text extraction. "
                      "Every row total verified against its cells.")
        t = tids[cuadro]
        if cuadro == "1.12":
            # Rows are the year the birth OCCURRED, columns the year it was
            # REGISTERED. reference_year takes the registration year, so the
            # registration lag is queryable as a real date difference.
            b.fact(t, "count", value, "birth", year=int(d2v),
                   basis="registro", geo=1,
                   dims=("year_of_occurrence", d1v),
                   marginal=1 if d1v.lower().startswith("total") else 0,
                   note=anomaly)
            n += 1
            continue
        if cuadro == "2.6":
            g = b.geo_id(d1v)
            if g is None:
                unmapped.add(d1v)
                continue
            lvl = b.c.execute("SELECT level FROM geography WHERE geo_id=?",
                              (g,)).fetchone()[0]
            b.fact(t, "count", value, "death", year=2025, basis="registro",
                   geo=g, dims=("deceased_age_band", d2v, "sex", sex),
                   marginal=1 if (lvl != "province" or d2v == "TOTAL"
                                  or sex == "both") else 0,
                   note=anomaly)
            n += 1
            continue
        if d1n == "geography":
            g = b.geo_id(d1v)
            if g is None:
                unmapped.add(d1v)
                continue
            lvl = b.c.execute("SELECT level FROM geography WHERE geo_id=?",
                              (g,)).fetchone()[0]
            dim = ROT.DIM_FOR_GEO_ROWS[cuadro]
            b.fact(t, "count", value, ROT.EVENT[cuadro], year=2025,
                   basis=ROT.BASIS[cuadro], geo=g, dims=(dim, d2v),
                   marginal=1 if (lvl != "province" or d2v == "TOTAL"
                                  or d2v.startswith("TOTAL ")) else 0,
                   note=anomaly)
        else:
            b.fact(t, "count", value, ROT.EVENT[cuadro], year=2025,
                   basis=ROT.BASIS[cuadro], geo=1,
                   dims=(d1n, "TOTAL" if d1v.lower().startswith("total")
                         else d1v, d2n, d2v),
                   marginal=1 if (d1v.lower().startswith("total")
                                  or d2v == "TOTAL") else 0, note=anomaly)
        n += 1
    if unmapped:
        raise SystemExit(f"rotated: unmapped geographies {sorted(unmapped)}")
    print(f"  Anuario 2025 rotated: {n} facts across {len(tids)} cuadros")


def ingest_atlas(b):
    """Atlas de Genero violence cuadros -- couple CONTEXT, not couplings."""
    d = ATLAS.DOCUMENT
    path = os.path.join(HERE, "raw", "one-atlas-genero-2020-violencia.csv")
    if not os.path.exists(path):
        print(f"  note: {path} absent; Atlas cuadros skipped")
        return
    b.load_macroregions(ATLAS.MACROREGIONS)
    b.edition = d["edition_year"]
    b.c.execute(
        "INSERT INTO source_document (source_id,institution,instrument,"
        "publication,edition_year,url,local_path,sha256,retrieved_at,"
        "page_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (d["source_id"], d["institution"], d["instrument"], d["publication"],
         d["edition_year"], d["url"], d["local_path"], d["sha256"],
         datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         d["page_count"]))

    rows = list(ATLAS.read(path))
    tids, n, decade = {}, 0, {}
    for r in rows:
        c = r["cuadro"]
        if c not in tids:
            event = "partner_violence" if c in ATLAS.SURVEY else "femicide"
            tids[c] = b.table(
                d["source_id"], f"Cuadro {c}", r["indicator"][:220], 0, event,
                "pdfplumber table extraction via extract_atlas.py",
                notes=("ENESIM 2018 survey estimate; sampling error not "
                       "published by the Atlas. Macro-regions do not nest "
                       "into planning regions."
                       if c in ATLAS.SURVEY else
                       "Administrative records. Planning regions.") +
                      f" partner_specific={r['partner']}")
        t = tids[c]
        label, section = r["label"], r["section"]
        low = label.strip().lower()

        if r["measure"] == "count_total":          # the 2009-2018 column
            decade[(c, label)] = r["value"]
            continue

        if c in ATLAS.SURVEY:
            geo, dims = 1, ("violence_scope", ATLAS.SCOPE[c])
            marg = 1 if low in ("total", "pais", "país") else 0
            if section.startswith("zona"):
                dims = dims + ("residence_zone", label)
            elif section.startswith("macro"):
                g = b.macro.get(R.fold(label))
                if g is None:
                    raise SystemExit(f"Atlas: unknown macro-region {label!r}")
                geo = g
            b.fact(t, "percent", r["value"], "partner_violence",
                   year=r["year"], geo=geo, dims=dims, marginal=marg)
        else:
            geo, dims = 1, (ATLAS.ADMIN[c], label)
            marg = 1 if low == "total" else 0
            if section.startswith("region"):
                g = b.geo_id(label)
                if g is None:
                    raise SystemExit(f"Atlas: unknown region {label!r}")
                geo, dims = g, (ATLAS.ADMIN[c], "Total")
                marg = 1
            b.fact(t, "count", r["value"],
                   "femicide", year=r["year"], geo=geo, dims=dims,
                   marginal=marg)
        n += 1

    # The published 2009-2018 'Total' column is a check, not a fact: verify
    # it equals the sum of the years rather than storing it twice.
    bad = 0
    for (c, label), published in decade.items():
        got = sum(r["value"] for r in rows
                  if r["cuadro"] == c and r["label"] == label
                  and r["measure"] == "count")
        if abs(got - published) > 0.5:
            bad += 1
            print(f"    WARN Cuadro {c} {label!r}: years sum to {got:.0f}, "
                  f"published decade total {published:.0f}")
    b.edition = 2025
    print(f"  Atlas 2020: {n} facts across {len(tids)} cuadros; "
          f"{len(decade)} decade totals checked, {bad} mismatched")


def ingest_cifras(b):
    """Provincial and monthly marriage/divorce counts, 2016-2020."""
    d = CIFRAS.DOCUMENT
    path = os.path.join(HERE, "raw", "one-cifras-2021-vitales.csv")
    if not os.path.exists(path):
        print(f"  note: {path} absent; Cifras cuadros skipped")
        return
    b.edition = d["edition_year"]
    b.c.execute(
        "INSERT INTO source_document (source_id,institution,instrument,"
        "publication,edition_year,url,local_path,sha256,retrieved_at,"
        "page_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (d["source_id"], d["institution"], d["instrument"], d["publication"],
         d["edition_year"], d["url"], d["local_path"], d["sha256"],
         datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         d["page_count"]))
    tids = {}
    for cuadro, (title, page, event, kind) in CIFRAS.CUADROS.items():
        tids[cuadro] = b.table(d["source_id"], f"Cuadro {cuadro}", title, page,
                               event, "text layer via extract_cifras.py",
                               notes="basis=registro. Region rows kept and "
                                     "flagged marginal.")
    n, unmapped = 0, set()
    for cuadro, event, kind, label, year, value in CIFRAS.read(path):
        t = tids[cuadro]
        if kind == "geography":
            g = b.geo_id(label)
            if g is None:
                unmapped.add(label)
                continue
            lvl = b.c.execute("SELECT level FROM geography WHERE geo_id=?",
                              (g,)).fetchone()[0]
            b.fact(t, "count", value, event, year=year, basis="registro",
                   geo=g, marginal=0 if lvl == "province" else 1)
        else:
            b.fact(t, "count", value, event, year=year, basis="registro",
                   geo=1, dims=("month", label),
                   marginal=1 if label.lower().startswith("total") else 0)
        n += 1
    if unmapped:
        raise SystemExit(f"Cifras: unmapped geographies {sorted(unmapped)}")
    b.edition = 2025
    print(f"  Cifras 2021: {n} facts across 4 cuadros, 2016-2020")


def ingest_subnacional(b):
    """Provincial and regional denominators."""
    d = SUBNAC.DOCUMENT
    path = os.path.join(HERE, "raw",
                        "one-proyecciones-subnacionales-2000-2030.csv")
    if not os.path.exists(path):
        print(f"  note: {path} absent; provincial denominators skipped")
        return
    b.c.execute(
        "INSERT INTO source_document (source_id,institution,instrument,"
        "publication,edition_year,url,local_path,sha256,retrieved_at,"
        "page_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (d["source_id"], d["institution"], d["instrument"], d["publication"],
         d["edition_year"], d["url"], d["local_path"], d["sha256"],
         datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         d["page_count"]))
    rows, unmapped = [], set()
    for lvl, name, sex, band, year, persons in SUBNAC.read(path, set(PROJ_YEARS)):
        g = b.geo_id(name)
        if g is None:
            unmapped.add(name)
            continue
        rows.append((d["source_id"], year, d["edition_year"], g, sex, band,
                     None, None, "persons", persons))
    if unmapped:
        raise SystemExit(f"subnacional: unmapped geographies {sorted(unmapped)}")
    b.c.executemany(
        "INSERT INTO population (source_id,reference_year,edition_year,geo_id,"
        "sex,age_band,nationality,marital_status,measure,value) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    print(f"  population: +{len(rows)} rows, 32 provinces + 10 regions")


# =====================================================================
# LAYER 2 -- couplings
# =====================================================================
def seed_acquisition(con):
    con.execute("DELETE FROM acquisition")
    con.executemany(
        "INSERT INTO acquisition (tier,institution,dataset,vintages,grain,"
        "couple_linkage,est_couplings,access,redistributable,priority,verify,"
        "note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ACQ.TARGETS)
    # Nothing external is reachable from this session, so every remote
    # target starts blocked rather than pretending to be merely pending.
    con.execute("UPDATE acquisition SET status='blocked', blocked_by=? "
                "WHERE status='not_started'",
                ("host denied by this environment's egress policy (403 on "
                 "CONNECT); needs an allowlist change or a manual download",))
    con.execute("""UPDATE acquisition SET status='ingested', blocked_by=NULL
        WHERE dataset LIKE 'Anuario%' """)
    # National projections are loaded; the PROVINCIAL breakdown is not --
    # it lives in ONE's subnacional reports, which are PDFs.
    con.execute("UPDATE acquisition SET status='ingested', blocked_by=NULL, "
                "note=note||' National loaded from the edades-simples "
                "workbook; provincial and regional from the 2016 subnacional "
                "report, Cuadro 5.3.' WHERE dataset LIKE 'Estimaciones%'")
    con.commit()


def derive_dyads_from_cuadros(con):
    """Turn published cross-tab cells into weighted dyads.

    Every non-marginal cell of a two-way cuadro IS a set of couples: the
    cell (bride 25-29, groom 30-34) = 2,226 says 2,226 dyads share those
    two attributes. Loading them at grain='cell' means v_couplings works
    on the aggregates we already hold, and microdata later lands in the
    same table at grain='record' with no migration.

    TRUST GOVERNS ENTRY. A cuadro whose cells do not reconcile never
    becomes a dyad -- otherwise the couplings layer would launder exactly
    the numbers layer 1 marks as unusable.
    """
    con.execute("DELETE FROM dyad_attribute")
    con.execute("DELETE FROM dyad")

    ROLES = {"bride": ("bride", "groom", "female", "male"),
             "wife":  ("wife", "husband", "female", "male"),
             "mother": ("mother", "father", "female", "male")}
    # `vital_event` names the event; `dyad_type` names the relationship the
    # pair stands in. For a birth cuadro those differ: the event is a
    # birth, the dyad is its parents.
    DYAD_TYPE = {"birth": "birth_parents"}
    rows = con.execute("""
        SELECT f.fact_id, f.table_id, st.source_id, f.reference_year,
               f.edition_year, f.geo_id, f.basis, f.vital_event, f.value,
               f.dim1_name, f.dim1_value, f.dim2_name, f.dim2_value
        FROM fact f JOIN source_table st ON st.table_id=f.table_id
        WHERE f.is_marginal=0 AND f.value IS NOT NULL
          AND f.dim2_name IS NOT NULL AND f.dim1_name <> 'construct'
          AND st.trust = 'verified'""").fetchall()

    dyads, attrs, did = [], [], 0
    for (_fid, tid, sid, ry, ey, geo, basis, event, val,
         d1n, d1v, d2n, d2v) in rows:
        prefix = d1n.split("_")[0]
        if prefix not in ROLES:
            continue
        role_a, role_b, sex_a, sex_b = ROLES[prefix]
        attribute = d1n[len(prefix) + 1:]
        did += 1
        dyads.append((did, sid, tid, DYAD_TYPE.get(event, event), "cell",
                      ry, ey, geo, basis, role_a, role_b, sex_a, sex_b, val))
        attrs.append((did, "a", attribute, d1v, None))
        attrs.append((did, "b", attribute, d2v, None))

    con.executemany(
        "INSERT INTO dyad (dyad_id,source_id,table_id,dyad_type,grain,"
        "reference_year,edition_year,geo_id,basis,role_a,role_b,sex_a,sex_b,"
        "weight) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", dyads)
    con.executemany("INSERT INTO dyad_attribute VALUES (?,?,?,?,?)", attrs)
    con.commit()


def check_constraints(con):
    """Published marginals become tests the dyad layer must reproduce.

    Today the dyads are derived FROM those cuadros, so agreement is
    tautological and says only that the derivation is lossless. The
    moment a microdata source lands, the same checks become a real test
    of weighting and coverage -- which is the point of writing them now.
    """
    con.execute("DELETE FROM constraint_check")
    rows = []
    # Only pairing cuadros: summing a column of mean ages, or a table
    # that repeats its total across three marriage types, produces a
    # number that means nothing and a check that tests nothing.
    for tid, cuadro, control in con.execute("""
            SELECT st.table_id, st.cuadro,
                   (SELECT SUM(value) FROM fact
                     WHERE table_id=st.table_id AND is_marginal=0)
            FROM source_table st
            WHERE st.trust='verified'
              AND EXISTS (SELECT 1 FROM fact f WHERE f.table_id=st.table_id
                          AND f.dim2_name IS NOT NULL
                          AND (f.dim1_name LIKE 'bride%' OR
                               f.dim1_name LIKE 'wife%'  OR
                               f.dim1_name LIKE 'mother%'))""").fetchall():
        got = con.execute("SELECT SUM(weight) FROM dyad WHERE table_id=?",
                          (tid,)).fetchone()[0]
        if got is None:
            rows.append((tid, f"{cuadro}: dyad total vs published cells",
                         control, None, None, None, "not_yet_testable"))
            continue
        delta = round(got - control, 6)
        rows.append((tid, f"{cuadro}: dyad total vs published cells",
                     control, got, delta,
                     round(100.0 * delta / control, 4) if control else None,
                     "ok" if abs(delta) <= 1e-6 else "divergent"))
    con.executemany(
        "INSERT INTO constraint_check (table_id,description,published,"
        "from_dyads,delta,pct_delta,verdict) VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()


# =====================================================================
def register_known_issues(con):
    c = con.cursor()
    c.execute("DELETE FROM known_issue")
    c.executemany(
        "INSERT INTO known_issue (scope,ref,severity,summary,evidence,resolution)"
        " VALUES (?,?,?,?,?,?)", [
        ("source_table", "Cuadro 3.5", "high",
         "SETTLED 2026-09-05 against the source PDF: the defect is ONE's, "
         "not the extractor's. The published cuadro contradicts itself. "
         "Cells are now verified faithful and may be quoted AS PUBLISHED, "
         "with the contradiction disclosed; the margins and the interior "
         "cannot both be used in one figure.",
         "Verified against pp.85-86 of the PDF (sha256 42ec03d0...), which "
         "matches source_document byte for byte. The cuadro is printed "
         "across two pages: p.85 carries Total plus the first 8 country "
         "columns, p.86 the remaining 9 under 'continuacion'. All 17 "
         "printed row totals disagree with the cells printed beside them, "
         "and the Estados Unidos row total (1,565) is SMALLER than a single "
         "cell in that row (1,904) -- so the Total column cannot be a row "
         "total at all. Interior sums to 44,349; the row margins, the "
         "column margins and the Total/Total cell all give 40,750, matching "
         "Cuadros 3.2, 3.3 and 3.4. One transcription error was found and "
         "fixed: the Peru and Puerto Rico columns were transposed, "
         "mislabelling 8 cells and 2 column totals; 281 of 289 cells were "
         "exact. That transposition sat exactly at the p.85/p.86 stitch.",
         "No further extraction work. The margins are corroborated by three "
         "other cuadros; the interior is not corroborated by anything. Quote "
         "either, never both in one figure, and say which. trust stays "
         "'marginals_only' because that grades ARITHMETIC consistency; "
         "transcription_verified=1 records separately that the cells are a "
         "faithful copy. The mechanism behind ONE's 3,599 excess is not "
         "recoverable from the publication and would need a query to ONE."),

        ("coverage", "population", "medium",
         "National denominators are loaded; PROVINCIAL and "
         "MARITAL-STATUS denominators are not. Rates are crude "
         "age-specific rates, not rates on the population at risk.",
         "population holds 540 rows, 2013-2030, national only, from ONE's "
         "edades-simples projections (bands sum to the published total "
         "exactly; male+female equals both exactly). Two gaps remain. "
         "(1) The denominator is the TOTAL population of that sex and age, "
         "not the never-married population, so v_event_rate_by_age gives a "
         "crude marriage rate, not a nuptiality rate -- an age band already "
         "largely married has a smaller true population at risk and its "
         "rate is understated. (2) Nothing is provincial, so La Altagracia "
         "still cannot be interpreted, and nothing is by nationality, so "
         "mixed-nationality pairing still has no exposure base.",
         "Provincial: extract ONE's subnacional projection report "
         "(2000-2030, 2016 revision) which covers 2025; it is a PDF. "
         "Population at risk: marital-status distribution by sex, age and "
         "province from the 2022 census or ENHOGAR. By nationality: ENI "
         "immigrant stock. Each is a separate acquisition; the schema "
         "already carries geo_id, nationality and marital_status columns."),

        ("source_table", "Cuadro 2.1-12", "high",
         "San Jose de Ocoa's divorce rate is implausible and is almost "
         "certainly an artefact of the REGISTRO basis, not a local "
         "phenomenon.",
         "736 divorces in 2019 against a resident population of 54,960 = "
         "13.39 per 1,000, more than double the next province (Monsenor "
         "Nouel, 5.70) and 3.6x the national rate. A province of that size "
         "producing that many dissolutions is not credible; the likely "
         "cause is that divorces are counted where they are REGISTERED, and "
         "a court or oficialia there serves a much wider catchment.",
         "Do not report provincial divorce rates without this caveat. A "
         "residence-based tabulation would settle it; none is available in "
         "the loaded sources. Check whether the same province is an outlier "
         "in other years before treating any single year as signal."),

        ("schema", "population", "medium",
         "Two projection products disagree by about 1%, and provincial and "
         "national rates therefore rest on slightly different denominators.",
         "For 2025 the national single-age workbook gives 10,986,098; the "
         "32 provinces of the 2016 subnacional report sum to 10,878,267, a "
         "difference of -107,831 (-0.98%). They are different vintages of "
         "ONE's projections, not an extraction error.",
         "Do not mix them in one ratio. National rates use source_id 2, "
         "provincial rates source_id 3; population.source_id distinguishes "
         "them. If ONE publishes a subnacional revision consistent with the "
         "current national series, load it and supersede source 3."),

        ("source_table", "Cuadro 22", "medium",
         "The Atlas's intimate-feminicide cuadro does not add up in three "
         "of its ten years, and its two breakdowns fail in different "
         "years. Quote the annual totals; do not quote the splits for "
         "2014, 2015 or 2017 without saying so.",
         "National total vs the two perpetrator categories: 2014 total 102 "
         "against 64+42=106 (-4), 2015 total 89 against 49+38=87 (+2), "
         "2017 total 104 against 74+28=102 (+2). The ten planning regions "
         "sum correctly in 2014 (102) but fall short in 2015 (86 vs 89) "
         "and 2017 (102 vs 104). So 2014 is an error in the perpetrator "
         "split alone, while 2015 and 2017 are short in BOTH breakdowns -- "
         "consistent with cases whose perpetrator relationship and region "
         "were both unrecorded and which were dropped from each split "
         "rather than shown as unknown. The decade column reconciles with "
         "the sum of years for every row, so the discrepancy is in the "
         "annual columns, not the totals.",
         "Not recoverable from the publication. The underlying registry is "
         "the Procuraduria's; a residual 'no declarada' category in both "
         "splits would have made this visible rather than silent. Treat "
         "the annual totals as sound and the 2014/2015/2017 splits as "
         "incomplete."),

        ("source_table", "Cuadro 1.9", "low",
         "Three of 43 geographies have a foreign-mother subtotal that is "
         "one birth away from the countries beneath it. Rows preserved as "
         "printed and flagged, not corrected.",
         "Region Enriquillo: subtotal 926 against 925 summed. Samana: 125 "
         "against 126. Region Cibao Nordeste: 651 against 652. Samana sits "
         "inside Cibao Nordeste and both are +1, so one birth appears to "
         "be counted in the province subtotal but not in any country "
         "column, and it propagates to the region. Enriquillo is -1 in the "
         "opposite direction. The outer identity (total = dominicana + "
         "foreign subtotal + no declarada) holds for all 43 rows; only the "
         "inner one fails.",
         "Immaterial at this magnitude -- three units across 154,449 "
         "births. Use the outer totals, which reconcile everywhere. The "
         "affected facts carry the discrepancy in fact.note."),

        ("coverage", "microdata", "high",
         "Three-way cross-tabs are unanswerable from published cuadros, in "
         "any edition, forever.",
         "An Anuario cuadro is a two-way table. Age gap x nationality x "
         "province cannot be recovered from marginals.",
         "ANDA holds marriage and divorce microdata. Both are needed: "
         "divorce records alone give failures with no population at risk. "
         "Login is manual; it is not automatable from here."),

        ("source_table", "Cuadro 3.2", "medium",
         "Provincial marriage counts are tabulated by place of REGISTRO, "
         "not residence.",
         "basis='registro' on every row. Destination-wedding provinces are "
         "structurally inflated.",
         "Do not read Cuadro 3.2 as where couples live. If a residence "
         "tabulation exists in another cuadro, load it as basis='residencia' "
         "and keep both."),

        ("schema", "geography.code", "low",
         "ONE provincia codes are recorded but unverified.",
         "geography.code_verified = 0 for all 32 provinces. The codes were "
         "not read off the Anuario.",
         "Verify against ONE's Division Territorial before using `code` as "
         "a join key. `name_norm` is the key that is verified."),
    ])


def finalize(con, views_sql):
    c = con.cursor()
    c.executescript(views_sql)
    c.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)", [
        ("schema_version", SCHEMA_VERSION),
        ("built_at", datetime.datetime.now(datetime.timezone.utc)
                          .isoformat(timespec="seconds")),
        ("builder", "data/build.py"),
        ("fact_rows", str(c.execute("SELECT COUNT(*) FROM fact").fetchone()[0])),
        ("read_me_first",
         "Run: SELECT * FROM v_coverage; then SELECT * FROM known_issue "
         "WHERE severity IN ('blocking','high'); then check source_table.trust "
         "before quoting any number."),
    ])
    c.execute("ANALYZE")
    con.commit()
    con.execute("VACUUM")            # ship a compact file


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(HERE, "dr_stats.db"))
    ap.add_argument("--views-only", action="store_true")
    args = ap.parse_args()

    views_sql = open(os.path.join(HERE, "views.sql")).read()

    if args.views_only:
        con = sqlite3.connect(args.db)
        con.executescript(views_sql)
        con.commit(); con.close()
        print(f"views reapplied to {args.db}")
        return

    if os.path.exists(args.db):
        os.remove(args.db)
    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(open(os.path.join(HERE, "schema.sql")).read())
    con.executescript(open(os.path.join(HERE, "schema_dyad.sql")).read())

    b = Build(con)
    b.load_reference()
    ingest_anuario_2025(b)
    ingest_births_2025(b)
    ingest_rotated_2025(b)
    ingest_proyecciones(b)
    ingest_subnacional(b)
    ingest_cifras(b)
    ingest_atlas(b)
    con.commit()

    con.execute("UPDATE source_table SET transcription_verified=1, "
                "verified_against=? WHERE cuadro='Cuadro 3.5'",
                ("pp.85-86 of sha256 42ec03d0ef6d7e2e18af0f4555eb8270"
                 "fae0b624aa89cd74d24fc6880956ef70, checked 2026-09-05: "
                 "281 of 289 cells exact; 8 mislabelled by a Peru/Puerto "
                 "Rico column transposition, now corrected",))
    con.commit()

    reconcile(con)
    seed_acquisition(con)
    derive_dyads_from_cuadros(con)
    check_constraints(con)
    register_known_issues(con)
    finalize(con, views_sql)

    n = con.execute("SELECT COUNT(*) FROM fact").fetchone()[0]
    print(f"{args.db}: {n} facts, "
          f"{con.execute('SELECT COUNT(*) FROM source_table').fetchone()[0]} cuadros")
    print("\ntrust:")
    for r in con.execute("SELECT cuadro, trust, COALESCE(trust_note,'') "
                         "FROM source_table ORDER BY table_id"):
        print(f"  {r[0]:<12} {r[1]:<15} {r[2][:70]}")
    con.close()


if __name__ == "__main__":
    main()
