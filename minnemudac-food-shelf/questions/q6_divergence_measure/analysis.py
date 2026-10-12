"""
Q6 -- A measure of need that is not demand, and where it diverges from activity

Owner: Valentino
Read questions/q6_divergence_measure/README.md and addendum.md before editing this file.

Run from the repo root:   python questions/q6_divergence_measure/analysis.py

Rules for this file:
  * It reads from data/processed/ and data/external/ only, never data/raw/.
  * Every number that ends up on a slide is produced here, by this script.
  * If you cannot explain a line of it live, it does not belong here.

The definition of need, the inputs with their defence, and the rejection and
revision criteria were written in notebooks/q6_exploration.ipynb (step 0) before
any result existed. This file only rebuilds the numbers and figures.

Inputs come from data/processed/county_covariates.parquet (python src/build_covariates.py,
after questions/q8_lila_access/build_lila.py once for the LILA share).

Outputs
    outputs/tables/q6_need_index.csv          step 2  index, rank, inputs per county (mean of 2022-2024)
    outputs/tables/q6_index_checks.csv        step 2  poverty and dominance checks
    outputs/tables/q6_divergence.csv          step 3  need rank vs activity rank, three metrics
    outputs/figures/q6_divergence_ranks.png   step 3  need rank against activity rank, one panel per metric
    outputs/tables/q6_stability.csv           step 4  named variants
    outputs/tables/q6_stability_random.csv    step 4  share of random weightings with each county in the top ten
    outputs/tables/q6_barriers_model.csv      step 5  divergence on the barriers: alone, with sites, with three more barriers
    outputs/tables/q6_barrier_sides.csv       step 5c no-internet on the need side and the activity side of the gap
    outputs/tables/q6_vs_mmg.csv              step 6  log activity on size + MMG rate / index / both, nine metric-years
    outputs/figures/q6_maps.png               step 5  need index and divergence, county maps
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

OUT_PREFIX = "q6"
METRICS = list(cfg.THREE_METRICS)
INPUTS = ["pct_hh_snap", "pct_no_vehicle", "senior_poverty_rate", "pct_hh_housing_burden",
          "pct_no_hs_diploma", "lila_share_1and10", "pct_debt_collections"]
STABLE_SHARE = 0.70          # "stable top ten" = in the top ten in this share of random draws
N_RANDOM = 500


def savefig(name):
    path = cfg.FIG / f"{name}.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close("all")
    print(f"  -> outputs/figures/{name}.png")


def county_frame():
    """County-year frame: activity + need + covariates. Wilkin's activity is a true zero."""
    df = qkit.county_year(cfg.Q1_YEARS).merge(
        qkit.covariates(cfg.Q1_YEARS).drop(columns="county_name"),
        on=["fips", "year"], how="left", validate="1:1")
    no_activity = df["households"].isna() & df["fi_persons"].notna()
    for m in METRICS:
        df.loc[no_activity, m] = 0
    missing = int(df[INPUTS].isna().sum().sum())
    assert missing == 0, f"{missing} missing input values; rebuild county_covariates"
    return df


def zscore_within_year(df, cols):
    return df.groupby("year")[cols].transform(lambda s: (s - s.mean()) / s.std())


def build_index(df, inputs=INPUTS, weights=None):
    """Z-score each input within year; weighted mean. Equal weights unless given."""
    w = pd.Series(1.0, index=inputs) if weights is None else pd.Series(weights, index=inputs)
    z = zscore_within_year(df, inputs)
    return (z * w).sum(axis=1) / w.sum()


def rank_index(df, inputs=INPUTS):
    return df.groupby("year")[inputs].rank(pct=True).mean(axis=1)


def county_rank(df, score):
    s = df.assign(score=score).groupby("county_name")["score"].mean()
    return s.rank(ascending=False).astype(int)


def fit_clustered(formula, data):
    return smf.ols(formula, data=data).fit(cov_type="cluster", cov_kwds={"groups": data["county_id"]})


def coef_table(fit, label):
    ci = fit.conf_int()
    return pd.DataFrame({"model": label, "term": fit.params.index, "coef": fit.params.values,
                         "se": fit.bse.values, "p": fit.pvalues.values,
                         "ci_low": ci[0].values, "ci_high": ci[1].values, "r2": fit.rsquared})


def main():
    print("=" * 70)
    print("Q6 -- A measure of need that is not demand")
    print("=" * 70)

    # Step 1. County-year frame.
    df = county_frame()
    print(f"{len(df)} county-years, {df['fips'].nunique()} counties")

    # Step 2. The index: equal-weight mean of within-year z-scores, higher = more need.
    #   County score = mean of the three years.
    df["need_index"] = build_index(df)
    need = (df.groupby(["fips", "county_name"], as_index=False)
              .agg(need_index=("need_index", "mean"), poverty_rate=("poverty_rate", "mean"),
                   fi_rate=("fi_rate", "mean"), population=("population", "mean"),
                   **{v: (v, "mean") for v in INPUTS}))
    need["need_rank"] = need["need_index"].rank(ascending=False).astype(int)
    need = need.sort_values("need_rank").reset_index(drop=True)
    wil = need[need["county_name"] == "Wilkin"].iloc[0]
    print(f"Wilkin: rank {wil['need_rank']} of 87 (predicted about 25th)")
    print("top ten:", ", ".join(need["county_name"].head(10)))
    qkit.save(need.round(4), f"{OUT_PREFIX}_need_index")

    # Checks tied to the revision criteria written in advance.
    pov_fit = smf.ols("need_index ~ poverty_rate", data=need).fit()
    z = zscore_within_year(df, INPUTS)
    _, S, Vt = np.linalg.svd(z.values - z.values.mean(axis=0), full_matrices=False)
    top = set(need.head(10)["county_name"])
    rows = [
        {"check": "R2 of index on poverty rate (revise if ~0.9+)", "value": pov_fit.rsquared},
        {"check": "top ten shared with poverty top ten",
         "value": len(top & set(need.nlargest(10, "poverty_rate")["county_name"]))},
        {"check": "top ten shared with MMG fi_rate top ten",
         "value": len(top & set(need.nlargest(10, "fi_rate")["county_name"]))},
        {"check": "Spearman, index vs poverty rate",
         "value": need["need_index"].corr(need["poverty_rate"], method="spearman")},
        {"check": "Spearman, index vs MMG fi_rate",
         "value": need["need_index"].corr(need["fi_rate"], method="spearman")},
        {"check": "share of input variance on first component", "value": S[0] ** 2 / (S ** 2).sum()},
    ]
    rows += [{"check": f"loading on first component: {v}", "value": l} for v, l in zip(INPUTS, Vt[0])]
    rows += [{"check": f"correlation with index: {v}", "value": c} for v, c in z.corrwith(df["need_index"]).items()]
    checks = pd.DataFrame(rows)
    print(checks.round(3).to_string(index=False))
    qkit.save(checks.round(4), f"{OUT_PREFIX}_index_checks")

    # Step 3. Divergence: activity per 1,000 residents ranked, against the need rank.
    #   divergence = activity_rank - need_rank; positive = need outranks recorded activity.
    act = (df.groupby(["fips", "county_name"])
             .apply(lambda g: pd.Series({m + "_per_1k": 1000 * g[m].sum() / g["population"].sum()
                                         for m in METRICS}), include_groups=False)
             .reset_index())
    div = need[["fips", "county_name", "need_index", "need_rank"]].merge(act, on=["fips", "county_name"])
    for m in METRICS:
        div[m + "_rank"] = div[m + "_per_1k"].rank(ascending=False).astype(int)
        div["div_" + m] = div[m + "_rank"] - div["need_rank"]
    div["div_mean"] = div[["div_" + m for m in METRICS]].mean(axis=1)
    div = div.sort_values("div_mean", ascending=False).reset_index(drop=True)
    print("Spearman, need index vs activity per 1,000:",
          {m: round(div["need_index"].corr(div[m + "_per_1k"], method="spearman"), 2) for m in METRICS})
    print("need outranks recorded activity:", ", ".join(div["county_name"].head(8)))
    print("recorded activity outranks need:", ", ".join(div["county_name"].tail(5)[::-1]))
    qkit.save(div.round(3), f"{OUT_PREFIX}_divergence")

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5), sharey=True)
    for ax, m in zip(axes, METRICS):
        ax.scatter(div["need_rank"], div[m + "_rank"], alpha=0.6)
        ax.plot([1, 87], [1, 87], color="grey", ls="--", lw=0.8, label="need and activity agree")
        d = div[m + "_rank"] - div["need_rank"]
        for idx in pd.concat([d.nlargest(6), d.nsmallest(4)]).index:
            ax.annotate(div.loc[idx, "county_name"], (div.loc[idx, "need_rank"], div.loc[idx, m + "_rank"]),
                        xytext=(4, 4), textcoords="offset points", fontsize=8)
        ax.invert_xaxis()
        ax.invert_yaxis()
        ax.set_xlabel("need rank (1 = most need)")
        ax.set_title(f"{m} per 1,000 residents")
    axes[0].set_ylabel("activity rank (1 = most recorded)")
    axes[0].legend(fontsize=8, loc="lower left")
    fig.suptitle("Where need outranks recorded activity (below the line) and the reverse (above)")
    plt.tight_layout()
    savefig(f"{OUT_PREFIX}_divergence_ranks")

    # Step 4. Stability: named variants, then random weights.
    base = county_rank(df, df["need_index"])
    base_top = set(base[base <= 10].index)
    no_snap_debt = [i for i in INPUTS if i not in ("pct_hh_snap", "pct_debt_collections")]
    lila_vehicle = [i if i != "lila_share_1and10" else "lila_share_vehicle" for i in INPUTS]
    variants = {
        "drop SNAP and debt": county_rank(df, build_index(df, no_snap_debt)),
        "LILA vehicle definition": county_rank(df, build_index(df, lila_vehicle)),
        "rank scaling": county_rank(df, rank_index(df)),
    }
    for i in INPUTS:
        variants["without " + i] = county_rank(df, build_index(df, [j for j in INPUTS if j != i]))
    stab = pd.DataFrame([{"variant": k, "top10_kept": len(base_top & set(r[r <= 10].index)),
                          "spearman_with_baseline": base.corr(r, method="spearman"),
                          "wilkin_rank": int(r["Wilkin"]),
                          "enters_top10": ", ".join(sorted(set(r[r <= 10].index) - base_top))}
                         for k, r in variants.items()])
    print(stab.round(3).to_string(index=False))
    qkit.save(stab.round(4), f"{OUT_PREFIX}_stability")

    rng = np.random.default_rng(0)
    hits = pd.Series(0, index=base.index)
    wilkin = []
    for _ in range(N_RANDOM):
        r = county_rank(df, build_index(df, INPUTS, rng.dirichlet(np.ones(len(INPUTS)))))
        hits[r[r <= 10].index] += 1
        wilkin.append(int(r["Wilkin"]))
    rand = (hits / N_RANDOM).rename("share_in_top10").sort_values(ascending=False).reset_index()
    rand["baseline_rank"] = rand["county_name"].map(base)
    stable = list(rand.loc[rand["share_in_top10"] >= STABLE_SHARE, "county_name"])
    print(f"stable top ten (in the top ten in at least {STABLE_SHARE:.0%} of {N_RANDOM} random weightings):",
          ", ".join(stable))
    print(f"Wilkin across draws: median {int(np.median(wilkin))}, range {min(wilkin)} to {max(wilkin)}")
    qkit.save(rand.round(3), f"{OUT_PREFIX}_stability_random")

    # Step 5. What explains the divergence: the barriers set aside in step 0, then sites.
    per_1k = df.assign(**{m + "_per_1k": 1000 * df[m] / df["population"] for m in METRICS})
    z_act = zscore_within_year(per_1k, [m + "_per_1k" for m in METRICS]).mean(axis=1)
    q5 = df[["fips", "county_name", "year", "need_index", "fi_rate", "mean_km_to_site", "rucc_2023",
             "pct_senior", "sites_per_10k", "pct_hh_limited_english", "pct_hh_no_internet",
             "pct_noncitizen"]].copy()
    q5["divergence_z"] = df["need_index"] - z_act
    q5["z_act"] = z_act
    # z-scores within year: the outcome is within-year, so a covariate with a time trend
    # (internet access rises every year) must not load onto the year dummies
    for v in ["mean_km_to_site", "pct_senior", "sites_per_10k", "pct_hh_limited_english",
              "pct_hh_no_internet", "pct_noncitizen"]:
        q5[v + "_z"] = q5.groupby("year")[v].transform(lambda s: (s - s.mean()) / s.std())
    q5["nonmetro_town"] = q5["rucc_2023"].between(4, 7).astype(int)
    q5["rural"] = (q5["rucc_2023"] >= 8).astype(int)
    q5["y2023"] = (q5["year"] == 2023).astype(int)
    q5["y2024"] = (q5["year"] == 2024).astype(int)
    q5["county_id"] = q5["fips"].astype("category").cat.codes
    barriers = "mean_km_to_site_z + nonmetro_town + rural + pct_senior_z + y2023 + y2024"
    new = "pct_hh_limited_english_z + pct_hh_no_internet_z + pct_noncitizen_z"
    m_a = fit_clustered("divergence_z ~ " + barriers, q5)
    m_b = fit_clustered("divergence_z ~ " + barriers + " + sites_per_10k_z", q5)
    m_c = fit_clustered("divergence_z ~ " + barriers + " + " + new, q5)
    m_d = fit_clustered("divergence_z ~ " + new + " + y2023 + y2024", q5)
    coefs = pd.concat([coef_table(m_a, "barriers only"), coef_table(m_b, "with sites"),
                       coef_table(m_c, "with three more barriers"), coef_table(m_d, "three more barriers alone")],
                      ignore_index=True)
    print(f"barriers model: n = {int(m_a.nobs)} | R2 barriers only {m_a.rsquared:.3f} | with sites {m_b.rsquared:.3f}"
          f" | with limited English, no internet, non-citizens {m_c.rsquared:.3f} | those three alone {m_d.rsquared:.3f}")
    print(coefs[coefs["model"] == "with three more barriers"][["term", "coef", "p", "ci_low", "ci_high"]]
          .round(3).to_string(index=False))
    qkit.save(coefs.round(4), f"{OUT_PREFIX}_barriers_model")

    # Step 5c. Which side of the gap does no-internet explain? The divergence is
    #   need_index - z_act, so regress each half on no-internet with the other half held fixed.
    m_act = fit_clustered("z_act ~ need_index + pct_hh_no_internet_z + " + barriers, q5)
    m_need = fit_clustered("need_index ~ z_act + pct_hh_no_internet_z + " + barriers, q5)
    sides = pd.concat([coef_table(m_act, "activity side (index held fixed)"),
                       coef_table(m_need, "need side (activity held fixed)")], ignore_index=True)
    sides = sides[sides["term"] == "pct_hh_no_internet_z"]
    print(sides[["model", "coef", "p", "ci_low", "ci_high"]].round(3).to_string(index=False))
    qkit.save(sides.round(4), f"{OUT_PREFIX}_barrier_sides")

    # Step 6. The index against MMG, head to head: nested models on log activity with
    #   log population holding county size, one fit per metric-year.
    rows = []
    for met in METRICS:
        for yr in cfg.Q1_YEARS:
            g = df[(df["year"] == yr) & (df[met] > 0)].copy()
            g["log_act"], g["log_pop"] = np.log(g[met]), np.log(g["population"])
            f0 = smf.ols("log_act ~ log_pop", data=g).fit()
            fa = smf.ols("log_act ~ log_pop + fi_rate", data=g).fit(cov_type="HC3")
            fb = smf.ols("log_act ~ log_pop + need_index", data=g).fit(cov_type="HC3")
            fc = smf.ols("log_act ~ log_pop + fi_rate + need_index", data=g).fit(cov_type="HC3")
            rows.append({"metric": met, "year": yr, "r2_size_only": f0.rsquared, "r2_mmg": fa.rsquared,
                         "r2_index": fb.rsquared, "r2_both": fc.rsquared,
                         "both_mmg_coef": fc.params["fi_rate"], "both_mmg_p": fc.pvalues["fi_rate"],
                         "both_index_coef": fc.params["need_index"], "both_index_p": fc.pvalues["need_index"]})
    vs = pd.DataFrame(rows)
    print("index vs MMG, mean over nine metric-years:")
    print(vs.drop(columns=["metric", "year"]).mean().round(3).to_string())
    qkit.save(vs.round(4), f"{OUT_PREFIX}_vs_mmg")

    # The maps. County outlines are the 2020 TIGER tracts dissolved to county.
    import geopandas as gpd
    tracts = gpd.read_file(cfg.EXTERNAL / "census" / "tract" / "tl_2020_27_tract" / "tl_2020_27_tract.shp")
    geo = tracts.dissolve(by="COUNTYFP")[["geometry"]].reset_index()
    geo["fips"] = "27" + geo["COUNTYFP"]
    geo = geo.merge(div[["fips", "county_name", "need_index", "div_mean"]], on="fips", how="left")
    fig, axes = plt.subplots(1, 2, figsize=(15, 8))
    geo.plot(column="need_index", cmap="YlOrRd", legend=True, edgecolor="white", lw=0.4, ax=axes[0],
             legend_kwds={"label": "need index (higher = more need)", "shrink": 0.6})
    geo[geo["county_name"].isin(stable)].boundary.plot(ax=axes[0], color="black", lw=1.2)
    axes[0].set_title("Need index, 2022-2024" + chr(10) + "Outlined: in the top ten under almost any weights",
                      fontsize=10)
    lim = geo["div_mean"].abs().max()
    geo.plot(column="div_mean", cmap="RdBu_r", vmin=-lim, vmax=lim, legend=True, edgecolor="white", lw=0.4,
             ax=axes[1], legend_kwds={"label": "divergence: activity rank - need rank", "shrink": 0.6})
    axes[1].set_title("Divergence" + chr(10) + "Red: need outranks recorded activity. Blue: the reverse",
                      fontsize=10)
    for _, r in geo.nlargest(6, "div_mean").iterrows():
        axes[1].annotate(r["county_name"], (r.geometry.centroid.x, r.geometry.centroid.y), ha="center", fontsize=7)
    for ax in axes:
        ax.set_axis_off()
    plt.tight_layout()
    savefig(f"{OUT_PREFIX}_maps")

    # Slide figures.
    # 1. Need rank against activity rank, households only, with the counties named.
    fig, ax = plt.subplots(figsize=(9, 7))
    d = div["households_rank"] - div["need_rank"]
    ax.scatter(div["need_rank"], div["households_rank"], alpha=0.65, s=40)
    ax.plot([1, 87], [1, 87], color="grey", ls="--", lw=1.4, label="need and activity agree")
    for idx in pd.concat([d.nlargest(6), d.nsmallest(4)]).index:
        ax.annotate(div.loc[idx, "county_name"], (div.loc[idx, "need_rank"], div.loc[idx, "households_rank"]),
                    xytext=(6, 5), textcoords="offset points", fontsize=11)
    ax.invert_xaxis()
    ax.invert_yaxis()
    ax.set_xlabel("need rank, Q6 index (1 = most need)", fontsize=13)
    ax.set_ylabel("recorded households per 1,000 residents, rank (1 = most)", fontsize=13)
    ax.tick_params(labelsize=11)
    rho = div["need_index"].corr(div["households_per_1k"], method="spearman")
    ax.set_title(f"Where need is high, recorded activity is not (Spearman {rho:.2f})\n"
                 "below the line: need outranks activity", fontsize=15, fontweight="bold")
    ax.legend(fontsize=11, loc="lower left")
    plt.tight_layout()
    savefig(f"{OUT_PREFIX}_divergence_ranks_slide")

    # 2. Three maps on one scale: need by MMG, need by the index, recorded activity.
    mmg_rank = need.set_index("fips")["fi_rate"].rank(ascending=False).astype(int)
    act_rank = div.set_index("fips")[[m + "_rank" for m in METRICS]].mean(axis=1).rank().astype(int)
    geo["mmg_rank"] = geo["fips"].map(mmg_rank)
    geo["activity_rank"] = geo["fips"].map(act_rank)
    geo["need_rank"] = geo["fips"].map(need.set_index("fips")["need_rank"])
    geo["gap"] = geo["mmg_rank"] - geo["need_rank"]
    movers = geo.reindex(geo["gap"].abs().sort_values(ascending=False).index).head(6)
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.2))
    fig.subplots_adjust(left=0.01, right=0.93, top=0.86, bottom=0.02, wspace=0.03)
    panels = [("mmg_rank", "Need: Feeding America rate"), ("need_rank", "Need: our index"),
              ("activity_rank", "Recorded activity per 1,000 residents")]
    for k, (ax, (col, title)) in enumerate(zip(axes, panels)):
        geo.plot(column=col, cmap="YlOrRd_r", vmin=1, vmax=87, edgecolor="white", lw=0.4, ax=ax)
        if col == "activity_rank":
            geo[geo["county_name"] == "Wilkin"].plot(ax=ax, facecolor="none", edgecolor="black", hatch="///", lw=0.6)
        for j, (_, r) in enumerate(movers.iterrows()):
            ax.annotate(r["county_name"], (r.geometry.centroid.x, r.geometry.centroid.y),
                        xytext=(0, 10 if j % 2 else -12), textcoords="offset points", ha="center",
                        fontsize=10, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_axis_off()
    sm = plt.cm.ScalarMappable(cmap="YlOrRd_r", norm=plt.Normalize(1, 87))
    cbar = fig.colorbar(sm, ax=axes, shrink=0.75, pad=0.01)
    cbar.set_label("rank (1 = most)", fontsize=12)
    fig.suptitle("Two measures of need, and where activity is recorded. Hatched: Wilkin, no reporting food shelf",
                 fontsize=15, fontweight="bold", y=0.97)
    fig.savefig(cfg.FIG / f"{OUT_PREFIX}_three_maps.png", dpi=150, bbox_inches="tight")
    plt.close("all")
    print(f"  -> outputs/figures/{OUT_PREFIX}_three_maps.png")


if __name__ == "__main__":
    main()
