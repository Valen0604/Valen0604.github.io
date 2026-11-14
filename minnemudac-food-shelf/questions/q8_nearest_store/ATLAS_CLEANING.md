# Cleaning notes — USDA Food Access Research Atlas (`data/external/usda/FoodAccessResearchAtlasData2019.xlsx`)

Checked 2026-09-25 against the file as committed. Read this after the Q8 README.

## What is in the file

| sheet | contents |
|---|---|
| `Read Me` | release note only (initial release April 2021) |
| `Variable Lookup` | 147 rows: `Field`, `LongName`, `Description` — the data dictionary, keep it |
| `Food Access Research Atlas` | 72,531 rows (every US tract) × 147 columns; **1,334 rows are Minnesota** |

Key facts about the data sheet:

- `CensusTract` is an 11-character **2010** tract GEOID stored as text (`27001770100`).
  Our `sites.parquet::tract_geoid` is a **2020** tract GEOID. They do not match one to
  one — Minnesota has 1,334 tracts in 2010 and 1,505 in 2020. This is the whole
  cleaning problem; see "The crosswalk" below.
- Flags (`LILATracts_*`, `LA*`, `LowIncomeTracts`, `HUNVFlag`, `Urban`) are 0/1 integers.
- `PovertyRate` and `MedianFamilyIncome` are empty for some group-quarters tracts
  (`GroupQuartersFlag = 1`). Leave them NaN; do not fill.
- `Pop2010` / `OHU2010` are 2010 census counts. They are the right weights *for the
  Atlas's own flags* (population-weighted coverage, README step 3). For anything at 2020
  tract grain, weight with `CenPop2020_Mean_TR27.txt`, which is already in
  `data/external/census/gazetteer/`.

## Rule 1 applies: do not clean the xlsx. Write a loader.

The file stays exactly as downloaded. Reading it with pandas takes ~1–2 minutes because
it is 85 MB, so the loader reads it **once**, keeps Minnesota, and caches a parquet.
Follow the pattern in `src/build_covariates.py`.

```python
# src/build_lila.py  (or a function in questions/q8_lila_access/analysis.py)
import pandas as pd
import config as cfg

ATLAS = cfg.EXTERNAL / "usda" / "FoodAccessResearchAtlasData2019.xlsx"
OUT   = cfg.PROCESSED / "lila_tracts_2010.parquet"

def build_lila_2010() -> pd.DataFrame:
    d = pd.read_excel(ATLAS, sheet_name="Food Access Research Atlas",
                      dtype={"CensusTract": str})
    d = d[d["State"] == "Minnesota"].copy()
    d["tract_geoid_2010"] = d["CensusTract"].str.zfill(11)   # guard, MN needs no pad
    d["fips"] = d["tract_geoid_2010"].str[:5]                 # county join key
    d = d.drop(columns=["CensusTract", "State"])

    assert len(d) == 1334, len(d)
    assert d["tract_geoid_2010"].is_unique
    assert d["tract_geoid_2010"].str.startswith("27").all()

    d.to_parquet(OUT, index=False)
    return d
```

Keep all 147 columns in the parquet — 1,334 rows is tiny — and pick columns in the
analysis. Also save `Variable Lookup` as `data/processed/lila_variable_lookup.csv` so the
column meanings travel with the data.

`data/processed/` is regenerated from scripts and is git-ignored, so the parquet is not
committed; the script is.

## The crosswalk — the actual work

`sites.parquet` is on 2020 tracts; the Atlas is on 2010 tracts. Nothing in Q8 can be
joined until this is solved. Steps:

1. **Download** the Census *2020 Tract to 2010 Tract Relationship File* for Minnesota:
   `tab20_tract20_tract10_st27.txt` from
   https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.2020.html
   → save to `data/external/census/relationship/` and **register it** in
   `docs/DATA_SOURCES.md`. It is pipe-delimited; read with `sep="|"`, `dtype=str`.
2. **Write the rule down before coding it.** The README's rule:
   - 2010 tract **split** into several 2020 tracts → every child inherits the parent's
     flags.
   - Several 2010 tracts **merged** into one 2020 tract → take the majority flag,
     weighted by overlap (the relationship file gives land-area overlap `AREALAND_PART`;
     use it as the weight, or use 2010 population if you go via the block-level file).
   - Implement as: for each 2020 tract, `lila_share = Σ(weight × flag) / Σ(weight)` over
     its 2010 parents; `LILA_2020 = lila_share ≥ 0.5`. Keep `lila_share` and the number
     of parents as columns — they are the limitation's magnitude.
3. **Report the magnitude.** How many of the 1,505 2020 tracts have exactly one 2010
   parent (clean inherit), how many have several (a judgement call was made), and how
   many sites sit in the second group. That is the first row of the README's
   limitations table, answered properly.
4. Save as `data/processed/lila_tracts_2020.parquet` keyed on `tract_geoid` (2020),
   so it joins `sites.parquet` directly.

Which flag to use is an analysis decision, not a cleaning one — but do the crosswalk for
all four `LILATracts_*` flags at once so switching is free (README step 5).

## Two housekeeping items

- **The xlsx is 85 MB.** GitHub warns above 50 MB and blocks above 100 MB; it is already
  pushed, so it works, but every clone downloads it forever. Suggested fix for the team
  to decide: add `data/external/usda/FoodAccessResearchAtlasData2019.xlsx` to
  `.gitignore`, keep the download URL in the registry row, and let `build_lila.py`
  produce the Minnesota extract. Do not rewrite git history for this.
- **A teammate's CPI file** `data/external/bls/CUUR0200SAF11.csv` is in the registry (row
  for `CUUR0200SAF11`) but is **not in the repo** — the folder `data/external/bls/`
  only holds `laus/`. It needs to be added and committed.
