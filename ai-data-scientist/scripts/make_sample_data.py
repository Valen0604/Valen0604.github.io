"""
Build the sample datasets in data/sample/.

All are synthetic. They are built with known relationships and known flaws, so you can
check whether the agent finds them. The answers are in data/sample/README.md. Two of the
files (support_tickets, store_details) exist to link to the other two, for the
Relationships tab.

    python scripts/make_sample_data.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "sample"


def customer_churn(n: int = 3000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    tenure = rng.gamma(2.0, 14, n).clip(1, 72).round()
    contract = rng.choice(["Month-to-month", "One year", "Two year"], n, p=[0.55, 0.25, 0.20])
    plan = rng.choice(["Basic", "Standard", "Premium"], n, p=[0.4, 0.4, 0.2])
    base = pd.Series(plan).map({"Basic": 25, "Standard": 55, "Premium": 95}).to_numpy()
    monthly = (base + rng.normal(0, 8, n)).clip(15).round(2)
    tickets = rng.poisson(1.2, n)
    region = rng.choice(["North", "South", "East", "West"], n)
    autopay = rng.choice(["Yes", "No"], n, p=[0.6, 0.4])
    age = rng.normal(44, 14, n).clip(18, 90).round()

    # The real drivers of churn. A good analysis should recover these, in this order.
    logit = (-1.1
             + 1.5 * (contract == "Month-to-month")
             - 0.9 * (contract == "Two year")
             - 0.045 * tenure
             + 0.42 * tickets
             + 0.012 * (monthly - 50)
             - 0.5 * (autopay == "Yes"))
    churned = rng.random(n) < 1 / (1 + np.exp(-logit))

    signup = pd.Series(pd.Timestamp("2024-01-01") - pd.to_timedelta(tenure * 30.4, unit="D"))
    df = pd.DataFrame({
        "customer_id": [f"C{100000 + i}" for i in range(n)],
        "signup_date": signup.dt.strftime("%Y-%m-%d"),
        "region": region,
        "age": age,
        "plan": plan,
        "contract": contract,
        "autopay": autopay,
        "tenure_months": tenure,
        "monthly_charge": monthly,
        "total_charges": (monthly * tenure * rng.normal(1, 0.03, n)).round(2),
        "support_tickets": tickets,
        "churned": np.where(churned, "Yes", "No"),
    })

    # ---- flaws, planted on purpose
    # 1. a leaky column: only customers who left have a cancellation reason
    reasons = rng.choice(["Price", "Service", "Moved", "Competitor"], n)
    df["cancellation_reason"] = np.where(churned, reasons, None)
    # 2. missing values, more common for older customers (not random)
    df.loc[rng.random(n) < 0.04 + 0.10 * (age > 60), "monthly_charge"] = np.nan
    df.loc[rng.random(n) < 0.06, "age"] = np.nan
    # 3. the same category written three ways
    messy = rng.random(n) < 0.05
    df.loc[messy, "region"] = df.loc[messy, "region"].str.lower()
    df.loc[rng.random(n) < 0.02, "region"] = "NORTH "
    # 4. impossible values
    df.loc[rng.choice(n, 6, replace=False), "age"] = 999
    # 5. exact duplicate rows
    df = pd.concat([df, df.sample(25, random_state=seed)], ignore_index=True)
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def store_sales(seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.date_range("2023-01-01", "2025-06-30", freq="D")
    stores = {"Downtown": 1.35, "Mall": 1.10, "Suburb": 0.85, "Airport": 0.95}
    rows = []
    for store, scale in stores.items():
        t = np.arange(len(days))
        trend = 1 + 0.00035 * t                          # slow growth
        week = 1 + 0.22 * np.isin(days.dayofweek, [4, 5])  # Friday and Saturday
        year = 1 + 0.18 * np.sin(2 * np.pi * (days.dayofyear - 80) / 365)
        promo = rng.random(len(days)) < 0.12
        temp = 12 + 14 * np.sin(2 * np.pi * (days.dayofyear - 110) / 365) + rng.normal(0, 4, len(days))
        holiday = days.strftime("%m-%d").isin(["01-01", "07-04", "11-28", "12-25", "12-24"])
        units = (220 * scale * trend * week * year
                 * (1 + 0.30 * promo) * (1 - 0.35 * holiday)
                 * rng.normal(1, 0.07, len(days)))
        price = np.where(promo, 8.49, 9.99)
        rows.append(pd.DataFrame({
            "date": days, "store": store, "promotion": np.where(promo, 1, 0),
            "holiday": holiday.astype(int), "temperature_c": temp.round(1),
            "unit_price": price, "units_sold": units.round().astype(int),
        }))
    df = pd.concat(rows, ignore_index=True)
    df["revenue"] = (df["units_sold"] * df["unit_price"]).round(2)
    # a store that opened late, and a sensor outage
    df = df[~((df["store"] == "Airport") & (df["date"] < "2023-09-01"))]
    df.loc[(df["date"].between("2024-03-10", "2024-03-24")) & (df["store"] == "Mall"),
           "temperature_c"] = np.nan
    return df.reset_index(drop=True)


def support_tickets(churn: pd.DataFrame, n: int = 2400, seed: int = 5) -> pd.DataFrame:
    """
    One row per support ticket. Links to customer_churn through `customer_id`, one
    customer to many tickets, so the two files test the Relationships tab.
    """
    rng = np.random.default_rng(seed)
    customers = churn.drop_duplicates("customer_id").set_index("customer_id")
    # Customers with more tickets in the churn file get more rows here, so the two
    # files agree: support_tickets there is roughly the count of their rows here.
    weight = customers["support_tickets"].to_numpy(dtype=float) + 0.3
    customer = rng.choice(customers.index.to_numpy(), n, p=weight / weight.sum())
    opened = pd.Timestamp("2024-01-01") - pd.to_timedelta(rng.integers(1, 720, n), unit="D")
    category = rng.choice(["Billing", "Outage", "Slow speed", "Equipment", "Other"], n,
                          p=[0.32, 0.22, 0.2, 0.14, 0.12])
    channel = rng.choice(["Phone", "Chat", "Email"], n, p=[0.5, 0.3, 0.2])
    minutes = np.where(channel == "Email", rng.gamma(2, 6, n), rng.gamma(2, 11, n)).round(1)
    # Outages are escalated more and resolved less on first contact.
    resolved = rng.random(n) < np.where(category == "Outage", 0.55, 0.82)
    satisfaction = np.where(resolved, rng.choice([3, 4, 5], n, p=[0.2, 0.4, 0.4]),
                            rng.choice([1, 2, 3], n, p=[0.4, 0.4, 0.2])).astype(float)
    df = pd.DataFrame({
        "ticket_id": [f"T{20000 + i}" for i in range(n)],
        "customer_id": customer,
        "opened": opened.strftime("%Y-%m-%d"),
        "channel": channel,
        "category": category,
        "handling_minutes": minutes,
        "resolved_first_contact": np.where(resolved, "Yes", "No"),
        "satisfaction": satisfaction,
    })
    # ---- flaws, planted on purpose
    # 1. tickets for customers that are not in the churn file (left after a data cut)
    df.loc[rng.choice(n, 60, replace=False), "customer_id"] = [f"C{200000 + i}" for i in range(60)]
    # 2. a batch keyed in lower case: same customer, different text, so it fails to match
    low = rng.choice(n, 45, replace=False)
    df.loc[low, "customer_id"] = df.loc[low, "customer_id"].str.lower()
    # 3. satisfaction is only recorded for some tickets
    df.loc[rng.random(n) < 0.35, "satisfaction"] = np.nan
    return df.sort_values("opened").reset_index(drop=True)


def store_details(seed: int = 13) -> pd.DataFrame:
    """One row per store: the lookup table for store_sales, linked through `store`.
    Harbor opened after the sales extract, so it is in this file and nowhere else."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "store": ["Downtown", "Mall", "Suburb", "Airport", "Harbor"],
        "city": ["Minneapolis", "Bloomington", "Maple Grove", "Minneapolis", "Duluth"],
        "opened": ["2015-03-02", "2017-11-20", "2019-06-10", "2023-09-01", "2025-08-15"],
        "floor_space_m2": [420, 610, 350, 180, 390],
        "staff": [14, 19, 9, 7, 11],
        "parking": ["No", "Yes", "Yes", "No", "Yes"],
        "manager": ["A. Lind", "R. Osei", "M. Chen", "J. Novak", "S. Patel"],
    })
    df["rent_per_month"] = (df["floor_space_m2"] * rng.uniform(18, 26, len(df))).round(0)
    return df


README = """# Sample data

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
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    churn = customer_churn()
    sales = store_sales()
    tickets = support_tickets(churn)
    stores = store_details()
    churn.to_csv(OUT / "customer_churn.csv", index=False)
    sales.to_csv(OUT / "store_sales.csv", index=False)
    tickets.to_csv(OUT / "support_tickets.csv", index=False)
    stores.to_csv(OUT / "store_details.csv", index=False)
    (OUT / "README.md").write_text(README, encoding="utf-8")
    print(f"customer_churn.csv   {churn.shape}")
    print(f"store_sales.csv      {sales.shape}")
    print(f"support_tickets.csv  {tickets.shape}")
    print(f"store_details.csv    {stores.shape}")


if __name__ == "__main__":
    main()
