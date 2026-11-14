# Q7 leakage audit

Run on 10 October 2026 by Valentino (not the author of the forecast) with
`python questions/q7_forecast_august/leakage_audit.py`, against `main` at `e25036e`.
Rerun it before the submission is sent; the script prints PASS or FAIL for every check.

## What the audit checks

The brief disqualifies a team for using any August 2026 data. The audit asks four
questions and answers each with code, not by reading the notebook:

1. **Does any processed table reach August 2026?** No. `county_month` and `site_month`
   both end at 2026-07; no site-month row is dated 2026-08 or later.
2. **Do the rolling-average columns recomputed in August 2026 reach the forecast?** No.
   The raw Organization file carries 11 `z12MoAverage_*` columns; none exists in
   `sites.parquet`, `site_month` or `county_month`, and the Q7 script never names them.
3. **Does the script or notebook read anything it should not?** The script reads
   `qkit.county_month`, `qkit.mmg` (for the Wilkin imputation only) and the organisers'
   submission template, which holds no data. No raw file, no external series.
4. **Could a backtest fold see its own future?** Tested empirically: for each of August
   2023, 2024 and 2025, the candidate predictions are recomputed from a panel cut off
   before that August and compared with the predictions from the full panel. All 3,132
   rows per fold are identical, so nothing after a target month enters its forecast.

Also checked: the training cutoff is 2026-07 and the target 2026-08; the RMSE values in
`q7_method_selection.csv` reproduce from the saved backtest predictions to one decimal;
the five scored outcomes all use the pooled May-July method and Individuals is the age
sum; the submission has 87 rows, no blank, negative or fractional value, and equals the
rounded forecast table; Wilkin is the only imputed county and is labelled as such.

## Result

17 of 19 checks pass. The two that do not are not leakage:

| check | status | what to do |
|---|---|---|
| `YourTeamID` filled in | FAIL | fill it in before submitting. The script will pass once it is. |
| county names match Map the Meal Gap | FAIL on one name | the organisers' template spells it "Lake Of The Woods"; our data says "Lake of the Woods". Keep the template's spelling in the submission. Not an error. |

## Signed

Audited by: Valentino, 10 October 2026. The forecast was built by a teammate.
