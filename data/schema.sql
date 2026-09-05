-- =====================================================================
-- dr_stats  schema v2
-- Dominican Republic vital statistics / couples research database
--
-- Design contract (see README.md for the full rationale):
--   1. ONE long-format `fact` table. Never one table per cuadro; cuadro
--      numbering and layout shift between editions.
--   2. Published cells are stored exactly as printed. Nothing is
--      reconciled, imputed, or repaired at load time.
--   3. Every fact carries reference_year AND edition_year, because ONE
--      restates its own series between editions.
--   4. Reconciliation results are DATA (`reconciliation`), not comments,
--      and trust flows from there into `source_table.trust` and into the
--      analysis views. A view must never silently serve untrusted cells.
--   5. Controlled vocabulary is enforced by trigger, so a typo in a
--      future edition's loader fails the build instead of forking a
--      dimension value.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- --------------------------------------------------------------- meta
CREATE TABLE meta (
  key    TEXT PRIMARY KEY,
  value  TEXT
);

-- ------------------------------------------------------------ sources
CREATE TABLE source_document (
  source_id     INTEGER PRIMARY KEY,
  institution   TEXT NOT NULL,
  instrument    TEXT NOT NULL             -- anuario/censo/eni/endesa/mics/proyecciones
                CHECK (instrument IN ('anuario','censo','eni','endesa','mics',
                                      'proyecciones','microdata','other')),
  publication   TEXT NOT NULL,
  edition_year  INTEGER,
  url           TEXT,
  local_path    TEXT,
  sha256        TEXT,
  retrieved_at  TEXT,
  page_count    INTEGER
);

CREATE TABLE source_table (
  table_id          INTEGER PRIMARY KEY,
  source_id         INTEGER NOT NULL REFERENCES source_document(source_id),
  cuadro            TEXT,
  title_es          TEXT,
  page_number       INTEGER,
  vital_event       TEXT,
  extraction_method TEXT,
  verified_visually INTEGER DEFAULT 0 CHECK (verified_visually IN (0,1)),
  -- Distinct from `trust`. transcription_verified=1 means the cells were
  -- machine-checked against the source PDF and match. A table can be a
  -- faithful transcription of a cuadro that does not add up -- Cuadro 3.5
  -- is exactly that -- so the two facts need separate columns.
  transcription_verified INTEGER NOT NULL DEFAULT 0
                    CHECK (transcription_verified IN (0,1)),
  verified_against  TEXT,
  -- Trust is the load-bearing addition in v2. `verified_visually` only
  -- says a human looked at the page; it says nothing about whether the
  -- numbers hold together.
  --   verified       cells and marginals both reconcile
  --   marginals_only marginals reconcile, interior cells do not
  --   unverified     not yet checked
  --   disputed       a registered known_issue contradicts this table
  trust             TEXT NOT NULL DEFAULT 'unverified'
                    CHECK (trust IN ('verified','marginals_only','unverified','disputed')),
  trust_note        TEXT,
  notes             TEXT
);

-- --------------------------------------------------------- geography
CREATE TABLE geography (
  geo_id        INTEGER PRIMARY KEY,
  level         TEXT NOT NULL
                -- 'macroregion' is the Atlas de Genero's four-zone split.
                -- It does NOT nest into 'region' and is left unparented so
                -- a join cannot silently mix the two geographies.
                CHECK (level IN ('national','region','province',
                                 'municipality','macroregion')),
  code          TEXT,                     -- ONE provincia code, 01..32
  code_scheme   TEXT,
  code_verified INTEGER DEFAULT 0 CHECK (code_verified IN (0,1)),
  name_es       TEXT NOT NULL,            -- as printed, accents preserved
  name_norm     TEXT NOT NULL,            -- accent-folded upper; the join key
  parent_geo_id INTEGER REFERENCES geography(geo_id)
);
CREATE UNIQUE INDEX ux_geo_norm ON geography(level, name_norm);
CREATE INDEX ix_geo_code       ON geography(code);

-- ------------------------------------------------- controlled vocabulary
-- One row per legal value of a dimension or attribute. `is_residual`
-- marks the categories that are NOT substantive units of analysis
-- (TOTAL, Otros paises, No declarada) so queries stop hardcoding
-- NOT IN ('Republica Dominicana','TOTAL') string lists.
CREATE TABLE vocab (
  domain      TEXT NOT NULL,              -- measure/basis/vital_event/dim_name/nationality/...
  term        TEXT NOT NULL,
  label_es    TEXT,
  is_residual INTEGER NOT NULL DEFAULT 0 CHECK (is_residual IN (0,1)),
  sort_order  INTEGER,
  note        TEXT,
  PRIMARY KEY (domain, term)
);

-- Age bands with numeric bounds, so age-gap arithmetic never parses
-- strings. A future edition that renames '50+' to '50 y mas' adds a row
-- here and every downstream query keeps working.
CREATE TABLE age_band_ref (
  band        TEXT PRIMARY KEY,
  lower_age   INTEGER,
  upper_age   INTEGER,                    -- NULL = open-ended
  midpoint    REAL,
  is_residual INTEGER NOT NULL DEFAULT 0 CHECK (is_residual IN (0,1)),
  sort_order  INTEGER
);

-- Nationality labels -> canonical ISO3. Editions spell these differently
-- ('Republica Dominicana' / 'Rep. Dominicana' / 'República Dominicana');
-- all variants map to one iso3 so pairing joins survive an edition bump.
CREATE TABLE nationality_ref (
  label       TEXT PRIMARY KEY,           -- label exactly as it appears in fact
  iso3        TEXT,                       -- NULL for residual categories
  canonical   TEXT NOT NULL,
  is_residual INTEGER NOT NULL DEFAULT 0 CHECK (is_residual IN (0,1)),
  sort_order  INTEGER
);
CREATE INDEX ix_nat_iso3 ON nationality_ref(iso3);

-- Constructs that look alike and are not.
CREATE TABLE construct_registry (
  construct     TEXT PRIMARY KEY,
  definition_es TEXT,
  note          TEXT
);

-- ---------------------------------------------------------------- fact
CREATE TABLE fact (
  fact_id        INTEGER PRIMARY KEY,
  table_id       INTEGER NOT NULL REFERENCES source_table(table_id),
  reference_year INTEGER NOT NULL,
  edition_year   INTEGER NOT NULL,
  vital_event    TEXT,
  measure        TEXT NOT NULL,
  value          REAL,                    -- NULL when the cell is a symbol
  value_symbol   TEXT,                    -- '..' / '-' / 'n/d' as printed
  basis          TEXT,                    -- registro/ocurrencia/residencia
  geo_id         INTEGER REFERENCES geography(geo_id),
  dim1_name TEXT, dim1_value TEXT,
  dim2_name TEXT, dim2_value TEXT,
  dim3_name TEXT, dim3_value TEXT,
  dim4_name TEXT, dim4_value TEXT,
  is_marginal    INTEGER NOT NULL DEFAULT 0 CHECK (is_marginal IN (0,1)),
  anomaly_flag   TEXT,
  note           TEXT,

  -- Natural key. SQLite treats NULLs as distinct in a UNIQUE index, so
  -- the nullable dim columns are folded through COALESCE into a stored
  -- generated column. This is what makes re-running a loader idempotent
  -- instead of doubling the table.
  nk TEXT GENERATED ALWAYS AS (
        table_id || '|' || reference_year || '|' || edition_year || '|' ||
        COALESCE(measure,'') || '|' || COALESCE(basis,'')  || '|' ||
        COALESCE(geo_id,'')  || '|' ||
        COALESCE(dim1_name,'') || '=' || COALESCE(dim1_value,'') || '|' ||
        COALESCE(dim2_name,'') || '=' || COALESCE(dim2_value,'') || '|' ||
        COALESCE(dim3_name,'') || '=' || COALESCE(dim3_value,'') || '|' ||
        COALESCE(dim4_name,'') || '=' || COALESCE(dim4_value,'')
      ) STORED,

  -- Dimension slots fill left to right. Without this a loader can drop a
  -- cross-tab into dim2/dim3 and every dim1 query silently misses it.
  CHECK (dim1_name IS NOT NULL OR dim2_name IS NULL),
  CHECK (dim2_name IS NOT NULL OR dim3_name IS NULL),
  CHECK (dim3_name IS NOT NULL OR dim4_name IS NULL),
  CHECK (dim1_name IS NULL OR dim1_value IS NOT NULL),
  CHECK (dim2_name IS NULL OR dim2_value IS NOT NULL),
  -- A cell is either a number or a printed symbol, never neither.
  CHECK (value IS NOT NULL OR value_symbol IS NOT NULL)
);
CREATE UNIQUE INDEX ux_fact_nk    ON fact(nk);
CREATE INDEX ix_fact_year         ON fact(reference_year, edition_year);
CREATE INDEX ix_fact_event        ON fact(vital_event, measure);
CREATE INDEX ix_fact_geo          ON fact(geo_id);
CREATE INDEX ix_fact_d1           ON fact(dim1_name, dim1_value);
CREATE INDEX ix_fact_d2           ON fact(dim2_name, dim2_value);
CREATE INDEX ix_fact_table        ON fact(table_id, is_marginal);
-- Covering index for the pairing scan: satisfies v_pairing without
-- touching the base table.
CREATE INDEX ix_fact_pair_cover   ON fact(dim1_name, dim1_value, dim2_value,
                                          reference_year, is_marginal, value);

-- Vocabulary enforcement. A future loader that writes measure='counts'
-- or dim1_name='bride_nation' fails here instead of quietly creating a
-- second dimension nobody joins to.
CREATE TRIGGER trg_fact_vocab_ins BEFORE INSERT ON fact
BEGIN
  SELECT RAISE(ABORT,'unknown measure')
    WHERE NOT EXISTS (SELECT 1 FROM vocab WHERE domain='measure' AND term=NEW.measure);
  SELECT RAISE(ABORT,'unknown vital_event')
    WHERE NEW.vital_event IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM vocab WHERE domain='vital_event' AND term=NEW.vital_event);
  SELECT RAISE(ABORT,'unknown basis')
    WHERE NEW.basis IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM vocab WHERE domain='basis' AND term=NEW.basis);
  SELECT RAISE(ABORT,'unknown dim1_name')
    WHERE NEW.dim1_name IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM vocab WHERE domain='dim_name' AND term=NEW.dim1_name);
  SELECT RAISE(ABORT,'unknown dim2_name')
    WHERE NEW.dim2_name IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM vocab WHERE domain='dim_name' AND term=NEW.dim2_name);
END;

-- ------------------------------------------------------ denominators
-- The structural gap in v1: counts with no population at risk. Every
-- pairing RATE needs an exposure base (how many Dominican women 25-29
-- in La Altagracia were available to marry a foreign man). This table is
-- the slot; README lists exactly which ONE/ENI series fill it.
CREATE TABLE population (
  pop_id         INTEGER PRIMARY KEY,
  source_id      INTEGER NOT NULL REFERENCES source_document(source_id),
  reference_year INTEGER NOT NULL,
  edition_year   INTEGER NOT NULL,
  geo_id         INTEGER REFERENCES geography(geo_id),
  sex            TEXT CHECK (sex IN ('male','female','both')),
  age_band       TEXT REFERENCES age_band_ref(band),
  nationality    TEXT,                    -- NULL = all; else nationality_ref.label
  marital_status TEXT,                    -- soltero/casado/union libre/... (ENI, censo)
  measure        TEXT NOT NULL,           -- persons / percent
  value          REAL NOT NULL,
  note           TEXT
);
CREATE INDEX ix_pop_key ON population(reference_year, geo_id, sex, age_band, nationality);

-- ------------------------------------------------------ reconciliation
-- Computed at build time from the facts themselves. Deltas are kept
-- signed and per-key: for pairing work the PATTERN of where a table
-- fails to add up is diagnostic, and a single boolean throws it away.
CREATE TABLE reconciliation (
  recon_id        INTEGER PRIMARY KEY,
  table_id        INTEGER NOT NULL REFERENCES source_table(table_id),
  axis            TEXT NOT NULL CHECK (axis IN ('row','column','grand','cross_table')),
  key_value       TEXT,
  published_total REAL,
  summed_cells    REAL,
  delta           REAL,                   -- published - summed
  pct_delta       REAL,
  verdict         TEXT NOT NULL CHECK (verdict IN ('ok','mismatch','no_published_total'))
);
CREATE INDEX ix_recon_table ON reconciliation(table_id, verdict);

-- Registered, human-written findings. Anything an analyst must know
-- before quoting a number lives here, keyed to the table it affects.
CREATE TABLE known_issue (
  issue_id   INTEGER PRIMARY KEY,
  scope      TEXT NOT NULL,               -- 'source_table' / 'schema' / 'coverage'
  ref        TEXT,                        -- cuadro or table name
  severity   TEXT NOT NULL CHECK (severity IN ('blocking','high','medium','low')),
  summary    TEXT NOT NULL,
  evidence   TEXT,
  resolution TEXT
);
