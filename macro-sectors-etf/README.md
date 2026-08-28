# Macroeconomic Policy and Sector ETF Returns
 
Provost Undergraduate Research Scholarship (PURS), University of Houston, Fall 2025.
Revised August 2026.
 
## Question
 
Do macroeconomic policy variables (interest rates, inflation, federal spending, tariffs, trade balance) explain U.S. sector ETF returns beyond what standard equity risk factors already capture?
 
## Data
 
| Series | Source | Frequency |
|---|---|---|
| 11 SPDR sector ETFs (XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY), adjusted close | Yahoo Finance | Monthly, Dec 1998 – Sep 2025 (XLC from Jun 2018, XLRE from Oct 2015) |
| Fama-French three factors and risk-free rate | Kenneth French Data Library | Monthly |
| Effective federal funds rate (DFF) | FRED | Daily |
| CPI (CPIAUCSL) and inflation rate | FRED / BLS | Monthly |
| Federal government expenditures (FGEXPND) | FRED | Quarterly |
| Customs duties receipts | FRED | Quarterly |
| Trade balance, goods and services (BOPGSTB) | FRED | Monthly |
| Average effective tariff rate | USITC | Annual |
| VIX (open) | CBOE via Yahoo Finance | Monthly |
 
All data are in `PURS Data.xlsx`, one sheet per series.
 
## Method
 
For each ETF, the excess real log return is regressed on the Fama-French factors plus changes in the macro variables:
 
    r_t − RF_t = α + β·Mkt_RF + s·SMB + h·HML
              + γ₁ ΔFedFunds + γ₂ ΔInflation + γ₃ Δlog(Spending) + γ₄ Δlog(Receipts)
              + γ₅ Δlog(TradeBalance) + γ₆ ΔTariff + γ₇ ΔVIX + ε
 
Nominal series are deflated by CPI. Standard errors are Newey-West (lag 3 monthly, lag 1 quarterly).
 
The model is estimated at monthly frequency for all 11 ETFs, and at quarterly frequency for the 9 ETFs with a full history, because three regressors (spending, receipts, trade balance) are quarterly and would otherwise be zero-padded two months in three.
 
An influence check (Cook's distance, re-estimation excluding 2020) is run on the Energy model, which is the only sector with material macro exposure.
 
## Findings
 
- **Sector returns are dominated by the market and value/growth factors.** Market betas range from ~0.5 (Staples, Utilities) to ~1.2 (Financials, Materials); HML loadings separate Energy and Financials (value) from Tech (growth). R² is 0.5–0.85 for most sectors, almost entirely from these three factors.
- **Energy is the only sector with robust macro exposure.** Its return rises with inflation (quarterly β ≈ 2.7–3.0, p < 0.002, robust to excluding 2020) and with federal spending growth (β ≈ 0.3–0.4, p ≈ 0.03 excluding 2020). A negative relationship with customs receipts is present but driven largely by the 2025 tariff shock and should not be read as a general effect.
- **Interest rates explain little at monthly frequency.** At quarterly frequency Materials and Industrials show negative rate sensitivity; the result does not appear monthly and is reported as suggestive only.
- **Tariff effects are unstable.** The annual tariff series changes once a year, so estimates depend heavily on a handful of observations. Health Care is the only sector with a consistent (positive) coefficient across frequencies; other sector results flip between monthly and quarterly.
## Limitations
 
- Mixed data frequencies: quarterly and annual regressors are forward-filled at monthly frequency. The quarterly specification addresses this for the quarterly series but not for the annual tariff rate.
- ~180 coefficient tests across the two frequency specifications; individual results at p ≈ 0.05 should be discounted accordingly.
- The federal funds rate on the first day of each month is used as the month's rate; a monthly average would be less noisy.
- XLC (86 months) and XLRE (119 months) have short histories and are excluded from the quarterly model.
## Revision history
 
The original Fall 2025 version contained two data-handling errors: the fed funds series was assigned synthetic dates rather than its actual dates, and ETF returns were computed from monthly open prices, which misaligned them with the month-end factor returns by one period. Both are corrected here. The original headline result (strong negative Energy sensitivity to real interest rates) does not survive the corrections; the inflation exposure reported above is the corrected finding.
 
## Running
 
    install.packages(c("tidyverse", "readxl", "sandwich", "lmtest", "broom"))
    source("PURS.R")
 
Requires `PURS Data.xlsx` in the working directory.
