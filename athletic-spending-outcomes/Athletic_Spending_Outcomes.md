# Athletic Spending and Academic Outcomes at NCAA Institutions

**A cross-sectional analysis of the 2023 academic year**

Valentino Salerni
September 2026

---

## 1. Objectives

This project examines whether the share of institutional spending allocated to athletics correlates with academic outcomes — specifically, 6-year graduation rates — across U.S. universities, and whether this relationship varies across NCAA divisions.

The motivation is both topical and methodological. College athletics has come under increased public scrutiny following the post-2021 NIL era and ongoing conference realignment, both of which have intensified athletic spending pressures across all divisions. Beyond the policy relevance, the question itself is an instructive empirical exercise: a univariate relationship that appears straightforward at first glance turns out to depend heavily on how the sample is structured and which institutional characteristics are controlled for. The analysis below illustrates how a single statistical finding can carry very different interpretations depending on the comparison being made.

The scope of the project is cross-sectional and descriptive. All findings are correlational rather than causal, a distinction returned to throughout the analysis.

---

## 2. Data Collection and Understanding

The analysis draws on three federal data sources, merged at the institutional level using the standardized UNITID identifier maintained by the National Center for Education Statistics (NCES).

The first source is the Equity in Athletics Disclosure Act (EADA) database, maintained by the U.S. Department of Education's Office of Postsecondary Education. EADA requires all postsecondary institutions receiving Title IV federal aid and offering athletic programs to report detailed expense data by sport and gender. The variable of interest is `Grand Total Expenses`, representing total athletic department expenditure across all programs. The 2023 file contained 1,319 institutions with athletic programs.

The second source is the Integrated Postsecondary Education Data System (IPEDS) Finance Survey, specifically the F1A form (2022–23, revised), which covers public institutions reporting under Governmental Accounting Standards Board (GASB) standards. The relevant variable is `F1C191`, defined as "Total expenses and deductions — current year total." This serves as the denominator for computing athletic spending share.

The third source is the IPEDS Graduation Rates Survey (GR2023, revised), which tracks the 2017 entering cohort through six years. The file is structured in long format, with each row representing a school × cohort-type × line-item combination. Filtering to GRTYPE 8 (adjusted bachelor's cohort) and GRTYPE 9 (completers within 150% of normal time) yields the standard 6-year graduation rate calculation used across the higher education literature.

A material limitation arises from the choice of IPEDS F1A. Private nonprofit institutions report on a separate form (F2) under FASB accounting standards, with different variable names and reporting conventions that complicate harmonization. Restricting the analysis to F1A excludes virtually all NCAA Division III institutions (which are heavily private) and approximately 45% of EADA filers. The resulting sample of 445 institutions consists primarily of public NCAA Division I and Division II schools. While this constraint reduces the scope of the analysis, the public-only sample remains a coherent population and includes nearly every major D-I athletic program.

---

## 3. Hypotheses

Two pairs of hypotheses guide the analysis.

The primary hypothesis tests whether athletic spending share has any linear relationship with graduation rate. Under the null, the slope coefficient on spending share in a regression of graduation rate on spending share is zero. Under the alternative, the slope differs from zero in either direction.

The secondary hypothesis tests whether this relationship is uniform across NCAA divisions. Under the null, the slope is the same across all four NCAA division groups (D-I FBS, D-I FCS, D-I no football, D-II). Under the alternative, slopes differ across divisions. This is tested through an F-test comparing nested regression models with and without spending share × division interaction terms.

All tests use a significance level of α = 0.05.

---

## 4. Data Cleaning and Preparation

The cleaning process produced a single analytical dataset of 445 institutions from approximately 1,319 raw EADA records. Several steps were required.

The EADA file required selection of three columns (`UNITID`, `Classification Name`, `Grand Total Expenses`) and renaming for clarity. The IPEDS Finance file required selection of `UNITID` and `F1C191` only. The IPEDS Graduation Rates file required substantially more processing: filtering to bachelor's-seeking cohort rows (GRTYPE 8 and 9), then pivoting from long to wide format using `pivot_wider`, producing one row per school with both adjusted cohort size and completer count as columns.

The three cleaned tables were merged via inner joins on UNITID. The largest attrition occurred at the finance merge, where the F1A-only restriction eliminated all private nonprofit and for-profit institutions. A small further reduction occurred at the graduation rates merge, primarily affecting institutions without bachelor's-seeking cohorts (a few specialized public institutions).

The merged dataset was then filtered to NCAA-classified institutions only, excluding NAIA, NCCAA, NWAC, USCAA, and unclassified independents. These non-NCAA categories represent small, structurally different competitive systems whose inclusion would have introduced noise without contributing to the research question. The "with football" and "without football" subdivisions within D-II were collapsed, since the football/no-football distinction adds complexity without analytical payoff for the questions at hand.

Two computed variables anchor the analysis: `spendRate`, defined as athletic expenses divided by total institutional expenses, and `gradRate`, defined as bachelor's completers within 150% of normal time divided by the adjusted bachelor's cohort.

Outliers were examined and retained. Several D-II institutions report athletic spending shares above 15%, with one near 21%. These reflect schools where athletics represents a disproportionate fraction of a relatively small total budget. They are substantively meaningful (not data errors) and were retained in the analysis with a note that future work might examine them as a separate group.

The final sample contains 108 D-I FBS, 75 D-I FCS, 46 D-I no football, and 216 D-II institutions.

---

## 5. Exploratory Data Analysis

Three exploratory views establish baseline patterns in the data.

**Distribution of athletic spending share by division.** Athletic spending share varies meaningfully across divisions. D-I FCS schools have the highest median share (7.7%), followed closely by D-I FBS (6.7%). D-II schools have the lowest median spending share (3.9%) but the widest right tail, with several institutions above 15%. D-I no football schools sit between these extremes, with a median of 4.4% and tighter distribution. These differences are formally significant under a one-way ANOVA (F = 17.0, p < 0.001).

**Distribution of graduation rates by division.** Graduation rates vary even more dramatically. D-I FBS schools have a median 6-year graduation rate of 67.6% — roughly 17 percentage points higher than the D-II median of 50.4%. D-I FCS (53.4%) and D-I no football (55.5%) fall between these poles. The one-way ANOVA confirms these differences are highly significant (F = 42.3, p < 0.001).

**The joint relationship.** The headline scatterplot of spending share against graduation rate, colored by division, reveals that within each division group, schools with higher athletic spending shares tend to have lower graduation rates. The negative slope is visible across all four divisions. However, the level differences between divisions are substantial: an FBS school spending 10% of its budget on athletics still typically graduates more students than a D-II school spending 3%.

Within-division Pearson correlations between spending share and graduation rate are: D-I FBS −0.32, D-I FCS −0.22, D-I no football −0.47, and D-II −0.32. All are negative; the strongest correlation is among D-I no football schools, the weakest among D-I FCS.

---

## 6. Modeling and Analysis

Five regression specifications are estimated, each addressing a different aspect of the research question.

**Specification 1: Pooled OLS.** Regressing graduation rate on spending share without any controls produces a slope of −0.60 (SE = 0.18, p < 0.001) with R² = 2.4%. The negative relationship is statistically significant but explains very little variation in the outcome.

**Specification 2: Within-division regressions.** Running the same regression separately for each NCAA division group yields slopes of −1.07 (FBS, p = 0.0008), −0.99 (FCS, p = 0.061), −2.55 (D-I no football, p = 0.001), and −1.03 (D-II, p < 0.001). All four are negative; three are statistically significant at conventional levels, with D-I FCS marginally above the 5% threshold.

**Specification 3: Additive model (division fixed effects).** Adding division as a categorical control in a single pooled regression produces a slope of −1.12 (SE = 0.16, p < 0.001) with R² = 29.8%. This is a striking result. Compared with the pooled specification, the slope nearly doubles in magnitude and the model's explanatory power increases by an order of magnitude. The interpretation is that division effects were attenuating, not creating, the spending–graduation rate relationship in the pooled model.

**Specification 4: Interaction model.** Allowing the slope to vary across divisions (rather than just the intercept) yields an R² of 30.6%. An F-test comparing this model to the additive model produces F = 1.56 with p = 0.199. The null hypothesis of equal slopes across divisions cannot be rejected. The simpler additive model is preferred.

**Specification 5: One-way ANOVAs.** Confirming the descriptive observation that divisions differ on both variables: graduation rates differ across divisions (F = 42.3, p < 0.001), and spending shares differ across divisions (F = 17.0, p < 0.001).

Diagnostic checks on the additive model show that standard linear regression assumptions are reasonably satisfied. Residuals show constant variance across fitted values, are approximately normally distributed based on quantile-quantile plots, and no individual observations exceed Cook's distance thresholds for influential outliers.

The combined result of these specifications is that athletic spending share is negatively associated with graduation rate within all NCAA division groups, with a magnitude that does not differ statistically across divisions. What differs across divisions is the baseline graduation rate, not the slope.

---

## 7. Visualization and Reporting

Five visualizations support the analysis. The first two are boxplots showing the distribution of spending share and graduation rate respectively, by division, establishing that divisions differ on both axes. The third is a scatterplot of spending share against graduation rate colored by division, with separate regression lines for each division. This is the primary visualization and tells most of the story at a glance. The fourth juxtaposes the pooled regression against the by-division regression, making visually concrete why controlling for division strengthens rather than weakens the relationship. The fifth is a coefficient plot showing the four within-division slopes with their 95% confidence intervals, with a reference line at zero — the visual analog of the regression results table.

The University of Houston, the author's home institution, is highlighted on the headline scatterplot. It sits at approximately 8% spending share and 65% graduation rate, near the FBS regression line and consistent with the FBS-conditional mean. Its position is illustrative rather than anomalous.

---

## 8. Insights and Recommendations

Four observations follow from the analysis.

The first is the headline finding itself. Within NCAA division groups, schools that allocate a higher share of their budget to athletics tend to graduate a lower share of their students. The relationship is statistically significant, consistent in magnitude across divisions, and survives the addition of division fixed effects. A one percentage point increase in athletic spending share is associated with roughly a one percentage point decrease in 6-year graduation rate.

The second observation is the critical caveat: these estimates are descriptive, not causal. The most plausible alternative explanation is not that athletic spending causes lower graduation rates, but that institutions with weaker academic profiles — for reasons of student SES, first-generation enrollment share, urban commuter populations, or institutional resources per student — both rely more heavily on athletic spending (as an enrollment and branding lever) and produce lower graduation rates (for reasons unrelated to the athletic budget itself). Under this interpretation, spending share is a symptom rather than a cause. Untangling these channels would require panel data exploiting within-school variation, or natural experiments such as conference reclassifications or unexpected athletic success.

The third observation concerns implications for institutional decision-making. The findings do not justify a strong recommendation that universities reduce athletic spending. They do, however, caution against the assumption that athletic spending is academically neutral. The descriptive correlation suggests that institutions considering substantial increases in athletic spending share should examine the channels through which that spending affects, or fails to affect, academic outcomes — rather than assuming that athletic revenue or branding effects will be neutral or positive for graduation rates.

The fourth observation is methodological. The pooled regression and the division-controlled regression produced markedly different slope estimates (−0.60 vs. −1.12) and R² values (2.4% vs. 29.8%). This is not Simpson's paradox in the strict sense — both slopes have the same sign — but it illustrates how a single regression coefficient can substantially understate or overstate the underlying relationship depending on the comparison group. Within-group analysis with appropriate fixed effects is essential when working with heterogeneous populations.

A natural extension of this work would assemble a multi-year panel of EADA and IPEDS data, allowing for institution-level fixed effects that eliminate time-invariant confounders. A further extension would exploit specific exogenous events — FCS-to-FBS reclassifications, conference realignments, or stadium construction shocks — using difference-in-differences designs to approach causal identification. Both are beyond the scope of this project but represent the appropriate next steps for the question.

---

## 9. References

**Data Sources**

U.S. Department of Education. (2024). *Equity in Athletics Disclosure Act (EADA) Database, 2023*. Office of Postsecondary Education. https://ope.ed.gov/athletics/

National Center for Education Statistics. (2024). *Integrated Postsecondary Education Data System (IPEDS) Finance Survey, F1A 2022–23 (Final/revised)*. U.S. Department of Education. https://nces.ed.gov/ipeds/

National Center for Education Statistics. (2024). *IPEDS Graduation Rates Survey (GR2023, Final/revised)*. U.S. Department of Education. https://nces.ed.gov/ipeds/

**Academic Literature**

Anderson, M. L. (2017). The benefits of college athletic success: An application of the propensity score design. *Review of Economics and Statistics*, 99(1), 119–134.

Pope, D. G., & Pope, J. C. (2009). The impact of college sports success on the quantity and quality of student applications. *Southern Economic Journal*, 75(3), 750–780.

Hoffer, A., Humphreys, B. R., Lacombe, D. J., & Ruseski, J. E. (2015). Trends in NCAA athletic spending: Arms race or rising tide? *Journal of Sports Economics*, 16(6), 576–596.

Knight Commission on Intercollegiate Athletics. (2024). *College Athletic Financial Information (CAFI) Database*. https://cafidatabase.knightcommission.org/

**Code References**

Anthropic. (2026). *Claude (Opus 4.7) [Large language model]*. Used for code structure, debugging, and analytical guidance throughout the project. https://claude.ai

R Core Team. (2024). *R: A Language and Environment for Statistical Computing*. R Foundation for Statistical Computing. https://www.R-project.org

R Documentation, *Linear Models*. https://stat.ethz.ch/R-manual/R-devel/library/stats/html/lm.html

Wickham, H. (2017). *R for Data Science*. O'Reilly Media. https://r4ds.hadley.nz

STHDA. *ggplot2 scatter plot with regression line*. http://www.sthda.com/english/wiki/ggplot2-scatter-plots-quick-start-guide-r-software-and-data-visualization

Bobbitt, Z. *How to perform multiple linear regression in R*. Statology. https://www.statology.org/multiple-linear-regression-r/

Wong, K. *Tidy Regression Output with broom*. RPubs. https://rpubs.com/aaronsc32/regression-with-broom
