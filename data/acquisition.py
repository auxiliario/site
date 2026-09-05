"""
The acquisition plan, as data.

Ranked by expected COUPLING YIELD, not by how easy the download is. The
arithmetic behind the ranking:

  a published cross-tab yields  1 coupling  (the one pairing it prints)
  a dyad source with K harmonized attributes per side yields K^2

So every Anuario edition ever published, all cuadros combined, yields
fewer couplings than a single DHS couples' recode file. That is why
Tier A dominates the plan even though Tier B is trivially easier.

`est_couplings` is K^2 for a defensible K per instrument; it is an order
of magnitude, not a promise. `verify` records what must be confirmed
against the actual catalogue before acting -- vintages and file
availability are stated here from general knowledge of these programmes
and have NOT been checked against a live catalogue from this session,
because every statistical host is blocked by this environment's egress
policy.
"""

# tier, institution, dataset, vintages, grain, couple_linkage,
# est_couplings, access, redistributable, priority, verify, note
TARGETS = [
 # ---------------------------------------------------------- TIER A: dyads
 ("A_dyad", "DHS Program (ENDESA)",
  "Demographic and Health Survey -- Couples' Recode (CR)",
  "DR rounds since 1986; last full ENDESA 2013", "record",
  "DHS builds the CR file by matching interviewed wives to interviewed "
  "husbands in the same household. The dyad is pre-linked; no work needed.",
  400, "registration", 0, 1,
  "Confirm which DR rounds published a CR file (not every round fields the "
  "men's questionnaire at the sample size needed) and the exact CR filenames.",
  "Richest per-couple attribute set of anything on this list: both partners' "
  "age, education, wealth quintile, age at first union, fertility, "
  "contraception, employment, plus dyad-level decision-making modules. "
  "Registration is free but manual; files may not be redistributed."),

 ("A_dyad", "IPUMS International",
  "Harmonized DR census microdata (SPLOC pointer)",
  "DR samples across the 1960-2010 census rounds", "record",
  "IPUMS constructs SPLOC (spouse's position in household), plus MOMLOC / "
  "POPLOC. Every co-resident couple becomes a dyad by self-join on SPLOC -- "
  "including CONSENSUAL UNIONS, which no marriage registry ever sees.",
  144, "registration", 0, 2,
  "Confirm which DR sample years are currently released and that SPLOC is "
  "available for each.",
  "The only source that reaches unions outside the registry, and the DR has "
  "a very large consensual-union population. Harmonized variables mean "
  "cross-year and cross-country comparability comes free."),

 ("A_dyad", "ONE / ANDA",
  "Marriage record microdata (Estadisticas Vitales)",
  "per year; coverage to confirm", "record",
  "One record per marriage, both contrayentes on the same row. Dyad is "
  "native.", 64, "manual_login", 0, 3,
  "Whether ANDA publishes marriage microdata at all, or only the Anuario "
  "tabulations; and whether province of RESIDENCE is carried alongside "
  "province of registro.",
  "Settles every three-way question the cuadros cannot: age gap x "
  "nationality x province. Also the only route to a residence-based "
  "denominator for provincial rates."),

 ("A_dyad", "ONE / ANDA",
  "Divorce record microdata",
  "per year; coverage to confirm", "record",
  "One record per divorce. Critical field: FECHA DE MATRIMONIO. Without "
  "it there is no duration, and the whole file becomes failures with no "
  "population at risk.",
  64, "manual_login", 0, 4,
  "Whether the marriage date is present. If it is not, median duration "
  "before divorce is not computable from this source at any price.",
  "Acquire together with marriage microdata or not at all."),

 ("A_dyad", "ONE",
  "Censo Nacional de Poblacion y Vivienda 2022 -- household roster",
  "2022", "record",
  "Relationship-to-head codes reconstruct couples within a household, the "
  "same mechanism IPUMS automates. Requires building the SPLOC equivalent "
  "by hand.", 144, "request", 0, 5,
  "Whether ONE releases roster-level microdata or only tabulations, and "
  "under what conditions.",
  "Most recent population base, and the natural denominator source. If "
  "IPUMS already carries a 2022 DR sample, prefer IPUMS -- linkage is "
  "prebuilt."),

 ("A_dyad", "ONE",
  "Encuesta Nacional de Inmigrantes (ENI)",
  "2012, 2017", "record",
  "Immigrant and descendant population with union status; supplies the "
  "foreign-side denominator that no vital-statistics table contains.",
  100, "request", 0, 6,
  "Vintages available and whether partner attributes are captured for "
  "respondents in a union.",
  "Without this, mixed-nationality pairing has no exposure base and "
  "La Altagracia looks like an outlier purely because more people marry "
  "there."),

 ("A_dyad", "UNICEF / ONE",
  "MICS / ENHOGAR-MICS household survey",
  "DR MICS rounds; ENHOGAR series", "record",
  "Household roster with relationship codes; couples reconstructible.",
  100, "registration", 0, 7,
  "Which DR rounds are released and whether a men's questionnaire was "
  "fielded (no men's file means no dyad, only reported partner traits).",
  "Fills years between census rounds."),

 # ------------------------------------------------------- TIER B: tabular
 ("B_tabular", "ONE",
  "Anuario de Estadisticas Vitales -- all prior editions",
  "one edition per year", "cell",
  "Published two-way cuadros only. Each cuadro = 1 coupling.",
  6, "open", 1, 8,
  "Which editions are online and their cuadro numbering (it shifts).",
  "Cheap and already handled by the existing loader. Real value is the "
  "TIME SERIES and the restatement signal, not new couplings. Loading ten "
  "editions multiplies rows, not pairings."),

 ("B_tabular", "UN Statistics Division",
  "Demographic Yearbook -- marriages by age of bride and groom",
  "annual", "cell",
  "A standardized bride x groom age cross-tab, compiled from national "
  "returns.", 2, "open", 1, 9,
  "Whether the DR reports this table and for which years.",
  "Independent cross-check on Cuadro 3.3, and the same table for other "
  "countries makes DR age-gap patterns comparable rather than merely "
  "described."),

 # ------------------------------------------------------- TIER C: context
 ("C_context", "ONE",
  "Estimaciones y Proyecciones de Poblacion",
  "by province, sex, five-year age group", "cell",
  "Not a coupling source. It is the DENOMINATOR without which every "
  "pairing figure is a count with no population at risk.",
  0, "open", 1, 3,
  "Base year and revision in force; projections get restated.",
  "Priority 3 despite yielding zero couplings, because it converts counts "
  "already held into rates. Highest analytic return per hour on this list."),

 ("C_context", "World Bank / UN DESA",
  "Comparative marriage, divorce and marital-status indicators",
  "annual panels", "cell",
  "Country-level series; no dyads.", 0, "open", 1, 10,
  "Which series actually cover the DR without long gaps.",
  "Context and sanity-checking only."),
]
