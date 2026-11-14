"""
eda.py -- first look at the cleaned data.

Run after clean_data.py, from the repo root:

    python src/eda.py

This script does not answer any competition question. Its job is to tell the
three of us what we are actually looking at before anyone starts modelling:
how big the network is, when it is busy, which counties are large or unusual,
how far people are from a site, and where the Feeding America estimates and
the observed activity already look like they disagree.

Everything it prints also lands on disk:
    outputs/tables/*.csv    numbers you can paste into a slide
    outputs/figures/*.png   charts
    docs/EDA_FINDINGS.md    a generated summary, refreshed on every run

Charts are matplotlib defaults on purpose. This is our working view, not the
deck. Design comes later, once we know which chart is worth showing.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

FINDINGS: list[str] = []


def note(text: str) -> None:
    """Record a finding for docs/EDA_FINDINGS.md and echo it to the console."""
    FINDINGS.append(text)
    print("  * " + textwrap.fill(text, 100, subsequent_indent="    "))


def save_table(df: pd.DataFrame, name: str) -> None:
    df.to_csv(cfg.TAB / f"{name}.csv", index=False)
    print(f"    -> outputs/tables/{name}.csv")


def save_fig(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(cfg.FIG / f"{name}.png", dpi=150)
    plt.close(fig)
    print(f"    -> outputs/figures/{name}.png")


# ===================================================================== load
def load():
    sm = pd.read_parquet(cfg.P_SITE_MONTH)
    cm = pd.read_parquet(cfg.P_COUNTY_MONTH)
    sites = pd.read_parquet(cfg.P_SITES)
    mmg = pd.read_parquet(cfg.P_MMG)
    calls = pd.read_parquet(cfg.P_CALLS)
    mb = pd.read_parquet(cfg.P_MARKETBUCKS)
    return sm, cm, sites, mmg, calls, mb


# ============================================================ 1. the network
def section_scale(sm: pd.DataFrame, sites: pd.DataFrame) -> None:
    print("\n=== 1. How big is the network, and what does it report?")
    d = sm[~sm["bad_period"] & ~sm["is_duplicate_superseded"]]

    note(f"The panel covers {d['yearmonth'].min()} to {d['yearmonth'].max()}: "
         f"{d['yearmonth'].nunique()} months, {d['site_id'].nunique()} distinct sites, "
         f"{len(d):,} site-month records, {d['fips'].nunique()} of Minnesota's 87 counties.")

    months_per_site = d.groupby("site_id")["yearmonth"].nunique()
    note(f"The panel is unbalanced. Median site reports {months_per_site.median():.0f} of "
         f"{d['yearmonth'].nunique()} months; a quarter of sites report "
         f"{months_per_site.quantile(0.25):.0f} months or fewer. A county total therefore moves "
         f"with who filed a report, not only with demand.")

    by_month = (d.groupby("yearmonth")
                  .agg(sites_reporting=("site_id", "nunique"),
                       households=("households_adj", "sum"),
                       individuals=("individuals_adj", "sum"),
                       pounds=("pounds_adj", "sum"))
                  .reset_index())
    save_table(by_month, "01_statewide_by_month")

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(range(len(by_month)), by_month["sites_reporting"], marker=".")
    ax.set_xticks(range(0, len(by_month), 3))
    ax.set_xticklabels(by_month["yearmonth"].astype(str)[::3], rotation=45, ha="right")
    ax.set_ylabel("sites reporting")
    ax.set_title("Reporting sites per month (the denominator behind every county total)")
    save_fig(fig, "01_sites_reporting")

    lo, hi = by_month["sites_reporting"].min(), by_month["sites_reporting"].max()
    last = by_month.iloc[-1]
    note(f"Between {lo} and {hi} sites report in a given month. The final month "
         f"({int(last['yearmonth'])}) has {int(last['sites_reporting'])} reporting sites, "
         f"{(last['sites_reporting'] / by_month['sites_reporting'].tail(13).mean() - 1) * 100:+.1f}% "
         f"against the trailing 12-month average. If July is still receiving late entries it will "
         f"bias the August forecast downward.")

    types = (sm.groupby("agency_type_clean")
               .agg(rows=("record_id", "size"), sites=("site_id", "nunique"),
                    households=("households_adj", "sum"))
               .sort_values("households", ascending=False).reset_index())
    types["pct_households"] = (types["households"] / types["households"].sum() * 100).round(1)
    save_table(types, "01_agency_types")
    non_fs = sm.loc[~sm["is_food_shelf_like"], "households_adj"].sum() / sm["households_adj"].sum()
    note(f"Site types are mixed. {non_fs:.1%} of all households served come from sites that are "
         f"not brick-and-mortar food shelves (meal programs, outreach, campus, mobile). Including "
         f"or excluding them changes county totals, so every result must state which set it used.")

    note(f"Geocoding: {sites['has_geoid'].mean():.1%} of organizations carry a block_geoid, and "
         f"{int(sites['geoid_is_zip_centroid'].sum())} of those are ZIP centroids rather than "
         f"street addresses. Question 8 can only speak for the sites that have one.")


# ============================================================ 2. seasonality
def section_seasonality(cm: pd.DataFrame) -> None:
    print("\n=== 2. Which months are busy? (this is the Q7 prior)")
    d = cm.copy()

    # Compare months within a year, so that the upward trend across years does
    # not decide which month looks busiest.
    rows = []
    for metric in cfg.THREE_METRICS:
        yearly = d.groupby("year")[metric].transform("mean")
        d[f"{metric}_idx"] = d[metric] / yearly
        s = d.groupby("month")[f"{metric}_idx"].mean()
        rows.append(s.rename(metric))
    seas = pd.concat(rows, axis=1)
    seas.index = [MONTH_NAMES[m - 1] for m in seas.index]
    save_table(seas.reset_index().rename(columns={"index": "month"}), "02_seasonal_index")

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for metric in cfg.THREE_METRICS:
        ax.plot(seas.index, seas[metric], marker="o", label=metric)
    ax.axhline(1.0, color="grey", lw=0.8, ls="--")
    ax.set_ylabel("index (1.00 = that year's average month)")
    ax.set_title("Seasonal pattern, averaged across counties and years")
    ax.legend()
    save_fig(fig, "02_seasonality")

    for metric in cfg.THREE_METRICS:
        busiest = seas[metric].idxmax()
        quietest = seas[metric].idxmin()
        note(f"{metric}: busiest month is {busiest} ({seas.loc[busiest, metric]:.3f} of an average "
             f"month), quietest is {quietest} ({seas.loc[quietest, metric]:.3f}). "
             f"Peak-to-trough spread {(seas[metric].max() / seas[metric].min() - 1) * 100:.1f}%.")

    # The ratio we actually have to predict for Q7.
    aug_jul = []
    for year in sorted(d["year"].unique()):
        jul = d[(d["year"] == year) & (d["month"] == 7)][cfg.THREE_METRICS].sum()
        aug = d[(d["year"] == year) & (d["month"] == 8)][cfg.THREE_METRICS].sum()
        if aug.sum() > 0 and jul.sum() > 0:
            aug_jul.append(pd.Series((aug / jul).values, index=cfg.THREE_METRICS, name=year))
    if aug_jul:
        ratios = pd.DataFrame(aug_jul)
        ratios.index.name = "year"
        save_table(ratios.reset_index(), "02_august_over_july_ratio")
        note("August over July, statewide, by year: "
             + "; ".join(f"{y} " + ", ".join(f"{m} {ratios.loc[y, m]:.3f}" for m in cfg.THREE_METRICS)
                         for y in ratios.index)
             + ". This ratio is the baseline any Q7 model has to beat.")


# =============================================================== 3. trends
def section_trends(cm: pd.DataFrame) -> None:
    print("\n=== 3. Trend: is the network growing, and in which metric?")
    st = cm.groupby("yearmonth")[cfg.THREE_METRICS].sum().reset_index()
    st["households_per_site"] = (cm.groupby("yearmonth")["households"].sum()
                                 / cm.groupby("yearmonth")["n_sites_reporting"].sum()).values
    save_table(st, "03_statewide_trend")

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for ax, metric in zip(axes, cfg.THREE_METRICS):
        ax.plot(range(len(st)), st[metric], marker=".")
        ax.set_ylabel(metric)
        ax.grid(alpha=0.3)
    axes[-1].set_xticks(range(0, len(st), 3))
    axes[-1].set_xticklabels(st["yearmonth"].astype(str)[::3], rotation=45, ha="right")
    axes[0].set_title("Statewide monthly totals, the three metrics")
    save_fig(fig, "03_statewide_trend")

    yearly = cm.groupby("year")[cfg.THREE_METRICS].sum()
    full_years = yearly.loc[yearly.index.isin([2022, 2023, 2024, 2025])]
    growth = (full_years.iloc[-1] / full_years.iloc[0] - 1) * 100
    note("Across the four complete years 2022-2025 the three metrics grow at different rates: "
         + ", ".join(f"{m} {growth[m]:+.0f}%" for m in cfg.THREE_METRICS)
         + ". They are not interchangeable, which is exactly why the brief asks for all three.")

    per_hh = (cm.groupby("year")["pounds"].sum() / cm.groupby("year")["households"].sum())
    note("Pounds per household by year: "
         + ", ".join(f"{int(y)} {v:.0f}" for y, v in per_hh.items())
         + ". A falling ratio means the network is spreading the same food over more households.")


# ======================================================== 4. county profile
def section_counties(cm: pd.DataFrame, mmg: pd.DataFrame, sites: pd.DataFrame) -> None:
    print("\n=== 4. County characteristics and the Q1 mismatch, in preview")
    # Q1 is scored on 2023 and 2024, so build the county frame on those years.
    act = (cm[cm["year"].isin([2023, 2024])]
           .groupby(["fips", "county_name", "year"])[cfg.THREE_METRICS].sum().reset_index())

    fi = mmg[mmg["year"].isin([2023, 2024])][
        ["fips", "year", "fi_rate", "fi_persons", "cost_per_meal", "rucc_2023"]]
    df = act.merge(fi, on=["fips", "year"], how="outer")

    n_sites = (sites[sites["fips"].notna()].groupby("fips").size().rename("n_sites").reset_index())
    df = df.merge(n_sites, on="fips", how="left")
    df["n_sites"] = df["n_sites"].fillna(0)
    df["is_rural"] = df["rucc_2023"] >= 4     # USDA: 4-9 are non-metro
    for m in cfg.THREE_METRICS:
        df[f"{m}_per_fi"] = df[m] / df["fi_persons"]
    save_table(df, "04_county_year_activity_vs_need")

    note(f"{int(df['fi_persons'].isna().sum())} county-years have activity but no Feeding America "
         f"estimate, and {int(df[cfg.M_VISITS].isna().sum())} have an estimate but no reported "
         f"activity at all. The second group is where Question 6 lives.")

    # Correlations, the headline number of Q1.
    corr_rows = []
    for year in (2023, 2024):
        sub = df[(df["year"] == year)].dropna(subset=["fi_persons"])
        for m in cfg.THREE_METRICS:
            s = sub.dropna(subset=[m])
            corr_rows.append({
                "year": year, "metric": m, "n_counties": len(s),
                "pearson_counts": s[m].corr(s["fi_persons"]),
                "spearman_counts": s[m].corr(s["fi_persons"], method="spearman"),
                "spearman_rate": s[f"{m}_per_fi"].corr(s["fi_rate"], method="spearman"),
            })
    corr = pd.DataFrame(corr_rows).round(3)
    save_table(corr, "04_correlation_activity_vs_fi")
    print(corr.to_string(index=False))
    note("Correlation of raw counts against food-insecure persons is very high for all three "
         "metrics, but that is mostly population: big counties have more of everything. The "
         "per-food-insecure-person column is the one that carries information, and it is much "
         "weaker. Q1 has to lead with rates, not counts.")

    # The counties that sit furthest from the statewide relationship.
    sub = df[(df["year"] == 2024)].dropna(subset=["fi_persons", cfg.M_VISITS])
    sub = sub[sub["fi_persons"] > 0].copy()
    x = np.log(sub["fi_persons"])
    y = np.log(sub[cfg.M_VISITS].clip(lower=1))
    b, a = np.polyfit(x, y, 1)
    sub["residual"] = y - (a + b * x)
    out = sub[["fips", "county_name", "fi_persons", cfg.M_VISITS, "n_sites",
               "rucc_2023", "residual"]].sort_values("residual")
    save_table(out, "04_residuals_2024")
    note("Counties with the LEAST activity relative to their food-insecure population (2024): "
         + ", ".join(out.head(8)["county_name"]) + ". These are the first candidates for the "
         "Q6 divergence story - check whether they are rural, low-site-count, or both.")
    note("Counties with the MOST activity relative to their food-insecure population (2024): "
         + ", ".join(out.tail(8)["county_name"][::-1]) + ".")

    fig, ax = plt.subplots(figsize=(7.5, 6))
    ax.scatter(sub["fi_persons"], sub[cfg.M_VISITS], s=18, alpha=0.7)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("food-insecure persons (Map the Meal Gap, 2024)")
    ax.set_ylabel(f"{cfg.M_VISITS} served, 2024")
    for _, r in pd.concat([out.head(5), out.tail(5)]).iterrows():
        ax.annotate(r["county_name"], (r["fi_persons"], r[cfg.M_VISITS]), fontsize=7)
    ax.set_title("Need estimate vs observed activity, MN counties, 2024")
    save_fig(fig, "04_need_vs_activity")

    # Rural / metro split.
    rural = (df[df["year"] == 2024].groupby("is_rural")
             .agg(counties=("fips", "nunique"),
                  fi_persons=("fi_persons", "sum"),
                  households=(cfg.M_VISITS, "sum"),
                  sites=("n_sites", "sum")).reset_index())
    rural["households_per_fi_person"] = (rural["households"] / rural["fi_persons"]).round(3)
    rural["fi_persons_per_site"] = (rural["fi_persons"] / rural["sites"]).round(0)
    save_table(rural, "04_rural_vs_metro")
    print(rural.to_string(index=False))
    note("Rural counties (USDA RUCC 4-9) and metro counties differ in both directions at once: "
         "compare households served per food-insecure person against food-insecure persons per "
         "site in the table above. One is a measure of reach, the other of load.")


# ============================================================= 5. distances
def section_distance(sites: pd.DataFrame, cm: pd.DataFrame) -> None:
    """
    Distance work we can do today, without downloading anything.

    We do not have coordinates. We have a 15-digit census block GEOID, which
    gives us the tract a site sits in, and that is enough for a first pass on
    coverage. Real distance needs the Census block centroid file; see
    docs/DATA_SOURCES.md for the exact file to download for Q8.
    """
    print("\n=== 5. Coverage, as far as block_geoid alone can take us")
    s = sites[sites["has_geoid"] & sites["state_fips"].eq(cfg.STATE_FIPS_MN)].copy()

    per_county = (s.groupby("fips")
                    .agg(n_sites=("site_id", "nunique"),
                         n_tracts_with_a_site=("tract_geoid", "nunique"))
                    .reset_index())
    save_table(per_county, "05_sites_and_tracts_per_county")
    note(f"{len(s)} geocoded MN sites sit in {s['tract_geoid'].nunique()} distinct census tracts. "
         f"Minnesota has roughly 1,500 tracts, so most tracts contain no site at all - which is the "
         f"whole premise of Question 8.")

    tract_counts = s.groupby("tract_geoid").size()
    note(f"Site clustering: {(tract_counts > 1).sum()} tracts hold more than one site and "
         f"{tract_counts.max()} sites share a single tract. Clustering matters because a county "
         f"with many sites in one tract is not the same as a county with sites spread out.")

    last12 = cm[cm["yearmonth"] > cm["yearmonth"].max() - 100]
    load = (last12.groupby(["fips", "county_name"])["households"].sum().reset_index()
            .merge(per_county, on="fips", how="left"))
    load["households_per_site"] = (load["households"] / load["n_sites"]).round(0)
    load = load.sort_values("households_per_site", ascending=False)
    save_table(load, "05_load_per_site_by_county")
    note("Counties carrying the most households per site over the last 12 months: "
         + ", ".join(load.head(6)["county_name"].astype(str))
         + ". High load per site is a capacity story; it is not the same as high need.")


# ================================================== 6. calls and marketbucks
def section_other_programs(calls: pd.DataFrame, mb: pd.DataFrame, cm: pd.DataFrame) -> None:
    print("\n=== 6. Call centre and Market Bucks (supporting evidence for Q5 and Q6)")
    c = calls[~calls["sparse_period"]]
    by_m = (c.groupby("yearmonth")
              .agg(calls=("call_id", "size"),
                   food_related=("is_food_related", "sum"),
                   snap_rx=("is_snap_rx", "sum"),
                   with_county=("fips", "count")).reset_index())
    save_table(by_m, "06_calls_by_month")
    note(f"Call volume runs from {int(by_m['calls'].min())} to {int(by_m['calls'].max())} calls a "
         f"month since 2023, and {c['is_snap_rx'].mean():.0%} of calls are SNAP Rx clinic "
         f"referrals. SNAP Rx volume is driven by which clinics are enrolled, not by household "
         f"demand, so it must be separated before calls are used as a demand signal.")
    note(f"{calls['fips'].isna().mean():.0%} of call records carry no usable county. Any "
         f"geographic use of the call data has to state that share up front.")

    season = mb.groupby("month")["MBDistributed"].sum()
    if season.notna().any():
        peak = MONTH_NAMES[int(season.idxmax()) - 1]
        active = [MONTH_NAMES[m - 1] for m in sorted(season[season > season.max() * 0.05].index)]
        note(f"Market Bucks is strongly seasonal: distribution peaks in {peak} and is effectively "
             f"limited to {', '.join(active)}. Any comparison with food shelf activity has to hold "
             f"the season fixed, or the seasonality of markets will masquerade as an effect.")
    mb_county = (mb.groupby(["fips", "county_name"])
                   .agg(sessions=("mb_id", "size"),
                        snap_distributed=("SNAPDistributed", "sum"),
                        mb_distributed=("MBDistributed", "sum"),
                        customers=("Customers", "sum")).reset_index())
    save_table(mb_county, "06_marketbucks_by_county")
    note(f"Market Bucks reaches {mb_county['fips'].nunique()} counties against "
         f"{cm['fips'].nunique()} with food shelf activity, so the overlap the brief asks for in "
         f"Question 3 is narrow. Treat it as supporting evidence, not as a main axis.")


# ========================================================= 7. data quality
def section_quality(sm: pd.DataFrame) -> None:
    print("\n=== 7. What the cleaning step had to deal with")
    q = pd.read_csv(cfg.P_QUALITY)
    print(q[["table", "issue", "n_rows"]].to_string(index=False))
    note(f"{(~sm['is_clean']).sum():,} of {len(sm):,} site-month rows "
         f"({(~sm['is_clean']).mean():.1%}) fail at least one quality check and are replaced by "
         f"the site's own median in the *_adj columns. The raw values are kept alongside, so any "
         f"result can be re-run with or without the correction.")

    worst = (sm[~sm["is_clean"]].groupby(["county_name"]).size()
             .sort_values(ascending=False).head(8))
    note("Counties contributing the most flagged rows: "
         + ", ".join(f"{c} ({n})" for c, n in worst.items()) + ".")


# ======================================================================= main
def write_findings() -> None:
    out = cfg.DOCS / "EDA_FINDINGS.md"
    lines = ["# EDA findings (generated)", "",
             "Regenerated by `python src/eda.py`. Do not hand-edit: write narrative in the",
             "question READMEs instead, and let this file stay a machine-produced record of",
             "what the data says on the current cleaning rules.", "",
             f"Tables in `outputs/tables/`, charts in `outputs/figures/`.", ""]
    lines += [f"{i}. {t}" for i, t in enumerate(FINDINGS, 1)]
    lines += ["", "## Open questions this raises", "",
              "- Which field do the organizers mean by *visits*? We are using households served.",
              "- Is the final month complete, or still receiving late entries?",
              "- Which site types are in the August actuals that Q7 is scored against?", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote docs/EDA_FINDINGS.md ({len(FINDINGS)} findings)")


def main() -> None:
    print("=" * 70)
    print("MinneMUDAC / The Food Group -- exploratory data analysis")
    print("=" * 70)
    sm, cm, sites, mmg, calls, mb = load()

    section_scale(sm, sites)
    section_seasonality(cm)
    section_trends(cm)
    section_counties(cm, mmg, sites)
    section_distance(sites, cm)
    section_other_programs(calls, mb, cm)
    section_quality(sm)
    write_findings()


if __name__ == "__main__":
    main()
