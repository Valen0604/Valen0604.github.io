# Valentino Salerni — Portfolio

A collection of academic projects spanning finance, statistics, and information systems coursework. Each project lives in its own subdirectory with its own documentation.

---

## About

I'm an MS in Business Analytics and Artificial Intelligence student at the University of Minnesota. My undergraduate coursework was in SCM & MIS at the University of Houston. This repository serves as a portfolio of projects that demonstrate the methods and tools I work with.

---

## Projects

### Athletic Spending and Academic Outcomes at NCAA Institutions

📂 [atheltic-spending-outcomes](./athletic-spending-outcomes)

A cross-sectional analysis examining whether the share of institutional spending allocated to athletics correlates with 6-year graduation rates across NCAA Division I and II public institutions in the 2023 academic year. Built in R, drawing on three federal data sources (EADA, IPEDS Finance F1A, IPEDS Graduation Rates) merged on a common institutional identifier.

**Methods:** Linear regression, multi-source data harmonization, fixed-effects modeling, ANOVA, regression diagnostics, ggplot2 visualization.

**Headline finding:** Within NCAA division groups, schools allocating a higher share of total expenses to athletics have lower graduation rates. The within-division slope of approximately −1.1 percentage points of graduation rate per percentage point of spending share is consistent across divisions. An F-test fails to reject the hypothesis of uniform slopes across divisions, despite large baseline differences in graduation rates.

**Deliverables:** R Markdown analysis pipeline, PowerPoint presentation, and a full written report.

---

### Seer Medical Web Form (MIS 3371)

🌐 [Live page](https://valen0604.github.io/medical-web-form/extraCredit/)

A multi-page medical-services website with HTML form built incrementally across four homework assignments for MIS 3371. The repository contains all four versions; the link above points to the final (extra credit) version with cookie consent functionality. Demonstrates HTML5, CSS, form validation, and basic client-side scripting. Hosted via GitHub Pages.

**Methods:** HTML, CSS, form design, GitHub Pages deployment.

---

## Repository Structure

```
.
├── athletic-spending-outcomes/    # NCAA spending analysis (R)
│   ├── code/                      # R Markdown source
│   ├── data/                      # Source data files
│   ├── output/                    # Plots, tables, deck
│   └── README.md                  # Project-specific documentation
├── medical-web-form/             # Seer Medical web form
    ├── extraCredit/               # Final Version of the website with all features
    ├── homework2/                 # V1 of the website
    ├── homework3/                 # V2
    ├── homework4/                 # V3
└── README.md                      # This file
```

Each project folder contains its own README with setup instructions, data sources, and reproduction steps.

---

## Tools and Languages

R · Python · SQL · HTML/CSS · Git · ggplot2

---

## Contact

University of Minnesota | Business Analytics
GitHub: [@Valen0604](https://github.com/Valen0604)
