# Q1 — Compare need estimates to observed activity

**Division:** all three answer this. It is the foundation for Q6 and Q8.
**Owner:** Valentino
**Status:** analysis done; `analysis.py` rebuilds every number and both figures. Slides next.

---

## The ask, in our words

Feeding America estimates how many food-insecure people live in each Minnesota county.
The Food Group counts what actually happens at food shelves. Four things have to come
out of this question:

1. Do the two tell the same story, for each of the **three metrics** (visits, pounds,
   individuals)?
2. **Which metric correlates most and least** with the Feeding America estimates?
3. **Which counties** are where the relationship breaks down?
4. Using public data, **what county characteristics explain the mismatch** — poverty
   rate, rural share, distance to nearest food shelf, SNAP enrollment, and anything else
   we can defend?

**Years: 2022, 2023 and 2024.** The brief originally said 2023–2024; the organizers
widened it to 2022–2024 in a later update (Sept 2026). The window is `cfg.Q1_YEARS` in
`src/config.py`. 2022 and 2023 need come from the same MMG edition (2025); 2024 comes
from the 2026 edition.

---

## Data

| what | where | note |
|---|---|---|
| activity | `data/processed/county_month.parquet` | `qkit.county_year(cfg.Q1_YEARS)` aggregates to county-year |
| need | `data/processed/mmg_county.parquet` | `fi_rate`, `fi_persons`, `child_fi_rate`, `rucc_2023` (rural class, free) |
| covariates | `data/processed/county_covariates.parquet` | `qkit.covariates()`, built by `python src/build_covariates.py` |

Every covariate, its source, and whether it is inside the MMG model (circularity risk).
Full source facts are in the [registry](../../docs/DATA_SOURCES.md#source-registry--fill-in-one-row-per-file-actually-downloaded).

| column | meaning | source | in MMG model? | status |
|---|---|---|---|---|
| `population`, `households_census` | residents, households (April 1) | MN State Demographic Center | no (denominator) | ✅ 2022–24 |
| `poverty_rate`, `child_poverty_rate` | % in poverty, all ages / 0–17 | Census SAIPE | **yes** | ✅ 2022–24 |
| `median_hh_income` | median household income | Census SAIPE | **yes** | ✅ 2022–24 |
| `unemployment_rate` | annual average | BLS LAUS | **yes** | ✅ 2022–24 |
| `pct_no_vehicle` | % households with no vehicle | ACS 5-yr B08201 | no | ✅ 2022–24 |
| `pct_senior`, `senior_poverty_rate` | % aged 65+, % of 65+ in poverty | ACS 5-yr B17001 | partly | ✅ 2022–24 |
| `pct_hh_snap` | % households receiving SNAP | ACS 5-yr B22003 | no | ✅ 2022–24 |
| `n_sites_reporting`, `sites_per_10k` | food-shelf-like sites with activity that year | derived, `site_month` | no | ✅ 2022–24 |
| `mean_km_to_site` | pop-weighted km from tract to nearest reporting site | derived, Gazetteer + CenPop2020 | no | ✅ 2022–24 |
| `rucc_2023` | rural-urban continuum code, 1–9 | USDA ERS, via MMG file | no | ✅ |
| `pct_hh_housing_burden` | % households paying 30%+ of income on rent or owner costs | ACS 5-yr B25070 + B25091 | no | ✅ 2022–24 (Q6 input) |
| `pct_no_hs_diploma` | % adults 25+ without a high-school diploma or GED | ACS 5-yr B15003 | no | ✅ 2022–24 (Q6 input) |
| `lila_share_1and10`, `lila_share_vehicle` | share of population in low-income, low-access tracts | USDA Atlas 2019, via Q8's extract | no | ✅ static (Q6 input) |
| `pct_debt_collections` | % adults with a credit record who have debt in collections | Urban Institute, Aug 2025 | no | ✅ static (Q6 input) |

ACS 5-year tables are assigned to their **end year** (2019–2023 → 2023).

`households` (`HouseholdsReg`) is what the brief labels **visits**. The organizers'
[glossary](../../docs/GLOSSARY.md) defines a visit as one trip by one household; our field
counts a household once per month, so it is a floor on trips. See
[DATA_ERRORS.md §1.2](../../docs/DATA_ERRORS.md).

---

## Approach

1. **Build the county-year frame.** 87 counties × 3 years. Activity from the panel, need
   from MMG, covariates joined on `fips`.
2. **Rates, not counts.** Report both, lead with rates. Denominators: per 1,000 residents
   (PEP) for general use, and **per food-insecure person** for this question specifically,
   since that is what makes "activity against need" a meaningful ratio.
3. **Correlations.** Pearson and Spearman, each metric against `fi_persons` (counts) and
   `fi_rate` (rates), each year separately. Report Spearman as the headline — 87 counties
   with a few very large ones is exactly the case Pearson handles badly.
4. **Find the breakdown counties.** Fit a simple relationship (log activity on log
   food-insecure persons), take the residuals, and rank. The tails are the answer to
   question 3.
5. **Explain the residuals.** Regress residuals on county characteristics. Keep the model
   small — 87 observations does not support a large one.

The EDA script already does a rough version of steps 1–4; start from
`outputs/tables/04_*.csv` rather than from scratch.

---

## What the preview already shows

From `python src/eda.py`:

| year | metric | Pearson (counts) | Spearman (counts) | Spearman (rate vs FI rate) |
|---|---|---|---|---|
| 2022 | households | 0.969 | 0.893 | **−0.149** |
| 2022 | pounds | 0.980 | 0.916 | **−0.129** |
| 2022 | individuals | 0.964 | 0.893 | **−0.180** |
| 2023 | households | 0.952 | 0.889 | **−0.146** |
| 2023 | pounds | 0.976 | 0.907 | **−0.203** |
| 2023 | individuals | 0.937 | 0.891 | **−0.156** |
| 2024 | households | 0.946 | 0.901 | **−0.294** |
| 2024 | pounds | 0.969 | 0.918 | **−0.285** |
| 2024 | individuals | 0.932 | 0.905 | **−0.262** |

Read that carefully, because it is the whole question in one table. In **counts** the two
sources agree almost perfectly — and that agreement is mostly population. In **rates** the
correlation is *negative*: counties with a higher food-insecurity rate serve **fewer**
households per food-insecure person. That is the brief's thesis, visible in our own data
before any modelling.

Counties with the least activity relative to their food-insecure population in 2024:
**Scott, Nicollet, Pope, Norman, Lac qui Parle, Nobles, Douglas, Stevens**.
Most: **Steele, Rice, Washington, Renville, Houston, Kittson, Olmsted, Cook**.
And **Wilkin County has no reporting food shelf at all**, in any month of the data.

Those lists are a starting point, not a finding — they use our current cleaning rules and
the household proxy. Re-derive them properly.

---

## Traps

- **Counts versus counts mostly measures population.** A scatter of county activity
  against county food-insecure persons will look excellent and mean almost nothing. Lead
  with rates.
- **Map the Meal Gap is modelled from poverty and unemployment.** Explaining its
  residuals with poverty is partly circular. Covariates *outside* the MMG model —
  distance, vehicle access, site density, rurality — are worth far more.
- **87 counties. Do not over-model.** Four or five covariates, stated clearly, beats a
  gradient boosting model nobody can explain in Q&A.
- **County means where the site is, not where the client lives.** Counties with a
  regional shelf absorb their neighbours' demand. This is a limitation on every slide.
- **Two MMG editions.** 2023 comes from the 2025 edition, 2024 from the 2026 edition, and
  the methodology changed between them. Do not present a 2023→2024 change as a real
  movement without reading the Read Me tab. 2022→2023 is within one edition and is
  comparable.

---

## Findings (30 September)

The numbers below come from `analysis.py`. The reasoning, and the predictions written
before each result, are in `notebooks/q1_exploration.ipynb`.

**Headline.** Recorded food-shelf activity rises faster than need. A county with ten times
as many food-insecure people records about sixteen times the activity (log-log slope 1.15
to 1.24 across nine metric-years, every interval above 1, R2 0.84 to 0.88). "Records" is
deliberate: activity is counted where the food shelf is, not where the household lives.

| sub-question | answer |
|---|---|
| 1. Same story? | In counts, yes: Spearman about 0.9 for every metric and year, mostly county size. In rates, no: activity per 1,000 residents against the food-insecurity rate is about zero (Spearman -0.03 to 0.17). Same for all three metrics in all three years. |
| 2. Most and least correlated? | Pounds highest, individuals next, households lowest, in the same order every year. The gap is 3 percentage points of R2 (0.87 vs 0.84): consistent but small. |
| 3. Where does it break down? | Wilkin has no reporting food shelf at all. Among counties with activity: Nicollet, Pope and Lac qui Parle record the least relative to need (Nicollet about 30% of predicted); Steele, Washington and Rice the most (Steele about 4 times). All six are on the same side in all nine metric-years, and none moves when non-food-shelf sites are dropped. Cook does: it falls from +0.89 to -0.12. |
| 4. What explains the mismatch? | The characteristics we tested (distance to nearest site, RUCC group, no-vehicle households, SNAP households) explain 3% of it, and none shows a clear association. Distance is the one to follow up: about 10% less recorded activity per extra 4 km, interval -25% to +4%. |

**Robustness, all in the notebook:** the conclusion is the same with RUCC grouped by metro
adjacency, with each covariate alone, with residuals from food-shelf-only sites (distance
-0.13, p = 0.07), and in a one-step model. The site count is the strongest single variable
(+0.11, p = 0.06) and weakens distance when added, because counties with many sites have
short distances. Moran's I on the residuals is 0.06 (p = 0.37): no general spatial
pattern. Two direct tests agree: counties recording less than need predicts border
counties recording more no oftener than chance (join counts, p = 0.88), and pooling
counties with their neighbours tightens the residuals only weakly more than random groups
(p = 0.07). The red/blue border pairs are examples, not evidence of spillover. Three
barriers from Q6 (limited English, no internet, non-citizens) add 1.6 points of R² here
and none is significant; against the Q6 need index the same three explain 10.5%.

**Caveats to state:**

- The residual partly measures the network, not need: counties with more sites record
  more activity per food-insecure person.
- 86 counties can only detect large effects. "No clear association" is not "no effect",
  and more years do not help because a county's years are clustered.
- Rates that divide by food-insecure persons and are plotted against the food-insecurity
  rate share a term and correlate negatively by construction. Use per 1,000 residents.
- 2024 need comes from a different MMG edition; year dummies are 0.00 and 0.01, so it did
  not shift the residuals.
- A residual is a gap between two imperfect measures, not a count of hungry people. The
  glossary's own caution: a visit does not mean a need was met, and a household can be
  food secure and still use a food shelf. So activity above need (Steele) does not mean
  need is overstated there, and activity below need (Nicollet) may be latent demand or
  households served in the next county. Q6 is where the two are told apart.
- Pounds is "a supply measure as much as a demand measure" (glossary). It is the metric
  with the highest R2 against need, and also the one most tied to what a site holds.

---

## Deliverables

- [x] `analysis.py` that rebuilds every number from `data/processed/`
- [x] One chart for the deck: need against activity, breakdown counties labelled (`outputs/figures/q1_loglog_fits.png`, `q1_residual_bars.png`)
- [x] A correlation table covering all three metrics, all three years, counts and rates (`outputs/tables/q1_correlations.csv`)
- [x] A ranked list of breakdown counties with the characteristics that explain them (`q1_residual_ranking.csv`, `q1_covariate_model.csv`)
- [x] One sentence a judge remembers (the headline above)
- [x] Limitations stated by us, before a judge states them (the caveats above)
- [ ] Slides
