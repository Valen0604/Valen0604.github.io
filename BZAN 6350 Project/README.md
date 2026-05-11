# Athletic Spending and Academic Outcomes at NCAA Institutions

A cross-sectional empirical analysis of whether athletic spending share correlates with 6-year graduation rates across NCAA Division I and II public institutions in the 2023 academic year.

📄 [Full writeup (Markdown)](./Athletic_Spending_Outcomes.md)
📊 [Presentation deck (PPTX)](./Athletic_Spending_Outcomes.pptx)

---

## Research Question

Does the share of institutional spending allocated to athletics correlate with academic outcomes (6-year graduation rates), and does this relationship vary across NCAA divisions?

## TL;DR

Across 445 public NCAA Division I and II institutions, athletic spending share is negatively associated with 6-year graduation rates. The relationship is robust within all four NCAA division groups (FBS, FCS, D-I no football, D-II), with a slope of approximately −1.1 percentage points of graduation rate per percentage point of spending share. An F-test fails to reject the hypothesis of uniform slopes across divisions, despite large baseline differences in graduation rates.

Findings are **descriptive, not causal**. The most plausible alternative explanation is that institutions with weaker academic profiles both rely more heavily on athletics and produce lower graduation rates for reasons unrelated to athletic budget decisions.

---

## Data Sources

Three federal datasets, merged on UNITID:

| Source | Role | Variable | Records |
|---|---|---|---|
| **EADA** (Equity in Athletics Disclosure Act) | Athletic spending (numerator) | `Grand Total Expenses` | 1,319 schools |
| **IPEDS Finance F1A** (public, GASB) | Total expenses (denominator) | `F1C191` | 1,916 schools |
| **IPEDS Graduation Rates** (GR2023) | Outcome | `GRTYPE 8 & 9` | 51,391 records |

Final analytical sample after inner joins and NCAA filtering: **445 institutions**.

**Limitation:** F1A covers public institutions only (GASB accounting). Private nonprofits report on F2 (FASB) with different reporting conventions. The public-only restriction excludes most D-III institutions but provides a coherent comparison sample including nearly every major D-I athletic program.

---

## Methods

Five regression specifications, in increasing complexity:

1. **Pooled OLS** — naive baseline, no controls
2. **Within-division regressions** — separate slopes per NCAA group
3. **Additive model** — pooled regression with division fixed effects
4. **Interaction model** — slopes allowed to vary by division
5. **One-way ANOVAs** — confirming divisions differ on both predictor and outcome

Diagnostic checks confirm standard linear regression assumptions are reasonably satisfied (homoscedasticity, normality, no influential outliers).

---

## Key Results

| Model | β (spendRate) | p-value | Adj R² |
|---|---|---|---|
| Pooled (no controls) | −0.60 | < 0.001 | 2.4% |
| Additive (+ division FE) | **−1.12** | < 0.001 | **29.8%** |
| Interaction | −1.07 (FBS baseline) | < 0.001 | 30.6% |

The interaction F-test yields F = 1.56, p = 0.199 — fail to reject uniform slopes across divisions.

The pooled-vs-additive comparison is the key methodological finding: controlling for division *strengthens* rather than weakens the relationship, with the slope nearly doubling and explanatory power increasing by an order of magnitude.

---

## Repository Structure

```
.
├── code/
│   └── Project.Rmd                 # R Markdown analysis pipeline (all code lives here)
├── data/
│   ├── raw/                        # Source files as downloaded
│   │   ├── Expenses_All_Sports_..._2023.csv   # EADA
│   │   ├── f2223_f1a_rv.csv                   # IPEDS Finance
│   │   └── gr2023_RV.csv                      # IPEDS Graduation Rates
│   └── clean/
│       └── univData.csv            # Merged analytical dataset
├── output/
│   ├── plots/                      # Generated figures (pre-rendered)
│   │   ├── 01_scatter_main.png
│   │   ├── 02_boxplot_spending.png
│   │   ├── 03_boxplot_gradrate.png
│   │   ├── 04_coefficient_plot.png
│   │   ├── 05_pooled_vs_additive.png
│   │   └── 06_diagnostic_plots.png
│   └── tables/                     # Regression results (CSV)
│       ├── 01_summary_stats_by_division.csv
│       ├── 02_within_division_regressions.csv
│       ├── 03_model_comparison.csv
│       ├── 04_ftest_additive_vs_interaction.csv
│       ├── 05a_anova_gradrate_by_division.csv
│       ├── 05b_anova_spendrate_by_division.csv
│       └── 06_hypothesis_tests_summary.csv
├── Athletic_Spending_Outcomes.md   # Full writeup
├── Athletic_Spending_Outcomes.pptx # Presentation deck
└── README.md                       # This file
```

All code is contained in `code/Project.Rmd`. Plots and tables in `output/` are rendered by knitting the Rmd; the versions included here are reference snapshots.

---

## Reproducing the Analysis

### Prerequisites

R 4.0+ with the following packages:

```r
install.packages(c("dplyr", "tidyr", "ggplot2", "broom", "scales"))
```

### Steps

1. Clone the repository.
2. Open `code/Project.Rmd` in RStudio.
3. Knit the document. The pipeline reads from `../data/raw/` and produces all summary statistics, regression tables, and plots.

The raw data files are included in the repository. If you want to refresh from source:

- EADA 2023: https://ope.ed.gov/athletics/
- IPEDS Finance F1A 2022–23: https://nces.ed.gov/ipeds/datacenter/data/F2223_F1A.zip
- IPEDS GR 2023: https://nces.ed.gov/ipeds/datacenter/data/GR2023.zip

---

## What I'd Do Differently

Three extensions worth pursuing if this work were continued:

1. **Multi-year panel.** Pulling 10+ years of EADA and IPEDS data would allow institution-level fixed effects, controlling for time-invariant institutional characteristics and identifying the relationship from within-school variation rather than between-school differences.

2. **Event studies on exogenous shocks.** FCS-to-FBS reclassifications and conference realignments produce discrete shifts in athletic spending that approximate exogenous variation, suitable for difference-in-differences designs.

3. **Robustness with institution size controls.** Adding `log(totalExp)` as a covariate substantially changes the spending-share coefficient, suggesting that institution size is a meaningful confounder in the baseline analysis. Future work should examine whether the spending-share relationship survives this control.

---

## References

Anderson, M. L. (2017). The benefits of college athletic success: An application of the propensity score design. *Review of Economics and Statistics*, 99(1), 119–134.

Pope, D. G., & Pope, J. C. (2009). The impact of college sports success on the quantity and quality of student applications. *Southern Economic Journal*, 75(3), 750–780.

Hoffer, A., Humphreys, B. R., Lacombe, D. J., & Ruseski, J. E. (2015). Trends in NCAA athletic spending: Arms race or rising tide? *Journal of Sports Economics*, 16(6), 576–596.

Full reference list with data source citations in [Athletic_Spending_Outcomes.md](./Athletic_Spending_Outcomes.md).

---

## Author

Valentino Salerni · University of Houston · Finance & MIS · April 2026
