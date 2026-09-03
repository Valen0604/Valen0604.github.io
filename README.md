# Valentino Salerni — Portfolio

A collection of academic projects spanning finance, statistics, and information systems coursework. Each project lives in its own subdirectory with its own documentation.

---

## About

I'm an MS in Business Analytics and Artificial Intelligence student at the University of Minnesota. My undergraduate coursework was in SCM & MIS at the University of Houston. This repository serves as a portfolio of projects that demonstrate the methods and tools I work with.

---

## Projects

### Athletic Spending and Academic Outcomes at NCAA Public Institutions

📂 [athletic-spending-outcomes](./athletic-spending-outcomes)

Does the share of institutional expenses going to athletics predict 6-year graduation rates once student composition is accounted for? A cross-sectional analysis of 445 NCAA public institutions (Divisions I–III, 2022–23) built from five federal data files (EADA athletic expenses; IPEDS Finance, Admissions, Financial Aid, and Graduation Rates) merged on a common institutional identifier. Hospital and independent-operations expenses are removed from institutional totals. An initial R analysis established the descriptive picture; a Python extension added weighted regression, gradient boosting, feature ablation, and partial dependence analysis.

**Methods:** Multi-source data harmonization, weighted least squares with HC3 robust errors, gradient boosting with repeated cross-validation, recursive feature elimination, drop-column ablation with paired-fold uncertainty, partial dependence plots.

**Headline finding:** Athletic spending share has no robust association with graduation rates. The unadjusted estimate is null; adjusting for division alone makes it look strongly negative and adjusting for size alone makes it look positive — the signature of confounding. With student composition controlled (Pell share, test scores, enrollment, selectivity) the estimate is small and negative (≈ −0.25, borderline significance, sensitive to weighting), and a gradient-boosting model finds no predictive value in any spending measure. Graduation rates are driven by who a school enrolls; division differences are almost entirely composition. FBS and FCS schools spend nearly identical shares on athletics and differ by 14 points in graduation rate.

**Deliverables:** R Markdown pipeline (data construction, exploratory regressions), Python notebook (weighted models, ML, ablation, PDPs), written report, presentation deck.

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