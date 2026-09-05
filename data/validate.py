#!/usr/bin/env python3
"""
Structural validation of dr_stats.db.  Exit 0 = safe to hand to an analyst.

    python validate.py [--db path]

This checks the things that make the database *trustworthy to query*, not
the things that make it complete. A cuadro whose numbers do not add up is
NOT a failure here -- it is a finding, and it passes as long as the
database says so out loud: reconciliation rows recorded, source_table.trust
downgraded, and a known_issue registered. An unreconciled table that
claims to be 'verified' is the actual failure.
"""
import argparse, os, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FAILURES, WARNINGS = [], []


def check(cond, msg):
    if not cond:
        FAILURES.append(msg)
    print(("  ok   " if cond else "  FAIL ") + msg)


def warn(cond, msg):
    if not cond:
        WARNINGS.append(msg)
    print(("  ok   " if cond else "  warn ") + msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(HERE, "dr_stats.db"))
    a = ap.parse_args()
    con = sqlite3.connect(a.db)
    con.execute("PRAGMA foreign_keys = ON")
    q = lambda s, *p: con.execute(s, p).fetchall()
    one = lambda s, *p: con.execute(s, p).fetchone()[0]

    print("\n== integrity ==")
    check(one("PRAGMA integrity_check") == "ok", "sqlite integrity_check")
    check(not q("PRAGMA foreign_key_check"), "no foreign key violations")
    check(one("SELECT COUNT(*) FROM fact") > 0, "fact table is populated")
    check(one("SELECT COUNT(*) FROM fact") ==
          one("SELECT COUNT(DISTINCT nk) FROM fact"),
          "every fact has a distinct natural key (loader is idempotent)")

    print("\n== vocabulary ==")
    for slot in (1, 2, 3, 4):
        check(not q(f"SELECT DISTINCT dim{slot}_name FROM fact "
                    f"WHERE dim{slot}_name IS NOT NULL AND dim{slot}_name NOT IN "
                    f"(SELECT term FROM vocab WHERE domain='dim_name')"),
              f"dim{slot}_name values are all registered in vocab")
    check(not q("SELECT DISTINCT measure FROM fact WHERE measure NOT IN "
                "(SELECT term FROM vocab WHERE domain='measure')"),
          "measure values are all registered")
    check(not q("SELECT DISTINCT basis FROM fact WHERE basis IS NOT NULL AND "
                "basis NOT IN (SELECT term FROM vocab WHERE domain='basis')"),
          "basis values are all registered")
    check(not q("SELECT DISTINCT dim1_value FROM fact WHERE dim1_name "
                "LIKE '%nationality' AND dim1_value NOT IN "
                "(SELECT label FROM nationality_ref) "
                "UNION SELECT DISTINCT dim2_value FROM fact WHERE dim2_name "
                "LIKE '%nationality' AND dim2_value NOT IN "
                "(SELECT label FROM nationality_ref)"),
          "every nationality label resolves in nationality_ref")
    check(not q("SELECT DISTINCT dim1_value FROM fact WHERE dim1_name "
                "LIKE '%age_band' AND dim1_value NOT IN "
                "(SELECT band FROM age_band_ref) "
                "UNION SELECT DISTINCT dim2_value FROM fact WHERE dim2_name "
                "LIKE '%age_band' AND dim2_value NOT IN "
                "(SELECT band FROM age_band_ref)"),
          "every age band resolves in age_band_ref")
    check(not q("SELECT DISTINCT dim1_value FROM fact WHERE dim1_name="
                "'construct' AND dim1_value NOT IN "
                "(SELECT construct FROM construct_registry)"),
          "every construct is defined in construct_registry")

    print("\n== structure ==")
    check(not q("SELECT 1 FROM fact WHERE dim1_name IS NULL AND "
                "dim2_name IS NOT NULL"), "dimension slots fill left to right")
    check(one("SELECT COUNT(*) FROM geography WHERE level='province'") == 32,
          "32 provinces present")
    check(one("SELECT COUNT(*) FROM geography WHERE level='region'") == 10,
          "10 regions present")
    check(not q("SELECT 1 FROM geography WHERE level='province' AND "
                "parent_geo_id IS NULL"), "every province has a parent region")
    check(not q("SELECT 1 FROM fact f LEFT JOIN geography g USING(geo_id) "
                "WHERE f.geo_id IS NOT NULL AND g.geo_id IS NULL"),
          "every geo_id resolves")
    warn(not q("SELECT 1 FROM geography WHERE code IS NOT NULL AND "
               "code_verified=0 LIMIT 1"),
         "geography codes are verified (expected to warn: see known_issue)")

    print("\n== trust is honest ==")
    bad = q("""SELECT st.cuadro FROM source_table st
               WHERE st.trust='verified' AND EXISTS (
                 SELECT 1 FROM reconciliation r
                 WHERE r.table_id=st.table_id AND r.verdict='mismatch')""")
    check(not bad, "no table claims 'verified' while failing reconciliation")
    unregistered = q("""SELECT DISTINCT st.cuadro FROM source_table st
                        JOIN reconciliation r ON r.table_id=st.table_id
                        WHERE r.verdict='mismatch'
                          AND st.cuadro NOT IN (SELECT ref FROM known_issue)""")
    check(not unregistered,
          "every non-reconciling cuadro has a registered known_issue")
    check(not q("SELECT 1 FROM v_pairing_symmetry_trusted t "
                "JOIN source_table st ON st.cuadro=t.cuadro "
                "WHERE st.trust<>'verified'"),
          "v_pairing_symmetry_trusted serves only reconciling tables")

    print("\n== views execute ==")
    for (v,) in q("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"):
        try:
            n = one(f"SELECT COUNT(*) FROM {v}")
            print(f"  ok   {v} ({n} rows)")
        except Exception as e:                                  # noqa: BLE001
            FAILURES.append(f"{v}: {e}")
            print(f"  FAIL {v}: {e}")

    print("\n== coverage (informational) ==")
    for r in q("SELECT instrument, cuadro, vital_event, trust, year_from, "
               "year_to, facts FROM v_coverage"):
        print("   " + " | ".join(str(x) for x in r))
    warn(one("SELECT COUNT(*) FROM population") > 0,
         "population denominators loaded (expected to warn: see known_issue)")

    print(f"\n{len(FAILURES)} failure(s), {len(WARNINGS)} warning(s)")
    for f in FAILURES:
        print("  FAIL " + f)
    con.close()
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
