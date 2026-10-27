# What this agent cannot do

The assignment asks us to automate the job of a data scientist as far as we can, because
whatever is left over is what a human is for. This document is that remainder.

It has four parts:

1. what was automated, with evidence
2. what was tried and could not be automated
3. what is not built yet, which is engineering and not a limit of AI
4. where the team should take it next

Parts 2 and 3 are different in kind, and the difference matters. "The agent cannot read a
database" is a missing feature. "The agent cannot know whether the question is worth
asking" is not.

---

## 1. What was automated

Each row is backed by a test in `tests/` that runs on data with known answers.

| Task | How well | Evidence |
|---|---|---|
| Reading messy files | Well | Keeps leading zeros in ZIP codes; reads "$1,200.50", "12%" and "(300)" as numbers; detects semicolon files; records every change it makes |
| Describing a dataset | Well | Types, gaps, distributions and correlations for every column |
| Finding data-quality problems | Well for known patterns | Found all 7 flaws planted in the sample data |
| Drawing standard charts | Well | 8 chart types, each returning the numbers behind the picture |
| Choosing a statistical test | Well for two-column questions | Picks the test from the column types and reports an effect size |
| Training and comparing models | Well for tabular data | Ranked the true drivers of churn first and the irrelevant columns last |
| Catching leakage | Partly | Catches a column that predicts the target alone, a column whose gaps do, and a column computed from the target. Misses subtler cases (section 2.4) |
| Writing custom analysis code | Depends on the LLM | Not yet measured. See section 3.1 |

---

## 2. What could not be automated

### 2.1 Deciding what question to ask

The agent answers the question it is given. It has no way to know whether that question
serves the decision someone has to make.

Ask it "what drives churn?" and it will build a model and rank the features. It will not
ask whether the company can do anything about those features, whether churn is even the
problem, or whether the customers who leave are the ones worth keeping. A model that
predicts churn perfectly is worth nothing if the only lever is the contract type and the
company cannot change contracts.

**What the human does:** turns a business situation into a question that data can answer
and that someone can act on.

### 2.2 Knowing what the data means

The agent sees `age = 999` and says it looks like a code for "unknown". That is a guess
from a pattern. It is usually right. It cannot know.

Things it has no access to:

- how the data was collected, and who was left out
- what a column meant to the person who filled it in
- that the definition of "active customer" changed in March
- that one store's numbers are entered by hand on Mondays
- whether a spike is a promotion, a bug, or a holiday

In the sample data, `temperature_c` correlates with sales. It follows the seasons and so
do sales. The agent reports the correlation and adds a caution about causation. Only
someone who knows the business can say that temperature is standing in for the calendar.

**What the human does:** brings the knowledge that is not in the file.

### 2.3 Telling cause from correlation

This is the hardest limit and the most important one.

The agent is instructed to say "is associated with" and never "causes". That makes it
careful. It does not make it capable of causal reasoning. From a table of what happened,
no method can show what would have happened otherwise, unless someone designs the
comparison.

In the sample data, customers on autopay churn less. Would enrolling more customers in
autopay reduce churn? The data cannot say. People who choose autopay may simply be people
who were going to stay.

The feature-importance chart is the most likely thing to be misread. It shows what the
model uses to predict. A reader will take it as a list of levers. The card says otherwise
in small print, and small print does not stop a misreading.

**What the human does:** designs the experiment, or names the assumption that would make a
causal reading valid, and takes responsibility for it.

### 2.4 Noticing what it was not told to look for

Every check in the engine is a pattern someone wrote down in advance. The agent finds what
it was built to find.

| The engine catches | The engine misses |
|---|---|
| A column that predicts the target almost perfectly alone | Two columns that leak only in combination |
| A column whose gaps predict the target | A column recorded a day after the outcome that is only moderately predictive |
| A column that is the product, sum or difference of two others | A ratio, a formula of three columns, or a rounded or lagged copy |
| 999 and -1 used as "unknown" | 0 used as "unknown" in a column where 0 is also a real value |
| The same category spelled three ways | Two different categories that should be one ("NYC" and "New York") |
| Duplicate rows | The same customer entered twice with different IDs |
| A random split on dated data | Groups that span the split, such as the same patient in training and test |

The thresholds are fixed numbers: 0.98 for leakage, 0.95 for date detection, 60% missing
before a column is dropped. They were chosen by judgment and will be wrong for some data.

**What the human does:** looks at the data with suspicion and no checklist.

### 2.5 Knowing when the answer is wrong

The agent is fluent whether it is right or not. A wrong analysis comes back in the same
confident paragraphs as a correct one.

The design reduces this. Numbers come from code, the code is visible, and tool errors are
reported. It does not remove it:

- The model can run the correct code and describe the result incorrectly.
- The model can choose a method that does not fit the question, run it correctly, and
  report it faithfully.
- The model can state something it never computed. The system prompt forbids this. A
  prompt is an instruction, and nothing enforces it.

Nothing in the system checks the final text against the tool results.

**What the human does:** reads the code, checks a number by hand, and asks whether the
answer makes sense.

### 2.6 Being accountable

When an analysis leads to a bad decision, someone answers for it. The agent cannot. It
does not know the stakes, it has no memory of the outcome, and it bears no consequence.

This covers ethics as well. The agent will build a model that predicts loan default from
ZIP code without noticing that ZIP code stands in for race. It has no fairness check, and
a fairness check would need a human to say which groups matter and what fair means here.

**What the human does:** decides what should not be done, and signs the result.

### 2.7 Persuading anyone

The agent writes a clear answer to one person in a chat. It does not know the audience,
what they already believe, what they are afraid of, or what they need to hear first. It
cannot sit in the meeting and notice that the room has stopped following.

**What the human does:** gets the finding used.

---

## 3. What is not built yet

These are gaps in this version. Each one is work, not a limit of the technology.

### 3.1 Not verified: the live agent

**The agent has never run against the real API.** No key was available during the build.

What was tested is everything around the model: the engine, the server, the interface, and
the agent loop with a scripted stand-in for the API. The request format was written from
the SDK documentation and checked against the installed SDK.

What is therefore unknown:

| Unknown | How to find out |
|---|---|
| Whether the first real request succeeds | `scripts/check_key.py`, then one question in the app |
| How often the agent picks the right tool | Run `tests/eval_questions.md` and score it |
| Whether it follows the rules in the system prompt | The same |
| What a typical question costs | Read the sidebar after each question |
| How it behaves in a long conversation | Hold one of 30 or more messages |

This is the first thing the team should do.

### 3.2 Data

| Gap | Detail |
|---|---|
| Data must fit in memory | A file of a few hundred megabytes works. A few gigabytes does not. |
| Files only | No connection to databases, APIs or cloud storage |
| Join keys are guessed from values | The Relationships tab finds columns whose values match. It cannot know that `id` in one file is the `customer_id` of another when the values are formatted differently, and a key with a few duplicate rows is accepted as "nearly unique" (95% or more distinct). It compares at most 12 datasets and 80 columns each. |
| Relationship ideas from the model are unverified | Asking the model for ideas sends only the schemas and three example values per column, so it reasons from names and formats. It can propose a link that the data does not support, and it cannot see values beyond those examples. Every idea is drawn dashed and labelled as unchecked until the agent runs the join. One call costs a few cents. |
| Joins are still the agent's | The tab shows the `pd.merge` line and a button that asks the agent to run it; nothing joins without a question. |
| Tables only | No images, audio or PDF. Free-text columns are left out of models. |
| Date formats | "03/04/2024" is read the American way, as March 4 |

### 3.3 Analysis

| Gap | Detail |
|---|---|
| No real forecasting | A time column orders the split. There is no ARIMA, no seasonal model, no prediction interval, no forecast beyond the data. On the sales sample the best model scores R² 0.96 in training and 0.56 on the later period, because tree models cannot extend a trend. |
| No tuning | Models run with fixed settings |
| Four model families | No neural networks, no clustering, no survival analysis |
| No tool for experiments | No A/B test sizing, no correction for running many tests |
| Importance, not explanation | No SHAP values, no partial dependence, no explanation of one prediction |
| Related features split importance | `tenure_months` and `signup_date` measure the same thing, and each gets part of the credit |

### 3.4 The agent

| Gap | Detail |
|---|---|
| No memory between sessions | Restarting the server ends every chat. The chat list in the sidebar is the server's memory; files a chat saved stay under `workspace/<id>/` but nothing reopens them. |
| Chats are separate, not private | Two chats never see each other's data unless a dataset is brought across, but all of them belong to whoever can reach the server. |
| The chart's own explanation is a template | The sentence under a dashboard chart is written from its numbers (the median, the largest bar, the strongest pair). It says what is large, never what it means; *Ask the agent* is there for that. |
| A report the agent writes is the agent's | `export_report` puts the agent's Markdown into a PDF or a deck as written. The file inherits every mistake in the text; the sidebar export is the same tool applied to answers you have already read. |
| Slides are a summary | A deck keeps up to 7 points per answer, 4 slides per answer, 10 rows per table. The PDF keeps everything. |
| No limit on conversation length | The whole history is sent each time. Cost grows with length. |
| Nothing checks the answer | See 2.5 |
| It rarely asks a clarifying question | It is told to proceed on the most reasonable reading |
| One agent | No second model reviews the first one's work |
| Charts in the chat are static | PNG images. The dashboard's charts are interactive (hover, pick a column, click a cell), but a chart the agent draws in answer to a question is a picture. |
| The dashboard's "what stands out" is a heuristic | It reports what is *large*: the strongest correlation, the biggest group gap, the worst missing column. It cannot know what is *important*, which is why the context form exists. |
| Follow-up questions depend on the model | The agent is asked to end each answer with a `followups` block. If it does not, the buttons fall back to nothing rather than to a guess. Whether Sonnet 5 does this reliably has not been measured (3.1). |
| The detail level is an instruction, not a guarantee | "Brief" asks for five sentences. Nothing truncates an answer that ignores it. |

### 3.5 Security and deployment

| Gap | Detail |
|---|---|
| The code guard is not a sandbox | It refuses obvious dangers. Code still runs with your permissions. |
| No login | Anyone who can reach the server can use it |
| One user | Sessions are held in memory in one process |
| Data leaves the laptop | Column names, statistics and sample values go to Anthropic |
| Prompt injection | Text inside an uploaded file is shown to the model. A cell that says "ignore your instructions" is a real risk, and it is not defended against. |

---

## 4. Where to take it next

Ordered by value. The first three should come before anything else.

| # | Task | Why | Size |
|---|---|---|---|
| 1 | Run it with a real key. Fix what breaks. | Nothing else can be judged until this works | Hours |
| 2 | Score the agent on `tests/eval_questions.md` | Turns "it seems good" into a number that can improve | 1 day |
| 3 | Measure cost per question | The assignment has a budget | Hours |
| 4 | Add a reviewer: a second model call that checks the answer against the tool results | Addresses 2.5, the largest risk | 2 days |
| 5 | Add real forecasting | The most common request the agent handles badly | 3 days |
| 6 | Run the worker in a container with no network | Turns the guard into a real boundary | 2 days |
| 7 | Save chats to disk | Survive a restart; the chat list already exists | 1 day |
| 8 | Interactive charts in the chat, not only in the dashboard | A better demonstration | 2 days |
| 9 | Connect to a database | Most real data is not in a file | 3 days |
| 10 | Trim long conversations | Cost control | 1 day |
| 11 | Let the user confirm or correct a join key | The Relationships tab guesses; a confirmed key could be remembered and passed to the agent | 1 day |

### A way to divide it among five

| Person | Area | Files |
|---|---|---|
| 1 | Agent quality: the prompt, tool descriptions, the evaluation set | `app/agent/`, `tests/eval_questions.md` |
| 2 | Modelling: forecasting, tuning, explanation | `app/analytics/modeling.py` |
| 3 | Data: more formats, databases, large files, joins | `app/analytics/loading.py`, `worker.py` |
| 4 | Interface: interactive charts, saved sessions, the report | `app/static/`, `app/report.py` |
| 5 | Trust: the reviewer, the sandbox, prompt injection, this document | `app/analytics/guard.py`, `engine.py` |

---

## The argument in one paragraph

The agent is fast and careful at the parts of analysis that can be written down: load,
check, chart, test, model, report. It applies a checklist without getting tired or
skipping a step. What it lacks is everything outside the file: why the question matters,
what the data means, what would happen under a different choice, and who answers when it
is wrong. Those are the parts of the job that need a person. The value of a human data
scientist moves from producing the analysis to deciding what to analyse, judging whether
to believe it, and standing behind it.
