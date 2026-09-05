-- =====================================================================
-- dr_stats  analysis views  (v2)
--
-- Kept in a separate file from schema.sql on purpose: views change far
-- more often than the fact table does, and `python build.py --views-only`
-- reapplies them against an existing database in under a second.
-- =====================================================================

DROP VIEW IF EXISTS v_fact_sourced;
DROP VIEW IF EXISTS v_pairing;
DROP VIEW IF EXISTS v_pairing_symmetry;
DROP VIEW IF EXISTS v_pairing_symmetry_trusted;
DROP VIEW IF EXISTS v_age_gap;
DROP VIEW IF EXISTS v_anomalies;
DROP VIEW IF EXISTS v_reconciliation;
DROP VIEW IF EXISTS v_series_restatement;
DROP VIEW IF EXISTS v_pairing_rate;
DROP VIEW IF EXISTS v_coverage;

-- Full provenance + trust for any fact. Start every session here.
CREATE VIEW v_fact_sourced AS
SELECT f.*,
       st.cuadro, st.page_number, st.verified_visually,
       st.trust, st.trust_note,
       sd.publication, sd.instrument, sd.url,
       g.name_es AS geo_name, g.level AS geo_level, g.code AS geo_code
FROM fact f
JOIN source_table st    ON st.table_id  = f.table_id
JOIN source_document sd ON sd.source_id = st.source_id
LEFT JOIN geography g   ON g.geo_id     = f.geo_id;

-- Any two-sided table normalized to side_a / side_b, whatever vocabulary
-- the cuadro used (bride/groom, wife/husband, mother/father). `attribute`
-- says what is being paired on; `trust` says whether you may quote it.
CREATE VIEW v_pairing AS
SELECT f.fact_id, f.reference_year, f.edition_year, f.vital_event,
       CASE
         WHEN f.dim1_name LIKE 'bride%'  THEN 'bride'
         WHEN f.dim1_name LIKE 'wife%'   THEN 'wife'
         WHEN f.dim1_name LIKE 'mother%' THEN 'mother'
       END AS side_a_role,
       CASE
         WHEN f.dim2_name LIKE 'groom%'   THEN 'groom'
         WHEN f.dim2_name LIKE 'husband%' THEN 'husband'
         WHEN f.dim2_name LIKE 'father%'  THEN 'father'
       END AS side_b_role,
       REPLACE(REPLACE(REPLACE(f.dim1_name,'bride_',''),'wife_',''),'mother_','')
            AS attribute,
       f.dim1_value AS side_a_value,
       f.dim2_value AS side_b_value,
       f.value      AS count,
       f.is_marginal, f.anomaly_flag, f.table_id,
       st.cuadro, st.trust,
       -- residual flags, so callers stop hardcoding string exclusion lists
       COALESCE(na.is_residual, ba.is_residual, 0) AS side_a_residual,
       COALESCE(nb.is_residual, bb.is_residual, 0) AS side_b_residual,
       na.iso3 AS side_a_iso3, nb.iso3 AS side_b_iso3,
       ba.sort_order AS side_a_band_order, bb.sort_order AS side_b_band_order
FROM fact f
JOIN source_table st ON st.table_id = f.table_id
LEFT JOIN nationality_ref na ON na.label = f.dim1_value
LEFT JOIN nationality_ref nb ON nb.label = f.dim2_value
LEFT JOIN age_band_ref    ba ON ba.band  = f.dim1_value
LEFT JOIN age_band_ref    bb ON bb.band  = f.dim2_value
WHERE f.dim1_name LIKE 'bride%' OR f.dim1_name LIKE 'wife%'
   OR f.dim1_name LIKE 'mother%';

-- Directional balance of mixed-nationality pairings. Carries `trust`
-- forward: a row sourced from a table whose interior cells do not
-- reconcile is still returned, but it arrives labelled.
CREATE VIEW v_pairing_symmetry AS
SELECT a.reference_year, a.vital_event, a.attribute, a.cuadro, a.trust,
       a.side_b_value                          AS foreign_side,
       a.side_b_iso3                           AS foreign_iso3,
       a.count                                 AS dom_a_foreign_b,
       b.count                                 AS foreign_a_dom_b,
       a.count + b.count                       AS total_mixed,
       ROUND(a.count*1.0/NULLIF(b.count,0),3)  AS ratio
FROM v_pairing a
JOIN v_pairing b
  ON  b.attribute      = a.attribute
  AND b.reference_year = a.reference_year
  AND b.vital_event    = a.vital_event
  AND b.table_id       = a.table_id
  AND b.side_a_value   = a.side_b_value
  AND b.side_b_value   = a.side_a_value
  AND b.is_marginal    = 0
WHERE a.attribute      = 'nationality'
  AND a.side_a_iso3    = 'DOM'
  AND a.is_marginal    = 0
  AND a.side_b_residual = 0
  AND a.side_b_iso3 <> 'DOM';

-- The same thing, restricted to tables whose cells actually reconcile.
-- Quote from this one.
CREATE VIEW v_pairing_symmetry_trusted AS
SELECT * FROM v_pairing_symmetry WHERE trust = 'verified';

-- Age-gap direction, derived from age_band_ref.sort_order rather than
-- from string comparison, and excluding residual bands on both sides.
CREATE VIEW v_age_gap AS
SELECT p.reference_year, p.vital_event, p.cuadro, p.trust,
       CASE WHEN p.side_b_band_order > p.side_a_band_order THEN 'side_b_older'
            WHEN p.side_b_band_order < p.side_a_band_order THEN 'side_a_older'
            ELSE 'same_band' END AS direction,
       SUM(p.count)              AS marriages
FROM v_pairing p
WHERE p.attribute = 'age_band'
  AND p.is_marginal = 0
  AND p.side_a_residual = 0 AND p.side_b_residual = 0
GROUP BY 1,2,3,4,5;

-- Reconciliation, joined back to provenance. Signed deltas preserved.
CREATE VIEW v_reconciliation AS
SELECT sd.publication, st.cuadro, st.page_number, st.trust,
       r.axis, r.key_value, r.published_total, r.summed_cells,
       r.delta, r.pct_delta, r.verdict
FROM reconciliation r
JOIN source_table st    ON st.table_id  = r.table_id
JOIN source_document sd ON sd.source_id = st.source_id;

-- One line per table that fails to add up, with the size of the failure.
CREATE VIEW v_anomalies AS
SELECT sd.publication, st.cuadro, st.page_number, st.trust,
       COUNT(*) FILTER (WHERE r.verdict='mismatch')       AS keys_mismatched,
       COUNT(*)                                           AS keys_checked,
       ROUND(SUM(ABS(r.delta)) FILTER (WHERE r.verdict='mismatch'),0) AS abs_delta,
       (SELECT COUNT(*) FROM fact f
         WHERE f.table_id = st.table_id AND f.anomaly_flag IS NOT NULL) AS facts_flagged
FROM source_table st
JOIN source_document sd ON sd.source_id = st.source_id
LEFT JOIN reconciliation r ON r.table_id = st.table_id
GROUP BY st.table_id
HAVING keys_mismatched > 0 OR facts_flagged > 0;

-- Where two editions publish different values for the same construct and
-- reference year. Returns nothing until a second edition is loaded, and
-- then it is the first thing to look at.
CREATE VIEW v_series_restatement AS
SELECT a.reference_year, a.vital_event, a.measure,
       a.dim1_value AS construct, a.dim2_value AS sex,
       a.edition_year AS edition_a, a.value AS value_a,
       b.edition_year AS edition_b, b.value AS value_b,
       ROUND(b.value - a.value, 4) AS drift
FROM fact a
JOIN fact b
  ON  b.reference_year = a.reference_year
  AND b.measure        = a.measure
  AND COALESCE(b.dim1_value,'') = COALESCE(a.dim1_value,'')
  AND COALESCE(b.dim2_value,'') = COALESCE(a.dim2_value,'')
  AND COALESCE(b.geo_id,-1)     = COALESCE(a.geo_id,-1)
  AND b.edition_year > a.edition_year
WHERE a.value IS NOT NULL AND b.value IS NOT NULL
  AND ABS(b.value - a.value) > 1e-9;

-- Population-adjusted pairing rates. Deliberately empty today: it
-- returns one row per pairing cell only once `population` is loaded.
-- That emptiness is the honest answer to "what is the rate?" -- the
-- denominators are not in any Anuario.
CREATE VIEW v_pairing_rate AS
SELECT p.reference_year, p.vital_event, p.attribute,
       p.side_a_value, p.side_b_value, p.count,
       pop.value                                        AS exposure_base,
       ROUND(p.count * 100000.0 / NULLIF(pop.value,0),2) AS per_100k_exposed,
       p.trust
FROM v_pairing p
JOIN fact f       ON f.fact_id = p.fact_id
JOIN population pop
  ON  pop.reference_year = p.reference_year
  AND COALESCE(pop.geo_id,-1) = COALESCE(f.geo_id,-1)
  AND (pop.nationality = p.side_a_value OR pop.nationality IS NULL)
  AND pop.measure = 'persons'
WHERE p.is_marginal = 0;

-- What is actually in here. First query for anyone new to the file.
CREATE VIEW v_coverage AS
SELECT sd.instrument, sd.publication, sd.edition_year,
       st.cuadro, st.vital_event, st.trust,
       MIN(f.reference_year) AS year_from, MAX(f.reference_year) AS year_to,
       GROUP_CONCAT(DISTINCT f.measure) AS measures,
       COUNT(*) AS facts
FROM fact f
JOIN source_table st    ON st.table_id  = f.table_id
JOIN source_document sd ON sd.source_id = st.source_id
GROUP BY st.table_id
ORDER BY sd.edition_year, st.page_number;


-- =====================================================================
-- LAYER 2 -- the couplings engine
-- =====================================================================
DROP VIEW IF EXISTS v_couplings;
DROP VIEW IF EXISTS v_coupling_inventory;
DROP VIEW IF EXISTS v_coupling_yield;
DROP VIEW IF EXISTS v_acquisition_plan;
DROP VIEW IF EXISTS v_dyad_gaps;

-- THE mining view. Self-joins the attribute table across the two sides,
-- so every pairing of every attribute is generated without anyone
-- writing a query per cross-tab. Add a source with K attributes per side
-- and K^2 couplings appear here with no schema change and no new view.
--
--   SELECT * FROM v_couplings WHERE attr_a='age_band' AND attr_b='nationality';
--
-- `grain` must be carried into any headline: 'cell' rows are aggregated
-- table cells, 'record' rows are individual couples, and mixing them
-- without saying so overstates precision.
CREATE VIEW v_couplings AS
SELECT d.dyad_type, d.grain, d.reference_year, d.edition_year,
       d.source_id, d.geo_id, d.basis,
       a.attribute AS attr_a, COALESCE(a.value_text, CAST(a.value_num AS TEXT)) AS val_a,
       b.attribute AS attr_b, COALESCE(b.value_text, CAST(b.value_num AS TEXT)) AS val_b,
       SUM(d.weight)  AS n,
       COUNT(*)       AS dyad_rows,
       MIN(d.role_a)  AS role_a, MIN(d.role_b) AS role_b
FROM dyad d
JOIN dyad_attribute a ON a.dyad_id = d.dyad_id AND a.side = 'a'
JOIN dyad_attribute b ON b.dyad_id = d.dyad_id AND b.side = 'b'
GROUP BY d.dyad_type, d.grain, d.reference_year, d.edition_year,
         d.source_id, d.geo_id, d.basis, a.attribute, b.attribute,
         val_a, val_b;

-- What couplings exist right now, and how much weight sits behind each.
-- This is the project's headline metric: the count of rows here is the
-- number of distinct questions the database can answer about pairing.
CREATE VIEW v_coupling_inventory AS
SELECT sd.instrument, sd.publication, c.dyad_type, c.grain,
       c.attr_a, c.attr_b,
       COUNT(*)      AS cells,
       SUM(c.n)      AS weighted_dyads,
       MIN(c.reference_year) AS year_from,
       MAX(c.reference_year) AS year_to
FROM v_couplings c
JOIN source_document sd ON sd.source_id = c.source_id
GROUP BY 1,2,3,4,5,6;

-- Held vs. planned, in the only unit that matters.
CREATE VIEW v_coupling_yield AS
SELECT 'held'    AS state, 'all loaded sources' AS dataset, NULL AS tier,
       (SELECT COUNT(*) FROM (SELECT DISTINCT attr_a, attr_b FROM v_couplings))
         AS distinct_couplings, NULL AS priority, NULL AS status
UNION ALL
SELECT 'planned', dataset, tier, est_couplings, priority, status
FROM acquisition WHERE est_couplings > 0
ORDER BY state, distinct_couplings DESC;

-- The plan, ordered the way it should be worked.
CREATE VIEW v_acquisition_plan AS
SELECT priority, tier, status, institution, dataset, vintages, grain,
       est_couplings, access, redistributable, blocked_by, couple_linkage,
       verify
FROM acquisition ORDER BY priority;

-- Attributes present on one side but not the other, i.e. couplings that
-- are one ingest fix away from existing. Cheapest yield on the board.
CREATE VIEW v_dyad_gaps AS
SELECT d.source_id, d.dyad_type, x.attribute,
       SUM(CASE WHEN x.side='a' THEN 1 ELSE 0 END) AS on_side_a,
       SUM(CASE WHEN x.side='b' THEN 1 ELSE 0 END) AS on_side_b
FROM dyad d JOIN dyad_attribute x ON x.dyad_id = d.dyad_id
WHERE x.side IN ('a','b')
GROUP BY 1,2,3
HAVING on_side_a = 0 OR on_side_b = 0;
