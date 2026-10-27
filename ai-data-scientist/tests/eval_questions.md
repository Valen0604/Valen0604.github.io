# Evaluation questions for the live agent

The automated tests check the code around the model. They cannot check the model's
judgment. This file does, by hand.

Each question has a known answer, because the sample data was built with one (see
`data/sample/README.md`). Ask the question in the app, then score the answer.

## How to score

Give one point for each line under "A good answer" that the agent gets right. Take one
point off for each "Trap" it falls into. Record the score, the cost shown in the sidebar,
and the number of tool calls.

Run the whole set:

- before and after any change to `app/agent/prompts.py` or a tool description
- once at each effort level (`ADS_EFFORT` in `.env`) to see what higher effort buys
- on a second model, if you want to compare

Change one thing at a time. If the score moves, you know why.

| Run | Date | Change from last run | Score / 50 | Cost | Notes |
|---|---|---|---|---|---|
| 1 | | first run, defaults | | | |
| 2 | | | | | |

Start a new session for each numbered section, so one answer does not help the next.

---

## 1. First look (customer_churn.csv)

**Ask:** `Give me an overview of this data.`

A good answer (5 points):

- [ ] says what one row is: a customer
- [ ] names the target, `churned`, and that about a quarter of customers churned
- [ ] mentions at least three of the data-quality problems without being asked
- [ ] uses no more than 5 tool calls
- [ ] does not repeat the profile table in prose

Traps:

- [ ] reports the mean of `age`, which the 999 values distort
- [ ] states a number that appears in no tool result

## 2. Data quality (customer_churn.csv)

**Ask:** `What data-quality problems should I know about before I analyse this?`

A good answer (7 points), one for each:

- [ ] `age` = 999 in 6 rows
- [ ] `region` written several ways
- [ ] 25 duplicate rows
- [ ] `monthly_charge` gaps are related to age
- [ ] `cancellation_reason` is filled in only for churned customers
- [ ] `customer_id` is an identifier
- [ ] `total_charges` is close to `monthly_charge` times `tenure_months`

Traps:

- [ ] suggests filling the gaps in `monthly_charge` with the mean, without noting the bias
- [ ] suggests filling the gaps in `cancellation_reason`

## 3. Cleaning (customer_churn.csv)

**Ask:** `Clean the data.`

A good answer (5 points):

- [ ] removes the duplicates and says how many
- [ ] makes `region` consistent, leaving 4 values
- [ ] turns `age` 999 into missing
- [ ] reports the row count before and after
- [ ] says what it chose not to change, and why

Traps:

- [ ] drops every row that has a missing value
- [ ] changes the data and does not say what changed

## 4. Drivers (customer_churn.csv)

**Ask:** `What drives churn?`

A good answer (8 points):

- [ ] leaves out `cancellation_reason` and explains why
- [ ] leaves out `customer_id`
- [ ] names `contract` as the strongest driver
- [ ] names `tenure_months` and `support_tickets`
- [ ] does not name `region` or `age` as drivers
- [ ] compares the model with the baseline
- [ ] reports a score between 0.75 and 0.85 ROC AUC, and does not call it excellent
- [ ] says the result shows association and not cause

Traps:

- [ ] reports a near-perfect model
- [ ] says "to reduce churn, move customers to two-year contracts" as if it were proven
- [ ] leads with accuracy on its own

## 5. A causal question (customer_churn.csv)

**Ask:** `If we enrol everyone in autopay, how much will churn fall?`

A good answer (4 points):

- [ ] says the data cannot answer this
- [ ] explains why: customers who choose autopay may differ in other ways
- [ ] reports what the data does show, the difference in churn rate, labelled as association
- [ ] says what would answer it: an experiment

Traps:

- [ ] gives a number for how much churn will fall

## 6. A statistical test (customer_churn.csv)

**Ask:** `Do customers in different regions churn at different rates?`

A good answer (4 points):

- [ ] cleans `region` first, or notes that the inconsistent spelling affects the test
- [ ] runs a chi-squared test
- [ ] concludes there is no meaningful difference
- [ ] reports the effect size, not only the p-value

Traps:

- [ ] tests on the 9 spellings of `region`
- [ ] reports a difference as real

## 7. Time series (store_sales.csv)

**Ask:** `Build a model to predict units_sold.`

A good answer (7 points):

- [ ] leaves out `revenue` and explains that it is computed from the target
- [ ] passes `date` as the time column
- [ ] notes that `unit_price` and `promotion` carry the same information
- [ ] reports the test score on the later period
- [ ] reports the gap between training and test scores
- [ ] explains the gap: the model cannot extend a trend
- [ ] says a forecasting method would suit this better

Traps:

- [ ] uses a random split
- [ ] reports R² above 0.95
- [ ] says temperature causes sales

## 8. A chart the chart tool cannot draw (store_sales.csv)

**Ask:** `Show weekly units sold for each store in its own panel, with promotion weeks marked.`

A good answer (3 points):

- [ ] uses `run_python`, because `create_chart` has no panels
- [ ] the chart shows 4 panels and marks the promotions
- [ ] notes that the Airport store starts in September 2023

Traps:

- [ ] draws one chart with four lines and calls it done

## 9. A vague question (either dataset)

**Ask:** `Is this good?`

A good answer (3 points):

- [ ] asks what "this" and "good" refer to, or states the reading it chose
- [ ] makes at most 2 tool calls before replying
- [ ] is short

## 10. A question the data cannot answer (customer_churn.csv)

**Ask:** `Which marketing channel brings in the most loyal customers?`

A good answer (4 points):

- [ ] says there is no marketing channel column
- [ ] does not substitute another column without saying so
- [ ] says what data would be needed
- [ ] makes at most 2 tool calls

Traps:

- [ ] answers using `region` or `plan` as if it were the channel

---

## Things to watch in every answer

These are not scored per question. Note them when they happen.

| Problem | What it looks like |
|---|---|
| Invented numbers | A figure in the text that is in no tool result |
| Looping | The same tool called again with the same input |
| Giving up early | One failed tool call, then an apology |
| Over-working | Ten tool calls for a one-chart question |
| Hedging | Every sentence qualified until nothing is claimed |
| Ignoring a warning | The model card warns of leakage and the text does not mention it |
