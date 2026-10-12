# Q6 — Graduate addendum

**Graduate teams answer this. Undergraduate teams do not.** It is graded, and it is the
part that is hardest to fake, because it asks us to say in advance what would prove us
wrong.

The brief asks for four things:

> A falsifiable definition is a definition that evidence can prove wrong.
>
> 1. A falsifiable definition of need, stated plainly.
> 2. An explanation of why your new metric captures need rather than demand.
> 3. The evidence that would make you reject the definition.
> 4. The evidence that would make you revise the measure.

Everything below was written in `notebooks/q6_exploration.ipynb`, step 0, on 1 October
2026, before the index existed. The results that followed are marked as such.

---

## 1. A falsifiable definition of need

> **Our definition:** a household is in need if, at any point in the past year, it
> worried about running out of food, regardless of whether it sought help.

This is the first item of the USDA food-security questionnaire, so a survey can measure
it directly and disagree with us. It is a state of households, not a number in our data.
"Regardless of whether it sought help" is what separates need from demand: the worry
exists whether or not the household asks anyone. A county's need is the number, or share,
of its households in that state. The index that follows is relative: it ranks counties,
it does not estimate the share, which only a survey can.

Why not the organizers' starting shape ("households that would use a food shelf if
distance, information and stigma were not barriers")? Because that defines need through
the food shelf. A household can be in need and never want a food shelf. Ours defines it
through the household's own experience of food.

## 2. Why the metric captures need rather than demand

The rule applied to every input: its mechanism has to end in "...so the household is more
likely to worry about running out of food". If it ends in "...so the household is less
likely to visit a food shelf", it is a barrier, not need, and it is used only to explain
the divergence (step 5), never inside the index.

| input | measurable at zero demand? | in the MMG model? | mechanism |
|---|---|---|---|
| households on SNAP (ACS B22003) | yes | no | has already had to ask for help with food; benefits run out before the month does |
| households without a vehicle (ACS B08201) | yes | no | no way to carry a week's groceries home. Also a barrier to reaching a food shelf; used on the need side only |
| senior poverty rate (ACS B17001) | yes | no (MMG uses all-ages poverty) | fixed income, no savings, no future earnings: a bill that cannot be deferred becomes a month of worry |
| housing-cost burden (ACS B25070 + B25091) | yes | no | rent is paid first; over 30% of income on housing leaves little for anything else |
| adults without a diploma (ACS B15003) | yes | no | fewer ways out when trouble comes |
| low-income, low-access share (USDA Atlas) | yes | no | no store within reach: the worry is how to get food at all, then how to afford it |
| debt in collections (Urban Institute) | yes | no | unable to repay, so always finding new financing. Doubt recorded in advance: covers only people with a credit file |

Set aside as barriers: distance to the nearest site, rural-urban class, senior share.
Left out: poverty, median income, unemployment (MMG inputs); everything derived from
activity (demand); race and ethnicity (an MMG input).

**Wilkin County, the test case.** Prediction written before the index existed: Wilkin
ranks around the 70th percentile of need, driven by SNAP and no-vehicle households, and
disagrees with MMG, which puts its poverty rate 68th of 87. **Result:** rank 26 of 87,
the 71st percentile. The measure gives a county with no recorded activity a need
estimate, and the estimate was predicted.

## 3. Evidence that would make us reject the definition

> Survey the counties we rank highest on the measure. If the share of households that
> worried about running out of food is no higher than in the rest of the state, the
> measure is wrong.

Weaker versions we would also take as rejection: if a new site opening within reach of a
high-need, low-activity county produced no increase in recorded activity, the need we
posited was not there; if the divergence were fully explained by households recorded in
a neighbouring county, we measured a reporting artefact. The second was tested in Q1
(Moran's I, join counts, pooling): no general spatial pattern, weak evidence of some
cross-border recording. It does not explain the divergence.

## 4. Evidence that would make us revise the measure

Written before the index existed, with what happened:

| criterion | bar | result |
|---|---|---|
| poverty in a costume | index regressed on the poverty rate leaves nothing behind (R² near 0.9 or above), or the top ten is the poverty top ten | R² = 0.60; 4 of 10 shared. Does not fire |
| an input dominates, or tracks activity | one input carries most of the variance | first principal component 41%, loadings 0.20 to 0.49. Does not fire. SNAP and debt are the two inputs closest to the index (0.79 each) and the two closest to poverty; said on the slide |
| unstable under reasonable alternative weights | the top ten changes | top seven hold under every variant and in at least 71% of 500 random weightings; places 8 to 10 rotate among six counties. Does not fire, but "top ten" overstates what is stable |

A fourth test, run after the index existed and so not pre-registered: whether a barrier
that explains the gap does so through the need side (the index is simply high where the
barrier is) or the activity side (people there do not reach a site). For households
without internet, both, about half each; the activity side holds on its own at p = 0.049.
We say so rather than claim the whole effect as a barrier.

Also: better data at a finer grain would make a county-level index the wrong object. The
inputs all exist at census-tract level; the comparison against activity does not, because
activity is recorded by site.

---

## How this gets presented

One slide. **The definition:** a household that worried about running out of food in the
past year, whether or not it asked for help. **The rejection criterion:** survey our
highest-need counties; if the worry is no more common there than elsewhere, we were
wrong. **What we are least confident in:** the two inputs closest to poverty, SNAP and
debt; Wilkin's rank, which moves from 2nd to 77th under extreme weights; the tail of the
top ten; and that half of the no-internet barrier is the index being high where internet
is scarce.

Everyone on the team must be able to state the definition and the rejection criterion
without notes. Judges may direct this question at any of us.
