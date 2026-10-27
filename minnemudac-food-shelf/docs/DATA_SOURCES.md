# Public data sources

The brief requires four facts for **every** public source we use:

1. the publisher and the **exact** series,
2. the **geographic grain** (county, tract, region),
3. the **time grain** (monthly, bimonthly, annual),
4. **why this source and not an alternative.**

This page is where that record lives. It has two parts: a candidate list per question,
with the four facts filled in as far as we can before downloading, and a registry table
that must be completed for every file we actually put in `data/external/`.

> **Rule:** nothing goes into `data/external/` without a row in the registry at the
> bottom of this file. An undocumented source is worth zero points and is a gift to a
> judge looking for a weakness.

> **Leakage rule:** nothing dated **August 2026 or later** enters this repo. Not a CPI
> release, not a SNAP caseload table, not a refreshed Map the Meal Gap. Q7 asks us to
> predict August 2026 and the brief says using August data from any source disqualifies
> the team. When you download a monthly series, **truncate it to 2026-07 before saving**.

---

## Already in the repo

| source                                         | file                                                               | grain  | time grain        | used by |
| ---------------------------------------------- | ------------------------------------------------------------------ | ------ | ----------------- | ------- |
| Feeding America, Map the Meal Gap 2025 edition | `data/raw/feeding_america/MMG2025_2019-2023_Data_To_Share_v2.xlsx` | county | annual, 2019–2023 | Q1, Q6  |
| Feeding America, Map the Meal Gap 2026 edition | `data/raw/feeding_america/MMG2026_2024_Data_To_Share.xlsx`         | county | annual, 2024 only | Q1, Q6  |

Both are mandated by the brief for Questions 1 and 6. Read the **Read Me** tab of the
2025 file before comparing 2023 to 2024: it records a methodology change for local meal
cost, food budget shortfall and meal gap. It also carries the Rural-Urban Continuum Code
(2013 and 2023 vintages), which gives us a free rural/urban classifier with no extra
download.

---

## Q1 — county characteristics that might explain the mismatch

The brief names four examples: poverty rate, rural share, distance to nearest food shelf,
SNAP enrollment. Take those as a floor, not a ceiling.

| #   | source                                         | exact series                                                                  | geographic grain        | time grain            | why this one                                                                                                                                              |
| --- | ---------------------------------------------- | ----------------------------------------------------------------------------- | ----------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Census Bureau, **SAIPE**                       | Small Area Income and Poverty Estimates, "All ages in poverty, percent"       | county                  | annual, ~1 year lag   | The standard county poverty number. ACS 5-year is also county-level but is a 5-year average, which blurs exactly the year-to-year movement Q1 asks about. |
| 2   | Census Bureau, **Population Estimates (PEP)**  | `CO-EST` annual county resident population                                    | county                  | annual                | Every rate in this project needs a denominator. PEP is the annual series; the decennial count is only every ten years.                                    |
| 3   | USDA ERS, **Rural-Urban Continuum Codes 2023** | already inside the Map the Meal Gap file                                      | county                  | decennial-ish vintage | Free — no download needed. Prefer it to "metro/non-metro" because it is a 9-point scale, so "how rural" becomes a continuous covariate.                   |
| 4   | Census Bureau, **ACS 5-year**                  | `B08201` (household vehicle availability), `B17001` (poverty by age), `S1701` | county **and tract**    | 5-year rolling        | Vehicle access is the barrier the brief names indirectly ("no transport"). Tract-level availability also makes it reusable in Q6 and Q8.                  |
| 5   | Census, **2020 Gazetteer**                     | `2020_Gaz_tracts_27.txt`, `2020_Gaz_blocks_27.txt`                            | tract / block centroids | static                | The only way to turn `block_geoid` into a distance. See [BLOCK_GEOID.md](BLOCK_GEOID.md).                                                                 |
| 6   | BLS, **LAUS**                                  | Local Area Unemployment Statistics, county unemployment rate                  | county                  | **monthly**           | The one labour-market series published monthly at county level. Q1 uses the annual average; Q4 and Q7 can use the monthly.                                |

**The trap to write on the slide:** Map the Meal Gap is itself _modelled_ from poverty
and unemployment. "Poverty explains the mismatch" is therefore partly mechanical — you
are partly regressing a variable on its own inputs. Covariates that are **not** in the
MMG model (distance, vehicle access, site density, rurality) carry much more information
and should lead the Q1 story.

---

## Q4 — food prices and food shelf activity

| #   | source                           | exact series                                                            | geographic grain      | time grain    | why this one                                                                                                                                                                                    |
| --- | -------------------------------- | ----------------------------------------------------------------------- | --------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | BLS, **CPI**                     | `CUUR0200SAF11` — Food at home, **Midwest region**, all urban consumers | Midwest census region | **monthly**   | The finest _monthly_ food-price series that covers all of Minnesota. National CPI would ignore regional price movement; Minneapolis-St. Paul CPI is bimonthly and covers only the metro.        |
| 2   | BLS, **CPI**                     | `CUUSA211SAF11` — Food at home, **Minneapolis-St. Paul-Bloomington**    | metro area            | **bimonthly** | Use as a robustness check on the metro counties only. State plainly that it is bimonthly and metro-only.                                                                                        |
| 3   | USDA ERS, **Food Price Outlook** | annual/forecast food-at-home price change                               | national              | annual        | Context for the deck, not for identification.                                                                                                                                                   |
| 4   | Feeding America                  | `Cost Per Meal`, already in Map the Meal Gap                            | **county**            | annual        | The only _county-level_ price signal we have. Annual grain means it cannot carry the lag analysis, but it can carry cross-sectional heterogeneity: do high-cost-per-meal counties respond more? |

**The trap:** prices and activity both trend upward over 2022–2026, so a correlation in
_levels_ is spurious. Work in **year-over-year percentage change**, include
month-of-year effects, and test lags 0–6 months. With one CPI series for all counties,
identification is purely over time — there is no cross-county variation in the driver,
so do not present a county-level "price effect" from the Midwest series.

---

## Q5 — SNAP enrollment and food shelf use

| #   | source            | exact series                                                                                                        | geographic grain | time grain                                         | why this one                                                                                                                                                                   |
| --- | ----------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | **Minnesota DHS** | SNAP/Food Support monthly county caseload reports (DHS publishes "Minnesota Public Assistance Caseload Statistics") | **county**       | **monthly**, publication lag of roughly 1–2 months | The only county-monthly SNAP series that exists for Minnesota. Everything else is state or annual. **Verify the exact report name, the URL and the lag before relying on it.** |
| 2   | USDA FNS          | **SNAP State Activity Report** / national and state participation & issuance                                        | state            | monthly (state), annual (state activity report)    | Use for benefit-level changes and as a cross-check on the DHS totals. Cannot support county heterogeneity.                                                                     |
| 3   | USDA FNS          | **SNAP COLA / maximum allotment** schedules                                                                         | national         | annual (October adjustments)                       | This is the _event_ series. Benefit levels change on a published schedule, which gives a clean date for an event study.                                                        |
| 4   | Feeding America   | `SNAP Threshold`, `% FI ≤ SNAP Threshold`, already in Map the Meal Gap                                              | county           | annual                                             | Free measure of how much of a county's food-insecure population is even income-eligible for SNAP. Feeds the Q6 "participation gap" directly.                                   |

**The trap:** SNAP caseloads and food shelf activity both rise when times are hard, so
their levels co-move for reasons that say nothing about substitution. Identification has
to come from **benefit changes** — the end of pandemic emergency allotments in early
2023 is the obvious one, and any later benefit disruption in the window is another
(**verify the dates before building the event study around them**). Compare counties by
how exposed they were, not just before and after.

---

## Q6 — a divergence measure for need and demand

The brief is explicit: the measure must consider **more than demand**, and will likely
need public data. The design constraint that matters is that the inputs must be
**independent of food shelf visits** and **not already inside the Map the Meal Gap model**,
or you have rebuilt MMG under a new name.

| #   | source               | exact series                                                              | grain           | time grain       | why                                                                                                                         |
| --- | -------------------- | ------------------------------------------------------------------------- | --------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 1   | Census ACS 5-year    | `B08201` no-vehicle households                                            | county, tract   | 5-year           | Transport is one of the four barriers the brief names. Not in the MMG model.                                                |
| 2   | MN Dept of Education | Free and reduced-price lunch eligibility by district                      | school district | annual           | Child need signal independent of both visits and MMG. District→county needs a crosswalk.                                    |
| 3   | Census ACS           | `S0101` age structure, senior share                                       | county          | 5-year           | Seniors are a known under-claiming group; a high senior share with low activity is a real divergence candidate.             |
| 4   | Derived, this repo   | distance to nearest site (from `block_geoid` + Gazetteer)                 | tract           | static           | Ours, not published anywhere. Directly measures a barrier.                                                                  |
| 5   | Derived, this repo   | SNAP participation gap = DHS caseload ÷ MMG income-eligible food-insecure | county          | monthly ÷ annual | A county where few eligible people claim SNAP is a county where few eligible people use a food shelf, for the same reasons. |

**The trap:** arbitrary weights. Whatever index you build, show the **county ranking is
stable** under reasonable alternative weightings. A rank that flips when you change a
weight from 0.2 to 0.3 is not a finding.

---

## Q7 — forecasting August activity

**Use no external data unless you are certain of its vintage.** The safest Q7 model uses
only the food shelf panel itself. If you bring in a driver from Q4 or Q5, it must be
truncated at **2026-07** and someone other than the model's author must verify it.

Candidate internal features: month-of-year, county, site count reporting, the county's
own July value, the historical August/July ratio, trailing 3- and 12-month levels.

---

## Q8 — low-income, low-access areas

| #   | source                                   | exact series                                                      | grain            | time grain                             | why this one                                                                                                               |
| --- | ---------------------------------------- | ----------------------------------------------------------------- | ---------------- | -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| 1   | USDA ERS, **Food Access Research Atlas** | `LILATracts_1And10`, `LILATracts_Vehicle`, `LILATracts_halfAnd10` | **census tract** | 2019 data on **2010** tract boundaries | The source the brief points at ("USDA shortens this to LILA"). State the vintage explicitly: it is the whole limitation.   |
| 2   | Census Bureau                            | **2010 → 2020 tract relationship file**                           | tract            | static                                 | **Required.** Our geoids are 2020, the Atlas is 2010. Without this the join is wrong in a way that still produces numbers. |
| 3   | Census, **2020 Gazetteer**               | `2020_Gaz_tracts_27.txt`                                          | tract centroid   | static                                 | Distance from tract centroid to nearest site.                                                                              |
| 4   | Census ACS 5-year                        | tract population, poverty, vehicle access                         | tract            | 5-year                                 | Weights the coverage measure by people rather than by tracts. A tract is not a person.                                     |

**The traps, all of which belong on the Q8 limitations slide:**

- Atlas vintage (2019 data, 2010 tracts) against our 2020 geoids.
- Straight-line distance, not drive time.
- No data on site **hours, capacity or eligibility** — presence is not access.
- 12.5% of sites have no geoid and cannot be placed at all.

---

## Where to put the files

```
data/external/
├── census/         SAIPE, PEP, ACS, Gazetteer, relationship files
├── bls/            CPI series, LAUS
├── usda/           Food Access Research Atlas, RUCC, FNS SNAP
└── mn_dhs/         SNAP county caseloads
```

Keep the file **exactly as downloaded**. Do not open it in Excel and save it — that is
how leading zeros die. All reshaping happens in a script.

---

## Source registry — fill in one row per file actually downloaded

| file path                                                                         | publisher                                          | exact series / table id                                                                               | geo grain                                      | time grain                                                    | vintage / last obs                                                                                                               | downloaded by | date                        | why this over the alternative                                                                                                                                                                                                    |
| --------------------------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| data/external/bls/CUUR0200SAF11.csv                                               | U.S. Bureau of Labor Statistics                    | CUUR0200SAF11 (CPI-U, not seasonally adjusted, Midwest region, Food at home)                          | Midwest Census region                          | monthly                                                       | 2021-01 through 2026-07 (2025-10 missing; retrieved via BLS public API, no vintage/revision date returned)                       | Teammate       | _(fill in actual run date)_ | Chosen over the Minneapolis–St. Paul metro series (CUUSA211SAF11) because it's monthly rather than bimonthly, giving full lag resolution at 1-month steps; the metro series is reserved as a robustness check per the brief      |
| `census/saipe/est22all.xls`, `est23all.xls`, `est24all.xls`                       | U.S. Census Bureau                                 | SAIPE state & county estimates: poverty % all ages, age 0–17, median HH income                        | county                                         | annual                                                        | 2022, 2023, 2024 (2024 released Jan 2026)                                                                                        | Valentino     | 2026-09-24                  | Single-year model-based estimates; ACS 5-yr poverty is a 5-year average and blurs year-to-year change. **Input to MMG — circular as an explanatory variable.**                                                                   |
| `mn_sdc/mn_county_edr_historical_estimates_sdc_1990-2025_tcm36-760413.xlsx`       | MN State Demographic Center & Metropolitan Council | County population and household estimates, 1990–2025                                                  | county                                         | annual (April 1)                                              | 2025, released July 2026                                                                                                         | Valentino     | 2026-09-24                  | Minnesota's official estimates, used by the state for funding formulas. Chosen over Census PEP as the local standard; also gives households.                                                                                     |
| `bls/laus/laucnty22.xlsx`, `laucnty23.xlsx`, `laucnty24.xlsx`                     | U.S. Bureau of Labor Statistics                    | LAUS county labor force data, annual averages, unemployment rate                                      | county                                         | annual (avg. of monthly)                                      | 2022–2024                                                                                                                        | Valentino     | 2026-09-24                  | The only official county unemployment series. **Input to MMG — circular.**                                                                                                                                                       |
| `census/acs/acs5_2022_B08201.csv`, `acs5_2023_B08201.csv`, `acs5_2024_B08201.csv` | U.S. Census Bureau                                 | ACS 5-year B08201, Household size by vehicles available                                               | county                                         | 5-year rolling (end year used)                                | 2018–22, 2019–23, 2020–24                                                                                                        | Valentino     | 2026-09-24                  | Only county source for vehicle access; ACS 1-year covers only counties ≥65k people. Not an MMG input.                                                                                                                            |
| `census/acs/acs5_2022_B17001.csv`, `acs5_2023_B17001.csv`, `acs5_2024_B17001.csv` | U.S. Census Bureau                                 | ACS 5-year B17001, Poverty status by sex by age                                                       | county                                         | 5-year rolling (end year used)                                | 2018–22, 2019–23, 2020–24                                                                                                        | Valentino     | 2026-09-24                  | Senior share and senior poverty, which SAIPE does not publish. ACS 1-year was rejected: it covers only the 14 counties over 65k people.                                                                                          |
| `census/acs/acs5_2022_B22003.csv`, `acs5_2023_B22003.csv`, `acs5_2024_B22003.csv` | U.S. Census Bureau                                 | ACS 5-year B22003, Receipt of Food Stamps/SNAP in the past 12 months by poverty status for households | county                                         | 5-year rolling (end year used)                                | 2018–22, 2019–23, 2020–24                                                                                                        | Valentino     | 2026-09-24                  | Self-reported SNAP receipt for all 87 counties, available now. MN DHS monthly caseloads (Q5) are administrative and more precise; use them as a cross-check if a teammate gets them. ACS 1-year rejected: 14 counties only.           |
| `census/gazetteer/CenPop2020_Mean_TR27.txt`                                       | U.S. Census Bureau                                 | 2020 Centers of Population by census tract, Minnesota                                                 | tract                                          | static (2020 census)                                          | 2020                                                                                                                             | Valentino     | 2026-09-24                  | Population-weighted tract centres plus 2020 tract population. Better than geometric centroids for "how far do people live from a site", and supplies the weights for the county average.                                         |
| `census/gazetteer/2026_Gaz_tracts_national.txt`                                   | U.S. Census Bureau                                 | 2026 Gazetteer, census tracts (2020 tract definitions), internal point lat/long                       | tract                                          | static                                                        | 2026 release                                                                                                                     | Valentino     | 2026-09-24                  | Places each site at its tract's internal point via `tract_geoid`; the 2020 Gazetteer directory has no block-level text file, so Q8 reports a tract-based displacement bound. |
| `usda/FoodAccessResearchAtlasData2019.xlsx`                                       | U.S. Department of Agriculture                     | All US States. Food Access Research Atlas (FARA) — Large Retailer Access Map (LRAM)/long              | Census tract (2010 boundaries, 11-digit GEOID) | Cross-sectional snapshot (multi-year benchmark)               | Released April 2021; store directory vintage 2019 (TDLinx & STARS), ACS income vintage 2014–2018, Decennial Census baseline 2010 | Teammate       | 2026-09-25                  | Chosen over the 2025 SRAM. LRAM strictly measures access to full-service grocery stores, aligning exactly with the brief's focus. SRAM includes convenience stores and gas stations, which artificially masks true food deserts. |
| `usda/Historical SNAP Retailer Locator Data 2005-2025.csv` (local source; pass to `questions/q8_lila_access/prepare_grocery_stores.py`) | USDA Food and Nutrition Service, [historical SNAP retailer data](https://www.fns.usda.gov/snap/retailer-locator/data) | SNAP-authorized retailer name, type, address, coordinates, authorization and end dates; filtered to supermarket/large-grocery types | Retailer point | Historical authorization records; active snapshot selected at 2025-12-31 | File current through 2025-12-31 | Teammate | 2026-10-03 | Primary direct store-point source for comparison with food shelves. SNAP-only coverage is incomplete for non-authorized grocers; results are reported for documented retailer type scopes. |
| `osm/minnesota-261003-free/` (local Geofabrik source; pass directory to `questions/q8_lila_access/prepare_grocery_stores.py`) | OpenStreetMap contributors via [Geofabrik Minnesota shapefile extract](https://download.geofabrik.de/north-america/us/minnesota.html) | Minnesota OSM features; Q8 uses `supermarket` in the POI point and polygon layers | Retailer point or polygon converted to interior point | Snapshot extract | OSM data timestamp 2026-10-03 20:20 UTC | Teammate | 2026-10-03 | Independent sensitivity source for supermarket locations. Coverage depends on OSM mapping; data are ODbL 1.0 and require attribution. |
| `census/relationship/tab20_tract20_tract10_st27.txt`                              | U.S. Census Bureau                                 | 2020 Census tract to 2010 Census tract relationship file; land-area overlap by tract pair             | Census tract (2010 and 2020 boundaries)         | static                                                        | 2020 Census relationship vintage                                                                                                  | Teammate       | 2026-09-25                  | Required to transfer the USDA Atlas's 2010 tract flags to 2020 site geography. Area-overlap weights support an explicit area-weighted rule rather than a direct, invalid GEOID join. |
| `census/tract/tl_2020_27_tract`                                                   | U.S. Census Bureau                                 | 2020 Minnesota TIGER/Line Shapefiles — Census Tracts                                                   | Census tract (2020 boundaries, 11-digit GEOID) | Decennial spatial baseline (static cross-sectional map layer) | 2020                                                                                                                             | Teammate       | 2026-09-27                  | TIGER/Line tract polygons support tract-level mapping and a conservative upper bound on the site displacement caused by using tract internal points. |
| `mn_dhs/snap_dashboard_county_month_2016-01_2026-07.csv` | Minnesota Department of Children, Youth, and Families (DCYF), page "SNAP Food Assistance in Minnesota", https://dcyf.mn.gov/snap-food-assistance-minnesota | SNAP dashboard data, file `snap-dashboard-data-through-august-2026.xlsx`: cases, persons, and food benefits issued, cancelled and net, for SNAP federal, MFAP state, and the MFIP food portion | county, except: Dodge + Steele + Waseca reported as one agency (MNPrairie); Grant inside Pope from 2022-01; three tribal nations reported separately | monthly | 2016-01 through 2026-07, no missing months. **Publication lag about one month**: the download on 2026-09-27 already held 2026-08. The 87 rows for 2026-08 were removed before the file entered the repo; no other change. Converted from .xlsx to .csv | Valentino | 2026-09-27 | The only county-by-month SNAP series. USDA FNS publishes state totals only, and ACS B22003 is a 5-year average, so neither can show the April 2023 benefit cut county by county. Reshaped by `src/build_snap.py`. |
| `census/adjacency/county_adjacency2023.txt` | U.S. Census Bureau, https://www2.census.gov/geo/docs/reference/county_adjacency/county_adjacency2023.txt | County Adjacency File 2023: every county paired with each county it borders (each county is also paired with itself) | county | static | 2023 vintage, file dated 2023-09-18. National file; the 87 Minnesota counties are all present | Valentino | 2026-09-29 | Needed to test whether Q1 residuals cluster among neighbouring counties (Moran's I). Chosen over building neighbours from a shapefile: it is the published list, needs no geometry library, and cannot differ by tolerance settings. Pairs include neighbours in other states, which the analysis drops. |
| `census/acs/acs5_2022_B25070.csv`, `acs5_2023_B25070.csv`, `acs5_2024_B25070.csv` | U.S. Census Bureau | ACS 5-year B25070, Gross rent as a percentage of household income in the past 12 months | county | 5-year rolling (end year used) | 2018–22, 2019–23, 2020–24 | Valentino | 2026-10-01 | Renter half of housing-cost burden (share paying 30% or more of income), a Q6 need input the glossary names. Not an MMG input. data.census.gov export, unchanged. |
| `census/acs/acs5_2022_B25091.csv`, `acs5_2023_B25091.csv`, `acs5_2024_B25091.csv` | U.S. Census Bureau | ACS 5-year B25091, Mortgage status by selected monthly owner costs as a percentage of household income | county | 5-year rolling (end year used) | 2018–22, 2019–23, 2020–24 | Valentino | 2026-10-01 | Owner half of housing-cost burden, with and without a mortgage. Combined with B25070 into `pct_hh_housing_burden`. |
| `census/acs/acs5_2022_B15003.csv`, `acs5_2023_B15003.csv`, `acs5_2024_B15003.csv` | U.S. Census Bureau | ACS 5-year B15003, Educational attainment for the population 25 years and over | county | 5-year rolling (end year used) | 2018–22, 2019–23, 2020–24 | Valentino | 2026-10-01 | Share of adults without a high-school diploma or GED (`pct_no_hs_diploma`), a Q6 need input. Chosen over S1501 because the detailed table gives the grade-by-grade counts the share is built from. Not an MMG input. |
| `urban/Debt in America County-Level Overall Debt.xlsx` | Urban Institute, Debt in America 2025, https://datacatalog.urban.org/dataset/debt-america-2025 | County-level overall debt file: share of adults with a credit record who have any debt in collections, plus delinquency rates | county | one cross-section | credit bureau records as of August 2025 (4% national panel); file carries no date itself, vintage from the technical appendix | Valentino | 2026-10-01 | The only public county measure of financial strain that is not income. Used as `pct_debt_collections`, a Q6 need input of last priority: it covers only people with a credit file, so the poorest households are missing from it. |
| `census/acs/acs5_2022_B16002.csv`, `acs5_2023_B16002.csv`, `acs5_2024_B16002.csv` | U.S. Census Bureau | ACS 5-year B16002, Household language by household limited English speaking status | county | 5-year rolling (end year used) | 2018–22, 2019–23, 2020–24 | Valentino | 2026-10-02 | `pct_hh_limited_english`: a barrier to finding out about and using a food shelf, in neither the MMG model nor the Q6 index. Used to explain divergence (Q6 step 5), never as a need input. |
| `census/acs/acs5_2022_B28002.csv`, `acs5_2023_B28002.csv`, `acs5_2024_B28002.csv` | U.S. Census Bureau | ACS 5-year B28002, Presence and types of internet subscriptions in household | county | 5-year rolling (end year used) | 2018–22, 2019–23, 2020–24 | Valentino | 2026-10-02 | `pct_hh_no_internet`: awareness barrier, most site information is online. Same role as B16002. |
| `census/acs/acs5_2022_B05001.csv`, `acs5_2023_B05001.csv`, `acs5_2024_B05001.csv` | U.S. Census Bureau | ACS 5-year B05001, Nativity and citizenship status | county | 5-year rolling (end year used) | 2018–22, 2019–23, 2020–24 | Valentino | 2026-10-02 | `pct_noncitizen`: eligibility and reluctance barrier. Same role as B16002. |

_(Every one of the four required facts is a column here. If a row cannot be completed,
the source does not get used.)_
