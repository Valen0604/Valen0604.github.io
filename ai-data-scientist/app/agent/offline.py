"""
Offline demo mode: what runs when there is no API key.

This is NOT the agent. It matches keywords and column names in the message and calls one
tool. It cannot plan, cannot write code, cannot interpret a result, and cannot recover
from a request it does not recognise. It exists so that:

  * the whole pipeline (upload, tools, charts, models, the interface) can be tested and
    demonstrated before the team has a key
  * the difference between this and the real agent is visible. Everything this mode
    cannot do is what the LLM adds.

It emits the same events as the real agent, so the front-end does not know the difference.
"""
from __future__ import annotations

import re

from ..config import ENV_FILE, Settings
from ..sessions import Session
from .loop import Emit, Recorder
from .tools import ToolOutcome

BANNER = (f"**Offline demo mode.** No API key is configured, so requests are matched by "
          f"keyword and cannot be interpreted. Add a key to `{ENV_FILE.name}` to use the "
          f"agent.")

HELP = """I can run these without an API key. Name the columns exactly as they appear.

| Ask for | Example |
|---|---|
| An overview | `profile the data` |
| The first rows | `show the first rows` |
| Missing values | `show missing values` |
| A distribution | `histogram of monthly_charge` |
| A comparison | `bar chart of contract` or `box plot of tenure_months by contract` |
| A relationship | `scatter of tenure_months vs total_charges` |
| A trend | `units_sold over time` |
| Correlations | `correlation heatmap` |
| A test | `is churned related to contract?` |
| A model | `predict churned` or `predict churned without cancellation_reason` |
| How the datasets relate | `how are the datasets related?` (with two or more loaded) |
| A report file | `make a pdf` or `make slides` |
| Your own code | paste it in a ```python code block |
"""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def find_columns(text: str, columns: list[str]) -> list[str]:
    """
    Columns named in the message, in the order they are mentioned.

    `monthly charge`, `monthly_charge` and `Monthly-Charge` all match `monthly_charge`.
    Longer names are matched first, so `total_charges` is not also read as `charges`.
    """
    raw = text.lower()
    spans: list[tuple[int, int, str]] = []
    for col in sorted(columns, key=len, reverse=True):
        tokens = [t for t in re.split(r"[\s_\-]+", col.lower()) if t]
        if not tokens:
            continue
        pattern = r"(?<![0-9a-z_])" + r"[\s_\-]+".join(map(re.escape, tokens)) + r"(?![0-9a-z_])"
        for m in re.finditer(pattern, raw):
            start, end = m.span()
            if any(s <= start and end <= e for s, e, _ in spans):
                continue                      # inside a longer name already matched
            spans.append((start, end, col))
            break
    return [col for _, _, col in sorted(spans)]


def _has(text: str, *words: str) -> bool:
    return any(re.search(rf"\b{w}", text) for w in words)


class OfflineAgent:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run_turn(self, session: Session, text: str, emit: Emit) -> list[dict]:
        rec = Recorder(emit)
        session.take_briefs()
        rec.notice(BANNER, "warning")
        self._counter = 0

        listing = session.engine.call("list")["datasets"]
        if not listing:
            rec.text("Upload a file to begin, or load one of the sample datasets.\n\n" + HELP)
            return rec.parts

        active = next((d for d in listing if d["active"]), listing[0])
        for d in listing:                          # a dataset named in the message wins
            if d["name"].lower() in text.lower():
                active = d
        kinds = {c["name"]: c["kind"] for c in active["columns"]}
        low = text.lower()
        if _has(low, "pdf", "slide", "deck", "presentation", "powerpoint", "report file",
                "export the report", "make a report", "write a report"):
            self._export(session, rec, low)
        elif len(listing) >= 2 and _has(low, "dataset", "file", "table") and \
                _has(low, "relat", "join", "link", "merge", "connect", "common column"):
            self._relations(session, rec)
        else:
            self._route(session, rec, text, active["name"], kinds)
        # Without a model there is nothing to write follow-ups; offer things this mode
        # can run, so the buttons still work.
        session.suggestions = self._followups(kinds, text)
        rec.suggestions(session.suggestions)
        return rec.parts

    @staticmethod
    def _followups(kinds: dict[str, str], text: str) -> list[str]:
        numeric = [c for c, k in kinds.items() if k == "numeric"]
        cats = [c for c, k in kinds.items() if k in ("categorical", "boolean")]
        dates = [c for c, k in kinds.items() if k == "datetime"]
        ideas = []
        if numeric and cats:
            ideas.append(f"box plot of {numeric[0]} by {cats[-1]}")
        if dates and numeric:
            ideas.append(f"{numeric[0]} over time")
        if len(numeric) >= 2:
            ideas.append(f"scatter of {numeric[0]} vs {numeric[1]}")
        if cats:
            ideas.append(f"predict {cats[-1]}")
        ideas.append("show missing values")
        low = text.lower()
        return [i for i in ideas if i.lower() != low][:3]

    # ------------------------------------------------------------ several datasets
    def _relations(self, session: Session, rec: Recorder) -> None:
        """How the datasets relate: the same numbers the Relationships tab shows."""
        rel = session.engine.call("relations", timeout_s=120)["relations"]
        rec.text("How the loaded datasets relate, from shared column names and values:\n\n"
                 + "\n".join("- " + line for line in rel["summary"])
                 + "\n\nThe Relationships tab shows the same as a graph, with the matched "
                   "and unmatched rows for each link."
                 + ("\n\nTo join two of them, paste this in a ```python block:\n\n```python\n"
                    + "\n".join(rel["merges"][:3]) + "\n```" if rel["merges"] else ""))

    def _export(self, session: Session, rec: Recorder, low: str) -> None:
        """A PDF or a deck of the conversation so far. The real agent writes the report
        itself; this mode can only collect what was already shown."""
        fmt = "pptx" if _has(low, "slide", "deck", "presentation", "powerpoint") else "pdf"
        lines, charts = [], []
        for item in session.transcript:
            if item["role"] == "user":
                lines.append(f'\n## {item["text"]}\n')
            elif item["role"] == "assistant":
                for p in item.get("parts", []):
                    if p["type"] == "text" and p["text"].strip():
                        lines.append(p["text"])
                    elif p["type"] == "tool":
                        for c in p.get("cards") or []:
                            if c["type"] == "chart":
                                lines.append(f'\n![{c.get("title") or ""}]({c["file"]})\n')
                                charts.append(c["file"])
        if not charts and len(lines) <= 1:
            rec.text("There is nothing to put in a report yet. Ask for a chart or a "
                     "profile first, then ask for the PDF or the slides again.")
            return
        out = self._call(session, rec, "export_report", {
            "format": fmt, "title": "Analysis so far",
            "content": "\n".join(lines) or "No text answers were written in offline mode.",
            "charts": charts})
        rec.text(out.text if out.is_error else
                 f"The {'slides are' if fmt == 'pptx' else 'PDF is'} ready above. In offline "
                 "mode it collects what the chat already showed; the agent would write the "
                 "findings itself. You can also export any answer from the sidebar.")

    # ------------------------------------------------------------------ plumbing
    def _call(self, session: Session, rec: Recorder, name: str, args: dict) -> ToolOutcome:
        self._counter += 1
        tool_id = f"offline_{len(session.transcript)}_{self._counter}"
        rec.tool_start(tool_id, name)
        rec.tool_running(tool_id, name, args)
        rec.status(f"Running {name}")
        outcome = session.toolbox.run(name, args)
        rec.tool_done(tool_id, name, outcome)
        return outcome

    # -------------------------------------------------------------------- routing
    def _route(self, session, rec, text, dataset, kinds) -> None:
        low = text.lower()
        cols = find_columns(text, list(kinds))
        numeric = [c for c in cols if kinds[c] == "numeric"]
        dates = [c for c, k in kinds.items() if k == "datetime"]
        base = {"dataset": dataset}

        code = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
        if code:
            out = self._call(session, rec, "run_python",
                             {"code": code.group(1), "purpose": "Code from your message"})
            rec.text("The code failed. The error is shown above." if out.is_error
                     else "Ran your code. The output is shown above.")
            return

        if _has(low, "help", "what can you"):
            rec.text(HELP)
            return

        if _has(low, "predict", "model", "forecast", "classif", "regress", "train", "driver"):
            if not cols:
                rec.text("Name the column to predict, for example `predict churned`.")
                return
            m = re.search(r"\b(?:without|exclud\w*|except|drop\w*|ignor\w*)\b(.*)", low)
            exclude = find_columns(m.group(1), list(kinds)) if m else []
            targets = [c for c in cols if c not in exclude]
            if not targets:
                rec.text("Name the column to predict, for example `predict churned`.")
                return
            args = {**base, "target": targets[0]}
            if exclude:
                args["exclude"] = exclude
            if dates and _has(low, "time", "forecast", "chronolog"):
                args["time_column"] = dates[0]
            out = self._call(session, rec, "train_model", args)
            rec.text(out.text if out.is_error else
                     "The model card above has the scores, the comparison with the "
                     "baseline, and any warnings. Read the warnings first.")
            return

        if _has(low, "missing", "null", "gaps"):
            out = self._call(session, rec, "create_chart", {**base, "chart_type": "missing"})
            rec.text(out.text if out.is_error else "Share of missing values in each column.")
            return

        if _has(low, "heatmap") or (_has(low, "correlat") and len(cols) < 2):
            spec = {**base, "chart_type": "heatmap"}
            if len(numeric) >= 2:
                spec["columns"] = numeric
            out = self._call(session, rec, "create_chart", spec)
            rec.text(out.text if out.is_error else
                     "Correlations among the numeric columns.")
            return

        if _has(low, "significan", "related", "relationship", "associat", "differ",
                "compare", "test", "correlat", "affect", "depend") and len(cols) >= 2:
            out = self._call(session, rec, "run_statistical_test",
                             {**base, "test": "auto", "x": cols[0], "y": cols[1]})
            rec.text(out.text if out.is_error else out.summary)
            return

        if _has(low, "histogram", "distribution", "spread of") and cols:
            spec = {**base, "chart_type": "histogram", "x": (numeric or cols)[0]}
            self._chart(session, rec, spec)
            return

        if _has(low, "scatter") or (_has(low, " vs ", "versus", "against") and len(numeric) >= 2):
            if len(numeric) < 2:
                rec.text("A scatter plot needs two numeric columns.")
                return
            spec = {**base, "chart_type": "scatter", "x": numeric[0], "y": numeric[1]}
            others = [c for c in cols if c not in numeric]
            if others:
                spec["color"] = others[0]
            self._chart(session, rec, spec)
            return

        if _has(low, "box"):
            if not numeric:
                rec.text("A box plot needs a numeric column.")
                return
            spec = {**base, "chart_type": "box", "y": numeric[0]}
            groups = [c for c in cols if c not in numeric]
            if groups:
                spec["x"] = groups[0]
            self._chart(session, rec, spec)
            return

        if _has(low, "trend", "over time", "time series", "timeline", "monthly", "weekly",
                "daily") and dates:
            if not numeric:
                rec.text("Name the numeric column to plot over time.")
                return
            spec = {**base, "chart_type": "line", "x": dates[0], "y": numeric[0],
                    "agg": "sum" if _has(low, "total", "sum") else "mean"}
            groups = [c for c in cols if kinds[c] in ("categorical", "boolean")]
            if groups:
                spec["color"] = groups[0]
            self._chart(session, rec, spec)
            return

        if _has(low, "bar", "count", "how many", "breakdown", "by ") and cols:
            groups = [c for c in cols if c not in numeric] or cols
            spec = {**base, "chart_type": "bar", "x": groups[0]}
            if numeric and groups[0] not in numeric:
                spec.update(y=numeric[0], agg="sum" if _has(low, "total", "sum") else "mean")
            self._chart(session, rec, spec)
            return

        if _has(low, "preview", "head", "first", "rows", "show me the data", "sample"):
            self._call(session, rec, "preview_rows", {**base, "rows": 10})
            rec.text("The first rows of the data.")
            return

        if _has(low, "profile", "overview", "summar", "describe", "explor", "eda",
                "quality", "clean", "about", "tell me"):
            out = self._call(session, rec, "profile_dataset", base)
            if out.is_error:
                rec.text(out.text)
                return
            for spec in session.engine.call("suggest_charts", dataset=dataset)["specs"][:3]:
                self._call(session, rec, "create_chart", {**base, **spec})
            rec.text("The profile lists every column and the data-quality warnings, most "
                     "serious first. The charts were chosen from the column types, not "
                     "from any reading of what the data is about.")
            return

        if len(numeric) == 1 and len(cols) == 1:
            self._chart(session, rec, {**base, "chart_type": "histogram", "x": numeric[0]})
            return
        if len(cols) == 1:
            self._chart(session, rec, {**base, "chart_type": "bar", "x": cols[0]})
            return

        rec.text("I could not match that to anything I can do without an API key.\n\n" + HELP)

    def _chart(self, session, rec, spec) -> None:
        out = self._call(session, rec, "create_chart", spec)
        rec.text(out.text if out.is_error else
                 "Chart drawn. Without an API key I cannot interpret it.")
