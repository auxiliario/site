# dr_stats — Dominican Republic vital statistics, couples-oriented

SQLite database and reproducible build for research on Dominican
partnership formation and dissolution. Schema **v2**.

```
python build.py        # rebuild dr_stats.db from sources/  (idempotent)
python validate.py     # structural checks; exit 0 = safe to query
python build.py --views-only    # reapply views.sql to an existing db
sqlite3 dr_stats.db < queries.sql
```

Currently loaded: ONE *Anuario de Estadísticas Vitales 2025*, 8 cuadros,
960 facts, 2013–2025.

---

## Read this before quoting a number

```sql
SELECT * FROM v_coverage;                                    -- what is here
SELECT severity, ref, summary FROM known_issue               -- what is wrong
 WHERE severity IN ('blocking','high');
SELECT cuadro, trust, trust_note FROM source_table;          -- what you may quote
```

**Cuadro 3.5 (marriage nationality × nationality) is `marginals_only`.**
Its interior cells sum to 44,349 while both sets of published margins
independently sum to 40,750 — the same total Cuadros 3.2, 3.3 and 3.4 give
for 2025 marriages. Both margins are therefore right and the interior is
3,599 too large; 16 of 17 rows fail, the Dominican row alone by 3,047.
The structurally identical Cuadro 4.5 reconciles exactly on all 17 rows
using the same extraction method, so this is not a general property of
ONE's nationality tables. The Perú row places 15 marriages under the
Puerto Rico column while its own diagonal is 0 and the entire Puerto Rico
row is 0 — the signature of a column shift.

Whether the defect is ONE's or the extractor's cannot be settled here: the
source PDF is not in this repository. Until someone re-reads page 85,
every mixed-nationality **marriage** finding is unsafe. The corresponding
**divorce** finding is not: Cuadro 4.5 is `verified`, and it reproduces the
same directional pattern (Italia 2.05 in the same direction as marriage's
untrusted 2.21; Venezuela 0.41 against 0.41).

---

## Why the schema looks like this

**One long-format `fact` table, not one table per cuadro.** Cuadro
numbering and layout shift between editions; a wide schema breaks the
moment 2021 is added. Four generic dimension slots carry any cross-tab and
you reshape at analysis time. Provenance lives in `source_document` and
`source_table`, so filtering to one source is a `WHERE`, not a different
table.

**Published cells are stored exactly as printed.** Nothing is reconciled,
imputed, or repaired at load time. For pairing work the *pattern* of where
a table fails to add up is diagnostic — silently fixing it destroys the
signal that located the Cuadro 3.5 defect in the first place.

**`No declarada` stays a category, never NULL.** It runs 1.3% in Cuadro
3.3 and 13% of the divorce table, and it is not missing at random.
`age_band_ref.is_residual` / `nationality_ref.is_residual` let a query
exclude it deliberately; nothing excludes it by accident. This is why
`v_age_gap` sums to 40,233 rather than 40,750.

**Every row carries `reference_year` *and* `edition_year`,** because ONE
restates its own series between editions. `v_series_restatement` returns
nothing today and becomes the first thing to look at the moment a second
edition loads.

**`construct` is a stored dimension, not a note.** 2.88 (observed mean
sobreedad) and 3.84 (EMNup synthetic-cohort difference) both read as "the
age gap" and are different measures. They physically cannot land in the
same column, and `construct_registry` carries the definitions.

---

## What v2 adds over the flat build

| | v1 | v2 |
|---|---|---|
| Re-running a loader | duplicates every row | idempotent — stored natural key + unique index, `ON CONFLICT DO UPDATE` |
| A typo'd `measure` or dimension name | silently forks a dimension | rejected by trigger against `vocab` |
| Cross-tab dropped into `dim2` with `dim1` empty | invisible to every `dim1` query | rejected by CHECK |
| "This table doesn't add up" | a comment in the build script | `reconciliation` rows with signed per-key deltas, plus `source_table.trust` |
| Cross-cuadro totals | never checked | 13 control-total checks; this is what found the 3.5 defect |
| Age-gap direction | string comparison on band labels | `age_band_ref.sort_order` + numeric bounds |
| Excluding `TOTAL` / `Otros países` | hardcoded `NOT IN (...)` in each query | `is_residual` flags on the reference tables |
| Joining a future census/ENI table | fold accents by hand each time | `geography.name_norm` + `code`, unique per level |
| Population denominators | absent, unmentioned | `population` table + `v_pairing_rate`, empty and documented |
| Trust reaching the analyst | none | `v_pairing_symmetry_trusted` serves only reconciling tables |

The `fact` column names from v1 are unchanged, so v1 queries still run.

---

## Layout

```
schema.sql              tables, constraints, indexes, vocabulary trigger
views.sql               analysis views (reapply without a rebuild)
reference.py            geography, controlled vocabulary, category lookups
sources/anuario_2025.py cells transcribed exactly as printed
build.py                loaders + reconciliation + trust derivation
validate.py             structural checks
queries.sql             eight worked couples queries
dr_stats.db             built artifact
```

Adding an edition: copy `sources/anuario_2025.py`, re-transcribe, add an
`ingest_anuario_YYYY()` to `build.py`. A genuinely new category must be
added to `reference.py` **first**, or the vocabulary trigger stops the
build — which is the point.

## Views

| view | use |
|---|---|
| `v_coverage` | what is loaded, by cuadro |
| `v_fact_sourced` | any fact + full provenance + trust |
| `v_pairing` | any two-sided table normalized to `side_a`/`side_b` regardless of whether the cuadro said bride/groom, wife/husband, mother/father |
| `v_pairing_symmetry` | directional balance of mixed pairings, carrying `trust` |
| `v_pairing_symmetry_trusted` | the same, reconciling tables only — quote from this |
| `v_age_gap` | who is older, derived from band bounds |
| `v_reconciliation` / `v_anomalies` | where and by how much the numbers fail |
| `v_series_restatement` | same year, different edition, different value |
| `v_pairing_rate` | population-adjusted rates; empty until `population` loads |

---

## Known limits

1. **No denominators.** Every figure here is a count with no population at
   risk. La Altagracia looks like an outlier partly because more people
   marry there. Fill `population` from ONE *Estimaciones y Proyecciones de
   Población* (province × sex × five-year age group) and ENI immigrant
   stock on the same breakdown; `v_pairing_rate` starts returning rows.

2. **No three-way cross-tabs, ever, from published cuadros.** An Anuario
   cuadro is a two-way table; age gap × nationality × province cannot be
   recovered from margins. ANDA holds marriage *and* divorce microdata —
   both, because divorce records alone give failures with no population at
   risk. ANDA and World Bank logins are manual and are not automated here.

3. **`basis='registro'` is not residence.** Cuadro 3.2 counts where the
   marriage was *registered*. Destination-wedding provinces are inflated.
   If a residence tabulation exists, load it as `basis='residencia'` and
   keep both.

4. **Banded ages are approximate.** The midpoint estimate of the mean
   signed gap is 2.95 years, against a published observed sobreedad of
   2.88 — close enough to corroborate both cuadros, not close enough to
   report to two decimals. Microdata is the fix, not a better query.

5. **`geography.code` is unverified** (`code_verified = 0`). The ONE
   provincia codes were not read off the Anuario. Verify against ONE's
   División Territorial before using `code` as a join key; `name_norm` is
   the key that is actually verified against the source.

6. **No "success rate" is derivable and none should be constructed.**
   Marriages and divorces registered in the same year are different
   cohorts. Report median duration before divorce, current relationship
   status, and population-adjusted pairing rates separately.

7. **Only marriage and divorce are loaded.** Births and deaths, the
   census, ENI, ENDESA and MICS have reserved vocabulary and schema slots
   but no data.
