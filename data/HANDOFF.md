# Handoff

State as of the last commit on `claude/fervent-knuth-xdt58r`.

```
10,054 facts · 37 cuadros · 5 sources · 23,220 population rows · 4 couplings
trust: 26 verified · 8 unverified · 2 disputed · 1 marginals_only
```

Verify in one step: `python data/build.py && python data/validate.py`
→ should print 10,054 facts and **0 failures, 2 warnings** (both warnings are
expected and documented).

## Read these first, in order

1. `data/README.md` — schema, design rules, current results
2. `data/DOCUMENTS.md` — all 16 source documents, what was taken, what wasn't, and six source defects
3. `data/STRATEGY.md` — acquisition plan and the coupling arithmetic that drives it

## The objective

Maximize **couplings** — pairings where both sides of a couple are observed on
one record. A published cross-tab yields 1. A dyad source with K attributes per
side yields K². That ratio drives every priority decision.

Currently **4**, all `grain='cell'`, over just two attributes per side
(nationality, age band). Zero record-grain dyads.

## Immediate next task

The user has ONE cuadro spreadsheets in `C:\Users\maxwe\Downloads`, all under
0.1 MB, that appear to be **multi-year time series** — everything loaded so far
is a single 2025 cross-section, so these are the highest-value item available:

```
cuadro-1-30-1-matrimonios-registrados-por-mes-según-año-2001-2025.xlsx
cuadro-1-30-2-matrimonios-registrados-por-año-según-región-provincia.xlsx
cuadro-1-30-3-matrimonios-registrados-por-edad-de-los-contrayentes.xlsx
cuadro-1-30-4-matrimonios-registrados-por-tipo-de-matrimonio.xlsx
cuadro-1-40-1-divorcios-registrados-por-mes-según-año-2001-2025.xlsx
cuadro-1-40-2-divorcios-registrados-por-año-según-región-provincia.xlsx
cuadro-1-40-3-divorcios-registrados-por-causa-de-divorcio-según-año.xlsx
cuadro-1-10-3-nacimientos-por-grupo-edad-madre-al-nacimiento-hijo.xlsx
cuadro-1-10-5-nacimientos-grupo-edad-padre-nacimiento-hijo-según-año.xlsx
```

Survey before extracting. If `1-30-3` (marriages by age of *both* contrayentes)
carries a year dimension, that is a **time series on an existing coupling** and
the single most valuable thing in the set.

Also in Downloads and not yet assessed: `cuadro-nacidos-vivos-…-msp-2013-2020`
and `cuadro-nacidos_muertos_…-2013-2020` (health-ministry births, a different
registration system from the civil registry — do not merge without checking
coverage).

## Working rules that earned their place

- **Survey before extracting.** Every significant find came from looking first.
  The rotated-page section — ten cuadros, invisible to plain text extraction —
  was found this way.
- **Preserve and flag, never drop or fix.** A row failing its own arithmetic is
  a finding about the source. `fact.note` carries it; `known_issue` records it.
- **Trust governs entry to the dyad layer.** A cuadro that fails reconciliation
  never becomes a dyad. Enforced by a check in `validate.py`.
- **`trust` and `transcription_verified` are different facts.** One grades
  arithmetic, the other grades faithfulness to the page. Cuadro 3.5 is a
  faithful copy of a table that contradicts itself.
- **Verify against an independent table.** Cuadro 3.7's de-rotation was
  confirmed because its national bride bands match Cuadro 3.3's row totals
  exactly across all eight.
- **Never mix bandings.** `age_band_ref` is a vocabulary, not a partition;
  marriage, projection and mortality cuadros band ages differently and overlap.

## Traps already hit — do not rediscover

| trap | what happened |
|---|---|
| rotated pages | `/Rotate 0`, content drawn at 90°, word characters **reversed**. Filter `upright=False`, group by x, reverse each word. |
| wrapped row labels | long names wrap *around* their own numbers once de-rotated |
| upright page furniture | breaks the trailing-numbers test; dropped four provinces |
| numeric row labels | year labels are indistinguishable from the year header row |
| nested subtotals | Cuadro 1.9: total = Dominican + foreign *subtotal* + not-declared |
| percentage tables | print under the same title as count tables; decimals split into two tokens and are rejected structurally |
| Excel date coercion | ONE's grouped-age workbook has `5-9` and `10-14` destroyed into dates |
| geography aliases | `Región Ozama` = `Región Metropolitana`; `Baoruco` = `Bahoruco` |
| two projection vintages | disagree ~1%; national and provincial rates use different sources — never mix in one ratio |

## Acquisition

Nothing external is reachable from the cloud session (all statistical hosts 403
by egress policy). A local session has no such limit.

Highest yield, in order: **DHS/ENDESA Couples' Recode** (~400 couplings, and the
only source with both partners' education, wealth and employment), **IPUMS
International** with `SPLOC` (the only route to consensual unions),
**ENI** (mixed-nationality denominators), **ANDA microdata** (duration — confirm
divorce records carry `fecha de matrimonio` before investing).

DHS and IPUMS prohibit redistribution: raw microdata goes in the git-ignored
`private/`, never into the repo.
