-- =====================================================================
-- dr_stats  LAYER 2: the couplings store
--
-- Layer 1 (`fact`, schema.sql) holds published aggregates -- what a
-- statistical office chose to print. It can only ever answer the
-- cross-tabs someone at ONE decided to typeset.
--
-- Layer 2 holds DYADS: one row per observed couple. It is the layer that
-- scales. A published cuadro yields exactly ONE coupling (the pairing it
-- prints). A dyad source carrying K attributes per side yields K^2
-- couplings, every one of them conditionable on any other variable. That
-- ratio is the entire acquisition argument.
--
-- Both grains live in the same table:
--   grain='record'  one real couple, weight = survey weight (or 1)
--   grain='cell'    one cell of a published cross-tab, weight = the count
-- so `v_couplings` works today on aggregate data and keeps working
-- unchanged when microdata lands beside it.
-- =====================================================================

-- ---------------------------------------------------------------- dyads
CREATE TABLE dyad (
  dyad_id        INTEGER PRIMARY KEY,
  source_id      INTEGER NOT NULL REFERENCES source_document(source_id),
  table_id       INTEGER REFERENCES source_table(table_id),  -- if from a cuadro
  dyad_type      TEXT NOT NULL
                 CHECK (dyad_type IN ('marriage','divorce','consensual_union',
                                      'cohabiting','birth_parents',
                                      'survey_couple','former_union')),
  -- 'record' = one couple; 'cell' = an aggregated cross-tab cell.
  -- Never mix them in a headline figure without saying which.
  grain          TEXT NOT NULL CHECK (grain IN ('record','cell')),
  reference_year INTEGER NOT NULL,
  edition_year   INTEGER NOT NULL,
  geo_id         INTEGER REFERENCES geography(geo_id),
  basis          TEXT,                    -- registro/ocurrencia/residencia

  -- Roles are recorded, not assumed. Do NOT hardcode bride=female:
  -- consensual unions in census rosters are captured by relationship to
  -- head, and a schema that assumes an opposite-sex pair silently drops
  -- the couples that do not fit it.
  role_a         TEXT, role_b TEXT,       -- bride/groom, wife/husband, partner
  sex_a          TEXT CHECK (sex_a IN ('male','female','unknown')),
  sex_b          TEXT CHECK (sex_b IN ('male','female','unknown')),

  -- Weighting. Survey dyads MUST carry design variables or every
  -- confidence interval computed from them is wrong.
  weight         REAL NOT NULL DEFAULT 1 CHECK (weight >= 0),
  psu            TEXT,
  strata         TEXT,

  -- Duration analysis: the questions worth asking ("median duration
  -- before divorce") need both ends, and a divorce record without the
  -- marriage date cannot answer them. Recorded here so its absence is
  -- visible rather than discovered late.
  union_start_year INTEGER,
  union_end_year   INTEGER,
  duration_years   REAL,

  note           TEXT
);
CREATE INDEX ix_dyad_type ON dyad(dyad_type, reference_year);
CREATE INDEX ix_dyad_src  ON dyad(source_id, grain);
CREATE INDEX ix_dyad_geo  ON dyad(geo_id);

-- Attributes, long format, so a source with 40 variables per person needs
-- no schema change -- it just produces more couplings.
CREATE TABLE dyad_attribute (
  dyad_id    INTEGER NOT NULL REFERENCES dyad(dyad_id) ON DELETE CASCADE,
  -- 'couple' carries dyad-level facts (children ever born, duration,
  -- whether the union is registered) that pair with either side.
  side       TEXT NOT NULL CHECK (side IN ('a','b','couple')),
  attribute  TEXT NOT NULL,
  value_text TEXT,
  value_num  REAL,
  PRIMARY KEY (dyad_id, side, attribute)
) WITHOUT ROWID;
CREATE INDEX ix_dattr_attr ON dyad_attribute(attribute, value_text);

-- --------------------------------------------------------- harmonization
-- Couplings only compose across sources if the categories do. ENDESA's
-- education ladder, the census's, and the Anuario's are three different
-- vocabularies for one concept; this maps each source's raw code onto a
-- shared term. Without it, a 2010 census dyad and a 2013 ENDESA dyad
-- cannot appear in the same table.
CREATE TABLE crosswalk (
  attribute    TEXT NOT NULL,
  source_scope TEXT NOT NULL,      -- instrument or source_id this applies to
  raw_value    TEXT NOT NULL,
  harmonized   TEXT NOT NULL,
  is_residual  INTEGER NOT NULL DEFAULT 0 CHECK (is_residual IN (0,1)),
  note         TEXT,
  PRIMARY KEY (attribute, source_scope, raw_value)
);

-- ------------------------------------------------------ acquisition plan
-- The pipeline as data. Priority is expected coupling yield per unit of
-- effort, not enthusiasm; `blocked_by` records why something is not done,
-- so the plan is auditable rather than a list of good intentions.
CREATE TABLE acquisition (
  acq_id          INTEGER PRIMARY KEY,
  tier            TEXT NOT NULL CHECK (tier IN ('A_dyad','B_tabular','C_context')),
  institution     TEXT NOT NULL,
  dataset         TEXT NOT NULL,
  vintages        TEXT,
  grain           TEXT CHECK (grain IN ('record','cell')),
  couple_linkage  TEXT,        -- HOW both sides are recoverable; the crux
  est_couplings   INTEGER,     -- expected distinct (attr_a, attr_b) pairs
  access          TEXT NOT NULL
                  CHECK (access IN ('open','registration','request',
                                    'manual_login','restricted','unknown')),
  redistributable INTEGER NOT NULL DEFAULT 0 CHECK (redistributable IN (0,1)),
  status          TEXT NOT NULL DEFAULT 'not_started'
                  CHECK (status IN ('not_started','blocked','requested',
                                    'acquired','ingested','superseded')),
  blocked_by      TEXT,
  priority        INTEGER,     -- 1 = do first
  verify          TEXT,        -- what must be confirmed against the catalogue
  note            TEXT
);
CREATE INDEX ix_acq_priority ON acquisition(priority, status);

-- ------------------------------------------------------- ingest auditing
CREATE TABLE ingest_run (
  run_id      INTEGER PRIMARY KEY,
  acq_id      INTEGER REFERENCES acquisition(acq_id),
  started_at  TEXT NOT NULL,
  loader      TEXT NOT NULL,
  input_path  TEXT,
  input_sha256 TEXT,
  rows_in     INTEGER,
  dyads_out   INTEGER,
  outcome     TEXT CHECK (outcome IN ('ok','failed','partial')),
  message     TEXT
);

-- --------------------------------------------------- aggregate as check
-- Flips layer 1 from a data source into a TEST. Once dyads exist, any
-- published marginal becomes an assertion the microdata must reproduce;
-- a large divergence means a weighting error, a coverage difference, or
-- a bad load -- and you want to find out which before publishing.
CREATE TABLE constraint_check (
  check_id     INTEGER PRIMARY KEY,
  table_id     INTEGER REFERENCES source_table(table_id),
  description  TEXT NOT NULL,
  published    REAL,
  from_dyads   REAL,
  delta        REAL,
  pct_delta    REAL,
  verdict      TEXT CHECK (verdict IN ('ok','divergent','not_yet_testable'))
);
