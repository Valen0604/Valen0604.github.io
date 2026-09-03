# Athletic Spending and Graduation Rates at NCAA Public Institutions
 
**A cross-sectional analysis of the 2022-23 academic year**
 
Valentino Salerni
September 2026
 
---
 
## 1. Objectives
 
Question: does the share of a university's budget that goes to athletics predict its 6-year graduation rate, once we account for who the school enrolls and what it has to spend?
 
The motivation is partly topical. Athletic budgets have grown fast since the NIL era and conference realignment, and the standard worry is that money going to athletics is money not going to students. But the more interesting part is methodological. The raw relationship between athletic share and graduation rate looks negative, looks worse once you control for division, flips positive once you control for size, and disappears once you control for student composition and resources per student. Which of those you report depends entirely on what you compare a school against. The project is built to walk through that path one control at a time and end up with the estimate that survives all of them.
 
Everything here is cross-sectional and correlational. Nothing is causal.
 
---
 
## 2. Data
 
Five federal files, all merged on the NCES UNITID.
 
**EADA 2023** (Office of Postsecondary Education). Every Title IV school with an athletic program reports expenses by sport. The variable used is `Grand Total Expenses`, total athletic department spending. 1,319 institutions. The `Classification Name` field gives the NCAA division.
 
**IPEDS Finance, F1A 2022-23 (revised).** Public institutions reporting under GASB. `F1C191` is total expenses and deductions and is the denominator for spending share. `F1C011` (instruction) and `F1C071` (institutional support) give instructional and administrative shares. `F1C121` (hospital services) and `F1C131` (independent operations) are subtracted from the total so that schools with a medical center don't look like they spend three times as much per student as everyone else.
 
**IPEDS Graduation Rates, GR2023 (revised).** The 2017 entering cohort tracked six years. Rows for GRTYPE 8 (adjusted bachelor's cohort) and GRTYPE 9 (completers within 150% of normal time) give the standard 6-year rate. The cohort size is also kept as the regression weight.
 
**IPEDS Admissions, ADM2023 (revised).** Applicants and admits give the admission rate. SAT 50th-percentile verbal and math are summed; ACT composite 50th percentile is converted to the SAT scale using the College Board concordance; the two are averaged, weighted by the number of students submitting each. Schools with no test data or no admissions data (open admission, test-optional with no reporting) get a missing flag rather than being dropped.
 
**IPEDS Student Financial Aid, SFA2223 (revised).** `SCUGRAD` is the undergraduate headcount, used for enrollment size and for per-student spending. `UPGRNTP` is the percent of undergraduates receiving Pell grants, the composition variable that turns out to matter most.
 
The F1A restriction is the main limitation. Private nonprofits file F2 under FASB and the variable definitions don't line up, so the sample is public institutions only. That excludes roughly 45% of EADA filers and most of D-III, which is heavily private. What's left is 445 public schools: 108 D-I FBS, 75 D-I FCS, 46 D-I no football, 143 D-II, 73 D-III. It's a coherent population and it includes nearly every major D-I program.
 
---
 
## 3. Hypotheses
 
Three questions, tested at α = 0.05.
 
**H1.** Does athletic spending share have a linear relationship with graduation rate, holding division, size, student composition and per-student resources fixed? Null: the coefficient on `spendRate` is zero.
 
**H2.** Is that relationship the same across divisions? Null: the slope on `spendRate` is equal for all five division groups. Tested with an F-test on nested models with and without `spendRate × division` interactions.
 
**H3.** Is a linear model adequate? Not a hypothesis test but a model comparison: if flexible nonlinear learners can't beat a linear regression out of sample, the linear coefficients are the right summary of the data and not a simplification of something more complicated.
 
---
 
## 4. Data Cleaning and Preparation
 
The build runs in two stages. `Project.Rmd` produces the base dataset from EADA, Finance and Graduation Rates and does the unweighted exploratory analysis. `dataProcess.py` adds admissions and financial aid and writes `features.csv`, which `main.ipynb` uses for everything else.
 
EADA needs only UNITID, classification, institution name and total expenses. The Finance file needs the five expense lines listed above. Graduation Rates is in long format (one row per school × cohort type × line item) and is filtered to GRTYPE 8 and 9 and pivoted wide, one row per school with cohort size and completers as columns.
 
The three are inner-joined on UNITID. Almost all attrition is at the finance merge, where F1A drops every private and for-profit school. A handful more go at the graduation merge, specialized publics with no bachelor's cohort.
 
The merged file is filtered to `Classification Name` starting with "NCAA", dropping NAIA, NCCAA, NWAC, USCAA and unclassified independents. These are small, structurally different systems and add noise without adding to the question. D-II with and without football is collapsed to D-II; D-III with and without football to D-III. The five groups are D-I FBS, D-I FCS, D-I no football, D-II, D-III.
 
Computed variables:
 
`spendRate` = athletic expenses / total expenses (after removing hospital and independent operations)
`gradRate` = completers within 150% / adjusted bachelor's cohort
`instrShare`, `adminShare` = instruction and institutional support as shares of the same total
`expPerStudent` = total expenses / undergraduate headcount
`admRate` = admits / applicants
`testScore` = SAT-scale composite, SAT and concorded ACT averaged by submitter count
`upPell` = Pell recipients as a fraction of undergraduates (the IPEDS percent divided by 100)
`testScoreMissing`, `admRateMissing` = 1 where the source value is absent
 
Admissions and aid are left-joined so schools without them are kept. In the notebook, remaining NAs are filled with the column median and the missing flags carry the information that a value was imputed. The two flags end up meaningful in their own right: schools that don't report test scores graduate more than their other characteristics predict, schools with no admission rate graduate much less.
 
Outliers are kept. A few D-II schools have athletic shares above 15%, one near 21%. These are small budgets where athletics is a real fraction of the whole, not data errors.
 
---
 
## 5. Exploratory Data Analysis
 
Medians by division from the final sample:
 
| Division | n | Test score | Pell share | Undergrads | Adm. rate | Athletic share | Exp. per student | Grad rate |
|---|---|---|---|---|---|---|---|---|
| D-I FBS | 108 | 1199 | 26% | 22,674 | 77% | 7.2% | $49,213 | 67.2% |
| D-I FCS | 75 | 1080 | 33% | 8,215 | 86% | 7.7% | $32,650 | 53.1% |
| D-I no football | 46 | 1114 | 33% | 11,962 | 81% | 4.3% | $35,168 | 55.5% |
| D-II | 143 | 1075 | 37% | 5,265 | 87% | 5.7% | $25,448 | 47.3% |
| D-III | 73 | 1173 | 34% | 4,859 | 81% | 2.2% | $33,766 | 58.4% |
 
Three things stand out. Divisions differ enormously on graduation rate, 20 points between FBS and D-II. They differ just as much on everything that predicts graduation rate: FBS schools are three to four times larger, admit a smaller share of applicants, have 120 points higher test scores, a lower Pell share and about twice the spending per student. And athletic share does not line up with graduation rate across divisions at all. FBS and FCS spend almost the same share (7.2% vs 7.7%) and are 14 graduation points apart; D-III spends the least share of anyone and graduates more than D-II, FCS or no-football.
 
The unweighted R pass (`Output/Plots/01` to `05`, `Output/Tables/01` to `06`) shows the within-division picture: inside each division, schools with a higher athletic share graduate fewer students, and the slope is negative in all five groups. That is the starting point. The rest of the project is about whether it holds up.
 
---
 
## 6. Modeling and Analysis
 
All regressions in `main.ipynb` are weighted least squares with cohort size as the weight (a graduation rate from 5,000 students is far more precise than one from 80) and HC3 robust standard errors.
 
### 6.1 The spendRate coefficient, one control at a time
 
| Specification | spendRate | p |
|---|---|---|
| Pooled | −0.20 | 0.37 |
| + division | −1.19 | < 0.001 |
| + log total expenses | +0.73 | < 0.001 |
| + Pell, test score, enrollment, admission rate (no resource control) | −0.35 | 0.002 |
| + log per-student spending, instruction and admin shares, test-score flag | +0.11 | 0.32 |
 
Three sign changes. That's confounding, not an effect.
 
The interaction model (`spendRate × division`) doesn't improve on the additive one (F = 1.88 on 4 df, p = 0.11), so H2 is not rejected: whatever the slope is, it's the same across divisions.
 
The size step is the one to understand. `spendRate` is athletic spending divided by total expenses. Total expenses is strongly and positively related to graduation rate. So without a size control, a high athletic share partly just means a small denominator, a small budget, and small budgets graduate fewer students. The coefficient inherits a negative sign through its denominator. Controlling for log total expenses removes that and the sign flips. A levels check confirms it isn't a ratio artifact: with log athletic spending and log total spending as separate terms, both are positive and significant.
 
The −0.35 row is the trap. Adding student composition (Pell share, test score, admission rate, enrollment) but dropping the resource control brings the negative sign back, and it's significant. That is the estimate that looks like a finding. It isn't: enrollment is in the model but per-student spending is not, so at a fixed enrollment a higher athletic share again means a poorer school. Put per-student spending in and the coefficient is +0.11 with a 95% CI of −0.11 to +0.33. Given athletic share ranges over roughly 12 percentage points in this sample, even the ends of that interval are small: a 5-point increase in share corresponds to about half a graduation point, with the interval spanning ±1 point.
 
H1 is not rejected. With composition and resources controlled there is no detectable association between athletic spending share and graduation rate in either direction.
 
Trimming the top 5% of cohorts (the schools carrying the most weight) doesn't move the estimate (+0.12, p = 0.34).
 
### 6.2 The full model
 
Everything else in the final specification behaves as expected. Pell share is the largest effect: 20% to 50% Pell costs about 11 graduation points, everything else fixed. Higher admission rates and a missing admission rate are strongly negative. Test scores, enrollment and per-student spending are positive: doubling per-student spending is worth about 3.5 points, doubling enrollment about 4. D-III sits 7 points above FBS; the other three divisions are 2 to 3 points above FBS and marginal, so football status does nothing once composition is controlled. Neither instructional share nor administrative share matters. Resources matter; how they're divided between athletics, instruction and administration does not.
 
### 6.3 Is linear enough (H3)
 
Four models on the same 14 encoded columns, 80% training split stratified by division, 5×5 repeated cross-validation, cohort-weighted RMSE. Gradient boosting and random forest are tuned by grid search; ridge picks its own penalty.
 
| Model | CV RMSE | CV R² |
|---|---|---|
| Linear | 0.063 | 0.82 |
| Ridge (cross-validated α) | 0.063 | 0.82 |
| Gradient boosting (tuned) | 0.065 | 0.81 |
| Random forest (tuned) | 0.067 | 0.79 |
 
The linear model wins. Ridge selected effectively no regularization and matched it to three decimals, so the linear model isn't overfit at this sample size. The tuned GBM chose the shallowest, slowest configuration in the grid (depth 2, learning rate 0.01, 1000 trees), which is boosting's way of approximating an additive function. On the 20% held-out test set the linear model scores RMSE 0.060 (R² 0.85) and the GBM 0.065 (R² 0.83), in line with CV.
 
The GBM's job after that is diagnostic.
 
**Feature selection.** Recursive elimination on the GBM flattens at 8 of 14 encoded features; the six it would drop are the four division dummies and the two missing flags, all binary. That ranking uses impurity importance, which favors continuous variables with many split points, so it's checked against a drop-column ablation on the raw columns with paired CV differences. The ablation says: Pell share is the one feature the model can't do without (12% of baseline RMSE, 5.5 SE). Admission rate is second. Test score, enrollment and per-student spending are individually weak because they substitute for each other. Division is nothing. Athletic share is nothing: the model predicts slightly better without it. This is the same answer the WLS gave, from a method that makes no linearity assumption.
 
**Partial dependence.** For each feature, the GBM's partial dependence is overlaid on the linear model's. They agree over the central 80% of the data for every feature but one. Athletic share is flat under both. The exception is enrollment, where the GBM is flat below roughly 3,000 undergraduates and rising above. Most of that turns out to be per-student spending doing the work in the WLS; a residual plot against log enrollment bends only in the bottom decile, and hinge terms at 3,000 and 8,000 undergraduates don't significantly improve the fit (HC3 p = 0.06 and 0.09). The linear form is kept. On the categorical features the GBM agrees with the WLS on direction but shrinks every effect, a known weakness of shallow trees with binary splits, so the WLS coefficients are the better estimates.
 
---
 
## 7. Visualization and Reporting
 
R phase (`Output/Plots/01` to `06`): scatter of athletic share against graduation rate with per-division lines, boxplots of share and graduation rate by division, a coefficient plot of within-division slopes with 95% CIs, pooled fit against the division-adjusted fit, and standard diagnostic plots.
 
Python phase (`Output/Plots/07` to `12`): the RFECV curve with the one-standard-error choice, the ablation bar chart with paired SEs, predicted-versus-actual on the test set for both models with points sized by cohort, partial dependence for the eight numeric features (GBM and linear overlaid) and for the three categoricals, and WLS residuals against log enrollment.
 
Tables (`Output/Tables/01` to `12`) hold the summary statistics, every regression and test from both phases, the CV comparison, the feature ranking, the ablation deltas, test-set metrics, division composition and the full WLS coefficient table.
 
---
 
## 8. Insights
 
**Athletic spending share has no detectable association with graduation rate once total resources are in the model.** It looks negative and significant with partial controls, and that's a denominator artifact: without per-student spending in the model a high share just means a small budget. With it, the coefficient is +0.11 and the interval covers zero comfortably. Three independent checks agree: the nonlinear models find no predictive value in athletic share, the ablation finds the model does better without it, and the partial dependence is flat.
 
**Graduation rates are driven by who a school enrolls and what it has per student.** Pell share, admission selectivity, test scores, enrollment size and per-student spending explain about 85% of the weighted variance. Division differences are almost entirely composition: FBS and FCS spend the same share on athletics and sit 14 points apart on graduation, tracking a 120-point gap in test scores, a threefold gap in size and a 50% gap in spending per student. Adjusted, D-III is 7 points above FBS and everyone else is within 3.
 
**The negative associations that show up between athletic spending and graduation are, in this data, what omitted-variable bias looks like.** The pooled, division-adjusted and composition-adjusted specifications each tell a different story, and each is wrong for the same reason: the denominator of the spending share is doing the work. Anyone reporting a spending-share coefficient without a resource control is reporting the size of the school.
 
**What this doesn't say.** None of this shows athletic spending is harmless. It shows that in a cross-section of public schools, share of budget going to athletics doesn't predict graduation once you know the school's size, wealth and student body. Whether a given school moving money from instruction to athletics would change its graduation rate is a within-school question and needs panel data. A multi-year EADA and IPEDS panel with school fixed effects is the natural next step; FCS-to-FBS reclassifications and conference moves would give a difference-in-differences design. Extending to private schools requires harmonizing the F2 finance form. Both are outside this project.
 
---
 
## 9. References
 
**Data Sources**
 
U.S. Department of Education. (2024). *Equity in Athletics Disclosure Act (EADA) Database, 2023*. Office of Postsecondary Education. https://ope.ed.gov/athletics/
 
National Center for Education Statistics. (2024). *IPEDS Finance Survey, F1A 2022-23 (Final/revised)*. U.S. Department of Education. https://nces.ed.gov/ipeds/
 
National Center for Education Statistics. (2024). *IPEDS Graduation Rates Survey, GR2023 (Final/revised)*. U.S. Department of Education. https://nces.ed.gov/ipeds/
 
National Center for Education Statistics. (2024). *IPEDS Admissions and Test Scores, ADM2023 (Final/revised)*. U.S. Department of Education. https://nces.ed.gov/ipeds/
 
National Center for Education Statistics. (2024). *IPEDS Student Financial Aid, SFA2223 (Final/revised)*. U.S. Department of Education. https://nces.ed.gov/ipeds/
 
College Board and ACT. (2018). *Guide to the 2018 ACT/SAT Concordance*. https://www.act.org/content/dam/act/unsecured/documents/ACT-SAT-Concordance-Tables.pdf
 
**Academic Literature**
 
Anderson, M. L. (2017). The benefits of college athletic success: An application of the propensity score design. *Review of Economics and Statistics*, 99(1), 119-134.
 
Pope, D. G., & Pope, J. C. (2009). The impact of college sports success on the quantity and quality of student applications. *Southern Economic Journal*, 75(3), 750-780.
 
Hoffer, A., Humphreys, B. R., Lacombe, D. J., & Ruseski, J. E. (2015). Trends in NCAA athletic spending: Arms race or rising tide? *Journal of Sports Economics*, 16(6), 576-596.
 
Knight Commission on Intercollegiate Athletics. (2024). *College Athletic Financial Information (CAFI) Database*. https://cafidatabase.knightcommission.org/
 
**Software and Code References**
 
Anthropic. (2026). *Claude (Opus 4.7) [Large language model]*. Used for code structure, debugging, and analytical guidance throughout the project. https://claude.ai
 
R Core Team. (2024). *R: A Language and Environment for Statistical Computing*. R Foundation for Statistical Computing. https://www.R-project.org
 
Wickham, H. (2017). *R for Data Science*. O'Reilly Media. https://r4ds.hadley.nz
 
Seabold, S., & Perktold, J. (2010). statsmodels: Econometric and statistical modeling with Python. *Proceedings of the 9th Python in Science Conference*. https://www.statsmodels.org
 
Pedregosa, F., et al. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research*, 12, 2825-2830. https://scikit-learn.org
 
R Documentation, *Linear Models*. https://stat.ethz.ch/R-manual/R-devel/library/stats/html/lm.html
 
STHDA. *ggplot2 scatter plot with regression line*. http://www.sthda.com/english/wiki/ggplot2-scatter-plots-quick-start-guide-r-software-and-data-visualization
 
Bobbitt, Z. *How to perform multiple linear regression in R*. Statology. https://www.statology.org/multiple-linear-regression-r/
 
Wong, K. *Tidy Regression Output with broom*. RPubs. https://rpubs.com/aaronsc32/regression-with-broom
 
