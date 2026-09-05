# Source document inventory

All sixteen files delivered through the repo, what each contains, and what
was taken from it. Assessed by keyword survey (`estado civil`, `unión`,
`matrimonio`, `pareja`, `cónyuge`, `jefatura de hogar`) plus inspection.

## Extracted and loaded

| document | what was taken |
|---|---|
| **Anuario de Estadísticas Vitales 2025** (PDF, 103 pp) | 8 cuadros, 960 facts. Settled the Cuadro 3.5 dispute. |
| **Proyecciones, edades simples 1950-2100** (XLSX) | National population by sex × single age → 540 rows, 2013–2030. **The national denominator.** |
| **Proyecciones subnacionales 2000-2030** (PDF, 614 pp) | Cuadro 5.3 → 38,556 rows: 32 provinces + 10 regions × sex × 5-year band × year → 22,680 population rows. **The provincial denominator.** |
| **Dominicana en Cifras 2021** (PDF, 502 pp) | Cuadros 2.1-09…2.1-12 → 560 facts: marriages and divorces by province and by month of registration, 2016–2020. **The only provincial divorce data anywhere in this collection.** |

## Reviewed, not loaded — with reasons

| document | finding |
|---|---|
| **Atlas de Género 2020** (85 pp) | Highest `pareja` keyword density of all sixteen, but the content is **intimate-partner violence** (ENESIM 2018) and feminicide by partner relationship — percentages of women by macro-region, not dyads. Genuinely couple-*related*; yields **no couplings**, since neither partner's attributes are cross-tabulated. Worth loading if the question becomes IPV rather than pairing; the macro-region granularity (4 zones) will not join to the province-level work here. |
| **Proyecciones, sexo e índice de masculinidad** (XLSX) | National totals by sex, no age. Superseded by the single-age workbook. |
| **Proyecciones, sexo y grupos de edades** (XLSX) | Superseded, and **corrupt at source**: the `5-9` and `10-14` row labels have been coerced into Excel dates (`2026-09-05`, `2014-10-01`) in all three sex blocks. |
| **Boletín: La población dominicana en el siglo XXI** (16 pp) | Narrative summary of the projections. No tables not already held. |
| **Documento metodológico** (31 pp) · **Estimaciones nacionales** (147 pp) · **Volumen I** (92 pp) · **Proyecciones derivadas Vol. III** (135 pp) · **Tomo II, mortalidad** (64 pp) · **Tomo IV** (154 pp) · **Subnacionales 1990-2020, 2007 rev.** (433 pp) | Projection methodology and superseded vintages. Their `estado civil` keyword hits are incidental prose, not tables. The 2007 subnacional revision stops at 2020 and is superseded by the 2016 revision covering 2000–2030. |

## Source defects found

Recorded because each would have silently corrupted a load:

1. **Cuadro 3.5 contradicts itself** (Anuario, pp.85–86). All 17 printed row totals disagree with the cells beside them; the Estados Unidos row total (1,565) is smaller than a cell in that row (1,904).
2. **Grouped-age workbook**: `5-9` and `10-14` labels destroyed by Excel date coercion.
3. **Subnacional headings mislabelled**: `DISTRITO NACIONAL:` and `SANTO DOMINGO:` carry no `PROVINCIA` prefix (Santo Domingo also omits the space before `Estimaciones`); `PROVINCIA CIBAO NORDESTE` and `PROVINCIA VALDESIA` are regions; `REGIÓN BAORUCO` is a province. Level is therefore resolved from the name against `reference.py`, never from ONE's heading.
4. **One San Cristóbal page headed `Cuadro 3`** instead of `Cuadro 5.3` — filtering on the cuadro number silently dropped eight years for that province. Pages are found by title line instead.
5. **Percentage tables printed under the same title as count tables** (e.g. p.419). Rejected structurally: decimals split into two integer tokens, so the row's value count never matches the year header. Never padded.
6. **`Región Metropolitana` vs `Región Ozama`** — same place, different name across ONE products. `reference.GEO_ALIASES` reconciles them.
