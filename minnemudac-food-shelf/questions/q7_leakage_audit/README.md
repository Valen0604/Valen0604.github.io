# Q7: independent leakage audit of the August forecast

The team's Question 7 deliverable was a county-level forecast of August 2026 activity,
built by a teammate. The organisers disqualify any entry that uses August 2026 data, so
before submission I audited the forecast as someone who had not written it. The forecast
itself is the teammate's work and is not in this folder.

## What is here

- `leakage_audit.py`: 19 scripted checks. Each prints PASS or FAIL, so the audit can be
  rerun after any change instead of being re-read.
- `LEAKAGE_AUDIT.md`: the signed write-up of the run on 10 October 2026.

## What the audit asks

1. Does any processed table reach August 2026?
2. Do the rolling-average columns the sponsor recomputed in August reach the forecast?
3. Does the forecast script or notebook read anything it should not?
4. Could a backtest fold see its own future? Tested empirically: predictions for each
   backtest August are recomputed from a panel cut off before that month and compared
   row by row with the predictions from the full panel.

It also reproduces the reported backtest scores from the saved predictions and checks the
submission file against the forecast table (87 rows, no blank, negative or fractional
value).

## Result

17 of 19 checks passed. The two failures were a team ID left blank and one county-name
spelling that differs from the organisers' template. Neither is leakage.

## Benchmarking the baseline

Alongside the audit I benchmarked alternative baselines against the method the forecast
used at the time (a pooled August-over-July ratio). Estimating the base from a pooled
May-to-July quarter lowered county-level backtest error on every scored outcome, and the
forecast owner adopted it for the submission. Mean sMAPE over three backtest Augusts
(2023 to 2025):

| outcome | pooled August/July ratio | pooled May-July base |
|---|---|---|
| households | 16.2% | 12.5% |
| individuals | 16.6% | 12.8% |
| adults | 18.4% | 12.9% |
| children | 20.9% | 17.5% |
| pounds | 19.3% | 14.9% |

An exploratory 50/50 blend of the ratio method with an ARIMA(1,1,0) scored better than
either component in the same backtests. It was scratch work, was not shipped, and its
script is not in this folder.

The audit script will not run from here: it expects the sponsor's data and the team's
forecast files. It is included to show how the checks were made.
