# Valentino Salerni — Portfolio

A collection of academic projects spanning finance, statistics, and information systems coursework. Each project lives in its own subdirectory with its own documentation.

---

## About

I'm an MS in Business Analytics student at the University of Minnesota. My undergraduate coursework was in SCM & MIS at the University of Houston. This repository serves as a portfolio of projects that demonstrate the methods and tools I work with.

---

## Projects

### Athletic Spending and Academic Outcomes at NCAA Public Institutions

📂 [athletic-spending-outcomes](./athletic-spending-outcomes)

Does the share of institutional expenses going to athletics predict 6-year graduation rates once student composition and total resources are accounted for? Cross-sectional analysis of 445 NCAA public institutions (Divisions I–III, 2022–23) built from five federal files (EADA athletic expenses; IPEDS Finance, Admissions, Financial Aid, Graduation Rates). Hospital and independent-operations expenses are removed from totals; SAT/ACT medians are concorded to one scale, with missing-value flags for test scores and admission rates. An R pass built the dataset and ran unweighted exploratory regressions; the Python extension is the primary analysis.

**Methods:** Cohort-weighted least squares with HC3 robust SEs and stepwise controls; OLS, ridge, tuned gradient boosting and random forest compared under 5×5 repeated CV with a held-out 20% test split; RFECV (one-SE rule); drop-column ablation with paired-fold SEs; partial dependence plots; hinge tests for nonlinearity in enrollment.

**Headline finding:** Athletic spending share has no detectable association with graduation rate once total per-student resources are in the model. The coefficient changes sign three times as controls are added — pooled −0.20 (p = 0.37), + division −1.19 (p < 0.001), + size +0.73 (p < 0.001), + student composition −0.35 (p = 0.002), + per-student spending +0.11 (p = 0.32, CI −0.11 to +0.33). The −0.35 is a denominator artifact: spendRate is athletic ÷ total spending, so without per-student spending in the model a high share proxies a small budget. Graduation rates are driven by Pell share (largest effect), selectivity, test scores, enrollment and per-student spending; division differences are almost entirely composition — FBS and FCS spend near-identical shares on athletics and differ by 14 points in graduation rate. The tuned GBM assigns spending share no predictive value and its partial dependence is flat.

**Model performance:** Linear model best under CV (weighted RMSE 0.063, R² 0.82); tuned GBM 0.065 / 0.81; held-out test RMSE 0.060 / R² 0.85 (linear), 0.065 / 0.83 (GBM).

**Deliverables:** R Markdown (data construction, EDA, exploratory regressions), Python notebook (weighted models, ML benchmark, ablation, PDPs), 12 output tables and plots, written report.

---

### Macroeconomic Policy and Sector ETF Returns (PURS)

📂 [macro-sectors-etf](./macro-sectors-etf)

Tests whether macroeconomic policy variables explain U.S. sector ETF returns beyond the Fama-French three-factor model, using 11 SPDR sector ETFs from 1998–2025 at monthly and quarterly frequency. Funded by the University of Houston Provost Undergraduate Research Scholarship.

**Methods:** Time-series regression, Fama-French factor models, Newey-West standard errors, multi-frequency robustness checks, influence diagnostics.

**Headline finding:** Sector returns are dominated by market and value/growth loadings. Energy is the only sector with robust macro exposure, rising with inflation and federal spending growth; interest-rate and tariff effects are weak and unstable across frequencies.

**Deliverables:** R analysis script, results tables, coefficient plots.

---

### Seer Medical Web Form (MIS 3371)

🌐 [Live page](https://valen0604.github.io/medical-web-form/extraCredit/)

A multi-page medical-services website with HTML form built incrementally across four homework assignments for MIS 3371. The repository contains all four versions; the link above points to the final (extra credit) version with cookie consent functionality. Demonstrates HTML5, CSS, form validation, and basic client-side scripting. Hosted via GitHub Pages.

**Methods:** HTML, CSS, form design, GitHub Pages deployment.

---

## Repository Structure

```
.
├── athletic-spending-outcomes/    # NCAA spending analysis (R + Python)
│   ├── Code/                      # R Markdown source (data construction, EDA, initial regressions)
│   ├── Python_Extension/          # Feature engineering, weighted models, ML, ablation, PDPs
│   ├── Data/                      # Raw federal files and cleaned analytical datasets
│   ├── Output/                    # Plots and tables from both pipelines
│   └── README.md                  # Project-specific documentation
├── macro-sectors-etf/            # PURS macroeconomic policy effects on industry ETF returns (R)
│   ├── code/
│   ├── data/
│   ├── output/            
│   └── README.md  
├── medical-web-form/              # Seer Medical web form
│   ├── extraCredit/               # Final version of the website with all features
│   ├── homework2/                 # V1 of the website
│   ├── homework3/                 # V2
│   └── homework4/                 # V3
└── README.md                      # This file
```

Each project folder contains its own README with setup instructions, data sources, and reproduction steps.

---

## Tools and Languages

R · Python · SQL · HTML/CSS · Git · ggplot2 · scikit-learn · statsmodels · pandas

---

## Contact

University of Minnesota | Business Analytics
GitHub: [@Valen0604](https://github.com/Valen0604)