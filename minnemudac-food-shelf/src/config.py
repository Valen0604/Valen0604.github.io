"""
Central configuration for the MinneMUDAC / The Food Group challenge.

Every analysis script imports paths and shared constants from here so that
nobody hard-codes a path or a metric name in their own notebook.

Team rule: raw files are read-only. Nothing in this project ever writes to
data/raw/.
"""
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[1]

RAW = ROOT / "data" / "raw"
RAW_TFG = RAW / "tfg"
RAW_FA = RAW / "feeding_america"
RAW_REF = RAW / "reference"

EXTERNAL = ROOT / "data" / "external"     # public data we download ourselves
INTERIM = ROOT / "data" / "interim"       # intermediate, throwaway
PROCESSED = ROOT / "data" / "processed"   # the canonical panels everyone reads

DOCS = ROOT / "docs"
OUT = ROOT / "outputs"
FIG = OUT / "figures"
TAB = OUT / "tables"
QUESTIONS = ROOT / "questions"

for _p in (EXTERNAL, INTERIM, PROCESSED, OUT, FIG, TAB):
    _p.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- raw files
F_FSSTATS = RAW_TFG / "org_FSStats.xlsx"
F_ORG = RAW_TFG / "Organization.xlsx"
F_MARKETBUCKS = RAW_TFG / "marketbucksUsage.xlsx"
F_CALLS = RAW_TFG / "IncomingCall.xlsx"
F_MMG_2025 = RAW_FA / "MMG2025_2019-2023_Data_To_Share_v2.xlsx"   # 2019-2023
F_MMG_2026 = RAW_FA / "MMG2026_2024_Data_To_Share.xlsx"           # 2024 only

# ---------------------------------------------------------------- processed outputs
P_SITE_MONTH = PROCESSED / "site_month.parquet"        # cleaned, flagged, one row per site-month
P_COUNTY_MONTH = PROCESSED / "county_month.parquet"    # aggregated to county x month
P_SITES = PROCESSED / "sites.parquet"                  # site master incl. geography
P_MMG = PROCESSED / "mmg_county.parquet"               # Map the Meal Gap, MN, 2019-2024
P_COVARIATES = PROCESSED / "county_covariates.parquet" # public county data, src/build_covariates.py
P_SNAP = PROCESSED / "snap_unit_month.parquet"         # SNAP caseloads, src/build_snap.py
P_SNAP_XWALK = PROCESSED / "snap_unit_crosswalk.csv"   # county -> SNAP reporting unit
P_CALLS = PROCESSED / "calls_clean.parquet"
P_MARKETBUCKS = PROCESSED / "marketbucks_clean.parquet"
P_COUNTY_XWALK = PROCESSED / "county_crosswalk.csv"    # TFG label -> FIPS
P_QUALITY = PROCESSED / "data_quality_log.csv"         # every row we flagged and why

# ---------------------------------------------------------------- metric config
# The brief names three metrics: visits, pounds distributed, individuals served.
# org_FSStats has no usable visits field (UniqueVisits* is 99.9% empty), so
# HOUSEHOLDS is our documented stand-in for "visits". See docs/DATA_ERRORS.md.
# These are parameters on purpose: if the organizers tell us to use a different
# field, it is a one-line change here and nothing downstream breaks.
M_VISITS = "households"        # proxy for visits  (HouseholdsReg)
M_POUNDS = "pounds"            # PoundsReg
M_INDIVIDUALS = "individuals"  # IndividualsReg
THREE_METRICS = [M_VISITS, M_POUNDS, M_INDIVIDUALS]
AGE_METRICS = ["children", "adults", "seniors"]   # Q7 graduate addendum

# Q1 study window. The brief said 2023-2024; the organizers widened it to
# 2022-2024 in a later update. 2022 and 2023 MMG come from the 2025 edition,
# 2024 from the 2026 edition.
Q1_YEARS = [2022, 2023, 2024]

# Source columns in org_FSStats. The *Reg fields and the *Total fields are
# byte-for-byte identical in this extract (verified), and only the *Total ones
# are marked Deprecated in the dictionary, so we read the *Reg ones.
SRC_COLUMNS = {
    "households": "HouseholdsReg",
    "individuals": "IndividualsReg",
    "pounds": "PoundsReg",
    "children": "ChildrenReg",
    "adults": "AdultsReg",
    "seniors": "SeniorsReg",
}

# ---------------------------------------------------------------- cleaning rules
# See docs/DATA_ERRORS.md for the evidence behind each threshold.
IPHH_MIN = 1.0      # individuals per household below this is impossible
IPHH_MAX = 8.0      # above this is almost certainly a keying error
SPIKE_RATIO = 5.0   # value > 5x the site's own median for that metric -> flagged
MIN_MONTHS_FOR_MEDIAN = 6

# Site types that we treat as "food-shelf-like" for need-vs-demand work
# (Q1, Q6, Q8). Q7 forecasts whatever the organizers score, so it does not
# apply this filter by default. Kept as a flag, never a deletion.
FOOD_SHELF_TYPES = {
    "Brick and Mortar Site",
    "Brick and Mortar Sites",
    "Food Shelf",
    "Mobile",
    "Tribal Program",
    "Agency or Tribal Nation",
}

# ---------------------------------------------------------------- leakage guard
# Q7 asks us to predict August 2026. Using ANY August 2026 data disqualifies
# the team. Every script that touches Q7 must respect this cutoff.
FORECAST_TARGET_YM = 202608
TRAIN_CUTOFF_YM = 202607     # last month we are allowed to see
STATE_FIPS_MN = "27"
