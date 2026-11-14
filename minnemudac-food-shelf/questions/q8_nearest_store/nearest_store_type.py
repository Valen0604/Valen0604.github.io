"""Q8 follow-up: what kind of store is the nearest SNAP retailer, by tract group?

The retail comparison (compare_retailer_distances.py) showed that counting small and
"combination" stores brings the nearest SNAP store in rural LILA tracts from about 10 miles
to about 6. This script asks what those closer stores are. For every tract it finds the
nearest SNAP-authorised store under four widening definitions and records its type and
name, then summarises by LILA class and urban/rural with population weights.

Data: the USDA FNS SNAP Retailer Locator feature service (currently authorised stores,
Minnesota, with USDA's current store types). It is a snapshot retrieved on the date in the
registry, not a dated series; it is used only for this check and nowhere near Q7.
Tract population centres: Census CenPop2020_Mean_TR27. Tract groups: q8_tract_coverage.csv.

Run:  python questions/q8_lila_access/nearest_store_type.py [--offline]
Outputs:
  data/external/usda/snap_retailers_mn_current.csv   (downloaded once; --offline reuses it)
  outputs/tables/q8_nearest_store_type.csv            (one row per tract group x definition)
  outputs/tables/q8_nearest_store_names.csv           (which 'Other' stores are nearest)
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import config as cfg  # noqa: E402

SERVICE = ("https://services1.arcgis.com/RLQu0rK7h4kbsBq5/arcgis/rest/services/"
           "snap_retailer_location_data/FeatureServer/0/query")
STORES = cfg.EXTERNAL / "usda" / "snap_retailers_mn_current.csv"
COVERAGE = cfg.TAB / "q8_tract_coverage.csv"
CENPOP = cfg.EXTERNAL / "census" / "gazetteer" / "CenPop2020_Mean_TR27.txt"
OUT_SUMMARY = cfg.TAB / "q8_nearest_store_type.csv"
OUT_NAMES = cfg.TAB / "q8_nearest_store_names.csv"

# USDA's current store-type scheme. The 2025 historical file used an older one
# (Large/Medium/Small Grocery Store, Combination Grocery/Other); the mapping is noted.
DEFINITIONS = [
    ("1 supermarkets", {"Supermarket", "Super Store"}),
    ("2 + grocery stores of any size", {"Supermarket", "Super Store", "Grocery Store"}),
    ("3 + other stores selling groceries (dollar, pharmacy, general)",
     {"Supermarket", "Super Store", "Grocery Store", "Other"}),
    ("4 + convenience stores",
     {"Supermarket", "Super Store", "Grocery Store", "Other", "Convenience Store"}),
]
DOLLAR_PATTERN = r"dollar general|family dollar|dollar tree"


def download_stores() -> pd.DataFrame:
    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({
            "where": "State='MN'", "f": "json", "resultOffset": offset, "resultRecordCount": 2000,
            "outFields": "Record_ID,Store_Name,Store_Type,City,County,Latitude,Longitude"})
        with urllib.request.urlopen(f"{SERVICE}?{q}", timeout=60) as r:
            d = json.loads(r.read().decode())
        feats = d.get("features", [])
        rows += [f["attributes"] for f in feats]
        if not feats or not d.get("exceededTransferLimit"):
            break
        offset += len(feats)
    df = pd.DataFrame(rows).dropna(subset=["Latitude", "Longitude"])
    df["retrieved"] = date.today().isoformat()
    STORES.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(STORES, index=False)
    return df


def haversine_miles(lat0, lon0, lats, lons):
    la0, lo0 = np.radians(lat0), np.radians(lon0)
    la, lo = np.radians(lats), np.radians(lons)
    a = np.sin((la - la0) / 2) ** 2 + np.cos(la0) * np.cos(la) * np.sin((lo - lo0) / 2) ** 2
    return 2 * 3958.8 * np.arcsin(np.sqrt(a))


def main(offline: bool) -> None:
    stores = pd.read_csv(STORES) if (offline and STORES.exists()) else download_stores()
    print(f"stores: {len(stores)} Minnesota SNAP retailers; types: "
          + ", ".join(f"{k} {v}" for k, v in stores.Store_Type.value_counts().items()))

    cov = pd.read_csv(COVERAGE, dtype={"tract_geoid": str})
    cp = pd.read_csv(CENPOP, dtype=str)
    cp["tract_geoid"] = cp.STATEFP + cp.COUNTYFP + cp.TRACTCE
    cp["lat"], cp["lon"] = cp.LATITUDE.astype(float), cp.LONGITUDE.astype(float)
    tracts = cov.merge(cp[["tract_geoid", "lat", "lon"]], on="tract_geoid", how="inner")
    tracts = tracts[tracts.population > 0].copy()

    summary, names = [], []
    for label, types in DEFINITIONS:
        sub = stores[stores.Store_Type.isin(types)].reset_index(drop=True)
        d = np.vstack([haversine_miles(r.lat, r.lon, sub.Latitude.values, sub.Longitude.values)
                       for r in tracts.itertuples()])
        idx = d.argmin(axis=1)
        tracts["nearest_miles"] = d[np.arange(len(tracts)), idx]
        tracts["nearest_type"] = sub.Store_Type.values[idx]
        tracts["nearest_name"] = sub.Store_Name.values[idx]
        tracts["nearest_is_dollar"] = tracts.nearest_name.str.contains(DOLLAR_PATTERN, case=False, regex=True)
        for (lila, ur), g in tracts.groupby(["lila_class", "urban_rural"]):
            w = g.population / g.population.sum()
            row = {"definition": label, "stores_in_definition": len(sub), "lila_class": lila,
                   "urban_rural": ur, "tracts": len(g), "population": int(g.population.sum()),
                   "weighted_mean_nearest_miles": round(float(np.average(g.nearest_miles, weights=w)), 2),
                   "population_within_5_mi_pct": round(float(100 * w[g.nearest_miles <= 5].sum()), 1),
                   "nearest_is_dollar_store_pct": round(float(100 * w[g.nearest_is_dollar].sum()), 1)}
            shares = (g.groupby("nearest_type").population.sum() / g.population.sum() * 100).round(1)
            for t in ["Supermarket", "Super Store", "Grocery Store", "Other", "Convenience Store"]:
                row[f"nearest_is_{t.lower().replace(' ', '_')}_pct"] = float(shares.get(t, 0.0))
            summary.append(row)
        if label.startswith("3"):
            other = tracts[tracts.nearest_type == "Other"]
            counts = (other.assign(name=other.nearest_name.str.replace(r"\s*#?\d+$", "", regex=True).str.title())
                      .groupby(["lila_class", "urban_rural", "name"]).agg(tracts=("tract_geoid", "size"),
                                                                        population=("population", "sum"))
                      .reset_index().sort_values(["lila_class", "urban_rural", "population"], ascending=[True, True, False]))
            names = counts

    out = pd.DataFrame(summary)
    out.to_csv(OUT_SUMMARY, index=False)
    names.to_csv(OUT_NAMES, index=False)
    pd.set_option("display.width", 220)
    show = out[(out.lila_class == "LILA") & (out.urban_rural == "Rural")][
        ["definition", "weighted_mean_nearest_miles", "population_within_5_mi_pct", "nearest_is_dollar_store_pct",
         "nearest_is_other_pct", "nearest_is_grocery_store_pct", "nearest_is_convenience_store_pct"]]
    print("\nrural LILA tracts:\n" + show.to_string(index=False))
    print(f"\nwrote {OUT_SUMMARY.name} ({len(out)} rows) and {OUT_NAMES.name}")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
