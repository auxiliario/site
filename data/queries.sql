-- =====================================================================
-- Worked queries.  Run with:  sqlite3 dr_stats.db < queries.sql
-- Each one is written the way it should be reused: no hardcoded string
-- exclusion lists, no assumptions about which cuadro number carries what.
-- =====================================================================

-- 0. ORIENTATION -- always run these three first. -------------------
SELECT '== what is in here ==' AS "";
SELECT instrument, cuadro, vital_event, trust, year_from, year_to, facts
FROM v_coverage;

SELECT '== what you must know before quoting anything ==' AS "";
SELECT severity, ref, summary FROM known_issue
WHERE severity IN ('blocking','high') ORDER BY severity, ref;

SELECT '== where the numbers do not add up ==' AS "";
SELECT cuadro, key_value, published_total, summed_cells, delta, pct_delta
FROM v_reconciliation WHERE verdict='mismatch'
ORDER BY ABS(delta) DESC LIMIT 10;


-- 1. AGE-GAP DIRECTION ----------------------------------------------
-- Who is older, and by how much does that skew. Direction comes from
-- age_band_ref.sort_order, so a renamed band in a future edition does
-- not silently reverse the answer. Residual bands ('No declarada') are
-- excluded, which is why this sums to less than the published total --
-- non-response is ~1.3% here and is NOT missing at random.
SELECT '== 1. age-gap direction ==' AS "";
SELECT reference_year, cuadro, trust, direction, marriages,
       ROUND(100.0*marriages/SUM(marriages) OVER (PARTITION BY reference_year),2)
         AS pct_of_declared
FROM v_age_gap ORDER BY marriages DESC;


-- 2. AGE-GAP MAGNITUDE ----------------------------------------------
-- Band midpoints, not band labels. Approximate by construction (banded
-- data), which is exactly why microdata is the fix, not a better query.
SELECT '== 2. mean signed age gap, groom minus bride (band midpoints) ==' AS "";
SELECT p.reference_year, p.trust,
       ROUND(SUM((bb.midpoint - ba.midpoint) * p.count) / SUM(p.count), 2)
         AS mean_gap_years,
       SUM(p.count) AS marriages_used
FROM v_pairing p
JOIN age_band_ref ba ON ba.band = p.side_a_value
JOIN age_band_ref bb ON bb.band = p.side_b_value
WHERE p.attribute='age_band' AND p.is_marginal=0
  AND ba.is_residual=0 AND bb.is_residual=0
GROUP BY 1,2;


-- 3. MIXED-NATIONALITY PAIRING, DIRECTIONAL -------------------------
-- Use the *_trusted view for anything you intend to publish. The
-- unrestricted view is here so you can see what you are excluding.
SELECT '== 3a. directional balance -- TRUSTED tables only ==' AS "";
SELECT vital_event, foreign_side, dom_a_foreign_b, foreign_a_dom_b, ratio
FROM v_pairing_symmetry_trusted ORDER BY total_mixed DESC;

SELECT '== 3b. the same question on untrusted cells, for comparison ==' AS "";
SELECT vital_event, cuadro, trust, foreign_side,
       dom_a_foreign_b, foreign_a_dom_b, ratio
FROM v_pairing_symmetry WHERE trust <> 'verified'
ORDER BY total_mixed DESC LIMIT 8;


-- 4. WHAT THE MARGINALS STILL SUPPORT -------------------------------
-- Cuadro 3.5's interior is unusable but its margins reconcile with three
-- other cuadros, so the one-sided question is still answerable: how many
-- marriages involved a bride of each nationality.
SELECT '== 4. marriages by bride nationality (published row margins) ==' AS "";
SELECT f.dim1_value AS bride_nationality, n.iso3, f.value AS marriages,
       ROUND(100.0*f.value/(SELECT SUM(value) FROM fact
                            WHERE table_id=f.table_id AND is_marginal=1
                              AND dim2_value='TOTAL'),2) AS pct
FROM fact f
JOIN source_table st ON st.table_id=f.table_id AND st.cuadro='Cuadro 3.5'
JOIN nationality_ref n ON n.label=f.dim1_value
WHERE f.is_marginal=1 AND f.dim2_value='TOTAL'
ORDER BY f.value DESC;


-- 5. PROVINCE -- AND THE TRAP IN IT ---------------------------------
-- basis='registro' means place of REGISTRATION. La Altagracia is a
-- destination-wedding province; this is not where couples live.
SELECT '== 5. marriages by province (BASIS=REGISTRO, not residence) ==' AS "";
SELECT g.name_es AS province, g.code, f.basis, f.value AS marriages,
       ROUND(100.0*f.value/40750,2) AS pct_of_national
FROM fact f
JOIN source_table st ON st.table_id=f.table_id AND st.cuadro='Cuadro 3.2'
JOIN geography g ON g.geo_id=f.geo_id AND g.level='province'
WHERE f.is_marginal=1
ORDER BY f.value DESC LIMIT 10;


-- 6. THE TWO MEAN AGES THAT ARE NOT THE SAME NUMBER -----------------
-- 2.88 and 3.84 both look like "the age gap". They measure different
-- things and the registry keeps them apart.
SELECT '== 6. observed mean vs synthetic cohort (EMNup) ==' AS "";
SELECT f.reference_year, f.dim1_value AS construct, f.measure,
       f.dim2_value AS sex, f.value, cr.note
FROM fact f
JOIN construct_registry cr ON cr.construct=f.dim1_value
WHERE f.reference_year=2025 AND f.measure IN ('mean_age','age_gap_years')
ORDER BY construct, sex;


-- 7. EMNup TREND -----------------------------------------------------
SELECT '== 7. EMNup 2013-2025 (this edition''s restatement) ==' AS "";
SELECT reference_year, edition_year,
       MAX(CASE WHEN dim2_value='male'   THEN value END) AS male,
       MAX(CASE WHEN dim2_value='female' THEN value END) AS female,
       MAX(CASE WHEN measure='age_gap_years' THEN value END) AS gap
FROM fact WHERE dim1_value='EMNup' GROUP BY 1,2 ORDER BY 1;


-- 8. WHAT THIS DATABASE CANNOT ANSWER --------------------------------
-- Empty by construction, and that is the honest answer. v_pairing_rate
-- starts returning rows the moment `population` is loaded; until then
-- there is no exposure base and no rate.
SELECT '== 8. population-adjusted pairing rates (empty until denominators load) ==' AS "";
SELECT COUNT(*) AS rate_rows_available FROM v_pairing_rate;
SELECT ref, summary, resolution FROM known_issue WHERE scope='coverage';
