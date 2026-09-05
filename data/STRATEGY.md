# Data acquisition & database management strategy

Objective: **maximize recoverable couplings** — pairings where both sides
of a couple are observed on the same record — for Dominican partnership
formation and dissolution.

---

## 1. The arithmetic that decides everything

A published cross-tab yields exactly **one** coupling: the single pairing
the statistical office chose to typeset. A dyad source carrying *K*
harmonized attributes per side yields **K²**, each conditionable on every
other variable in the file.

| source | couplings |
|---|---:|
| every Anuario cuadro currently loaded | **2** |
| all Anuario editions ever published, all cuadros | ~6 |
| one DHS/ENDESA couples' recode file | ~400 |
| one IPUMS census sample with `SPLOC` | ~144 |

Ten more Anuario editions multiply *rows*, not *pairings*. One microdata
file changes the class of question the database can answer. Everything
below follows from that ratio.

Consequence for sequencing: **Tier A (dyad-level) before Tier B
(tabular)**, even though Tier B is trivially easier to obtain. The
exception is denominators — see §3.

---

## 2. Hard constraint: nothing is reachable from here

Every statistical host tested returns 403 at the proxy — a policy denial,
not a network fault:

```
one.gob.do  anda.one.gob.do  ipums.org  dhsprogram.com  microdata.worldbank.org
api.worldbank.org  unstats.un.org  data.un.org  mics.unicef.org  humdata.org
ilostat.ilo.org  statistics.cepal.org
```

Only pypi, npm and github are allowlisted. **No acquisition can be
automated from this session.** Two ways forward, and the first is worth
far more than the second:

1. **Widen the egress allowlist** (an org admin action). This is the
   highest-leverage infrastructure change available; it converts the
   whole plan from operator-fed to scheduled.
2. **Operator-fed pipeline** — the working assumption. You download; the
   repo ingests, harmonizes, validates and mines. Every loader is written
   to take a local path and verify a sha256, so a hand-delivered file is a
   first-class input rather than a workaround.

Tier A sources need a manual login regardless (IPUMS, DHS and ANDA all
require registration), so operator-fed is the steady state for the files
that matter most. The allowlist mainly buys you Tier B and C automation.

---

## 3. Acquisition plan

Held in the database as data — `SELECT * FROM v_acquisition_plan` — so the
plan is queryable and auditable rather than a list of intentions. Ranked
by expected coupling yield per unit of effort.

| # | source | linkage mechanism | est. couplings | access |
|---|---|---|---:|---|
| 1 | **DHS / ENDESA couples' recode** | dyad is pre-linked by DHS | 400 | registration |
| 2 | **IPUMS International, DR census** | `SPLOC` spouse pointer | 144 | registration |
| 3 | **ONE projections by province × sex × age** | *denominator, 0 couplings* | 0 | open |
| 4 | **ONE marriage microdata (ANDA)** | both spouses on one record | 64 | manual login |
| 5 | **ONE divorce microdata (ANDA)** | both spouses + marriage date | 64 | manual login |
| 6 | **Censo 2022 roster** | relationship-to-head reconstruction | 144 | request |
| 7 | **ENI 2012 / 2017** | immigrant stock + union status | 100 | request |

Notes that change what you should ask for:

- **IPUMS is the only source that reaches consensual unions.** No marriage
  registry ever sees them, and they are a large share of Dominican
  partnerships. A registry-only strategy systematically studies the
  minority of couples that formalize.
- **Divorce microdata is worthless without `fecha de matrimonio`.**
  Confirm that field exists before spending effort; without it there is no
  duration, and the file is failures with no population at risk. Acquire
  it *with* marriage microdata or not at all.
- **Denominators are priority 3 despite yielding zero couplings.** They
  convert counts already held into rates. Best analytic return per hour on
  the list.
- DHS couples' recodes only exist where a men's questionnaire was fielded
  at adequate sample size. Verify per round before planning around it.

Vintages in `acquisition.verify` are stated from general knowledge of
these programmes and have **not** been checked against a live catalogue,
because the catalogues are unreachable. Confirm before acting.

---

## 4. Database management

### Two layers, one store

**Layer 1 `fact`** — published aggregates, long format, immutable, with
provenance and a derived `trust` grade. Answers only what ONE typeset.

**Layer 2 `dyad` + `dyad_attribute`** — one row per couple, attributes in
long format. Answers anything.

Both grains coexist in `dyad`:

- `grain='cell'` — one cross-tab cell, `weight` = the published count
- `grain='record'` — one real couple, `weight` = the survey weight

So `v_couplings` works **today** on aggregates and keeps working unchanged
when microdata lands beside it. No migration, no second pipeline. Mixing
grains in a headline figure overstates precision, which is why `grain`
is carried through every view rather than summed away.

### The mining engine

`v_couplings` self-joins `dyad_attribute` across the two sides. Add a
source with *K* attributes per side and *K²* couplings appear with no
schema change and no new view:

```sql
SELECT * FROM v_couplings WHERE attr_a='age_band' AND attr_b='nationality';
SELECT * FROM v_coupling_inventory;   -- what exists, and how much weight
SELECT * FROM v_coupling_yield;       -- held vs planned, same unit
SELECT * FROM v_dyad_gaps;            -- attributes on one side only
```

`v_dyad_gaps` is the cheapest yield on the board: an attribute captured
for one partner but not the other is a coupling that an ingest fix away.

### Governing rules

1. **Trust governs entry.** A cuadro that fails reconciliation never
   becomes a dyad. Validated: `no dyad derives from a cuadro that fails
   reconciliation`. Otherwise layer 2 launders the numbers layer 1 marks
   unusable — Cuadro 3.5 is currently excluded on exactly this rule.
2. **Aggregates become tests.** Once microdata exists, every published
   marginal is an assertion the dyads must reproduce; `constraint_check`
   holds them. A divergence means a weighting error, a coverage
   difference, or a bad load — and you want to know which *before*
   publishing, not after. Today the checks are tautological (dyads are
   derived from those cuadros) and only prove the derivation is lossless.
   They become real on the first microdata ingest, which is why they are
   written now.
3. **Weights are not optional.** `weight`, `psu`, `strata` on every dyad.
   Survey dyads loaded without design variables produce confidence
   intervals that are simply wrong, and nothing downstream will catch it.
4. **Harmonize at ingest, via `crosswalk`.** ENDESA's education ladder,
   the census's, and the Anuario's are three vocabularies for one concept.
   Each source's raw codes map to a shared term at load time; couplings
   only compose across sources if the categories do.
5. **Roles are recorded, never assumed.** `role_a/role_b` and `sex_a/sex_b`
   are stored per dyad. Do not hardcode bride=female: census consensual
   unions are captured by relationship-to-head, and a schema that presumes
   an opposite-sex registered pair silently drops the couples that do not
   fit it. (For DR *civil marriage* the pairing is a property of the legal
   instrument, so it is recorded as data, not assumed by the schema.)
6. **No cross-source couple linkage.** The same physical couple may appear
   in the census, ENDESA and the registry. Without identifiers they cannot
   be matched, and should not be. Sources are parallel evidence, never
   deduplicated into a single roster.
7. **Idempotent loaders, audited runs.** Natural keys on `fact`;
   `ingest_run` records loader, input sha256, rows in, dyads out, outcome.
   Re-running is always safe.

### Licensing — do not commit microdata

IPUMS and DHS prohibit redistribution; ONE microdata terms need checking
per file. `acquisition.redistributable` records the status per source.
Raw microdata goes in a git-ignored `private/` directory; the repository
carries **loaders and derived aggregates only**. Publishing a DHS extract
to a public repo would breach the licence you agreed to at registration.

### Sensitivity

Haitian and Haitian-descent population figures in the DR are politically
contested and subject to known undercount. Handle as a data-quality
caveat attached to the relevant `known_issue` rows — neither suppressed
nor reported without the caveat.

---

## 5. Current state

```
distinct couplings held ....... 2   (age_band × age_band, nationality × nationality)
weighted dyads ................ 65,461   (40,750 marriages + 24,711 divorces)
acquisition targets ........... 11, of which 10 blocked by egress policy
```

Both held couplings derive from `verified` cuadros only. Cuadro 3.5 is
excluded by rule 1 above and would add a third if it is settled — which
needs page 85, which needs the PDF, which needs either an allowlist change
or a hand delivery.

## 6. What to do next, in order

1. **Ask an admin to allowlist the hosts in §2.** Cheapest structural win;
   unblocks 10 of 11 targets and makes the rest schedulable.
2. **Register for IPUMS International and DHS** — free, manual, and gates
   the two highest-yield sources. Start it now; approval is not instant.
3. **Load ONE population projections.** Zero couplings, but it converts
   every count already held into a rate.
4. **Confirm ANDA carries marriage/divorce microdata and that divorce
   records include the marriage date** before committing effort there.
5. **Deliver the Anuario PDF** to settle Cuadro 3.5 and recover the
   nationality × nationality marriage coupling.
