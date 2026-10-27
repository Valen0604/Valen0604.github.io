# AI Data Scientist

> **Portfolio snapshot.** This folder is a copy of the committed files of the team repository
> `Valen0604/ai-data-scientist`, taken on 26 October 2026 after the in-class presentation.
> It is included to show the code and the design; the project README below is as written
> for the team. See the portfolio [README](../README.md) for a summary and for my part in it.

A chat application that analyses data. You upload a file and ask a question in plain
language. An AI agent decides what analysis answers it, runs that analysis as real code on
your data, and explains the result. It runs on your laptop.

This is the base version. It is meant to be improved by the team. What it cannot do, and
why, is in [LIMITATIONS.md](LIMITATIONS.md).

---

## Start here

You need Python 3.10 or newer. Setup creates the project's own Python in `.venv`, so
nothing is installed into your system.

| | Windows | macOS or Linux |
|---|---|---|
| 1. Set up (once) | `.\setup.bat` | `bash setup.sh` |
| 2. Add the key | open `.env`, paste the key | open `.env`, paste the key |
| 3. Start | `.\run.bat` | `bash run.sh` |

The terminal says `Starting`, then `Ready` with the address, and the browser opens at
http://127.0.0.1:8000 at that moment. Stop it with Ctrl+C.

On Windows, type the leading `.\` or double-click the file. PowerShell, which is the
default terminal in VS Code, does not run a script from the current folder without it.

### If it does not start

Run the self-check. It prints one line per thing the app needs, and what to do about any
that fails:

```
.venv\Scripts\python -m app --check          (Windows)
.venv/bin/python -m app --check              (macOS, Linux)
```

The usual causes:

| What you see | Cause | Fix |
|---|---|---|
| `Starting` and then nothing for a minute | First start on a new computer: matplotlib builds its font cache once | Wait. The next start takes seconds. |
| `Port 8000 is already in use` | An earlier copy is still running | Open http://127.0.0.1:8000, or stop the other copy, or set `ADS_PORT=8001` in `.env` |
| The browser says the page cannot be found | The tab opened before the server was ready (older versions) | Reload the page once the terminal says `Ready` |
| `The project is not set up yet` | `.venv` is missing | Run setup once |
| An error ending in `ModuleNotFoundError` | A package did not install | Run setup again; it is safe to repeat |

If the self-check passes and the app still does not load, copy the terminal output into
the team chat.

### Where the API key goes

Setup creates a file named `.env` in the project folder. Open it and put the key on the
first setting:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Then restart the app. To test the key before starting:

```
.venv\Scripts\python scripts\check_key.py      (Windows)
.venv/bin/python scripts/check_key.py          (macOS, Linux)
```

- Get a key at https://console.anthropic.com/ under **API keys**. Add a few dollars of
  credit under **Billing**.
- `.env` is git-ignored. Do not commit it, and do not paste the key into chat.
- Each teammate needs their own `.env`. The key is not shared through the repository.

### With no key

The app still starts, in **offline demo mode**. It matches keywords in your message to one
tool. It cannot interpret a question, plan, or write code. It is there so you can test and
demonstrate everything except the language model. Type `help` in the chat to see what it
recognises.

---

## What it does

**Before you ask anything.** When a file loads, you get three things with no model call:

| | Where | What |
|---|---|---|
| A dashboard | the **Dashboard** tab | what stands out (the likely outcome column, the strongest relationships, the biggest group differences, trends, serious data problems), then distributions, categories, a time series, a correlation heatmap and a group comparison. Interactive: pick a column, hover a bar, click a correlation cell to see the points. |
| A data-quality report | the **Data quality** tab | every warning, grouped into serious, worth checking and notes, one card each. The badge on the tab counts them. |
| A short form | a dialog, once | what the data is, what you want to decide, what cannot be done. Optional, and editable later from the sidebar. The agent reads it before every analysis and will not recommend an action it rules out. |

**How much detail you get** is yours to choose, in the sidebar: *Brief* (a few sentences, no
method names), *Standard*, or *Technical* (methods, assumptions, intervals). The level
changes how the answer is written, never what is computed.

**After every answer** the agent writes two or three follow-up questions. They appear as
buttons above the message box; click one to ask it.

**Several files at once.** Upload them all. Each gets its own dashboard, and the
**Relationships** tab shows how they fit together: which columns could join them (a
customer id that is unique in one file and repeated in another), which columns they
merely share (a region, a month), and how well the values actually match, with the rows
that have no match on the other side and the `pd.merge` line that would join them. It is
computed from column names and values, with no model call, and the same summary is given
to the agent so it uses the right keys when you ask it to merge.

The map can be zoomed (scroll or the buttons), moved (drag the background) and rearranged
(drag a box). Pick the two datasets to compare at the top, or click a box or a line; the
links for that pair are listed under the map. With many files the labels show only for the
pair you chose. **Ask the model for relationship ideas** sends the column names, types and
three example values per column (not the data) in one request, apart from the chat, and
draws what comes back as dashed purple lines: links the values cannot show, such as a key
with a prefix on one side or a date that lines up with a month, each with a reason, the
transform it would need and a button that asks the agent to check it on the data. The
model also gives a verdict on each link the values found. Nothing from the model is
verified until the agent runs the join; the cards say so.

**Every chart explains itself.** Under each dashboard chart a line says what it shows in
words, and it changes to describe whatever you point at: this bar is 312 rows, 10% of the
data, above the median. *Ask the agent* sends that sentence to the chat as a question.

**Datasets the agent makes are yours.** A merge, an aggregate or a scored table that the
agent keeps with `save_dataset` appears in the sidebar marked ✦, with a dashboard, a
data-quality report and a download (CSV, Excel or Parquet). A dataset the agent changes
gets its dashboard recomputed after the reply.

**Several chats.** The sidebar lists every open chat. Each one holds its own datasets in
its own analysis process, so two projects never see each other's data. *From another chat*
copies one dataset across when you want that; it is the only way data crosses.

**Chart colours.** *One blue* draws a single-series chart in one hue, the way a careful
chart is drawn. *Varied* gives each category its own hue, in a fixed order that keeps
neighbouring colours apart for colour-blind readers, and a new hue to each chart in turn.

**Reports.** *Export PDF / slides* saves the answers you tick as a PDF (full text, tables
and charts) or as a slide deck (.pptx: one slide of main points per answer, plus one per
chart and per table), with or without the dashboards' findings and the code. Asking the
agent for "a PDF report" or "slides" does the same through its own tool, with the report
text written for the purpose. *Print* opens the full report with the print dialog;
*HTML* saves the whole conversation as one file that opens anywhere.

| You ask | What runs |
|---|---|
| "What's in this data?" | A profile of every column, plus data-quality checks |
| "Plot sales by region" | One of 8 chart types, or a custom chart in Python |
| "Is the difference between groups real?" | A statistical test chosen from the column types, with an effect size |
| "What drives churn?" | Four models compared against a baseline and scored on held-out data |
| "Score this new file" | Predictions from a model trained earlier in the conversation |
| "Remove duplicates and fix the region names" | Python the agent writes, with the row counts before and after |
| "Join the orders to the customers" | Python the agent writes, using the keys the Relationships tab found; the result is a dataset you can download |
| "Write this up as a PDF" or "make slides" | A report file written by the agent, with the charts from the conversation |
| anything else | Python the agent writes |

It reads CSV, TSV, Excel (every sheet), JSON and Parquet.

Checks that run without being asked:

| Check | Example from the sample data |
|---|---|
| Placeholder values | `age` is 999 in 6 rows while every other value is 18 to 90 |
| Inconsistent categories | `region` contains "North", "north" and "NORTH " |
| Gaps that are not random | `monthly_charge` is missing more often for older customers |
| Leakage | `cancellation_reason` is filled in only for customers who left |
| Computed columns | `revenue` is `units_sold` times `unit_price`, so it cannot be used to predict `units_sold` |
| Identifiers | `customer_id` is left out of models |
| A model no better than guessing | every score is shown next to the baseline's |
| Overfitting | training and test scores are compared |
| Time order | a random split on dated data produces a warning |

---

## How it works

```
 Browser                        Web server                       Analysis worker
 app/static/                    app/main.py                      app/analytics/worker.py
 ┌───────────────┐   HTTP      ┌─────────────────────┐   pipe   ┌────────────────────┐
 │ chat, upload, │ ──────────► │ sessions, uploads   │ ───────► │ holds the data     │
 │ charts, cards │ ◄────────── │                     │ ◄─────── │ runs every analysis│
 └───────────────┘   stream    │  agent loop         │          │ runs model-written │
                               │  app/agent/loop.py  │          │ Python             │
                               └──────────┬──────────┘          └────────────────────┘
                                          │ HTTPS                 one process per chat,
                                          ▼                       no API key, time limit
                                    Claude API
```

**What happens when you send a message:**

1. The server sends the conversation and the list of 11 tools to Claude.
2. Claude replies with text, or asks for a tool: "draw a bar chart of `contract`".
3. The server checks the request against the tool's schema and passes it to the worker.
4. The worker runs it on the data and returns numbers, tables and chart files.
5. The server sends the result back to Claude, including a picture of any chart.
6. Steps 2 to 5 repeat until Claude answers without asking for a tool.

The browser receives each step as it happens, so you watch the work.

**Three design decisions, and why:**

| Decision | Why |
|---|---|
| The model never computes a number. Code does. | A language model asked for a mean will produce a plausible one. Every number in an answer comes from code that ran, and the code is one click away. |
| Analysis runs in a separate process. | Code that runs forever can be stopped without stopping the server. The process never receives the API key, so code the model writes cannot read it. |
| Purpose-built tools sit beside free-form Python. | `train_model` always uses a baseline and a held-out test set. Left to write its own modelling code, a model sometimes skips them. Python covers everything the tools do not. |

---

## Project layout

```
app/
  config.py            settings, and where the key is read
  doctor.py            the self-check behind "python -m app --check"
  main.py              web server and routes
  sessions.py          one chat: data, history, cost; the store that lists every open chat
  report.py            the full report: one HTML file, or the printable page
  export/
    markdown.py        reads the Markdown the agent writes into blocks
    document.py        a document from chosen answers, or from the agent's own report text
    pdf.py             the document as a PDF (reportlab)
    slides.py          the document as a slide deck (python-pptx)
  agent/
    prompts.py         the system prompt           <- how the agent behaves
    tools.py           tool definitions            <- what the agent can do
    loop.py            the agent loop              <- the core, about 250 lines
    offline.py         keyword fallback used when there is no key
  analytics/                                       no LLM anywhere in this folder
    loading.py         reads files, infers types, records what it changed
    schema.py          decides what kind of column each one is
    profiling.py       column summaries and data-quality checks
    dashboard.py       the first-look dashboard: highlights and the numbers behind its charts
    relations.py       how several datasets relate: join keys, shared columns, value overlap
  agent/relations_ai.py  one model call that reads the schemas and suggests links the values hide
    plotting.py        8 chart types, the validated palette, the one-hue / varied styles
    stats.py           statistical tests with effect sizes
    modeling.py        model comparison, leakage screening, importance
    guard.py           refuses obviously dangerous code
    worker.py          the analysis process
    engine.py          starts, stops and times the worker
  static/              the web page: index.html, app.js, render.js, styles.css
data/sample/           four datasets with known answers (two pairs that link), and README.md listing them
scripts/
  check_key.py         tests the API key
  make_sample_data.py  rebuilds the sample data
tests/                 121 automated tests, and eval_questions.md for testing the live agent
```

---

## Changing it

| To change | Edit |
|---|---|
| How the agent talks, what it prioritises | `app/agent/prompts.py` |
| The model, effort, limits | `.env` (options are listed in `.env.example`) |
| What a tool does | its handler in `app/agent/tools.py`, and the function it calls in `app/analytics/` |
| How a result looks | the card's function in `app/static/render.js` |
| What a chart says about itself | the `narrator(...)` sentences in `dashboard()` in `app/static/render.js` |
| How datasets are matched | the thresholds at the top of `app/analytics/relations.py` |
| Colours of the page | the variables at the top of `app/static/styles.css` |
| Colours of the charts | `PALETTE` in `app/analytics/plotting.py` and the matching `--series-N` variables in `styles.css`; keep the order, it was validated for colour-blind readers |
| The PDF or the deck | `app/export/pdf.py`, `app/export/slides.py`; both read the same document |

**To add a tool**, for example one that detects anomalies:

1. Write the analysis in `app/analytics/` as a plain function. Test it on its own.
2. Add an operation for it in `worker.py`: a function `op_anomalies` and an entry in `HANDLERS`.
3. Add its schema to `TOOLS` in `app/agent/tools.py`. In the description, say *when* to
   call it, starting with "Call this when". The model decides from that sentence.
4. Add a handler `_tool_detect_anomalies` to `Toolbox`. Return a `ToolOutcome`.
5. Add a card for its result in `render.js` and register it in `CARDS`.
6. Add a test in `tests/test_agent_loop.py`.

---

## Testing

```
.venv\Scripts\python -m pytest          (Windows)
.venv/bin/python -m pytest              (macOS, Linux)
```

128 tests, about two minutes. None of them calls the API or needs a key.

| File | What it checks |
|---|---|
| `test_analytics.py` | The engine finds every flaw planted in the sample data and ranks the true drivers first |
| `test_agent_loop.py` | The agent loop, using a scripted stand-in for the Claude API |
| `test_api.py` | A full conversation through the web server in offline mode |
| `test_api_multi.py` | Several chats that do not share data, datasets the agent creates, downloads, the relationships map, the PDF and slide exports |
| `test_export_and_relations.py` | The relationship finder on tables with a known key, the Markdown reader, both renderers, the palette |
| `test_relations_ai.py` | The model's relationship ideas: what it is shown, invented columns dropped, proved pairs turned into verdicts, the endpoint without a key |

`tests/eval_questions.md` is a set of questions with known answers for testing the live
agent by hand.

---

## Cost

Claude Sonnet 5 costs $2 per million input tokens and $10 per million output tokens. The
sidebar shows a running estimate for the session.

Three things keep the cost down:

- **Prompt caching.** The system prompt and the conversation so far are cached, and cached
  input costs a tenth of the normal price.
- **Compact tool results.** The model gets a summary of a dataset, never the rows.
- **Effort is set to medium.** Raise it in `.env` for harder questions.

The cost per question has not been measured, because no key was available during the
build. Measure it on the first day with a key.

---

## Security

This app runs code written by a language model on your computer.

- `guard.py` refuses code that imports `subprocess`, opens network connections, deletes
  files, or reads the environment. **This is a guard rail, not a security boundary.** It
  stops mistakes. It would not stop a determined attacker.
- The server listens on `127.0.0.1` only, so other computers cannot reach it.
- Do not upload data you are not allowed to send to a third party. Column names, summary
  statistics and sample values go to Anthropic's API.
- Do not deploy this on the public internet as it is. See LIMITATIONS.md.

---

## What has and has not been verified

| | Status |
|---|---|
| Analysis engine | Tested against data with known answers |
| Web server, uploads, streaming, exports, several chats | Tested end to end in offline mode |
| Front-end | Checked in Microsoft Edge, by screenshot: chat, dashboard, relationships, a dataset the agent created; the slide deck rendered in PowerPoint |
| Agent loop | Tested with a scripted stand-in for the API |
| The live agent, with a real key | Run in the in-class presentation on 26 October 2026 without issues; the 50-point hand evaluation in `tests/eval_questions.md` passed, at about $0.20 for the full set |

The request the app sends was written from the Anthropic SDK documentation and checked
against the installed SDK (version 1.9.0). If a run with a key fails, the error appears
in the chat in plain words, and `scripts/check_key.py` separates key problems from
application problems.
