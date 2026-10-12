"""
build_covariates.py -- public county characteristics, one row per county-year.

Reads data/external/ (never data/raw/) and the processed site panel, writes
data/processed/county_covariates.parquet. Q1 joins it on (fips, year); Q6 and
Q8 can reuse it.

Run from the repo root:   python src/build_covariates.py

Every source is registered in docs/DATA_SOURCES.md. A source whose file is not
on disk yet is skipped with a warning and its columns come out empty, so the
rest of the build still runs.

Year convention: an ACS 5-year table is assigned to its END year
(2019-2023 -> 2023). State this on any slide that uses an ACS column.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg

YEARS = cfg.Q1_YEARS
EXT = cfg.EXTERNAL
OUT = cfg.P_COVARIATES


def _warn(msg: str) -> None:
    print(f"  !! {msg}")


def _counties() -> pd.DataFrame:
    """The 87 MN counties, fips + name, taken from Map the Meal Gap."""
    m = pd.read_parquet(cfg.P_MMG)
    return m[["fips", "county_name"]].drop_duplicates().reset_index(drop=True)


# ------------------------------------------------------------------ SAIPE
def saipe() -> pd.DataFrame:
    rows = []
    for y in YEARS:
        f = EXT / "census" / "saipe" / f"est{y % 100:02d}all.xls"
        if not f.exists():
            _warn(f"SAIPE {y} missing: {f.name}")
            continue
        d = pd.read_excel(f, header=3, dtype=str)
        d = d[(d["State FIPS Code"] == cfg.STATE_FIPS_MN) & (d["County FIPS Code"] != "000")]
        rows.append(pd.DataFrame({
            "fips": d["State FIPS Code"] + d["County FIPS Code"],
            "year": y,
            "poverty_rate": pd.to_numeric(d["Poverty Percent, All Ages"], errors="coerce"),
            "child_poverty_rate": pd.to_numeric(d["Poverty Percent, Age 0-17"], errors="coerce"),
            "median_hh_income": pd.to_numeric(d["Median Household Income"], errors="coerce"),
        }))
    return pd.concat(rows) if rows else pd.DataFrame(columns=["fips", "year"])


# ------------------------------------------------------------------ population
def population(counties: pd.DataFrame) -> pd.DataFrame:
    """MN State Demographic Center / Met Council annual estimates (April 1)."""
    f = next((EXT / "mn_sdc").glob("mn_county_edr_historical_estimates*.xlsx"), None)
    if f is None:
        _warn("MN SDC population file missing")
        return pd.DataFrame(columns=["fips", "year"])
    d = pd.read_excel(f, sheet_name=0)
    d = d[(d["Geography Type"] == "County") & d["Year"].isin(YEARS)]
    d = d.rename(columns={"Geography Name": "county_name", "Year": "year",
                          "Population": "population", "Households": "households_census"})
    d = d.merge(counties, on="county_name", how="left")
    assert d["fips"].notna().all(), "SDC county name failed to match MMG"
    return d[["fips", "year", "population", "households_census"]]


# ------------------------------------------------------------------ LAUS
def laus() -> pd.DataFrame:
    """BLS LAUS annual average unemployment rate. Note: an input to the MMG model."""
    rows = []
    for y in YEARS:
        f = EXT / "bls" / "laus" / f"laucnty{y % 100:02d}.xlsx"
        if not f.exists():
            _warn(f"LAUS {y} missing: {f.name}")
            continue
        d = pd.read_excel(f, header=1, dtype=str)
        d = d[d["State FIPS Code"] == cfg.STATE_FIPS_MN]
        rows.append(pd.DataFrame({
            "fips": d["State FIPS Code"] + d["County FIPS Code"],
            "year": y,
            "unemployment_rate": pd.to_numeric(d["Unemployment Rate (%)"], errors="coerce"),
        }))
    return pd.concat(rows) if rows else pd.DataFrame(columns=["fips", "year"])


# ------------------------------------------------------------------ ACS
def _read_acs(table: str, year: int, counties: pd.DataFrame) -> pd.DataFrame | None:
    """
    Read a data.census.gov table export (rows = variables, columns = counties)
    and return it long: one row per county, one column per variable label.
    Labels are indented with non-breaking spaces; the indentation is kept as a
    path ("Total:|1-person household:|No vehicle available") so that repeated
    labels at different levels stay distinct.
    """
    f = EXT / "census" / "acs" / f"acs5_{year}_{table}.csv"
    if not f.exists():
        _warn(f"ACS 5-year {table} {year} missing: {f.name}")
        return None
    d = pd.read_csv(f, dtype=str, encoding="utf-8-sig")
    labels, stack = [], []
    for raw in d["Label (Grouping)"]:
        depth = (len(raw) - len(raw.lstrip("  "))) // 4
        stack = stack[:depth] + [raw.strip("  ")]
        # drop the "Total:" root from every path below it
        labels.append("|".join(stack[1:]) if depth else stack[0])
    est = d[[c for c in d.columns if c.endswith("!!Estimate")]]
    est.index = labels
    est = est.T
    est.index = est.index.str.replace(" County, Minnesota!!Estimate", "", regex=False)
    est = est.apply(lambda s: pd.to_numeric(s.str.replace(",", ""), errors="coerce"))
    est = est.rename_axis("county_name").reset_index().merge(counties, on="county_name", how="left")
    assert est["fips"].notna().all(), f"{f.name}: county names failed to match MMG"
    assert len(est) == 87, f"{f.name}: expected 87 counties, got {len(est)}"
    est["year"] = year
    return est


def acs(counties: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for y in YEARS:
        out = counties[["fips"]].assign(year=y)

        veh = _read_acs("B08201", y, counties)
        if veh is not None:
            out = out.merge(veh.assign(
                pct_no_vehicle=100 * veh["No vehicle available"] / veh["Total:"]
            )[["fips", "pct_no_vehicle"]], on="fips", how="left")

        pov = _read_acs("B17001", y, counties)
        if pov is not None:
            below = "Income in the past 12 months below poverty level:"
            senior_cols = [c for c in pov.columns if c.startswith(below)
                           and c.endswith(("65 to 74 years", "75 years and over"))]
            all_senior = [c for c in pov.columns
                          if c.endswith(("65 to 74 years", "75 years and over"))]
            out = out.merge(pov.assign(
                senior_poverty_rate=100 * pov[senior_cols].sum(axis=1) / pov[all_senior].sum(axis=1),
                pct_senior=100 * pov[all_senior].sum(axis=1) / pov["Total:"],
            )[["fips", "senior_poverty_rate", "pct_senior"]], on="fips", how="left")

        snap = _read_acs("B22003", y, counties)
        if snap is not None:
            recv = [c for c in snap.columns if c.startswith("Household received Food Stamps/SNAP")
                    and c.count("|") == 0]
            out = out.merge(snap.assign(
                pct_hh_snap=100 * snap[recv[0]] / snap["Total:"]
            )[["fips", "pct_hh_snap"]], on="fips", how="left")

        # Q6 inputs. Housing-cost burden: households paying 30% or more of income on
        # rent (B25070) or owner costs (B25091), over households with a computed ratio.
        rent = _read_acs("B25070", y, counties)
        own = _read_acs("B25091", y, counties)
        if rent is not None and own is not None:
            burden = ["30.0 to 34.9 percent", "35.0 to 39.9 percent",
                      "40.0 to 49.9 percent", "50.0 percent or more"]
            own_burden = [c for c in own.columns if c.split("|")[-1] in burden]
            own_nc = [c for c in own.columns if c.endswith("Not computed")]
            h = rent[["fips"]].copy()
            h["num"] = rent[burden].sum(axis=1).to_numpy()
            h["den"] = (rent["Total:"] - rent["Not computed"]).to_numpy()
            o = own[["fips"]].assign(num=own[own_burden].sum(axis=1).to_numpy(),
                                     den=(own["Total:"] - own[own_nc].sum(axis=1)).to_numpy())
            h = h.merge(o, on="fips", suffixes=("_r", "_o"))
            h["pct_hh_housing_burden"] = 100 * (h["num_r"] + h["num_o"]) / (h["den_r"] + h["den_o"])
            out = out.merge(h[["fips", "pct_hh_housing_burden"]], on="fips", how="left")

        # Adults 25+ without a high-school diploma or equivalent (B15003).
        edu = _read_acs("B15003", y, counties)
        if edu is not None:
            cols = list(edu.columns)
            no_hs = cols[cols.index("No schooling completed"):cols.index("12th grade, no diploma") + 1]
            out = out.merge(edu.assign(
                pct_no_hs_diploma=100 * edu[no_hs].sum(axis=1) / edu["Total:"]
            )[["fips", "pct_no_hs_diploma"]], on="fips", how="left")

        # Q6 barriers in neither need model: limited English, no internet, non-citizens.
        lang = _read_acs("B16002", y, counties)
        if lang is not None:
            lim = [c for c in lang.columns if c.endswith("|Limited English speaking household")]
            out = out.merge(lang.assign(
                pct_hh_limited_english=100 * lang[lim].sum(axis=1) / lang["Total:"]
            )[["fips", "pct_hh_limited_english"]], on="fips", how="left")

        net = _read_acs("B28002", y, counties)
        if net is not None:
            out = out.merge(net.assign(
                pct_hh_no_internet=100 * net["No Internet access"] / net["Total:"]
            )[["fips", "pct_hh_no_internet"]], on="fips", how="left")

        cit = _read_acs("B05001", y, counties)
        if cit is not None:
            out = out.merge(cit.assign(
                pct_noncitizen=100 * cit["Not a U.S. citizen"] / cit["Total:"]
            )[["fips", "pct_noncitizen"]], on="fips", how="left")

        frames.append(out)
    return pd.concat(frames)


# ------------------------------------------------------------------ debt (Q6)
def debt(counties: pd.DataFrame) -> pd.DataFrame | None:
    """
    Share of adults with a credit record who have any debt in collections, from
    the Urban Institute's Debt in America county file. Static: one value, attached
    to every year. Covers only people with a credit file; the poorest households
    often have none, which is a known gap in the measure.
    """
    f = EXT / "urban" / "Debt in America County-Level Overall Debt.xlsx"
    if not f.exists():
        _warn(f"Urban Institute debt file missing: {f.name}")
        return None
    d = pd.read_excel(f, dtype={"County FIPS": str})
    d = d[d["State Name"] == "Minnesota"].rename(columns={"County FIPS": "fips"})
    d["pct_debt_collections"] = 100 * pd.to_numeric(d["Share with any debt in collections, All"])
    d = counties[["fips"]].merge(d[["fips", "pct_debt_collections"]], on="fips", how="left")
    assert d["pct_debt_collections"].notna().all(), "Urban debt file: not all 87 counties matched"
    return d.merge(pd.DataFrame({"year": YEARS}), how="cross")


# ------------------------------------------------------------------ site access
def site_access(pop: pd.DataFrame) -> pd.DataFrame:
    """
    Per county-year:
      n_sites_reporting      food-shelf-like sites with any activity that year
      sites_per_10k          the same, per 10,000 residents
      mean_km_to_site        population-weighted straight-line distance from each
                             tract's centre of population to the nearest reporting
                             site. Sites are placed at their tract's centroid
                             (Gazetteer), so within-tract distance reads as ~0.
    Sites are counted wherever they are, not only inside the county: a resident
    of Wilkin is measured to the nearest site in Clay if that is closer.
    """
    sm = pd.read_parquet(cfg.P_SITE_MONTH)
    sm = sm[~sm["bad_period"] & ~sm["is_duplicate_superseded"] & sm["is_food_shelf_like"]
            & sm["year"].isin(YEARS) & (sm["households"].fillna(0) > 0)]
    active = sm[["site_id", "year", "fips", "tract_geoid", "has_geoid",
                 "geoid_is_zip_centroid"]].drop_duplicates(["site_id", "year"])

    out = (active.groupby(["fips", "year"])["site_id"].nunique()
                 .rename("n_sites_reporting").reset_index())
    out = pop[["fips", "year", "population"]].merge(out, on=["fips", "year"], how="left")
    out["n_sites_reporting"] = out["n_sites_reporting"].fillna(0).astype(int)
    out["sites_per_10k"] = 1e4 * out["n_sites_reporting"] / out["population"]

    gaz_f = EXT / "census" / "gazetteer" / "2026_Gaz_tracts_national.txt"
    cen_f = EXT / "census" / "gazetteer" / "CenPop2020_Mean_TR27.txt"
    if not (gaz_f.exists() and cen_f.exists()):
        _warn("distance skipped: need both 2026_Gaz_tracts_national.txt and "
              "CenPop2020_Mean_TR27.txt in census/gazetteer/")
        out["mean_km_to_site"] = np.nan
        return out.drop(columns="population")

    gaz = pd.read_csv(gaz_f, sep="|", dtype={"GEOID": str})
    gaz.columns = gaz.columns.str.strip()
    gaz = gaz[gaz["GEOID"].str.startswith(cfg.STATE_FIPS_MN)]
    cen = pd.read_csv(cen_f, dtype=str, encoding="utf-8-sig")
    cen["tract_geoid"] = cen["STATEFP"] + cen["COUNTYFP"] + cen["TRACTCE"]
    cen["fips"] = cen["STATEFP"] + cen["COUNTYFP"]
    for c in ("POPULATION", "LATITUDE", "LONGITUDE"):
        cen[c] = pd.to_numeric(cen[c])

    # site_month stores these two flags as the strings "True"/"False"
    placed = active[(active["has_geoid"].astype(str) == "True")
                    & (active["geoid_is_zip_centroid"].astype(str) == "False")]
    placed = placed.merge(gaz[["GEOID", "INTPTLAT", "INTPTLONG"]],
                          left_on="tract_geoid", right_on="GEOID", how="inner")

    rows = []
    for y in YEARS:
        s = placed[placed["year"] == y]
        lat1 = np.radians(cen["LATITUDE"].to_numpy())[:, None]
        lon1 = np.radians(cen["LONGITUDE"].to_numpy())[:, None]
        lat2 = np.radians(s["INTPTLAT"].to_numpy())[None, :]
        lon2 = np.radians(s["INTPTLONG"].to_numpy())[None, :]
        a = (np.sin((lat2 - lat1) / 2) ** 2
             + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
        km = 2 * 6371.0 * np.arcsin(np.sqrt(a))
        t = cen[["fips", "POPULATION"]].assign(km=km.min(axis=1))
        g = t.groupby("fips").apply(
            lambda x: np.average(x["km"], weights=x["POPULATION"]), include_groups=False)
        rows.append(g.rename("mean_km_to_site").reset_index().assign(year=y))
    out = out.merge(pd.concat(rows), on=["fips", "year"], how="left")
    return out.drop(columns="population")


# ------------------------------------------------------------------ LILA (Q6)
def lila(counties: pd.DataFrame) -> pd.DataFrame | None:
    """
    Share of a county's population living in a low-income, low-access tract, from
    the USDA Food Access Research Atlas (2019 vintage, 2010 tracts, 2010 weights).
    Static: the same value is attached to every year. Built by
    questions/q8_lila_access/build_lila.py; skipped with a warning if absent.
      lila_share_1and10    LILA at 1 mile urban / 10 miles rural (USDA's headline)
      lila_share_vehicle   LILA counting households without a vehicle beyond half a mile
    """
    f = cfg.PROCESSED / "lila_tracts_2010.parquet"
    if not f.exists():
        _warn("LILA tract extract missing: run questions/q8_lila_access/build_lila.py")
        return None
    t = pd.read_parquet(f, columns=["County", "Pop2010", "LILATracts_1And10", "LILATracts_Vehicle"])
    t["county_name"] = t["County"].str.replace(r" County$", "", regex=True)
    g = t.groupby("county_name").apply(
        lambda d: pd.Series({"lila_share_1and10": (d["Pop2010"] * d["LILATracts_1And10"]).sum() / d["Pop2010"].sum(),
                             "lila_share_vehicle": (d["Pop2010"] * d["LILATracts_Vehicle"]).sum() / d["Pop2010"].sum()}),
        include_groups=False).reset_index()
    g = g.merge(counties, on="county_name", how="right")
    assert g["lila_share_1and10"].notna().all(), "Atlas county names failed to match MMG"
    return g.drop(columns="county_name").merge(pd.DataFrame({"year": YEARS}), how="cross")


# ------------------------------------------------------------------ main
def main() -> None:
    print(f"Building county covariates for {YEARS}")
    counties = _counties()
    pop = population(counties)

    df = counties.merge(pd.DataFrame({"year": YEARS}), how="cross")
    for part in (pop, saipe(), laus(), acs(counties), site_access(pop), lila(counties), debt(counties)):
        if part is not None:
            df = df.merge(part, on=["fips", "year"], how="left")

    assert len(df) == 87 * len(YEARS), f"expected {87 * len(YEARS)} rows, got {len(df)}"
    assert not df.duplicated(["fips", "year"]).any()

    df.to_parquet(OUT, index=False)
    print(f"  -> {OUT.relative_to(cfg.ROOT)}  ({len(df)} rows)")
    print("\nNon-missing per column:")
    print(df.notna().sum().to_string())


if __name__ == "__main__":
    main()
