# Athletic Spending and Academic Outcomes at NCAA Public Institutions
 
A cross-sectional analysis of whether the share of institutional expenses allocated to athletics is associated with 6-year graduation rates, and whether that association survives controls for student composition. 445 NCAA public institutions (Divisions I–III), 2022–23 academic year.
 
📄 [Full writeup (Markdown)](./Athletic_Spending_Outcomes.md)
🐍 [Python extension (notebook)](./Python_Extension/main.ipynb)
 
---
 
## Research Question
 
Does the share of institutional spending allocated to athletics predict 6-year graduation rates, and does the relationship hold once we account for who the institution enrolls?
 
## TL;DR
 
Athletic spending share has **no robust association** with graduation rates.
 
The estimate is null without controls. Adjusting for NCAA division alone makes it look strongly negative (−1.19); adjusting for institution size alone makes it look positive (+0.73). Two sign changes across specifications is the signature of confounding, not of an effect. With student composition controlled — Pell share, test scores, enrollment size, admission rate — the estimate settles at roughly −0.25: about 1.2 graduation points per 5-point increase in spending share, borderline at conventional significance, and sensitive to how observations are weighted.
 
A gradient-boosting model reaches the same conclusion from the other direction: removing every spending measure from the model costs nothing in held-out accuracy, while removing Pell share, test scores, or enrollment costs 6–12% of baseline RMSE.
 
Graduation rates are driven by who a school enrolls. Division differences (47% at D-II vs 67% at FBS) are almost entirely composition; after controls, all five division groups sit within 3 points of each other. FBS and FCS institutions spend nearly identical shares on athletics (7.2% vs 7.7%) and differ by 14 points in graduation rate.
 
Findings are **descriptive, not causal**. Under no specification is there evidence that athletic spending is associated with *higher* graduation rates.
 
---
 
## Data Sources
 
Five federal datasets, merged on UNITID, plus NCAA classification from EADA:
 
| Source | Role | Key variables |
|---|---|---|
| **EADA** 2023 | Athletic spending (numerator), NCAA division | `Grand Total Expenses`, `Classification Name` |
| **IPEDS Finance F1A** 2022–23 | Total, instructional, administrative, hospital, independent-ops expenses | `F1C191`, `F1C011`, `F1C071`, `F1C121`, `F1C131` |
| **IPEDS Graduation Rates** 2023 | Outcome: 6-year completion, cohort size | `GRTYPE 8, 9` |
| **IPEDS Admissions** 2023 | Admission rate, SAT/ACT midpoints | `APPLCN`, `ADMSSN`, `SATVR50`, `SATMT50`, `ACTCM50` |
| **IPEDS Student Financial Aid** 2022–23 | Undergraduate enrollment, Pell share | `SCUGRAD`, `UPGRNTP` |
 
Final analytical sample after inner joins and NCAA filtering: **445 institutions** (108 FBS, 75 FCS, 46 D-I no football, 143 D-II, 73 D-III).
 
**Data construction notes:**
- Hospital services and independent operations are subtracted from total expenses so institutions with medical centers or federal labs are not inflated.
- ACT composite midpoints are converted to the SAT scale and combined with SAT midpoints, weighted by the number of submitters, into a single `testScore`.
- Missing admission rates and test scores are median-imputed with indicator flags, since non-reporting is informative (open-enrollment institutions).
**Limitation:** F1A covers public institutions only (GASB accounting). Private nonprofits report on F2 (FASB) and are excluded. The sample includes nearly every major public D-I athletic program but under-represents D-III.
 
---
 
## Methods
 
**R pipeline (`Code/Project.Rmd`)** — data construction, EDA, and the exploratory regressions: pooled OLS, within-division slopes, additive and interaction models with division dummies, F-test, one-way ANOVAs, diagnostics. Unweighted; establishes the descriptive picture.
 
**Python extension (`Python_Extension/`)** — the primary analysis:
 
1. **Feature engineering** (`dataProcess.py`): admission, test score, enrollment, and Pell variables joined to the R output.
2. **Weighted regression path**: the spending coefficient across four specifications (pooled → +division → +size → +composition), weighted by graduation cohort size with HC3 robust standard errors. Weighting reflects that a rate estimated from 5,000 students is more precise than one from 80. Robustness: top-5% cohort trim.
3. **Model comparison**: linear, ridge, random forest, gradient boosting under 5×5 repeated CV on an 80% stratified training split.
4. **Feature selection**: RFECV with the one-standard-error rule; full RFE ranking.
5. **Drop-column ablation**: each raw feature (and two feature groups) removed in turn; change in CV RMSE computed as paired fold-by-fold differences to remove fold-difficulty noise.
6. **Final model**: GBM on six surviving features, evaluated once on the 20% test split.
7. **Partial dependence plots** for direction and shape.
---
 
## Key Results
 
**Spending-share coefficient path (WLS, HC3, n = 445)**
 
| Specification | β (spendRate) | p |
|---|---|---|
| Pooled | −0.20 | 0.37 |
| + division | −1.19 | < 0.001 |
| + log total expenses | +0.73 | < 0.001 |
| + student composition | −0.35 | 0.002 |
| + composition, top 5% cohorts trimmed | −0.23 | 0.07 |
 
Interaction F-test (slopes vary by division): F = 1.88, p = 0.11 — no evidence slopes differ.
 
**Gradient boosting** — test set (n = 89): RMSE 0.068, R² 0.82.
 
**Ablation** — increase in CV RMSE when dropped, as % of baseline:
 
| Feature | ΔRMSE | % | Mean/SE |
|---|---|---|---|
| Pell share | 0.0092 | 11.6 | 13.7 |
| Test score | 0.0055 | 7.0 | 5.2 |
| log enrollment | 0.0046 | 5.8 | 5.2 |
| Admission rate + missing flag (group) | 0.0022 | 2.8 | 2.4 |
| Division | 0.0015 | 1.9 | 3.9 |
| All four spending measures (group) | 0.0015 | 1.9 | 1.6 |
| Athletic spending share alone | 0.0002 | 0.2 | 0.4 |
 
**Composition by division** (medians):
 
| Division | n | Test score | Pell | Enrollment | Adm. rate | Spend share | Grad rate |
|---|---|---|---|---|---|---|---|
| D-I FBS | 108 | 1199 | 0.26 | 22,674 | 0.77 | 0.072 | 0.672 |
| D-I FCS | 75 | 1080 | 0.33 | 8,215 | 0.86 | 0.077 | 0.531 |
| D-I no football | 46 | 1114 | 0.33 | 11,962 | 0.81 | 0.043 | 0.555 |
| D-II | 143 | 1075 | 0.37 | 5,265 | 0.87 | 0.057 | 0.473 |
| D-III | 73 | 1173 | 0.34 | 4,859 | 0.81 | 0.022 | 0.584 |
 
---
 
## Repository Structure
 
```
.
├── Code/
│   └── Project.Rmd                  # Data construction, EDA, exploratory regressions
├── Python_Extension/
│   ├── dataProcess.py               # Adds admissions, test score, enrollment, Pell features
│   └── main.ipynb                   # Weighted regressions, ML, ablation, PDPs
├── Data/
│   ├── Raw/                         # EADA, IPEDS F1A, GR, ADM, SFA as downloaded
│   └── Clean/
│       ├── univData.csv             # R output: merged finance + graduation + division
│       └── features.csv             # Python output: full feature set
├── Output/
│   ├── Plots/                       # 01–06 from R, 07–11 from Python
│   └── Tables/                      # 01–06 from R, 07–12 from Python
├── Athletic_Spending_Outcomes.md    # Full writeup
├── Athletic_Spending_Outcomes.pptx  # Presentation deck
└── README.md                        # This file
```
 
---
 
## Reproducing the Analysis
 
### Prerequisites
 
R 4.0+:
```r
install.packages(c("dplyr", "tidyr", "ggplot2", "broom", "scales", "readr"))
```
 
Python 3.10+:
```
pip install pandas numpy scikit-learn>=1.4 statsmodels matplotlib joblib
```
 
### Steps
 
Run in this order — each stage reads the previous one's output:
 
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
4. **Weighted evaluation.** Models are fit with cohort-size weights but CV scoring is unweighted. Routing weights through the scorer would make the two consistent.
---
 
## References
 
Anderson, M. L. (2017). The benefits of college athletic success: An application of the propensity score design. *Review of Economics and Statistics*, 99(1), 119–134.
 
Pope, D. G., & Pope, J. C. (2009). The impact of college sports success on the quantity and quality of student applications. *Southern Economic Journal*, 75(3), 750–780.
 
Hoffer, A., Humphreys, B. R., Lacombe, D. J., & Ruseski, J. E. (2015). Trends in NCAA athletic spending: Arms race or rising tide? *Journal of Sports Economics*, 16(6), 576–596.
 
Full reference list with data source citations in [Athletic_Spending_Outcomes.md](./Athletic_Spending_Outcomes.md).
 
---
 
## Author
 
Valentino Salerni · MS Business Analytics candidate, Carlson School of Management (University of Minnesota) · B.B.A., University of Houston
