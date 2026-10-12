"""
Q1 -- Need estimates against observed activity

Owner: Valentino
Read questions/q1_need_vs_activity/README.md before editing this file.

Run from the repo root:   python questions/q1_need_vs_activity/analysis.py

Rules for this file:
  * It reads from data/processed/ and data/external/ only, never data/raw/.
  * Every number that ends up on a slide is produced here, by this script.
  * If you cannot explain a line of it live, it does not belong here.

The exploration behind each step, with the predictions that were written before
each result, is notebooks/q1_exploration.ipynb. This file only rebuilds the
numbers and figures the slides cite.

Outputs
    outputs/tables/q1_correlations.csv        step 3  rank correlations, counts and rates
    outputs/tables/q1_loglog_fits.csv         step 4  slope, CI, R2 per metric-year
    outputs/figures/q1_loglog_fits.png        step 4  the 3 x 3 chart
    outputs/tables/q1_residual_ranking.csv    step 5  county mean residual, all sites and food shelves only
    outputs/figures/q1_residual_bars.png      step 5  the red / blue chart
    outputs/tables/q1_covariate_model.csv     step 6  main model, per metric, food shelves only
    outputs/tables/q1_morans_i.csv            step 7  spatial autocorrelation of the residuals
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import config as cfg
import qkit

OUT_PREFIX = "q1"
METRICS = list(cfg.THREE_METRICS)          # households, pounds, individuals
COVARIATES = ("mean_km_to_site_z + nonmetro_town + rural "
              "+ pct_no_vehicle_z + pct_hh_snap_z + y2023 + y2024")


def savefig(name: str) -> None:
    path = cfg.FIG / f"{name}.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close("all")
    print(f"  -> outputs/figures/{name}.png")


def county_frame(food_shelf_only: bool = False) -> pd.DataFrame:
    """County-year frame: activity + need + covariates. Wilkin's activity is a true zero."""
    df = qkit.county_year(cfg.Q1_YEARS, food_shelf_only=food_shelf_only).merge(
        qkit.covariates(cfg.Q1_YEARS).drop(columns="county_name"),
        on=["fips", "year"], how="left", validate="1:1")
    no_activity = df["households"].isna() & df["fi_persons"].notna()
    for m in METRICS:
        df.loc[no_activity, m] = 0
        df.loc[no_activity, f"{m}_per_fi"] = 0
    df.loc[no_activity, "months_observed"] = 0
    return df


def loglog_residuals(df: pd.DataFrame) -> pd.DataFrame:
    """One fit per metric and year: log activity on log food-insecure persons.
    Returns one row per county x metric x year with the residual."""
    out = []
    for m in METRICS:
        for yr in cfg.Q1_YEARS:
            g = df[(df["year"] == yr) & (df[m] > 0)].dropna(subset=["fi_persons"]).copy()
            g["resid"] = smf.ols(f"np.log({m}) ~ np.log(fi_persons)", data=g).fit().resid
            out.append(g[["fips", "county_name", "year", "resid"]].assign(metric=m))
    return pd.concat(out, ignore_index=True)


def coef_table(fit, label: str) -> pd.DataFrame:
    ci = fit.conf_int()
    return pd.DataFrame({"model": label, "term": fit.params.index, "coef": fit.params.values,
                         "se": fit.bse.values, "p": fit.pvalues.values,
                         "ci_low": ci[0].values, "ci_high": ci[1].values})


def fit_clustered(formula: str, data: pd.DataFrame):
    return smf.ols(formula, data=data).fit(cov_type="cluster", cov_kwds={"groups": data["county_id"]})


def main() -> None:
    print("=" * 70)
    print("Q1 -- Need estimates against observed activity")
    print("=" * 70)

    # Step 1. County-year frame: activity + Map the Meal Gap + covariates, 2022-2024.
    df = county_frame()
    print(f"{len(df)} county-years, {df['fips'].nunique()} counties")

    # Step 2. Rates. Per 1,000 residents does not share a term with fi_rate;
    #   per food-insecure person does (it divides by fi_persons, fi_rate multiplies by it).
    for m in METRICS:
        df[f"{m}_per_1k"] = 1000 * df[m] / df["population"]

    # Step 3. Rank correlations, each metric against need, per year.
    #   Sub-question 1: counts agree (mostly county size); rates do not.
    rows = []
    for yr in cfg.Q1_YEARS:
        sub = df[df["year"] == yr].dropna(subset=["fi_persons"])
        for m in METRICS:
            s = sub.dropna(subset=[m])
            rows.append({"year": yr, "metric": m, "n_counties": len(s),
                         "spearman_counts_vs_fi_persons": s[m].corr(s["fi_persons"], method="spearman"),
                         "spearman_per_1k_vs_fi_rate": s[f"{m}_per_1k"].corr(s["fi_rate"], method="spearman"),
                         "spearman_per_fi_vs_fi_rate": s[f"{m}_per_fi"].corr(s["fi_rate"], method="spearman")})
    corr = pd.DataFrame(rows).round(3)
    print(corr.to_string(index=False))
    qkit.save(corr, f"{OUT_PREFIX}_correlations")

    # Slide figure: activity per 1,000 residents against the food-insecurity rate, the
    # latest year, one panel per metric. The grey line is where the points would sit if
    # every county recorded the same activity per food-insecure person.
    yr = max(cfg.Q1_YEARS)
    g = df[df["year"] == yr]
    fig, axes = plt.subplots(1, len(METRICS), figsize=(15, 4.8), sharey=True)
    for ax, m in zip(axes, METRICS):
        x = 1e3 * g[m] / g["population"]
        y = g["fi_rate"]
        k = g[m].sum() / g["fi_persons"].sum()
        ax.scatter(x, y, alpha=0.65, s=34)
        ax.margins(x=0.14)
        xs = np.linspace(0, x.max(), 100)
        slope, intercept = np.polyfit(x, y, 1)
        ax.plot(xs, slope * xs + intercept, color="red", lw=2, label="actual fit")
        ax.plot(xs, xs / (1e3 * k), color="grey", ls="--", lw=1.6, label="if activity tracked need")
        for name in [g.loc[x.idxmax(), "county_name"], "Wilkin"]:
            r = g[g["county_name"] == name].iloc[0]
            ax.annotate(name, (1e3 * r[m] / r["population"], r["fi_rate"]),
                        xytext=(5, 5), textcoords="offset points", fontsize=11)
        ax.set_title(f"{m}: Spearman {x.corr(y, method='spearman'):.2f}", fontsize=14)
        ax.set_xlabel(f"{m} per 1,000 residents", fontsize=12)
        ax.tick_params(labelsize=11)
    axes[0].set_ylabel("Food-insecurity rate (Feeding America)", fontsize=12)
    axes[0].legend(loc="upper left", fontsize=11)
    fig.suptitle(f"Per resident, recorded activity does not follow the food-insecurity rate ({yr})",
                 fontsize=16, fontweight="bold")
    plt.tight_layout()
    savefig(f"{OUT_PREFIX}_per_1k_slide")

    # Step 4. Log-log fits, one per metric and year. Slope > 1: activity rises faster
    #   than need. Sub-question 2: R2 by metric. HC3 errors for the interval.
    fig, axes = plt.subplots(len(METRICS), len(cfg.Q1_YEARS), figsize=(15, 12), sharex=True)
    fit_rows = []
    for i, m in enumerate(METRICS):
        for j, yr in enumerate(cfg.Q1_YEARS):
            g = df[(df["year"] == yr) & (df[m] > 0)].copy()
            fit = smf.ols(f"np.log({m}) ~ np.log(fi_persons)", data=g).fit(cov_type="HC3")
            b0, b1 = fit.params.iloc[0], fit.params.iloc[1]
            lo, hi = fit.conf_int().iloc[1]
            g["resid"] = fit.resid
            fit_rows.append({"metric": m, "year": yr, "slope": b1, "ci_low": lo, "ci_high": hi,
                             "r2": fit.rsquared, "n": int(fit.nobs)})
            ax = axes[i, j]
            ax.scatter(g["fi_persons"], g[m], alpha=0.6)
            xs = np.geomspace(g["fi_persons"].min(), g["fi_persons"].max(), 50)
            ax.plot(xs, np.exp(b0) * xs ** b1, color="red", label="fit")
            k = np.exp(np.log(g[m]).mean() - np.log(g["fi_persons"]).mean())
            ax.plot(xs, k * xs, color="grey", linestyle="--", label="slope 1 (proportional)")
            for idx in (g["resid"].idxmin(), g["resid"].idxmax()):
                ax.annotate(g.loc[idx, "county_name"], (g.loc[idx, "fi_persons"], g.loc[idx, m]),
                            xytext=(4, 4), textcoords="offset points", fontsize=8)
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_title(f"{m}, {yr}: slope {b1:.2f} [{lo:.2f}, {hi:.2f}], R2 {fit.rsquared:.2f}")
            if i == len(METRICS) - 1:
                ax.set_xlabel("food-insecure persons (log)")
            if j == 0:
                ax.set_ylabel(f"{m} (log)")
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Recorded activity rises faster than need: every slope is above 1", y=1.0)
    plt.tight_layout()
    savefig(f"{OUT_PREFIX}_loglog_fits")
    fits = pd.DataFrame(fit_rows).round(3)
    print(fits.to_string(index=False))
    qkit.save(fits, f"{OUT_PREFIX}_loglog_fits")

    # Step 5. Residual ranking. Sub-question 3: the tails are the breakdown counties.
    #   Positive = more activity recorded than need predicts. Wilkin has no residual.
    res = loglog_residuals(df)
    summary = (res.groupby(["fips", "county_name"])
                  .agg(mean_resid=("resid", "mean"),
                       n_below=("resid", lambda r: int((r < 0).sum())),
                       n=("resid", "size"))
                  .reset_index())
    res_fs = loglog_residuals(county_frame(food_shelf_only=True))
    summary = summary.merge(res_fs.groupby("fips")["resid"].mean().rename("mean_resid_food_shelf_only"),
                            on="fips", how="left")
    summary["shift_food_shelf_only"] = summary["mean_resid_food_shelf_only"] - summary["mean_resid"]
    summary["activity_share_of_predicted"] = np.exp(summary["mean_resid"])
    summary = summary.sort_values("mean_resid").reset_index(drop=True)
    print("least activity relative to need:", ", ".join(summary["county_name"].head(6)))
    print("most activity relative to need: ", ", ".join(summary["county_name"].tail(6)[::-1]))
    print("Spearman, all sites vs food shelves only:",
          round(summary["mean_resid"].corr(summary["mean_resid_food_shelf_only"], method="spearman"), 3))
    qkit.save(summary.round(3), f"{OUT_PREFIX}_residual_ranking")

    k = 15
    show = pd.concat([summary.head(k), summary.tail(k)])
    colors = ["#c0392b" if v < 0 else "#2471a3" for v in show["mean_resid"]]
    fig, ax = plt.subplots(figsize=(8, 10))
    ax.barh(range(len(show)), show["mean_resid"], color=colors)
    ax.set_yticks(range(len(show)), show["county_name"])
    ax.invert_yaxis()
    ax.axvline(0, color="black", lw=0.8)
    ax.axhline(k - 0.5, color="grey", ls="--", lw=0.8)
    ax.set_xlabel("Mean log residual  (-0.5 = about 40% less activity than need predicts)")
    ax.set_title("Red: estimated need > recorded activity\n"
                 "Blue: recorded activity > estimated need\n"
                 f"{k} counties each way, 2022-2024. Not shown: Wilkin (no reporting food shelf)")
    plt.tight_layout()
    savefig(f"{OUT_PREFIX}_residual_bars")

    # Step 6. Sub-question 4: regress the residual on county characteristics.
    #   County-years, year dummies, errors clustered on county. Hypotheses and the
    #   reasons for leaving out poverty (MMG input), sites_per_10k (restates the
    #   outcome) and population (is fi_persons) are in the notebook and README.
    def model_frame(residuals: pd.DataFrame) -> pd.DataFrame:
        q = (residuals.groupby(["fips", "year"], as_index=False)["resid"].mean()
                      .merge(df[["fips", "year", "mean_km_to_site", "rucc_2023",
                                 "pct_no_vehicle", "pct_hh_snap"]], on=["fips", "year"], how="left"))
        for v in ["mean_km_to_site", "pct_no_vehicle", "pct_hh_snap"]:
            q[v + "_z"] = (q[v] - q[v].mean()) / q[v].std()
        q["nonmetro_town"] = q["rucc_2023"].between(4, 7).astype(int)
        q["rural"] = (q["rucc_2023"] >= 8).astype(int)
        q["y2023"] = (q["year"] == 2023).astype(int)
        q["y2024"] = (q["year"] == 2024).astype(int)
        q["county_id"] = q["fips"].astype("category").cat.codes
        return q

    q4 = model_frame(res)
    m_main = fit_clustered("resid ~ " + COVARIATES, q4)
    tables = [coef_table(m_main, "main (mean of three metrics)")]
    print(f"main model: n = {int(m_main.nobs)}, counties = {q4['county_id'].nunique()}, "
          f"R2 = {m_main.rsquared:.3f}")
    print(tables[0][["term", "coef", "p", "ci_low", "ci_high"]].round(3).to_string(index=False))
    for m in METRICS:
        tables.append(coef_table(fit_clustered("resid ~ " + COVARIATES, model_frame(res[res["metric"] == m])), m))
    m_fs = fit_clustered("resid ~ " + COVARIATES, model_frame(res_fs))
    tables.append(coef_table(m_fs, "food shelves only"))
    coefs = pd.concat(tables, ignore_index=True)
    coefs["r2"] = coefs["model"].map({"main (mean of three metrics)": m_main.rsquared,
                                      "food shelves only": m_fs.rsquared})
    qkit.save(coefs.round(4), f"{OUT_PREFIX}_covariate_model")

    # Step 7. Moran's I on the county mean residual: do neighbours look alike?
    #   Census County Adjacency File 2023; equal weights within each county's
    #   neighbour list; permutation p-value. Prediction was negative (spillover).
    adj = pd.read_csv(cfg.EXTERNAL / "census" / "adjacency" / "county_adjacency2023.txt",
                      sep="|", dtype=str)
    adj.columns = ["county", "fips", "neighbor", "nfips"]
    r = summary.set_index("fips")["mean_resid"]
    adj = adj[adj["fips"].isin(r.index) & adj["nfips"].isin(r.index) & (adj["fips"] != adj["nfips"])]
    W = pd.DataFrame(0.0, index=r.index, columns=r.index)
    for a, b in zip(adj["fips"], adj["nfips"]):
        W.loc[a, b] = 1.0
    W = W.div(W.sum(axis=1), axis=0).values

    def morans_i(x):
        z = x - x.mean()
        return (len(z) / W.sum()) * (z @ W @ z) / (z @ z)

    i_obs = morans_i(r.values)
    rng = np.random.default_rng(0)
    perm = np.array([morans_i(rng.permutation(r.values)) for _ in range(999)])
    p = (np.sum(np.abs(perm) >= abs(i_obs)) + 1) / (len(perm) + 1)
    moran = pd.DataFrame([{"n_counties": len(r), "morans_i": i_obs,
                           "expected_if_no_pattern": -1 / (len(r) - 1),
                           "permutation_p": p, "permutations": len(perm)}]).round(4)
    print(moran.to_string(index=False))
    qkit.save(moran, f"{OUT_PREFIX}_morans_i")


if __name__ == "__main__":
    main()
