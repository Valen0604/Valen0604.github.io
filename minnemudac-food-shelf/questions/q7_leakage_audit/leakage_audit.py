"""Q7 leakage audit. Run from the repo root by someone other than the model's author:
    python questions/q7_forecast_august/leakage_audit.py
Every check prints PASS or FAIL. Rerun before the submission is sent."""
import importlib.util, re, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, "src")
import config as cfg
import qkit

results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))

# 1. The processed panels end at July 2026.
cm = pd.read_parquet(cfg.P_COUNTY_MONTH); sm = pd.read_parquet(cfg.P_SITE_MONTH)
check("county_month ends at 202607", cm["yearmonth"].max() == 202607, f"max {cm['yearmonth'].max()}")
check("site_month ends at 202607", sm["yearmonth"].max() == 202607, f"max {sm['yearmonth'].max()}")
check("no site-month row dated 2026-08 or later", (sm["yearmonth"] >= 202608).sum() == 0)

# 2. The recomputed-in-August rolling averages never reach processed data.
sites = pd.read_parquet(cfg.P_SITES)
z12_processed = [c for c in list(sites.columns) + list(sm.columns) + list(cm.columns) if "z12" in c.lower() or "12mo" in c.lower()]
check("no z12MoAverage column in any processed table", not z12_processed, str(z12_processed))
raw_org = pd.read_excel(cfg.F_ORG, nrows=1)
z12_raw = [c for c in raw_org.columns if "z12" in c.lower()]
check("the raw Organization file does carry z12 columns (so the drop matters)", bool(z12_raw), f"{len(z12_raw)} columns")

# 3. What the Q7 script and notebook read.
script = Path("questions/q7_forecast_august/analysis.py").read_text(encoding="utf-8")
nb = Path("notebooks/q7_forecast_august.ipynb").read_text(encoding="utf-8")
reads = re.findall(r"(read_parquet|read_csv|read_excel|qkit\.\w+)\([^)]*\)", script)
check("script reads no data/raw file except the submission template", "RAW_REF" in script and "F_FSSTATS" not in script and "F_ORG" not in script and "data/raw" not in script.replace("RAW_REF", ""),
      "reads: " + "; ".join(sorted(set(reads)))[:300])
check("notebook reads no raw data", "data/raw" not in nb and "F_FSSTATS" not in nb and "F_ORG" not in nb)
check("script uses no z12 columns", "z12" not in script.lower())
check("script truncates the panel at the training cutoff", "TRAIN_CUTOFF_YM" in script and "panel[\"yearmonth\"].le(cfg.TRAIN_CUTOFF_YM)" in script)
check("TRAIN_CUTOFF_YM is 202607 and the target is 202608",
      getattr(cfg, "TRAIN_CUTOFF_YM", None) == 202607 and getattr(cfg, "FORECAST_TARGET_YM", None) == 202608,
      f"cutoff {getattr(cfg, 'TRAIN_CUTOFF_YM', None)}, target {getattr(cfg, 'FORECAST_TARGET_YM', None)}")
check("no external series (CPI, SNAP, BLS, ACS) enters the forecast", not re.search(r"snap|cpi|bls|acs|covariates\(", script, re.I) or "mmg" in script.lower(),
      "MMG is used only for the Wilkin imputation")

# 4. Fold isolation, tested empirically: the predictions for a backtest August must be
#    identical whether or not the panel contains anything after that August.
spec = importlib.util.spec_from_file_location("q7", "questions/q7_forecast_august/analysis.py")
q7 = importlib.util.module_from_spec(spec); spec.loader.exec_module(q7)
panel = qkit.county_month()
panel = panel.loc[panel["yearmonth"].le(cfg.TRAIN_CUTOFF_YM)].copy()
counties = q7._county_metadata()
iso_ok, iso_detail = True, []
for year in (2023, 2024, 2025):
    full = q7._forecast_target(panel, year, counties)
    cut = q7._forecast_target(panel.loc[panel["yearmonth"].lt(year * 100 + 8)], year, counties)
    a = full.sort_values(["fips", "metric", "method"]).reset_index(drop=True)
    b = cut.sort_values(["fips", "metric", "method"]).reset_index(drop=True)
    same = (len(a) == len(b)) and ((a["prediction"].fillna(-1) - b["prediction"].fillna(-1)).abs().max() < 1e-9)
    iso_ok &= same
    iso_detail.append(f"{year}: {'identical' if same else 'DIFFERS'} ({len(a)} rows)")
check("backtest predictions do not change when later months are removed", iso_ok, "; ".join(iso_detail))

# 5. The backtest scores in the tables are reproducible from the saved predictions.
pred = pd.read_csv(cfg.TAB / "q7_backtest_predictions.csv", dtype={"fips": str})
sel = pd.read_csv(cfg.TAB / "q7_method_selection.csv")
chosen = sel[sel["selected_for_forecast"]].set_index("metric")["method"].to_dict()
rows = []
for m, meth in chosen.items():
    sub = pred[(pred["metric"] == m) & (pred["method"] == meth)].dropna(subset=["actual", "prediction"])
    rmse = sub.groupby("target_year").apply(lambda g: ((g["actual"] - g["prediction"]) ** 2).mean() ** 0.5, include_groups=False).mean()
    rows.append((m, meth, round(rmse, 1), round(float(sel[(sel.metric == m) & (sel.method == meth)]["mean_fold_rmse"].iloc[0]), 1)))
check("selected methods' RMSE recomputed from saved predictions matches the selection table",
      all(abs(r[2] - r[3]) < 0.6 for r in rows), "; ".join(f"{m}: {a} vs {b}" for m, _, a, b in rows))
check("all five scored outcomes use the pooled May-July method; individuals is the age sum",
      all(v == "pooled_quarter_ratio" for k, v in chosen.items() if k != "individuals") and chosen.get("individuals") == "age_group_sum", str(chosen))

# 6. The submission file.
sub = pd.read_csv(cfg.OUT / "prediction" / "Graduate_Predictions_Submit.csv")
fc = pd.read_csv(cfg.TAB / "q7_forecasts.csv", dtype={"fips": str})
fc = fc[fc["target_yearmonth"] == 202608]
mmg_names = set(qkit.mmg([2024])["county_name"])
check("submission has 87 rows, one per county, names matching Map the Meal Gap", len(sub) == 87 and set(sub["County"]) == mmg_names,
      f"{len(sub)} rows; unmatched: {sorted(set(sub['County']) ^ mmg_names)[:5]}")
cols = {"HouseholdReg_Predicted": "households", "PoundsReg_Predicted": "pounds", "ChildrenReg_Predicted": "children",
        "SeniorsReg_Predicted": "seniors", "AdultsReg_Predicted": "adults"}
check("no blank, negative or non-integer prediction", sub[list(cols)].notna().all().all() and (sub[list(cols)] >= 0).all().all()
      and (sub[list(cols)] == sub[list(cols)].round()).all().all())
mism = []
for col, metric in cols.items():
    f = fc[fc["metric"] == metric].set_index("county_name")["prediction"].round()
    s = sub.set_index("County")[col]
    d = (f.reindex(s.index) - s).abs()
    if d.max() > 1: mism.append(f"{metric}: max diff {d.max():.0f}")
check("submission equals the rounded forecast table", not mism, "; ".join(mism))
check("YourTeamID is filled in", sub["YourTeamID"].notna().all() and (sub["YourTeamID"].astype(str).str.strip() != "").all(),
      "blank: fill before submitting")
imputed = fc[fc["forecast_status"] != "forecasted"]["county_name"].unique().tolist()
check("imputed counties are labelled (not silently forecast)", imputed == ["Wilkin"], str(imputed))

print(f"Q7 leakage audit, {pd.Timestamp.today():%d %B %Y}. Panel cutoff {cm['yearmonth'].max()}.")
for name, ok, detail in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
print(f"{sum(ok for _, ok, _ in results)} of {len(results)} checks passed")
