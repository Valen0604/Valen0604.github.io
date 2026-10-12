"""
clean_data.py -- build the canonical, analysis-ready tables.

Run this once, from the repo root:

    python src/clean_data.py

It reads only from data/raw/ and writes to data/processed/. Nothing else in
this project is allowed to read data/raw/ directly, so that every question is
answered off the same numbers.

What it produces
----------------
    data/processed/site_month.parquet        one row per site-month, flagged
    data/processed/county_month.parquet      county x month panel, keyed on FIPS
    data/processed/sites.parquet             site master with census geography
    data/processed/mmg_county.parquet        Map the Meal Gap, MN, 2019-2024
    data/processed/calls_clean.parquet       call log with FIPS and food flag
    data/processed/marketbucks_clean.parquet market sessions with FIPS
    data/processed/county_crosswalk.csv      TFG county label -> FIPS
    data/processed/data_quality_log.csv      every flagged issue and the reason

Cleaning philosophy
-------------------
We FLAG, we do not DELETE. Every suspect row keeps its raw value and gains a
boolean column saying what is wrong with it. Aggregations then choose which
flags to exclude, and that choice is visible in the code instead of buried in
a spreadsheet edit. Judges will ask why a number is what it is; this is the
answer.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfg
import geography as geo

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

QUALITY_LOG: list[dict] = []


def to_site_id(series: pd.Series) -> pd.Series:
    """
    Render a site key as an exact string.

    The primary keys in this extract are NOT all integers: 13 organizations and
    571 stat rows carry a '.1' suffix (13462.1, 14696.1, ...). For five of them
    the plain integer id also exists as a separate organization, so 14696 and
    14696.1 are two different sites. Casting to int would silently merge them
    and casting to float invites '14696.1000000001' style drift, so the key is
    carried as text everywhere in this project.
    """
    v = pd.to_numeric(series, errors="coerce")
    return v.map(lambda x: pd.NA if pd.isna(x)
                 else (str(int(x)) if float(x).is_integer() else f"{x:.10g}")).astype("string")


def write_parquet(df: pd.DataFrame, path) -> None:
    """
    Write a frame to parquet, forcing mixed-type text columns to string first.

    Several FileMaker-exported columns hold both text and numbers in the same
    column (SuperShelfStatus, TefapStatus, FindHelpMapCategory, ...). Parquet
    needs one type per column, and silently guessing would be worse than making
    them all text.
    """
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "object":
            out[col] = out[col].astype("string")
    out.to_parquet(path, index=False)


def log(table: str, issue: str, n_rows: int, action: str, detail: str = "") -> None:
    QUALITY_LOG.append({"table": table, "issue": issue, "n_rows": int(n_rows),
                        "action": action, "detail": detail})
    print(f"  [{table}] {issue}: {n_rows} rows -> {action}")


# ====================================================================== sites
def build_sites() -> pd.DataFrame:
    """Site master: one row per organization, with census geography attached."""
    print("\n== Organization -> sites.parquet")
    o = pd.read_excel(cfg.F_ORG, dtype={"block_geoid": "string", "Zip": "string"})

    o = o.rename(columns={"__ID": "site_id"})
    o["site_id"] = to_site_id(o["site_id"])

    # block_geoid arrives as a float in some readers, which appends '.0'.
    # geo.split_block_geoid coerces to a zero-padded 15-char string first.
    parts = geo.split_block_geoid(o["block_geoid"]).rename(columns={"fips": "fips_from_geoid"})
    o = o.drop(columns=["block_geoid"])
    for col in parts.columns:
        o[col] = parts[col].to_numpy()

    log("Organization", "block_geoid missing", int(o["block_geoid"].isna().sum()),
        "kept, flagged has_geoid=False",
        "These sites cannot be placed in a census tract, so they drop out of Q8.")

    o["has_geoid"] = o["block_geoid"].notna()
    o["geoid_is_zip_centroid"] = o["is_zip_centroid"].fillna(0).astype(int).astype(bool)
    log("Organization", "block_geoid from ZIP centroid, not street address",
        int(o["geoid_is_zip_centroid"].sum()),
        "kept, flagged geoid_is_zip_centroid=True",
        "Location is the middle of the ZIP, not the site. Do not use for distance work.")

    # County FIPS: prefer the one implied by the geocoded block, fall back to
    # the free-text County label. They disagree for a handful of sites, which is
    # itself worth knowing, so we record the disagreement rather than hide it.
    o = geo.attach_fips(o, "County")
    disagree = (o["fips_from_geoid"].notna() & o["fips"].notna()
                & (o["fips_from_geoid"] != o["fips"]))
    log("Organization", "block_geoid county disagrees with the County text field",
        int(disagree.sum()), "block_geoid wins, disagreement flagged fips_disagrees=True",
        "The geocoded address is more reliable than a hand-typed county name.")
    o["fips_disagrees"] = disagree
    o["fips"] = o["fips_from_geoid"].fillna(o["fips"])

    # State field is dirty: it contains ZIP codes and a stray newline.
    state_txt = o["State"].astype("string").str.strip().str.upper()
    bad_state = o["State"].notna() & ~state_txt.isin(["MN"])
    log("Organization", "State field holds a ZIP code or a non-MN value", int(bad_state.sum()),
        "kept, flagged state_dirty=True", "Trust block_geoid and County over State.")
    o["state_dirty"] = bad_state

    o["is_active"] = o["ActiveInactive"].astype("string").str.strip().eq("Active")

    keep = ["site_id", "City", "Zip", "County", "county_name", "fips", "county_match",
            "Region", "SuperRegion", "AgencyType", "AgencySubType", "MarketSeasons",
            "isAgency", "isDistributionSite", "ActiveInactive", "is_active",
            "InactiveDate", "TefapStatus", "SuperShelfStatus", "FindHelpMapCategory",
            "block_geoid", "state_fips", "tract_geoid", "bg_geoid",
            "has_geoid", "geoid_is_zip_centroid", "state_dirty", "fips_disagrees"]
    sites = o[[c for c in keep if c in o.columns]].copy()

    # The z12MoAverage_* columns are deliberately NOT carried forward.
    # They were recomputed in Aug 2026 and may contain August activity, which
    # would be leakage into the Q7 forecast. See docs/DATA_ERRORS.md.
    log("Organization", "z12MoAverage_* rolling-average columns dropped", 11,
        "dropped from the processed output",
        "Recomputed Aug 2026; carrying them forward risks Q7 disqualification.")

    write_parquet(sites, cfg.P_SITES)
    print(f"  wrote {cfg.P_SITES.name}: {sites.shape}")
    return sites


# ================================================================= site-month
def build_site_month(sites: pd.DataFrame) -> pd.DataFrame:
    """Cleaned site x month food shelf activity, with one flag column per defect."""
    print("\n== org_FSStats -> site_month.parquet")
    fs = pd.read_excel(cfg.F_FSSTATS)
    n0 = len(fs)

    fs = fs.rename(columns={"__ID": "record_id", "_id_site": "site_id",
                            "_Year": "year", "_Month": "month",
                            "_YearMonth": "yearmonth"})
    fs["site_id"] = to_site_id(fs["site_id"])

    # --- metric columns -------------------------------------------------
    # The *Reg and *Total columns are identical wherever both are present
    # (checked below: 0 disagreements). Only *Total is marked Deprecated in the
    # data dictionary, so we read *Reg and record the check rather than trust
    # either family blindly.
    for out_name, src in cfg.SRC_COLUMNS.items():
        fs[out_name] = pd.to_numeric(fs[src], errors="coerce")

    equal_checks = {"households": "HouseholdsTotal", "individuals": "IndividualsTotal",
                    "pounds": "PoundsTotal", "children": "ChildrenTotal",
                    "adults": "AdultsTotal", "seniors": "SeniorsTotal"}
    mismatches = 0
    for out_name, tot in equal_checks.items():
        both = fs[[cfg.SRC_COLUMNS[out_name], tot]].dropna()
        mismatches += int((both[cfg.SRC_COLUMNS[out_name]] != both[tot]).sum())
    log("org_FSStats", "Reg vs Total column families disagree", mismatches,
        "none found - Reg columns used",
        "The two families are duplicates in this extract, so the Deprecated label costs us nothing.")

    # --- calendar -------------------------------------------------------
    bad_month = ~fs["month"].between(1, 12)
    log("org_FSStats", "impossible month code (202300, 202315)", int(bad_month.sum()),
        "flagged bad_period=True, excluded from every time series",
        "Month 0 and month 15 cannot be placed on a calendar.")
    fs["bad_period"] = bad_month

    fs["date"] = pd.to_datetime(
        dict(year=fs["year"], month=fs["month"].where(~bad_month, 1), day=1), errors="coerce")
    fs.loc[bad_month, "date"] = pd.NaT

    # --- duplicates -----------------------------------------------------
    dup_mask = fs.duplicated(subset=["site_id", "yearmonth"], keep=False)
    n_dup_rows = int(dup_mask.sum())
    n_dup_groups = fs[dup_mask].groupby(["site_id", "yearmonth"]).ngroups
    # Rule: keep the most recently modified record for a site-month. If the
    # duplicates carry different numbers, the later edit is the correction.
    fs["zzModificationTS"] = pd.to_datetime(fs["zzModificationTS"], errors="coerce")
    fs = fs.sort_values(["site_id", "yearmonth", "zzModificationTS"]).reset_index(drop=True)
    fs["is_duplicate_superseded"] = fs.duplicated(subset=["site_id", "yearmonth"], keep="last")
    log("org_FSStats", "duplicate site-month records", n_dup_rows,
        "kept the latest zzModificationTS, older rows flagged is_duplicate_superseded=True",
        f"{n_dup_groups} site-months affected. Summing the raw table double counts them.")

    # --- county ---------------------------------------------------------
    fs["county_split_label"] = fs["County"]   # keeps Hennepin-Minneapolis etc.
    fs = geo.attach_fips(fs, "County")
    log("org_FSStats", "county label missing on the record", int(fs["fips"].isna().sum()),
        "flagged, excluded from county-level results",
        "Cannot be joined to any public data source.")
    log("org_FSStats", "sub-county labels rolled up to whole counties",
        int(fs["county_match"].eq("rolled_up").sum()),
        "rolled up to Hennepin / Ramsey, original kept in county_split_label",
        "91 labels for 87 counties; nothing joins to FIPS until they are merged.")

    # --- value sanity ---------------------------------------------------
    neg = pd.DataFrame({c: fs[c] < 0 for c in cfg.SRC_COLUMNS}).any(axis=1)
    log("org_FSStats", "negative counts or pounds", int(neg.sum()),
        "flagged negative_value=True", "A count of people or pounds cannot be below zero.")
    fs["negative_value"] = neg

    age_sum = fs[["children", "adults", "seniors"]].sum(axis=1, min_count=3)
    age_bad = age_sum.notna() & fs["individuals"].notna() & (age_sum != fs["individuals"])
    log("org_FSStats", "children + adults + seniors does not equal individuals", int(age_bad.sum()),
        "flagged age_split_mismatch=True", "Matters for the Q7 graduate addendum.")
    fs["age_split_mismatch"] = age_bad

    with np.errstate(divide="ignore", invalid="ignore"):
        fs["individuals_per_hh"] = fs["individuals"] / fs["households"].replace(0, np.nan)
        fs["pounds_per_hh"] = fs["pounds"] / fs["households"].replace(0, np.nan)
    iphh_bad = fs["individuals_per_hh"].notna() & (
        (fs["individuals_per_hh"] < cfg.IPHH_MIN) | (fs["individuals_per_hh"] > cfg.IPHH_MAX))
    log("org_FSStats", f"individuals per household outside [{cfg.IPHH_MIN}, {cfg.IPHH_MAX}]",
        int(iphh_bad.sum()), "flagged implausible_ratio=True",
        "Catches the Waseca 202307 row: 273,385 households for 646 individuals.")
    fs["implausible_ratio"] = iphh_bad

    # Households exactly equal to pounds is a copy-paste, not a coincidence.
    hh_eq_lbs = (fs["households"] == fs["pounds"]) & fs["households"].gt(1000)
    log("org_FSStats", "households exactly equals pounds", int(hh_eq_lbs.sum()),
        "flagged households_equals_pounds=True",
        "One field was pasted into the wrong column (Ramsey-Suburbs site, 202503).")
    fs["households_equals_pounds"] = hh_eq_lbs

    # --- site-level spikes ----------------------------------------------
    # A value many times a site's own typical level is a keying error far more
    # often than it is real demand. Compared against the site's own median so
    # that a large site is not penalised for being large.
    fs["spike_flag"] = False
    base = ~fs["bad_period"] & ~fs["is_duplicate_superseded"]
    for m in cfg.THREE_METRICS:
        grp = fs.loc[base].groupby("site_id")[m]
        med = grp.transform("median").reindex(fs.index)
        cnt = grp.transform("count").reindex(fs.index)
        spike = base & (cnt >= cfg.MIN_MONTHS_FOR_MEDIAN) & med.gt(0) & (fs[m] > cfg.SPIKE_RATIO * med)
        fs["spike_flag"] = fs["spike_flag"] | spike.fillna(False)
    log("org_FSStats", f"value above {cfg.SPIKE_RATIO}x the site's own median", int(fs["spike_flag"].sum()),
        "flagged spike_flag=True", "Reviewed, never auto-deleted. Listed in outputs/tables/flagged_rows.csv.")

    # --- agency type ----------------------------------------------------
    fs["AgencyType"] = fs["AgencyType"].astype("string").str.strip()
    variants = ["Brick and Mortar Sites", "Meal Programs", "On-Site Meal Programs"]
    fs["agency_type_clean"] = fs["AgencyType"].replace({
        "Brick and Mortar Sites": "Brick and Mortar Site",
        "Meal Programs": "Meal Program",
        "On-Site Meal Programs": "Meal Program"})
    fs["is_food_shelf_like"] = fs["agency_type_clean"].isin(cfg.FOOD_SHELF_TYPES)
    log("org_FSStats", "AgencyType spelled several ways", int(fs["AgencyType"].isin(variants).sum()),
        "collapsed into agency_type_clean",
        "'Food Shelf' and 'Brick and Mortar Site' describe the same kind of site.")
    log("org_FSStats", "site types that are not food shelves (meal, outreach, campus)",
        int((~fs["is_food_shelf_like"]).sum()),
        "flagged is_food_shelf_like=False, NOT deleted",
        "Q1/Q6/Q8 filter to food-shelf-like sites; Q7 forecasts everything.")

    # --- the master usability flag --------------------------------------
    fs["is_clean"] = (~fs["bad_period"] & ~fs["is_duplicate_superseded"]
                      & ~fs["negative_value"] & ~fs["implausible_ratio"]
                      & ~fs["households_equals_pounds"] & ~fs["spike_flag"])
    log("org_FSStats", "rows failing at least one check", int((~fs["is_clean"]).sum()),
        "is_clean=False", f"{(~fs['is_clean']).mean():.1%} of {n0} rows.")

    # Adjusted metric: the raw value where the row is clean, the site's own
    # median where it is not. Use these in aggregates so that one keying error
    # cannot move a county total.
    for m in cfg.THREE_METRICS + cfg.AGE_METRICS:
        med = fs.loc[fs["is_clean"]].groupby("site_id")[m].transform("median").reindex(fs.index)
        fs[f"{m}_adj"] = fs[m].where(fs["is_clean"], med)

    fs = fs.merge(sites[["site_id", "block_geoid", "tract_geoid", "has_geoid",
                         "geoid_is_zip_centroid"]],
                  on="site_id", how="left")
    log("org_FSStats", "site has no matching Organization record",
        int(fs["has_geoid"].isna().sum()), "left null",
        "Join key is Organization.__ID = org_FSStats._id_site (94.9% of sites match).")

    keep = (["record_id", "site_id", "year", "month", "yearmonth", "date",
             "County", "county_split_label", "county_name", "fips", "county_match",
             "FoodBank", "AgencyType", "agency_type_clean", "is_food_shelf_like",
             "block_geoid", "tract_geoid", "has_geoid", "geoid_is_zip_centroid"]
            + cfg.THREE_METRICS + cfg.AGE_METRICS
            + [f"{m}_adj" for m in cfg.THREE_METRICS + cfg.AGE_METRICS]
            + ["individuals_per_hh", "pounds_per_hh",
               "bad_period", "is_duplicate_superseded", "negative_value",
               "age_split_mismatch", "implausible_ratio", "households_equals_pounds",
               "spike_flag", "is_clean"])
    out = fs[[c for c in keep if c in fs.columns]].copy()
    write_parquet(out, cfg.P_SITE_MONTH)
    print(f"  wrote {cfg.P_SITE_MONTH.name}: {out.shape}")

    flagged = out.loc[~out["is_clean"]]
    flagged.to_csv(cfg.TAB / "flagged_rows.csv", index=False)
    print(f"  wrote outputs/tables/flagged_rows.csv: {len(flagged)} rows for manual review")
    return out


# ===================================================== sites: shared definition
def attach_site_activity(sites: pd.DataFrame, sm: pd.DataFrame) -> pd.DataFrame:
    """
    Add the shared site definition and a reporting summary to sites.parquet.

    is_food_shelf_like   from the master's own AgencyType, cleaned the same way
                         as in site_month, so every site has it whether or not
                         it ever reported. This is THE definition Q1, Q6 and Q8
                         share; the row-level flag in site_month is the type a
                         site had in that month, which can differ.
    ever_reported        the site has at least one usable activity row
    first_yearmonth, last_yearmonth, n_months_reported
    share_months_food_shelf_like   of its reported months, the share in which
                         the activity file called it a food-shelf-like site
    """
    print("\n== sites.parquet: shared food-shelf definition + reporting summary")
    at = sites["AgencyType"].astype("string").str.strip().replace({
        "Brick and Mortar Sites": "Brick and Mortar Site",
        "Meal Programs": "Meal Program",
        "On-Site Meal Programs": "Meal Program"})
    sites = sites.copy()
    sites["agency_type_clean"] = at
    sites["is_food_shelf_like"] = at.isin(cfg.FOOD_SHELF_TYPES).fillna(False).astype(bool)

    usable = sm[~sm["bad_period"] & ~sm["is_duplicate_superseded"]]
    g = (usable.groupby("site_id")
               .agg(first_yearmonth=("yearmonth", "min"),
                    last_yearmonth=("yearmonth", "max"),
                    n_months_reported=("yearmonth", "nunique"),
                    share_months_food_shelf_like=("is_food_shelf_like", "mean"))
               .reset_index())
    sites = sites.merge(g, on="site_id", how="left")
    sites["ever_reported"] = sites["n_months_reported"].notna()
    sites["n_months_reported"] = sites["n_months_reported"].fillna(0).astype(int)
    for c in ("first_yearmonth", "last_yearmonth"):
        sites[c] = sites[c].astype("Int64")

    never = ~sites["ever_reported"]
    log("Organization", "site never reported activity", int(never.sum()),
        "kept, flagged ever_reported=False",
        f"{int((never & sites['is_food_shelf_like']).sum())} of them are food-shelf-like. "
        "A site with no activity cannot be a served location in Q8.")
    changed = sites["ever_reported"] & (sites["share_months_food_shelf_like"].between(0, 1, inclusive="neither"))
    log("Organization", "site's type changed over time in the activity file", int(changed.sum()),
        "master type kept as is_food_shelf_like; share_months_food_shelf_like records the history",
        "The master holds the current type. County _fs totals use the month-by-month type.")
    orphan = set(usable["site_id"]) - set(sites["site_id"])
    log("org_FSStats", "site reports activity but is not in the Organization master", len(orphan),
        "not added to sites.parquet", "No address or type is known for them; they stay in site_month.")

    write_parquet(sites, cfg.P_SITES)
    print(f"  rewrote {cfg.P_SITES.name}: {sites.shape}")
    return sites


# =============================================================== county-month
def build_county_month(sm: pd.DataFrame) -> pd.DataFrame:
    """
    County x month panel. This is the table most questions actually join on.

    It carries n_sites_reporting next to every metric, because a county total
    moves with how many sites filed a report that month, not only with demand.
    Any month-over-month claim has to look at both columns.
    """
    print("\n== county x month panel")
    d = sm[sm["fips"].notna() & ~sm["bad_period"] & ~sm["is_duplicate_superseded"]].copy()

    aggs = {m: (f"{m}_adj", "sum") for m in cfg.THREE_METRICS + cfg.AGE_METRICS}
    g = (d.groupby(["fips", "county_name", "yearmonth", "year", "month", "date"], dropna=False)
           .agg(n_sites_reporting=("site_id", "nunique"),
                n_rows=("record_id", "size"),
                n_flagged=("is_clean", lambda s: int((~s).sum())),
                n_food_shelf_like=("is_food_shelf_like", "sum"),
                **aggs)
           .reset_index())

    # The same panel restricted to food-shelf-like sites, for need-vs-demand work.
    d2 = d[d["is_food_shelf_like"]]
    g2 = (d2.groupby(["fips", "yearmonth"])
            .agg(**{f"{m}_fs": (f"{m}_adj", "sum") for m in cfg.THREE_METRICS})
            .reset_index())
    g = g.merge(g2, on=["fips", "yearmonth"], how="left")

    g = g.sort_values(["fips", "yearmonth"]).reset_index(drop=True)
    write_parquet(g, cfg.P_COUNTY_MONTH)
    print(f"  wrote {cfg.P_COUNTY_MONTH.name}: {g.shape}")

    # A county-month with no row at all is a reporting gap, not a zero.
    n_full = g["fips"].nunique() * g["yearmonth"].nunique()
    log("county_month", "county-months with no reporting site at all", n_full - len(g),
        "left absent, NOT filled with zero",
        "Treating a reporting gap as a zero would invent a collapse in demand.")

    # A whole county can be absent from the panel. That is a finding, not a bug.
    all_mn = set(geo.mn_county_fips()["fips"])
    never = sorted(all_mn - set(g["fips"]))
    log("county_month", "MN counties with no reporting food shelf in any month", len(never),
        "absent from the panel, listed here",
        f"FIPS {never}. Zero observed demand is not zero need: this is the Q6 case in its purest form.")
    return g


# ========================================================= map the meal gap
def build_mmg() -> pd.DataFrame:
    """Map the Meal Gap, Minnesota only, 2019-2024, on a single FIPS key."""
    print("\n== Map the Meal Gap -> mmg_county.parquet")
    frames = []
    for path, label in [(cfg.F_MMG_2025, "MMG 2025 edition"), (cfg.F_MMG_2026, "MMG 2026 edition")]:
        d = pd.read_excel(path, sheet_name="County")
        d = d[d["State"] == "MN"].copy()
        # FIPS arrives as an integer here but as text in other sources.
        # Standardise on a 5-character zero-padded string everywhere.
        d["fips"] = pd.to_numeric(d["FIPS"], errors="coerce").astype("Int64").astype(str).str.zfill(5)
        d["county_name"] = d["County, State"].str.replace(r" County, Minnesota$", "", regex=True)
        d["source_edition"] = label
        frames.append(d)
    m = pd.concat(frames, ignore_index=True)

    ren = {"Overall Food Insecurity Rate": "fi_rate",
           "# of Food Insecure Persons Overall": "fi_persons",
           "Child Food Insecurity Rate": "child_fi_rate",
           "# of Food Insecure Children": "fi_children",
           "Cost Per Meal": "cost_per_meal",
           "Weighted Annual Food Budget Shortfall": "annual_shortfall",
           "Rural-Urban Continuum Code (2023)": "rucc_2023",
           "Rural-Urban Continuum Code (2013)": "rucc_2013",
           "SNAP Threshold": "snap_threshold"}
    # The "% FI <= SNAP Threshold" column name contains a unicode <= sign.
    for c in m.columns:
        if isinstance(c, str) and c.startswith("% FI") and "SNAP Threshold" in c:
            ren[c] = "pct_fi_below_snap_threshold" if "≤" in c else "pct_fi_above_snap_threshold"
    m = m.rename(columns={k: v for k, v in ren.items() if k in m.columns})

    keep = ["fips", "county_name", "Year", "source_edition", "fi_rate", "fi_persons",
            "child_fi_rate", "fi_children", "cost_per_meal", "annual_shortfall",
            "rucc_2013", "rucc_2023", "snap_threshold",
            "pct_fi_below_snap_threshold", "pct_fi_above_snap_threshold"]
    m = m[[c for c in keep if c in m.columns]].rename(columns={"Year": "year"})

    dup = m.duplicated(subset=["fips", "year"], keep=False)
    log("MapTheMealGap", "same county-year appears in both editions", int(dup.sum()),
        "both kept, distinguished by source_edition",
        "The 2026 edition revised some counties. Do not average the two editions.")
    log("MapTheMealGap", "FIPS stored as an integer here, as text in other sources", len(m),
        "cast to a 5-character zero-padded string on load",
        "Leading zeros vanish silently; MN is 27xxx so the bug only shows up once other states are added.")

    write_parquet(m, cfg.P_MMG)
    print(f"  wrote {cfg.P_MMG.name}: {m.shape}")
    return m


# ======================================================================= calls
def build_calls() -> pd.DataFrame:
    """Call log with a FIPS key and an explicit food-related flag."""
    print("\n== Incoming Call -> calls_clean.parquet")
    c = pd.read_excel(cfg.F_CALLS)
    c = c.rename(columns={"__ID": "call_id", "Date": "date",
                          "PrimaryReasonForCall": "reason", "SNAP Status": "snap_status"})
    c["date"] = pd.to_datetime(c["date"], errors="coerce")
    c["yearmonth"] = c["date"].dt.year * 100 + c["date"].dt.month

    c = geo.attach_fips(c, "County")
    log("IncomingCall", "no usable county on the call record", int(c["fips"].isna().sum()),
        "flagged, excluded from geographic analysis",
        f"{c['fips'].isna().mean():.0%} of calls. Free-text field; typos fixed where unambiguous.")

    c["sparse_period"] = c["date"] < "2023-01-01"
    log("IncomingCall", "records dated before 2023", int(c["sparse_period"].sum()),
        "flagged sparse_period=True",
        "Logging was not yet in routine use. Do not read a trend across the 2022/2023 boundary.")

    # "Food-related" is OUR definition. It is stated here so it can be argued with.
    FOOD_REASONS = {"Food Shelf", "Meal Program", "Farmers market", "SUN Bucks",
                    "Affordable Groceries"}
    SNAP_REASONS = {"SNAP Rx", "Eligibility Requirements", "Application Assistance",
                    "Application Status", "Recertification", "SNAP Changes",
                    "EBT Card", "E-SNAP", "Interview", "Case-Specific Issues",
                    "County Office Details", "Retailer"}
    c["is_food_direct"] = c["reason"].isin(FOOD_REASONS)
    c["is_snap_related"] = c["reason"].isin(SNAP_REASONS)
    c["is_food_related"] = c["is_food_direct"] | c["is_snap_related"]
    c["is_snap_rx"] = c["isSNAPRx"].fillna(0).astype(int).astype(bool)
    log("IncomingCall", "SNAP Rx clinic referrals", int(c["is_snap_rx"].sum()),
        "flagged is_snap_rx=True",
        f"{c['is_snap_rx'].mean():.0%} of calls. Clinics push these; callers do not pull them. Different signal.")

    keep = ["call_id", "date", "yearmonth", "County", "county_name", "fips", "county_match",
            "Region", "reason", "snap_status", "CallMethod", "NumberInHouse",
            "ReferralInfoEntry", "HowHear", "is_food_direct", "is_snap_related",
            "is_food_related", "is_snap_rx", "sparse_period"]
    out = c[[k for k in keep if k in c.columns]]
    write_parquet(out, cfg.P_CALLS)
    print(f"  wrote {cfg.P_CALLS.name}: {out.shape}")
    return out


# ================================================================ marketbucks
def build_marketbucks(sites: pd.DataFrame) -> pd.DataFrame:
    print("\n== marketbucksUsage -> marketbucks_clean.parquet")
    mb = pd.read_excel(cfg.F_MARKETBUCKS)
    mb = mb.rename(columns={"_ID": "mb_id", "_id_site": "site_id", "Dated": "date"})
    mb["site_id"] = to_site_id(mb["site_id"])
    mb["date"] = pd.to_datetime(mb["date"], errors="coerce")
    mb["yearmonth"] = mb["date"].dt.year * 100 + mb["date"].dt.month
    mb["month"] = mb["date"].dt.month

    mb = mb.merge(sites[["site_id", "fips", "county_name", "block_geoid", "tract_geoid"]],
                  on="site_id", how="left")
    # Every session joins to a site; the gap is that some of those sites have
    # no county on their own record.
    log("marketbucksUsage", "market session whose site record carries no county",
        int(mb["fips"].isna().sum()), "flagged, excluded from county-level results",
        "All 155 market sites join to Organization.__ID; the county itself is missing upstream.")

    money = ["SNAPDistributed", "SNAPRedeemed", "MBDistributed", "MBRedeemed",
             "PBDistributed", "PBRedeemed", "RCMBDistributed", "RCMBRedeemed", "GiftCerts"]
    for col in money:
        if col in mb.columns:
            mb[col] = pd.to_numeric(mb[col], errors="coerce")

    # Redemption above distribution is legitimate here: customers carry tokens
    # over between visits. Flag it so that nobody "fixes" it later.
    over = (mb["MBRedeemed"] > mb["MBDistributed"]).fillna(False)
    log("marketbucksUsage", "Market Bucks redeemed exceeds Market Bucks distributed", int(over.sum()),
        "flagged redeemed_over_distributed=True, value kept",
        "Legitimate: tokens carry over between market visits. Do not net these to zero.")
    mb["redeemed_over_distributed"] = over
    mb["is_late_entry"] = mb["isLateEntry"].fillna(0).astype(int).astype(bool)

    keep = (["mb_id", "site_id", "date", "yearmonth", "month", "fips", "county_name",
             "block_geoid", "tract_geoid", "Customers", "Transactions"]
            + money + ["redeemed_over_distributed", "is_late_entry"])
    out = mb[[c for c in keep if c in mb.columns]]
    write_parquet(out, cfg.P_MARKETBUCKS)
    print(f"  wrote {cfg.P_MARKETBUCKS.name}: {out.shape}")
    return out


# ======================================================================= main
def main() -> None:
    print("=" * 70)
    print("MinneMUDAC / The Food Group -- cleaning pipeline")
    print("=" * 70)

    sites = build_sites()
    sm = build_site_month(sites)
    sites = attach_site_activity(sites, sm)
    build_county_month(sm)
    build_mmg()
    build_calls()
    build_marketbucks(sites)

    xw = geo.build_crosswalk(pd.read_excel(cfg.F_FSSTATS, usecols=["County"])["County"])
    xw.to_csv(cfg.P_COUNTY_XWALK, index=False)
    print(f"\nwrote {cfg.P_COUNTY_XWALK.name}: {len(xw)} county labels mapped")

    q = pd.DataFrame(QUALITY_LOG)
    q.to_csv(cfg.P_QUALITY, index=False)
    print(f"wrote {cfg.P_QUALITY.name}: {len(q)} logged issues")
    print("\nDone. Every question script should now read from data/processed/ only.")


if __name__ == "__main__":
    main()
