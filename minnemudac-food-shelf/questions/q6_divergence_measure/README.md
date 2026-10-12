# Q6 — Build a divergence measure for need and demand

**Division:** undergraduate and graduate. **Graduate addendum required** — see
[addendum.md](addendum.md).
**Owner:** Valentino
**Status:** index built, divergence and stability done, addendum written; `analysis.py` and slides next

---

## The ask, in our words

Food shelf activity shows where people **arrive**. It does not show where people **need
help and do not get it**.

The organizers' [glossary](../../docs/GLOSSARY.md) splits that gap in two. **Latent
demand** is need that never becomes a request (awareness, stigma, eligibility doubts,
distance). **Unmet demand** is a request the system cannot fill (stockouts, location,
hours). Our data has no stockout, waitlist or hours fields, so the measure built here
targets latent demand, and the write-up should say that unmet demand is out of reach.

1. Create a **new metric or measure** that highlights areas where need is likely larger
   than the activity data shows.
2. **Compare and contrast** it against the three food shelf metrics.
3. Identify **where the new measure and the activity metrics diverge**.
4. Like Q1, **investigate county characteristics** that explain the disagreement.

The brief adds two constraints that are really the whole question:

> Your new metric or measure of need should consider **more than just demand**.
> A sufficient and complete measure of need will likely require the use of **other
> publicly available data**.

---

## The design constraint that decides everything

Your inputs must be **independent of food shelf visits** and **not already inside the Map
the Meal Gap model**. MMG is modelled largely from poverty and unemployment. If you build
an index out of poverty and unemployment, you have rebuilt Map the Meal Gap, given it a
new name, and discovered that it correlates with Map the Meal Gap.

The measure has to add something MMG does not have. The candidates that do:

| signal | why it is not in MMG and not demand | source |
|---|---|---|
| **distance to nearest site** | pure access, derived from our own `block_geoid` | ours, via Gazetteer — see [BLOCK_GEOID.md](../../docs/BLOCK_GEOID.md) |
| **no-vehicle households** | the brief's "no transport" barrier, measured | ACS `B08201` |
| **SNAP participation gap** | eligible-but-not-enrolled: under-claiming, not poverty | DHS caseload ÷ MMG income-eligible FI persons |
| **senior share** | seniors under-claim food assistance at known rates | ACS `S0101` |
| **school meal eligibility** | child need, measured outside the MMG pipeline | MN Dept of Education |
| **site density / capacity** | supply-side, not need-side, but it is what makes need invisible | ours |

---

## Approach

1. **Define need in one sentence, before you touch the data.** The graduate addendum
   requires a falsifiable definition, and writing it first stops the index from becoming
   whatever the data happened to produce.
2. **Build the index.** Normalise each input (rank or z-score), combine with stated
   weights. Simple and explainable beats sophisticated — you will defend this live.
3. **Divergence = need rank − activity rank.** Do it for each of the three metrics
   separately; the brief asks for all three. A county that ranks 5th in need and 60th in
   households served is the story.
4. **Map it.** This is the one question where a Minnesota map genuinely earns its place.
5. **Explain the divergence** with county characteristics, exactly as in Q1.
6. **Stability check.** Re-run with alternative weights. If the top ten counties change,
   the ranking is not a finding — say so and fix it.

---

## What the preview already shows

From `python src/eda.py`:

- The rank correlation between activity per food-insecure person and the food insecurity
  rate is **negative** (−0.26 to −0.29 in 2024). Higher-need counties serve *fewer*
  households per food-insecure person. The divergence the brief hypothesises is already
  visible in the raw comparison.
- **Wilkin County (FIPS 27167) has no reporting food shelf in any of the 55 months.**
  Feeding America estimates food-insecure people there. Observed demand is zero. This is
  the cleanest possible illustration of the question and it belongs on a slide.
- **Rural against metro, 2024:** metro counties serve **4.91** households per
  food-insecure person; rural counties serve **2.98**. But rural counties carry **400**
  food-insecure people per site against metro's **637**. Reach and load point in opposite
  directions, and an index that collapses them into one number loses that.

---

## Traps

- **Rebuilding Map the Meal Gap.** Covered above. This is the failure mode.
- **Arbitrary weights.** Show stability, or do not show a ranking.
- **Circularity through site density.** If low site density drives your need index, and
  you then conclude that low-site-density counties are underserved, you have written a
  tautology. Site density is a *plausible explanation* of divergence, not an *input* to
  need.
- **Small-county noise.** A county with 400 food-insecure people moves ranks on almost
  nothing. Report uncertainty or pool.
- **Cross-county use.** A household that drives to the next county makes its own county
  look underserved. Check whether the divergent counties border a high-activity one —
  and if they do, say so before a judge does.

---

## Findings (2 October)

The numbers come from `analysis.py`. The definition, the inputs argued one by one, and
the predictions written before each result are in `notebooks/q6_exploration.ipynb`; the
falsifiability material is in [addendum.md](addendum.md).

**The measure.** A household is in need if, at any point in the past year, it worried
about running out of food, regardless of whether it sought help. The county index is an
equal-weight mean of within-year z-scores of seven public inputs, none of which is
food-shelf demand or an input to Map the Meal Gap: SNAP households, no-vehicle
households, senior poverty, housing-cost burden, adults without a diploma, low-income
low-access share (USDA, 1-and-10), debt in collections.

| question | answer |
|---|---|
| Compare and contrast against the three metrics | Like MMG, the index does not predict recorded activity per resident: Spearman 0.07 (pounds) to 0.14 (individuals) against activity per 1,000, the same for all three metrics. It agrees with MMG's rate broadly (Spearman 0.77) and differs on five of the top ten counties. |
| Where they diverge | Need outranks recorded activity most in Nobles, Grant, Wilkin (no recorded activity; need rank 26 of 87, predicted before the index was built), Benton, Wadena, Chippewa, Todd. The reverse in Washington, Dodge, Cook, Houston. Mahnomen is first on need and records more than MMG predicts: a high-need county that is reached. |
| What explains the divergence | Two barriers: households without internet (+0.41 per SD, p = 0.005, clears a three-test Bonferroni bar) and distance to the nearest site (+0.23, p = 0.025, the hypothesis written first). More of either widens the gap between need and recorded activity. Rural loses its effect once no-internet is in (they overlap, 0.65). Limited English and non-citizens (0.93 correlated) come to nothing together; seniors and site density show nothing. The barriers explain 17% of the divergence (adjusted 14%), against 5% of Q1's residual with the same variables. |
| Stability | The top seven (Mahnomen, Clearwater, Beltrami, Wadena, Ramsey, Pine, Nobles) hold under every variant and in at least 71% of 500 random weightings; places 8 to 10 rotate among six counties. Wilkin is weight-sensitive (2nd to 77th), an argument for keeping equal weights. |

**No-internet is both a driver of need and a barrier** (step 5c): with activity held
fixed, counties with more households without internet score higher on the index (+0.27 per
SD, p < 0.001); with the index held fixed, they record less activity (−0.26, p = 0.049). The
second half is what makes it a barrier, and it holds narrowly.

**Against MMG, head to head** (step 6): county size explains 85.3% of recorded activity;
MMG's rate adds 0.6 points, the index 0.4, both together 0.7, neither significant with the
other in. The two residual rankings correlate 0.99. Recorded activity follows how many
people live in a county and almost nothing else, whichever way need is measured. The same
three barriers that explain 10.5% of the index's gap on their own explain 1.0% of MMG's
(Q1 appendix): the index is higher where internet is scarce, MMG's rate less so.

**Checks written in advance, none fired:** index on poverty rate R² = 0.60 (bar 0.9);
4 of the top ten shared with the poverty top ten; first principal component 41% of input
variance with loadings 0.20 to 0.49. SNAP and debt are the inputs closest to the index
(0.79 each) and to poverty; said on the slide.

**Caveats to state:** the index ranks counties, it does not estimate the share of
households in need; the inputs are 5-year ACS averages and two static sources (Atlas
2019, debt 2025); debt covers only people with a credit file; 87 counties see only large
effects; recorded activity is where people arrive, not whether need was met.

---

## Deliverables

- [x] `analysis.py` that rebuilds the index from `data/processed/` + `data/external/`
- [x] The index itself, documented input by input, with weights and the reason for each (notebook step 0, addendum §2)
- [x] A county-level divergence table against all three metrics (`outputs/tables/q6_divergence.csv`)
- [x] One map for the deck (`outputs/figures/q6_maps.png`)
- [x] Stability analysis under alternative weights (`q6_stability.csv`, `q6_stability_random.csv`)
- [x] [addendum.md](addendum.md) completed — it is graded separately
- [ ] Slides
