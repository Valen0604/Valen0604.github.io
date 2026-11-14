"""
build_snap.py -- Minnesota SNAP caseloads, one row per reporting unit and month.

Reads data/external/mn_dhs/ (never data/raw/), writes
    data/processed/snap_unit_month.parquet     unit x month, all measures
    data/processed/snap_unit_crosswalk.csv     which of our 87 counties is in which unit

Run from the repo root:   python src/build_snap.py

Why "unit" and not "county": the source does not report every county on its own.

  * Dodge, Steele and Waseca are reported together as "MNPrairie".
  * Grant has no row after December 2021. From January 2022 its cases are inside
    Pope's row (Pope rises by Grant's count that month). To keep one definition for
    the whole period, Pope and Grant are added together in every month.
  * Lincoln, Lyon, Murray, Pipestone, Redwood and Rock each have a row, but cases move
    between those rows from month to month while their total stays flat. They are
    added together as "Southwest".
  * Three tribal nations are reported separately from the counties their members live
    in. They are kept as their own units and are NOT added to any county.

That gives 79 county units (76 single counties + 3 combined) and 3 tribal nations.
To change a grouping, edit COMBINED below; nothing else needs to change.

The source file is already cut at 2026-07. This script checks that again.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg
import qkit

SOURCE = cfg.EXTERNAL / "mn_dhs" / "snap_dashboard_county_month_2016-01_2026-07.csv"

# Names the source spells differently from the rest of the project.
RENAME = {"Lac Qui Parle": "Lac qui Parle", "Lake of Woods": "Lake of the Woods"}

# unit name -> the counties inside it
COMBINED = {
    "MNPrairie": ["Dodge", "Steele", "Waseca"],
    "Pope-Grant": ["Pope", "Grant"],
    "Southwest": ["Lincoln", "Lyon", "Murray", "Pipestone", "Redwood", "Rock"],
}
WHY = {
    "MNPrairie": "reported as one agency in the source",
    "Pope-Grant": "Grant is inside Pope's row from 2022-01",
    "Southwest": "cases move between these six rows; only the total is stable",
}
TRIBAL = ["Mille Lacs Band", "Red Lake Nation", "White Earth Band"]

COUNTY_TO_UNIT = {c: unit for unit, members in COMBINED.items() for c in members}


def _counties() -> pd.DataFrame:
    """The 87 MN counties, fips + name, taken from Map the Meal Gap."""
    m = pd.read_parquet(cfg.P_MMG)
    return m[["fips", "county_name"]].drop_duplicates().reset_index(drop=True)


def load_source() -> pd.DataFrame:
    if not SOURCE.exists():
        raise FileNotFoundError(f"SNAP source not found: {SOURCE}")
    d = pd.read_csv(SOURCE, dtype=str)
    d["date"] = pd.to_datetime(d["Report_Month"])
    d["yearmonth"] = d["date"].dt.year * 100 + d["date"].dt.month
    d["source_name"] = d["CountyTribeName"].replace(RENAME)
    measures = [c for c in d.columns
                if c not in ("Report_Month", "CountyTribeName", "date", "yearmonth", "source_name")]
    for c in measures:
        d[c] = pd.to_numeric(d[c], errors="raise")
    d = d.rename(columns={c: _snake(c) for c in measures})
    return d.drop(columns=["Report_Month", "CountyTribeName"])


def _snake(name: str) -> str:
    """CaseCount -> case_count, SNAP_Federal_Food_Issued -> snap_federal_food_issued."""
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and name[i - 1].islower():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def crosswalk() -> pd.DataFrame:
    """One row per county: which SNAP unit it belongs to, and why."""
    x = _counties()
    x["snap_unit"] = x["county_name"].map(COUNTY_TO_UNIT).fillna(x["county_name"])
    x["unit_type"] = x["snap_unit"].map(lambda u: "combined" if u in COMBINED else "county")
    x["n_counties_in_unit"] = x.groupby("snap_unit")["fips"].transform("size")
    x["reason"] = x["snap_unit"].map(WHY).fillna("")
    return x.sort_values("fips").reset_index(drop=True)


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    src = load_source()
    xw = crosswalk()
    measures = [c for c in src.columns if c not in ("date", "yearmonth", "source_name")]

    # Every row of the source must land in exactly one unit.
    src["snap_unit"] = src["source_name"].map(
        lambda n: n if n in COMBINED or n in TRIBAL else COUNTY_TO_UNIT.get(n, n))
    known = set(xw["snap_unit"]) | set(TRIBAL)
    stray = sorted(set(src["snap_unit"]) - known)
    if stray:
        raise ValueError(f"source names that match no county or unit: {stray}")
    unseen = sorted(set(xw["snap_unit"]) - set(src["snap_unit"]))
    if unseen:
        raise ValueError(f"units with no rows in the source: {unseen}")

    out = (src.groupby(["snap_unit", "yearmonth", "date"], as_index=False)[measures].sum())
    out["unit_type"] = out["snap_unit"].map(
        lambda u: "tribal nation" if u in TRIBAL else ("combined" if u in COMBINED else "county"))
    out["n_counties_in_unit"] = (out["snap_unit"].map(xw.groupby("snap_unit").size())
                                 .fillna(0).astype(int))
    out = out[["snap_unit", "unit_type", "n_counties_in_unit", "yearmonth", "date"] + measures]

    # Checks: nothing lost, nothing doubled, every unit present in every month.
    for m in ("case_count", "person_count", "total_net"):
        if out[m].sum() != src[m].sum():
            raise ValueError(f"statewide {m} changed during grouping")
    months = out["yearmonth"].nunique()
    short = out.groupby("snap_unit").size().loc[lambda s: s != months]
    if len(short):
        raise ValueError(f"units missing months: {short.to_dict()}")
    if out.duplicated(["snap_unit", "yearmonth"]).any():
        raise ValueError("duplicate unit-months")
    qkit.leakage_check(out)
    return out, xw


def main() -> None:
    out, xw = build()
    out.to_parquet(cfg.P_SNAP, index=False)
    xw.to_csv(cfg.P_SNAP_XWALK, index=False)
    print(f"  -> {cfg.P_SNAP.relative_to(cfg.ROOT)}  "
          f"({len(out)} rows, {out['snap_unit'].nunique()} units, "
          f"{out['yearmonth'].min()} to {out['yearmonth'].max()})")
    print(f"  -> {cfg.P_SNAP_XWALK.relative_to(cfg.ROOT)}  ({len(xw)} counties)")
    print(out.drop_duplicates("snap_unit")["unit_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
