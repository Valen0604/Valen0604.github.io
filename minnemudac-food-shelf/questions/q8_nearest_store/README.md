# Q8 follow-up: what is the nearest SNAP store, really?

This is the analysis behind the team's **Serendipitous Discovery Award** (graduate
division, MinneMUDAC 2026).

## Where it came from

Question 8 asked about food access in low-income, low-access (LILA) census tracts. A
teammate's retail comparison showed that the nearest SNAP-authorised store to rural LILA
residents is about twelve miles away if only supermarkets count, and about six miles if
smaller and "combination" stores count too. I asked the follow-up question: what are
those closer stores?

## What I did

`nearest_store_type.py` takes every Minnesota census tract's population centre (Census
CenPop 2020) and finds the nearest SNAP-authorised store (USDA FNS SNAP Retailer Locator,
current snapshot) under four widening definitions of "store". It records the store's
USDA type and name, then summarises by LILA class and urban or rural with population
weights. Everything it reads is public.

## What it found

Rural LILA tracts: 65 tracts, 171,240 residents.

| stores counted | nearest store, population-weighted | residents within 5 miles |
|---|---|---|
| supermarkets only | 12.1 miles | 12% |
| plus grocery stores of any size | 7.3 miles | 35% |
| plus other stores selling groceries | 6.0 miles | 49% |
| plus convenience stores | 5.2 miles | 57% |

- Once "other stores selling groceries" count, **the nearest SNAP store for 45% of rural
  LILA residents is a dollar store**. Of the 31 rural LILA tracts whose nearest store
  falls in USDA's "Other" type, 29 are nearest to a Dollar General.
- In urban LILA tracts the nearest supermarket is under a mile away and 99% of residents
  have one within five miles, so the widening barely matters there.
- A teammate's coverage analysis gives the other half of the picture: 37% of rural LILA
  residents live within five miles of a food shelf, against 98% of urban LILA residents.

So the distance gap in rural low-access areas is being closed by dollar stores, not by
supermarkets or food shelves.

## Files

- `nearest_store_type.py`: the script.
- `../../tables/q8_nearest_store_type.csv`: one row per tract group and store definition
  (mean distance, share within five miles, share of residents nearest to each store type).
- `../../tables/q8_nearest_store_names.csv`: which named stores are nearest where the
  type is "Other".
- `ATLAS_CLEANING.md`: my cleaning notes on the USDA Food Access Research Atlas, written
  for the team. The Atlas uses 2010 tract boundaries and the site data uses 2020, so the
  notes are mostly about the crosswalk.

## Caveats

The store list is USDA's current authorisation snapshot, not a dated series, so distances
differ slightly from the 2025 historical extract used in the team's main comparison. The
point of the table is the store type, not the mile. Distances are straight-line from
tract population centres. The script needs one table from the team's Q8 pipeline (the
tract groups), so it is shown here, not runnable.
