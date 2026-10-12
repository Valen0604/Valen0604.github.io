# Glossary — Key Concepts for The Food Group Data Challenge

Given to teams by the organizers (added to the repo 30 September 2026). These are the
words the judges use. Where one of our files says something different, this glossary
wins; the first section below says what each term is in our data.

## How the terms map to our data

| glossary term | in our data | note |
|---|---|---|
| Need | `fi_persons`, `fi_rate` from Map the Meal Gap (`qkit.mmg()`) | modelled from poverty and unemployment, so those two cannot explain it |
| Demand, "observed demand" | food shelf activity in `county_month.parquet`, hotline calls in `calls_clean.parquet` | the Q1 charts already say "observed demand" |
| Visit | `households` (`HouseholdsReg`) | the brief itself labels visits as `HouseholdsReg`. A glossary visit is one trip; our field counts a household once per month, so it is a floor. See [DATA_ERRORS.md §1.2](DATA_ERRORS.md) |
| Pounds distributed | `pounds` (`PoundsReg`) | **a supply measure as much as a demand measure**. Q1's site-count result and Q4's "pounds grew less" both rest on this |
| Individuals served | `individuals` (`IndividualsReg`), split into `children`, `adults`, `seniors` | the glossary says to check for duplication; a household counted monthly means the same person can appear twelve times a year |
| Latent demand | a Q1 residual below zero *may* be this, but it may also be spillover to a neighbouring county | Q6's measure targets it |
| Unmet demand | mostly invisible in our data: no stockout, waitlist or hours fields | say so when Q6 is presented |
| SNAP emergency allotments | `snap_federal_food_issued` per case falls from $453 to $267 between March and April 2023 | "ended nationally after the February 2023 issuance"; Minnesota paid the last extra amount in March. See [SNAP_DATA_NOTES.md](../questions/q5_snap/SNAP_DATA_NOTES.md) |
| MFIP, MFAP | `snap_mfip_fed_food_issued`, `mfip_state_food_issued`, `mfap_state_food_issued` | the glossary confirms what these are |
| LILA | Q8's tracts from the USDA Food Access Research Atlas | do not say "food desert" on a slide |
| Publication lag, vintage | columns in the [source registry](DATA_SOURCES.md) | |

---

## Need, demand and the gap between them

**Need.** People who lack enough food. This includes people that are not currently
interacting with the system for any reason (e.g. awareness, proximity,
transportation/mobility, reluctance to engage, lack of eligibility for relevant programs,
etc.) Data like food insecurity rate, poverty, unemployment, housing-cost burden, SNAP
eligibility, local food prices might highlight needs that are not showing up in active
demand.

**Demand.** People actively seeking or receiving food assistance. Data like food pantry
visits, meal requests, hotline calls, waitlists, benefit applications/redemptions are
examples reflecting active demand. Can be thought of as "observed demand". Caution, a
visit to a food shelf, or hotline call, or any other service requirement does not mean an
entire Need has been met.

**Unmet Need.** People needing food assistance but do not receive it or receive it in
full.

Demand is an imperfect proxy for Need because Need can fail to turn into Demand, and
Demand can fail to get served. In a retail setting, you would call these Latent Demand and
Unmet Demand.

**Latent Demand** is Need that never becomes a request: the person needs food but does not
know how to ask for it. Awareness, stigma, and uncertainty about eligibility keep that Need
hidden.

**Unmet Demand** is a request that the system cannot fill: the person is ready to ask, but
a stockout, the location, or the hours of operation stop them.

## Hunger relief in Minnesota

**Food bank.** A warehouse that holds food and supplies other organizations. A food bank
does not usually give food to a household directly. The Food Group runs a food bank.

**Food shelf.** A site that gives food directly to households. Other states call the same
thing a food pantry. Minnesota uses food shelf, and the data uses that term.

**Visit.** One trip by one household to a food shelf. A visit is not a unique person. The
same household can make many visits in a year, and each one counts.

**Pounds distributed.** The weight of food that leaves a food shelf location. This is a
supply measure as much as a demand measure, because a site cannot distribute food it does
not hold.

**Individuals served.** A count of people. The data splits this count into children,
seniors, and adults. Check whether the count is duplicated before you use it.

**Food insecurity.** The condition of a household that cannot get enough food for an active
and healthy life. It is a household condition, not an individual one, and standard surveys
measure it with a set of questions rather than an income threshold.

**Food security.** The condition of a household that can get enough food. A household can
be food secure and still use a food shelf.

**Stigma.** The social cost a person expects to pay for using a program. Stigma is one
reason a household in need may never appear in demand data.

## Programs and policy

**SNAP.** The Supplemental Nutrition Assistance Program. A federal program that gives a
household money to buy food at a retailer. It was formerly called food stamps. Minnesota
administers it at the county level.

**SNAP emergency allotments.** A temporary increase to SNAP benefits during the COVID-19
period. Every household was raised to the maximum benefit for its size, with a minimum
increase. The program ended nationally after the February 2023 issuance.

**MFIP.** The Minnesota Family Investment Program. The state welfare program for families
with children. Part of its benefit is issued as food assistance, so it appears inside some
SNAP data files.

**MFAP.** The Minnesota Food Assistance Program. A state-funded food benefit for people who
do not qualify for federal SNAP. It appears alongside SNAP in the state data files.

**MarketBucks.** A Minnesota program that matches SNAP and SUN Bucks spending at
participating farmers markets, so that a customer can buy more fresh food for the same
money.

**SUN Bucks.** The Minnesota name for Summer EBT, a federal program that gives families
money for food during the summer months when school meals are not served.

**TEFAP.** The Emergency Food Assistance Program. A federal program that supplies commodity
food to food banks and food shelves. TEFAP eligibility is why many Minnesota food shelves
report visit data to the state at all.

**NSLP and SBP.** The National School Lunch Program and the School Breakfast Program. The
federal programs through which schools serve reimbursable meals.

**FRPL.** Free and reduced-price lunch. Historically a measure of household income based on
an application. It is widely used as a poverty proxy for school areas, and it is becoming
less reliable as universal meal programs remove the incentive to apply.

**CEP.** The Community Eligibility Provision. A federal option that lets a high-poverty
school serve free meals to all students without collecting applications. A school on CEP
no longer produces FRPL application counts, which breaks the FRPL time series.

**Publication lag.** The delay between the period a dataset describes and the date it
becomes available. A source with a twelve-month lag cannot answer a question about last
month.

**Vintage.** The year of the underlying data in a published product, which is often
earlier than the year in its title. A 2025 edition that uses 2023 data has a 2023 vintage.

## Access and geography

**Low-income, low-access area.** A census tract where household incomes are low and the
distance to a grocery store is large. USDA shortens this to LILA.

**Food desert.** An older name for the same idea. It has fallen out of favour on two
grounds. First, it suggests a natural condition and hides the investment and policy
decisions that produced the gap. Second, it centres distance, which pushes attention
toward building stores and away from income, transport, and benefit levels. You will
still meet the term in older sources.

**Food swamp.** An area with a high density of outlets selling low-nutrition food, relative
to outlets selling fresh food. It is a different condition from low access, and an area
can be both.

**Rurality.** The degree to which an area is rural. Definitions vary between agencies, and
the choice changes results. Most access measures use a longer distance threshold in rural
areas than in urban ones.

**Census tract.** A small statistical area defined by the Census Bureau, usually holding
between 1,200 and 8,000 people. Tracts sit inside counties. Many federal access measures
are published at this grain.
