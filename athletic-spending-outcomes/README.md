# Athletic Spending and Academic Outcomes at NCAA Public Institutions
 
Does the share of institutional spending allocated to athletics predict 6-year graduation rates once student composition and total resources are accounted for? Cross-sectional analysis of 445 NCAA public institutions (Divisions I–III, 2022–23), built from five federal datasets.
 
📄 [Full writeup](./Athletic_Spending_Outcomes.md)
🐍 [Python notebook](./Python_Extension/main.ipynb)
 
---
 
## TL;DR
 
**Athletic spending share has no detectable association with graduation rate once total per-student resources are in the model.**
 
The estimate is null without controls, then changes sign three times as controls are added. With student composition controlled but per-student spending left out, it looks negative and significant (−0.35, p = 0.002). That is the estimate that looks like a finding, and it is a denominator artifact: the spending share is athletic spending ÷ total spending, so at a fixed enrollment a high share proxies a small budget. Put per-student spending in the model and the coefficient is +0.11 (p = 0.32, 95% CI −0.11 to +0.33) — about half a graduation point per 5 points of share, with the interval spanning ±1 point.
 
Three checks that make no linearity assumption agree. A tuned gradient-boosting model assigns athletic share no predictive value; drop-column ablation shows the model predicts slightly *better* without it; and its partial dependence is flat.
 
Graduation rates are driven by who a school enrolls and what it has per student: Pell share (largest effect), admission selectivity, test scores, enrollment size, and per-student spending explain about 85% of the cohort-weighted variance. Division differences are almost entirely composition. FBS and FCS institutions spend near-identical shares on athletics (7.2% vs 7.7%) and differ by 14 graduation points, tracking a 120-point gap in median test score, a threefold gap in size, and a 50% gap in spending per student.
 
Findings are **descriptive, not causal**. There is no evidence of an association in either direction.
 
---
 
## Data
 
Five federal datasets merged on `UNITID`, with NCAA classification from EADA:
 
| Source | Role | Key variables |
|---|---|---|
| **EADA** 2023 | Athletic spending (numerator), NCAA division | `Grand Total Expenses`, `Classification Name` |
| **IPEDS Finance F1A** 2022–23 | Total, instructional, administrative, hospital, independent-ops expenses | `F1C191`, `F1C011`, `F1C071`, `F1C121`, `F1C131` |
| **IPEDS Graduation Rates** 2023 | Outcome: 6-year completion, cohort size | `GRTYPE 8, 9` |
| **IPEDS Admissions** 2023 | Admission rate, SAT/ACT midpoints | `APPLCN`, `ADMSSN`, `SATVR50`, `SATMT50`, `ACTCM50` |
| **IPEDS Student Financial Aid** 2022–23 | Undergraduate enrollment, Pell share | `SCUGRAD`, `UPGRNTP` |
 
Final sample after inner joins and NCAA filtering: **445 institutions** (108 FBS, 75 FCS, 46 D-I no football, 143 D-II, 73 D-III).
 
**Construction notes**
- Hospital services and independent operations are subtracted from total expenses so institutions with medical centers or federal labs are not inflated.
- ACT composite midpoints are concorded to the SAT scale and combined with SAT midpoints, weighted by number of submitters, into a single `testScore`.
- Missing admission rates and test scores are median-imputed with indicator flags; non-reporting is informative (open-enrollment and test-optional institutions).
- Per-student spending is total expenses (net of hospital and independent ops) ÷ undergraduate headcount.
**Limitation.** F1A covers public institutions only (GASB). Private nonprofits report on F2 (FASB) and are excluded. The sample includes nearly every major public D-I program but under-represents D-III, which is heavily private.
 
---
 
## Methods
 
**R pipeline (`Code/Project.Rmd`)** — data construction, EDA, and unweighted exploratory regressions: pooled OLS, within-division slopes, additive and interaction models with division dummies, F-test, one-way ANOVAs, diagnostics. Establishes the descriptive picture: inside every division, schools with a higher athletic share graduate fewer students.
 
**Python extension (`Python_Extension/`)** — the primary analysis:
 
1. **Feature engineering** (`dataProcess.py`) — admissions, test score, enrollment, Pell, and per-student spending joined to the R output.
2. **Weighted regression path** — the spending coefficient across five nested specifications (pooled → +division → +size → +student composition → +per-student resources), weighted by graduation cohort size with HC3 robust SEs. A rate estimated from 5,000 students is more precise than one from 80. Robustness: top-5% cohort trim.
3. **Model comparison** — linear, ridge, random forest, and tuned gradient boosting under 5×5 repeated CV on an 80% stratified training split. Fitting *and* scoring are cohort-weighted.
4. **Feature selection** — RFECV on the GBM with the one-SE rule, plus a full RFE ranking.
5. **Drop-column ablation** — each raw feature (and two feature groups) removed in turn; ΔRMSE computed as paired fold-by-fold differences to strip out fold-difficulty noise.
6. **Held-out evaluation** — linear and GBM scored once on the 20% test split.
7. **Partial dependence** — GBM and linear PDPs overlaid for every feature; hinge tests where they disagree.
---
 
## Key Results
 
**Spending-share coefficient path** (WLS, HC3, n = 445)
 
| Specification | β (spendRate) | p |
|---|---|---|
| Pooled | −0.20 | 0.37 |
| + division | −1.19 | < 0.001 |
| + log total expenses | +0.73 | < 0.001 |
| + Pell, test score, enrollment, admission rate (no resource control) | −0.35 | 0.002 |
| + log per-student spending, instructional & admin shares, test-score flag | **+0.11** | **0.32** |
 
Interaction F-test (slopes vary by division): F = 1.88 on 4 df, p = 0.11 — no evidence slopes differ. Trimming the top 5% of cohorts leaves the final estimate near zero and insignificant.
 
**Full model, other coefficients** (cohort-weighted, HC3)
 
| Effect | Estimate |
|---|---|
| Pell share 20% → 50% | ≈ −11 graduation points |
| Doubling per-student spending | ≈ +3.5 points |
| Doubling enrollment | ≈ +4 points |
| Admission rate (per 10 points) | ≈ −1.8 points |
| Test score (per 100 points) | ≈ +4 points |
| Test score not reported | ≈ +4 points (test-optional selective schools) |
| D-III vs FBS | ≈ +7 points; other divisions +2–3 and marginal |
| Instructional share, administrative share | not significant |
 
**Model comparison** (5×5 repeated CV, cohort-weighted)
 
| Model | RMSE | R² |
|---|---|---|
| Linear | 0.063 | 0.82 |
| Ridge | 0.063 | 0.82 |
| Tuned GBM | 0.065 | 0.81 |
| Random forest | 0.067 | 0.79 |
 
Held-out test (n = 89): linear RMSE 0.060 / R² 0.85; GBM 0.065 / 0.83. The linear model wins; the GBM is the cross-check.
 
**Drop-column ablation** (tuned GBM, ΔRMSE as % of baseline, paired-fold SE)
 
| Feature dropped | % of baseline RMSE | Mean/SE |
|---|---|---|
| Pell share | 12.0 | 5.5 |
| Admission rate + missing flag | 7.0 | 2.2 |
| log enrollment | 4.3 | 1.8 |
| All four spending measures (group) | 4.2 | 1.5 |
| Test score | 3.3 | 1.3 |
| Per-student spending | 3.1 | 1.3 |
| Division | 0.3 | 0.7 |
| **Athletic spending share alone** | **−0.9** | **−1.2** |
 
Pell share is the one feature the model cannot do without. Test score, enrollment, and per-student spending are individually weak because they substitute for each other. Division is nothing. The spending group's contribution comes from per-student spending; athletic share alone makes the model slightly worse.
 
**Partial dependence.** GBM and linear PDPs agree over the central 80% of the data for every feature except enrollment, where the GBM is flat below ~3,000 undergraduates and rising above. Hinge terms at 3,000 and 8,000 do not significantly improve the WLS fit (HC3 p = 0.06 and 0.09), so the linear form is retained. Athletic share is flat under both models.
 
**Composition by division** (medians)
 
| Division | n | Test score | Pell | Enrollment | Adm. rate | Spend / student | Athletic share | Grad rate |
|---|---|---|---|---|---|---|---|---|
| D-I FBS | 108 | 1199 | 0.26 | 22,674 | 0.77 | $49,213 | 0.072 | 0.672 |
| D-I FCS | 75 | 1080 | 0.33 | 8,215 | 0.86 | $32,650 | 0.077 | 0.531 |
| D-I no football | 46 | 1114 | 0.33 | 11,962 | 0.81 | $35,168 | 0.043 | 0.555 |
| D-II | 143 | 1075 | 0.37 | 5,265 | 0.87 | $25,448 | 0.057 | 0.473 |
| D-III | 73 | 1173 | 0.34 | 4,859 | 0.81 | $33,766 | 0.022 | 0.584 |
 
---
 
## Repository Structure
 
```
.
├── Code/
│   └── Project.Rmd                  # Data construction, EDA, exploratory regressions
├── Python_Extension/
│   ├── dataProcess.py               # Adds admissions, test score, enrollment, Pell, per-student spending
│   └── main.ipynb                   # Weighted regressions, ML benchmark, ablation, PDPs
├── Data/
│   ├── Raw/                         # EADA, IPEDS F1A, GR, ADM, SFA as downloaded
│   └── Clean/
│       ├── univData.csv             # R output: merged finance + graduation + division
│       └── features.csv             # Python output: full feature set
├── Output/
│   ├── Plots/                       # 01–06 from R, 07–12 from Python
│   └── Tables/                      # 01–06 from R, 07–12 from Python
├── Athletic_Spending_Outcomes.md    # Full writeup
└── README.md                        # This file
```
 
---
 
## Reproducing the Analysis
 
**Prerequisites**
 
R 4.0+:
```r
install.packages(c("dplyr", "tidyr", "ggplot2", "broom", "scales", "readr"))
```
 
Python 3.10+:
```
pip install pandas numpy "scikit-learn>=1.4" statsmodels matplotlib joblib
```
 
**Steps** — run in order; each stage reads the previous one's output:
 
1. Knit `Code/Project.Rmd`. Reads `Data/Raw/`, writes `Data/Clean/univData.csv` and `Output/` items 01–06.
2. Run `python Python_Extension/dataProcess.py`. Reads `univData.csv` plus the admissions and financial-aid files, writes `Data/Clean/features.csv`.
3. Open `Python_Extension/main.ipynb` and run all cells. The RFECV fit takes a few minutes. Writes `Output/` items 07–12.
Raw data files are included. To refresh from source:
 
- EADA 2023: https://ope.ed.gov/athletics/
- IPEDS Finance F1A 2022–23: https://nces.ed.gov/ipeds/datacenter/data/F2223_F1A.zip
- IPEDS Graduation Rates 2023: https://nces.ed.gov/ipeds/datacenter/data/GR2023.zip
- IPEDS Admissions 2023: https://nces.ed.gov/ipeds/datacenter/data/ADM2023.zip
- IPEDS Student Financial Aid 2022–23: https://nces.ed.gov/ipeds/datacenter/data/SFA2223.zip
---
 
## What I'd Do Differently
 
1. **Multi-year panel.** Ten-plus years of EADA and IPEDS would allow institution fixed effects, identifying the relationship from within-school changes rather than between-school differences.
2. **Event studies on exogenous shocks.** FCS-to-FBS reclassifications and conference realignments produce discrete shifts in athletic spending suitable for difference-in-differences designs.
3. **Private institutions.** Harmonizing F2 (FASB) finance data with F1A would roughly double the sample and bring in the D-III institutions that are currently under-represented.
4. **Align spending with the cohort.** The 2023 graduation rate describes students who entered around 2017; spending is measured in 2022–23. A spending measure averaged over the cohort's enrollment years would remove that timing mismatch.
---
 
## References
 
Anderson, M. L. (2017). The benefits of college athletic success: An application of the propensity score design. *Review of Economics and Statistics*, 99(1), 119–134.
 
Pope, D. G., & Pope, J. C. (2009). The impact of college sports success on the quantity and quality of student applications. *Southern Economic Journal*, 75(3), 750–780.
 
Hoffer, A., Humphreys, B. R., Lacombe, D. J., & Ruseski, J. E. (2015). Trends in NCAA athletic spending: Arms race or rising tide? *Journal of Sports Economics*, 16(6), 576–596.
 
Full reference list with data source citations in [Athletic_Spending_Outcomes.md](./Athletic_Spending_Outcomes.md).
 
---
 
## Author
 
Valentino Salerni · MS Business Analytics candidate, Carlson School of Management (University of Minnesota) · B.B.A., University of Houston
