# Source document inventory

All sixteen files delivered through the repo, what each contains, and what
was taken from it. Assessed by keyword survey (`estado civil`, `unión`,
`matrimonio`, `pareja`, `cónyuge`, `jefatura de hogar`) plus inspection.

## Extracted and loaded

| document | what was taken |
|---|---|
| **Anuario de Estadísticas Vitales 2025** (PDF, 103 pp) | 11 of its 26 cuadros. The marriage/divorce set (8), plus **1.2 mother × father nationality**, **1.4 mother × father age**, and **1.3 maternal marital status** — two further couplings over a different population, and the only union-status data held. |
| **Proyecciones, edades simples 1950-2100** (XLSX) | National population by sex × single age → 540 rows, 2013–2030. **The national denominator.** |
| **Proyecciones subnacionales 2000-2030** (PDF, 614 pp) | Cuadro 5.3 → 38,556 rows: 32 provinces + 10 regions × sex × 5-year band × year → 22,680 population rows. **The provincial denominator.** |
| **Dominicana en Cifras 2021** (PDF, 502 pp) | Cuadros 2.1-09…2.1-12 → 560 facts: marriages and divorces by province and by month of registration, 2016–2020. **The only provincial divorce data anywhere in this collection.** |
| **Atlas de Género 2020** (PDF, 85 pp) | Cuadros 13–22 → 356 facts: violence against women by sphere, zone and macro-region (ENESIM 2018), plus femicide and intimate femicide by year, perpetrator relationship and planning region, 2009–2018. Couple **context**, not couplings. |

## Reviewed, not loaded — with reasons

| document | finding |
|---|---|
| **Proyecciones, sexo e índice de masculinidad** (XLSX) | National totals by sex, no age. Superseded by the single-age workbook. |
| **Proyecciones, sexo y grupos de edades** (XLSX) | Superseded, and **corrupt at source**: the `5-9` and `10-14` row labels have been coerced into Excel dates (`2026-09-05`, `2014-10-01`) in all three sex blocks. |
| **Boletín: La población dominicana en el siglo XXI** (16 pp) | Narrative summary of the projections. No tables not already held. |
| **Documento metodológico** (31 pp) · **Estimaciones nacionales** (147 pp) · **Volumen I** (92 pp) · **Proyecciones derivadas Vol. III** (135 pp) · **Tomo II, mortalidad** (64 pp) · **Tomo IV** (154 pp) · **Subnacionales 1990-2020, 2007 rev.** (433 pp) | Projection methodology and superseded vintages. Their `estado civil` keyword hits are incidental prose, not tables. The 2007 subnacional revision stops at 2020 and is superseded by the 2016 revision covering 2000–2030. |

## The rotated-page section

Ten of the 2025 Anuario's 26 cuadros are laid out landscape across 26
pages, and the PDF stores them in a way no ordinary text extraction
reaches: the page carries `/Rotate 0`, the table is *drawn* rotated 90°,
and every word's characters are stored in reverse order. `extract_text()`
returns mirrored nonsense — `ortsiger` for *registro*, `033` for `330` —
so these pages looked empty and their cuadros were silently absent.

De-rotation: keep only words with `upright = False` (the running header
and folio are upright and would corrupt the line), group into visual lines
by x-position, order each line by descending `top`, reverse each word.

| cuadro | content | loaded |
|---|---|---|
| **3.7** | marriages by **bride age band × province** | ✅ enables provincial age-specific rates |
| **1.10** | **mother's marital status × age band** | ✅ the only union-status-by-age data held |
| **3.6** | marriages by month × province | ✅ |
| **4.6** | divorces by month × province | ✅ |
| **1.1** | births by mother nationality × province | ✅ |
| **1.9** | births by mother's country of birth × province | ✅ 3 rows flagged |
| **1.11** | births by month × province | ✅ |
| **1.12** | births by year of registration × year of occurrence | ✅ registration lag |
| **2.2** | deaths by month × province | ✅ |
| **2.5** | deaths by nationality × province | ✅ |
| **2.6** | deaths by age × sex × province | ✅ 3,087 rows: 2 column blocks × 4 sex sections × 43 geographies |

All ten rotated cuadros are loaded. Verification: every row's printed total was checked against the sum of its
cells (0 rejected), all 43 geographies resolve for 3.6/3.7/4.6, and
Cuadro 3.7's national bride-band totals match Cuadro 3.3's row totals
exactly across all eight bands — an independent confirmation that the
de-rotation is correct.

## Source defects found

Recorded because each would have silently corrupted a load:

1. **Cuadro 3.5 contradicts itself** (Anuario, pp.85–86). All 17 printed row totals disagree with the cells beside them; the Estados Unidos row total (1,565) is smaller than a cell in that row (1,904).
2. **Grouped-age workbook**: `5-9` and `10-14` labels destroyed by Excel date coercion.
3. **Subnacional headings mislabelled**: `DISTRITO NACIONAL:` and `SANTO DOMINGO:` carry no `PROVINCIA` prefix (Santo Domingo also omits the space before `Estimaciones`); `PROVINCIA CIBAO NORDESTE` and `PROVINCIA VALDESIA` are regions; `REGIÓN BAORUCO` is a province. Level is therefore resolved from the name against `reference.py`, never from ONE's heading.
4. **One San Cristóbal page headed `Cuadro 3`** instead of `Cuadro 5.3` — filtering on the cuadro number silently dropped eight years for that province. Pages are found by title line instead.
5. **Percentage tables printed under the same title as count tables** (e.g. p.419). Rejected structurally: decimals split into two integer tokens, so the row's value count never matches the year header. Never padded.
6. **Atlas Cuadro 22 does not add up** in three of its ten years, and its two breakdowns fail in *different* years — 2014 is wrong in the perpetrator split only, while 2015 and 2017 are short in both the perpetrator and the regional split. Consistent with cases of unknown relationship/region being dropped from each split instead of shown as a residual.
7. **`Región Metropolitana` vs `Región Ozama`** — same place, different name across ONE products. `reference.GEO_ALIASES` reconciles them.
