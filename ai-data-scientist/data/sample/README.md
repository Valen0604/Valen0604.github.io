# Sample data

All four files are synthetic. They were built with known answers so you can test the
agent. Regenerate them with `python scripts/make_sample_data.py`.

Two of them exist to test the **Relationships** tab: load `customer_churn.csv` with
`support_tickets.csv`, or `store_sales.csv` with `store_details.csv`.

## customer_churn.csv

3,025 rows. Target: `churned`.

**What drives churn, strongest first** (the agent should recover this order):

1. `contract`: month-to-month customers leave most, two-year customers least
2. `tenure_months`: newer customers leave more
3. `support_tickets`: more tickets, more churn
4. `autopay`: customers on autopay leave less
5. `monthly_charge`: a small effect

`region`, `age` and `plan` have **no effect** on churn. A model that ranks them highly is
wrong. (`plan` sets the price, so it can look related through `monthly_charge`.)

**Flaws planted on purpose** (the agent should find these):

| flaw | detail |
|---|---|
| Leakage | `cancellation_reason` is filled in only for customers who left. A model using it scores almost perfectly and is useless. |
| Missing, not at random | `monthly_charge` is missing more often for customers over 60. |
| Inconsistent categories | `region` has "North", "north" and "NORTH ". |
| Impossible values | six customers have `age` = 999. |
| Duplicates | 25 exact duplicate rows. |
| Identifier | `customer_id` is unique per row and must not be a feature. |
| Derived column | `total_charges` is about `monthly_charge` times `tenure_months`. |

## store_sales.csv

About 3,400 rows, one per store per day. Target: `units_sold` or `revenue`.

**What is in it:**

- slow growth over time
- higher sales on Fridays and Saturdays
- a yearly cycle that peaks in summer
- promotions lift units by about 30%
- holidays cut units by about 35%
- the Airport store opened in September 2023
- temperature is missing for the Mall for two weeks in March 2024

**Traps:**

- `revenue` is `units_sold` times `unit_price`. Using `revenue` to predict `units_sold`
  is leakage.
- `unit_price` is lower during promotions, so the two are the same signal.
- Rows are ordered in time. A random train/test split lets the model see the future.
- `temperature_c` follows the seasons. It correlates with sales but does not cause them.

## support_tickets.csv

2,400 rows, one per support ticket. Links to `customer_churn.csv` through `customer_id`:
one customer, many tickets. Customers with more `support_tickets` in the churn file have
more rows here.

**What the Relationships tab should find:**

- `customer_id` is nearly unique in `customer_churn` (25 duplicate rows) and repeats
  here: a one-to-many link, strong.
- About 95% of tickets match a customer. The rest are the planted flaws below.
- `region` is not here, so the only shared column is the key.

**Flaws planted on purpose:**

| flaw | detail |
|---|---|
| Orphans | 60 tickets belong to customers `C200000` to `C200059`, who are not in the churn file. |
| Format mismatch | 45 tickets have the customer id in lower case (`c101234`). They are real customers but do not match until the case is fixed. |
| Missing values | `satisfaction` is empty for about a third of tickets. |

Outage tickets are resolved on first contact less often, and `satisfaction` is lower
when a ticket is not resolved on first contact.

## store_details.csv

5 rows, one per store: the lookup table for `store_sales.csv`, linked through `store`.
`Harbor` opened after the sales extract, so it is here and in no sales row: the tab
should report that every sales row has a store, and that one store has no sales.
