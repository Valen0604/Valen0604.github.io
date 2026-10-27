"""
The tools the model can call, and the code that runs them.

Each tool has three parts:

  1. a schema, which the model reads to decide when and how to call it
  2. a handler, which forwards the call to the analysis worker
  3. a ToolOutcome: text for the model, and cards for the user's screen

To add a tool: write its schema in TOOLS, write a `_tool_<name>` handler, and add a
renderer for its card in app/static/render.js. Nothing else needs to change.
"""
from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from ..analytics.engine import Engine, EngineError
from ..analytics.plotting import AGGREGATIONS, CHART_TYPES
from ..analytics.stats import TESTS
from ..config import Settings

DATASET = {"type": "string",
           "description": "Name of the dataset to use. Leave out to use the active one "
                          "(the most recently uploaded or used)."}

TOOLS: list[dict] = [
    {
        "name": "profile_dataset",
        "description": (
            "Describe a dataset: every column with its type, missing values and summary "
            "statistics, the strongest correlations, and data-quality warnings such as "
            "placeholder values, duplicate rows, inconsistent categories and gaps that are "
            "not random. Call this when the user asks what is in the data or how clean it "
            "is, and again after code has changed a dataset. Do not call it if the "
            "description attached to the upload already answers the question."),
        "input_schema": {"type": "object", "properties": {"dataset": DATASET}},
    },
    {
        "name": "preview_rows",
        "description": ("Show the first rows of a dataset as a table. Call this when the "
                        "user asks to see the data, or when you need to see raw values "
                        "to understand a column."),
        "input_schema": {"type": "object", "properties": {
            "dataset": DATASET,
            "rows": {"type": "integer", "description": "How many rows, 1 to 50. Default 10."},
        }},
    },
    {
        "name": "create_chart",
        "description": (
            "Draw a standard chart and return the numbers behind it. Call this for any "
            "request to plot, chart, graph or visualise that one of these types covers:\n"
            "- histogram: distribution of one numeric column (x). Optional color.\n"
            "- bar: a category (x) against a count, or against an aggregate of a numeric "
            "column (y with agg).\n"
            "- line: a numeric column (y) over a date or ordered column (x). Dates are "
            "grouped by day, week, month or year automatically.\n"
            "- scatter: two numeric columns (x, y), with a trend line and correlations.\n"
            "- box: spread of a numeric column (y), optionally split by a category (x).\n"
            "- heatmap: correlations among numeric columns. Optional columns list.\n"
            "- missing: share of missing values in each column.\n"
            "- pairs: scatter matrix of up to 5 numeric columns.\n"
            "For anything else, such as facets, dual axes or annotations, draw it with "
            "matplotlib or seaborn in run_python."),
        "input_schema": {"type": "object", "required": ["chart_type"], "properties": {
            "dataset": DATASET,
            "chart_type": {"type": "string", "enum": CHART_TYPES},
            "x": {"type": "string", "description": "Column for the x axis or the grouping."},
            "y": {"type": "string", "description": "Numeric column for the y axis."},
            "color": {"type": "string",
                      "description": "Column to split by colour. At most 8 groups are kept."},
            "agg": {"type": "string", "enum": AGGREGATIONS,
                    "description": "How to combine y within each group. Default: count for "
                                   "bar, mean for line."},
            "columns": {"type": "array", "items": {"type": "string"},
                        "description": "Columns for heatmap or pairs. Default: all numeric."},
            "top": {"type": "integer",
                    "description": "bar only: keep this many categories. Default 15."},
            "bins": {"type": "integer", "description": "histogram only."},
            "freq": {"type": "string", "enum": ["D", "W", "MS", "QS", "YS"],
                     "description": "line only: group dates by day, week, month, quarter "
                                    "or year. Default: chosen from the date range."},
            "method": {"type": "string", "enum": ["spearman", "pearson"],
                       "description": "heatmap only. Default spearman."},
            "title": {"type": "string", "description": "Chart title. A default is written "
                                                       "if this is left out."},
        }},
    },
    {
        "name": "run_statistical_test",
        "description": (
            "Test whether a relationship or a difference is real, and how large it is. "
            "Returns the p-value together with an effect size, the assumptions that were "
            "checked, and a one-sentence reading. Call this when the user asks whether "
            "something is significant, whether groups differ, or whether two columns are "
            "related. Use test=auto with two columns in x and y, and the right test is "
            "chosen from the column types: correlation for two numeric columns, "
            "chi-squared for two categories, a t-test or ANOVA for a numeric column "
            "across groups."),
        "input_schema": {"type": "object", "properties": {
            "dataset": DATASET,
            "test": {"type": "string", "enum": TESTS, "description": "Default auto."},
            "x": {"type": "string", "description": "First column."},
            "y": {"type": "string", "description": "Second column."},
            "value": {"type": "string",
                      "description": "ttest and anova: the numeric column being compared."},
            "group": {"type": "string",
                      "description": "ttest and anova: the column that defines the groups."},
        }},
    },
    {
        "name": "train_model",
        "description": (
            "Train and evaluate predictive models for one target column. Compares a "
            "do-nothing baseline, a linear model, a random forest and gradient boosting "
            "with cross-validation, then scores the best one on a test set it never saw. "
            "Returns test metrics, the baseline's metrics, permutation importance, and "
            "warnings about leakage, class imbalance, overfitting and small samples. "
            "Identifier and free-text columns are left out automatically. Call this when "
            "the user asks to predict, forecast, classify, model, or find what drives an "
            "outcome. If the data is ordered in time, pass time_column so the test set is "
            "a later period than the training set. Takes 5 to 60 seconds."),
        "input_schema": {"type": "object", "required": ["target"], "properties": {
            "dataset": DATASET,
            "target": {"type": "string", "description": "The column to predict."},
            "task": {"type": "string", "enum": ["auto", "classification", "regression"],
                     "description": "Default auto: chosen from the target's type."},
            "features": {"type": "array", "items": {"type": "string"},
                         "description": "Columns to use. Default: every usable column."},
            "exclude": {"type": "array", "items": {"type": "string"},
                        "description": "Columns to leave out, for example one flagged as "
                                       "leakage or one derived from the target."},
            "time_column": {"type": "string",
                            "description": "Date column that orders the rows in time."},
            "models": {"type": "array", "items": {"type": "string", "enum": [
                "logistic_regression", "ridge_regression", "random_forest",
                "gradient_boosting"]},
                "description": "Limit the comparison to these. The baseline always runs."},
            "test_size": {"type": "number",
                          "description": "Share of rows held back for testing, 0.05 to 0.5. "
                                         "Default 0.2."},
        }},
    },
    {
        "name": "predict",
        "description": ("Score the rows of a dataset with a model trained earlier in this "
                        "conversation. Adds prediction columns, saves the result as a new "
                        "dataset and gives the user a CSV to download. Call this when the "
                        "user asks to apply a model to data, including a newly uploaded "
                        "file with the same columns."),
        "input_schema": {"type": "object", "required": ["model_id"], "properties": {
            "model_id": {"type": "string",
                         "description": "The model_id returned by train_model."},
            "dataset": DATASET,
        }},
    },
    {
        "name": "run_python",
        "description": (
            "Run Python in a session that keeps its variables between calls, like cells in "
            "a notebook. Call this for cleaning, reshaping, joining, custom aggregation, "
            "custom charts, and any method the other tools do not cover.\n\n"
            "Already defined: pd, np, plt, sns, stats (scipy.stats), sm (statsmodels.api), "
            "smf (statsmodels.formula.api). scikit-learn can be imported.\n"
            "- `df` is the active dataset. `datasets` is a dict of all of them by name.\n"
            "- The value of the last line is returned, as in a notebook. print() works.\n"
            "- A DataFrame on the last line is shown to the user as a table. Call "
            "show(frame, 'title') to display others.\n"
            "- Every matplotlib figure left open is shown to the user. Do not call "
            "plt.show() or savefig(). Set a title on each figure.\n"
            "- To change the active dataset, assign to it: `df = df.dropna()`. To keep a "
            "new one, call save_dataset('name', frame).\n\n"
            "Not available: the network, the file system outside the session folder, "
            "subprocesses. Code is stopped after about 90 seconds, so sample large data."),
        "input_schema": {"type": "object", "required": ["code"], "properties": {
            "code": {"type": "string", "description": "The Python source to run."},
            "purpose": {"type": "string",
                        "description": "What this code does, in a few words. Shown to the "
                                       "user above the code."},
        }},
    },
    {
        "name": "list_datasets",
        "description": ("List the datasets in this session with their sizes and columns. "
                        "Call this when you are unsure what is loaded or what a dataset "
                        "is called."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "reset_dataset",
        "description": ("Undo every change made to an uploaded dataset and return it to "
                        "the file as uploaded. Call this when the user asks to start over "
                        "or when cleaning went wrong."),
        "input_schema": {"type": "object", "required": ["dataset"], "properties": {
            "dataset": {"type": "string", "description": "Name of the dataset to reset."}}},
    },
    {
        "name": "export_dataset",
        "description": ("Give the user a download of a dataset as it is now, including "
                        "changes made during the session and datasets created with "
                        "save_dataset. Call this when the user asks to download, export "
                        "or save data. Every dataset can also be downloaded from the "
                        "sidebar, so mention that when the user asks how."),
        "input_schema": {"type": "object", "properties": {
            "dataset": DATASET,
            "format": {"type": "string", "enum": ["csv", "xlsx", "parquet"],
                       "description": "Default csv."},
        }},
    },
    {
        "name": "export_report",
        "description": (
            "Write a report file the user can download: a PDF document, or a slide deck "
            "(.pptx). Call this when the user asks for a PDF, a report file, a document, "
            "slides, a deck or a presentation of the findings. Write the body yourself in "
            "`content` as Markdown: `##` headings for sections, short paragraphs, lists "
            "and pipe tables; no title line, the title is a separate input. Place a chart "
            "from this conversation where it belongs with a line of the form "
            "`![caption](chart_003.png)`, using the file names from earlier tool results; "
            "charts listed in `charts` but not placed in the text are added at the end. "
            "Every number must come from a tool result in this conversation. For slides, "
            "each section becomes one slide of a few short points, plus one slide per "
            "chart and per table, so keep sections short and put one message in each."),
        "input_schema": {"type": "object", "required": ["format", "title", "content"],
                         "properties": {
            "format": {"type": "string", "enum": ["pdf", "pptx"]},
            "title": {"type": "string", "description": "The report or deck title."},
            "content": {"type": "string", "description": "The body, in Markdown."},
            "charts": {"type": "array", "items": {"type": "string"},
                       "description": "Chart files from this conversation to include, in "
                                      "order, for example [\"chart_001.png\"]."},
        }},
    },
]

# Streamed requests send large inputs (code) as they are written, not in one burst at the
# end. The cost is that the API no longer validates the input, so validate() below does.
for _tool in TOOLS:
    _tool["eager_input_streaming"] = True
    _tool["input_schema"].setdefault("required", [])

BY_NAME = {t["name"]: t for t in TOOLS}


# ---------------------------------------------------------------------------- validation
_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool,
          "array": list, "object": dict}


def validate(name: str, args: object) -> str | None:
    """Check a tool call against its schema. Returns a message, or None if it is valid."""
    tool = BY_NAME.get(name)
    if tool is None:
        return f"There is no tool named {name}. Tools: {list(BY_NAME)}."
    if not isinstance(args, dict):
        return "The input must be a JSON object."
    schema = tool["input_schema"]
    props = schema["properties"]
    missing = [k for k in schema.get("required", []) if args.get(k) in (None, "")]
    if missing:
        return f"Missing required input: {missing}."
    unknown = [k for k in args if k not in props]
    if unknown:
        return f"Unknown input {unknown}. Accepted: {list(props)}."
    for key, value in list(args.items()):
        if value is None:
            continue
        spec = props[key]
        expected = _TYPES[spec["type"]]
        if spec["type"] == "integer" and isinstance(value, float) and value.is_integer():
            value = args[key] = int(value)          # JSON has one number type: 10.0 is 10
        if isinstance(value, bool) and spec["type"] != "boolean":
            return f"{key} must be a {spec['type']}."
        if not isinstance(value, expected):
            return f"{key} must be a {spec['type']}."
        if "enum" in spec and value not in spec["enum"]:
            return f"{key} must be one of {spec['enum']}."
        if spec["type"] == "array":
            item = spec.get("items", {})
            for v in value:
                if not isinstance(v, _TYPES[item.get("type", "string")]):
                    return f"Every item of {key} must be a {item.get('type')}."
                if "enum" in item and v not in item["enum"]:
                    return f"Items of {key} must be from {item['enum']}."
    return None


# ------------------------------------------------------------------------------ outcome
@dataclass
class ToolOutcome:
    text: str                                        # what the model reads
    cards: list[dict] = field(default_factory=list)  # what the user sees
    images: list[Path] = field(default_factory=list) # charts the model may look at
    is_error: bool = False
    summary: str = ""                                # one line for the activity log


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def _limit(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return (text[:limit] + f"\n[Output cut: {len(text) - limit:,} more characters. "
            "Ask for less at a time, for example fewer columns or an aggregate.]")


class Toolbox:
    """Runs tools for one session."""

    def __init__(self, engine: Engine, settings: Settings):
        self.engine = engine
        self.settings = settings
        self.style = {"palette": "single"}       # chart colours, chosen in the sidebar
        self.datasets_for_report = lambda: []    # set by the server: datasets to list

    @property
    def artifacts(self) -> Path:
        return self.engine.workspace / "artifacts"

    def run(self, name: str, args: dict) -> ToolOutcome:
        problem = validate(name, args)
        if problem:
            return ToolOutcome(text=f"Invalid call to {name}. {problem}", is_error=True,
                               summary="invalid input")
        try:
            outcome = getattr(self, f"_tool_{name}")(**args)
        except EngineError as e:
            text = str(e)
            if e.kind == "internal" and e.detail:
                text += f"\n{e.detail[-1200:]}"
            return ToolOutcome(text=text, is_error=True, summary=str(e)[:140],
                               cards=[{"type": "error", "tool": name, "message": str(e)}]
                               if e.kind != "request" else [])
        outcome.text = _limit(outcome.text, self.settings.max_tool_output_chars)
        return outcome

    # ------------------------------------------------------------------------ tools
    def _tool_profile_dataset(self, dataset=None) -> ToolOutcome:
        r = self.engine.call("profile", dataset=dataset)
        p = r["profile"]
        return ToolOutcome(text=r["brief"], cards=[{"type": "profile", "profile": p}],
                           summary=f'{p["name"]}: {p["rows"]:,} rows, '
                                   f'{len(p["warnings"])} warnings')

    def _tool_preview_rows(self, dataset=None, rows=10) -> ToolOutcome:
        rows = max(1, min(int(rows or 10), 50))
        r = self.engine.call("preview", dataset=dataset, rows=rows)
        t = r["table"]
        return ToolOutcome(
            text=_json({"dataset": r["dataset"], "columns": t["columns"], "rows": t["rows"]}),
            cards=[{"type": "table", "title": f'First {len(t["rows"])} rows of '
                                              f'{r["dataset"]}', **t}],
            summary=f'{len(t["rows"])} rows of {r["dataset"]}')

    def _tool_create_chart(self, dataset=None, **spec) -> ToolOutcome:
        r = self.engine.call("chart", dataset=dataset, spec=spec, style=self.style)
        return ToolOutcome(
            text=_json({"chart": r["title"], "file": r["file"], "dataset": r["dataset"],
                        "data": r["summary"]}),
            cards=[{"type": "chart", "file": r["file"], "title": r["title"]}],
            images=[self.artifacts / r["file"]], summary=r["title"])

    def _tool_run_statistical_test(self, dataset=None, **spec) -> ToolOutcome:
        r = self.engine.call("stat_test", dataset=dataset, spec=spec)
        return ToolOutcome(text=_json(r), cards=[{"type": "stat", "result": r}],
                           summary=r.get("plain", r.get("test", "")))

    def _tool_train_model(self, dataset=None, **spec) -> ToolOutcome:
        r = self.engine.call("train", timeout_s=self.settings.model_timeout_s,
                             dataset=dataset, spec=spec)
        for_model = {k: v for k, v in r.items() if k not in ("charts", "model_file")}
        return ToolOutcome(
            text=_json(for_model), cards=[{"type": "model", "result": r}],
            images=[self.artifacts / c["file"] for c in r["charts"][1:2]],
            summary=r["headline"])

    def _tool_predict(self, model_id, dataset=None) -> ToolOutcome:
        r = self.engine.call("predict", model_id=model_id, dataset=dataset)
        table = r.pop("table")
        return ToolOutcome(
            text=_json(r),
            cards=[{"type": "table", "title": f'Predictions ({r["new_dataset"]})', **table},
                   {"type": "download", "file": r["download"],
                    "label": f'Download {r["rows"]:,} scored rows (CSV)'}],
            summary=f'{r["rows"]:,} rows scored with {model_id}')

    def _tool_run_python(self, code, purpose=None) -> ToolOutcome:
        r = self.engine.call("exec", timeout_s=self.settings.code_timeout_s, code=code,
                             style=self.style)
        for_model = {"stdout": r["stdout"] or None, "value": r["value"], "error": r["error"],
                     "warnings": r["stderr"] or None,
                     "figures": [{"title": f["title"], "file": f["file"]}
                                 for f in r["figures"]] or None,
                     "tables_shown": [t["title"] for t in r["tables"]] or None,
                     "dataset_changes": r["dataset_changes"] or None}
        if r["error"] is None and not any(v for k, v in for_model.items() if k != "error"):
            for_model["note"] = ("The code ran and produced no output. End with an "
                                 "expression or print() to see a result.")
        cards = [{"type": "code", "code": code, "purpose": purpose, "stdout": r["stdout"],
                  "value": r["value"] if not r["tables"] else None, "error": r["error"],
                  "changes": r["dataset_changes"]}]
        cards += [{"type": "table", **t} for t in r["tables"]]
        cards += [{"type": "chart", **f} for f in r["figures"]]
        return ToolOutcome(
            text=_json({k: v for k, v in for_model.items() if v is not None} or
                       {"note": "no output"}),
            cards=cards, images=[self.artifacts / f["file"] for f in r["figures"][:3]],
            is_error=r["error"] is not None,
            summary=(purpose or "ran code") + (" (failed)" if r["error"] else ""))

    def _tool_list_datasets(self) -> ToolOutcome:
        r = self.engine.call("list")
        brief = [{"name": d["name"], "rows": d["rows"], "active": d["active"],
                  "columns": {c["name"]: c["kind"] for c in d["columns"]}}
                 for d in r["datasets"]]
        return ToolOutcome(text=_json(brief), summary=f'{len(brief)} dataset(s)')

    def _tool_reset_dataset(self, dataset) -> ToolOutcome:
        r = self.engine.call("reset", dataset=dataset)
        return ToolOutcome(text=_json(r), summary=f'{dataset} reset to the uploaded file',
                           cards=[{"type": "notice", "message":
                                   f'"{dataset}" was reset to the file as uploaded '
                                   f'({r["rows"]:,} rows).'}])

    def _tool_export_dataset(self, dataset=None, format="csv") -> ToolOutcome:
        r = self.engine.call("export", dataset=dataset, format=format or "csv")
        return ToolOutcome(
            text=_json(r), summary=f'{r["dataset"]} exported',
            cards=[{"type": "download", "file": r["download"],
                    "label": f'Download {r["dataset"]} ({r["rows"]:,} rows, '
                             f'{r["format"].upper()})'}])

    def _tool_export_report(self, format, title, content, charts=None) -> ToolOutcome:
        from ..export import document, pdf, slides
        doc = document.from_markdown(title, content, self.artifacts, charts or [],
                                     model=self.settings.model if self.settings.live else "",
                                     datasets=self.datasets_for_report())
        data = pdf.render(doc) if format == "pdf" else slides.render(doc)
        n = 1 + sum(1 for p in self.artifacts.glob("report_*"))
        file = f"report_{n:03d}.{format}"
        (self.artifacts / file).write_bytes(data)
        missing = [c for c in (charts or []) if c not in doc["images"]]
        text = {"file": file, "format": format, "sections": len(doc["sections"]),
                "charts_included": sorted(doc["images"]),
                "kilobytes": round(len(data) / 1024)}
        if missing:
            text["charts_not_found"] = missing
        what = "PDF report" if format == "pdf" else "slide deck"
        return ToolOutcome(
            text=_json(text), summary=f"{what}: {file}",
            cards=[{"type": "download", "file": file,
                    "label": f"Download the {what}: {doc['title']} ({format.upper()}, "
                             f"{text['kilobytes']} KB)"}])


# ------------------------------------------------------------------- images for the model
def image_block(path: Path, max_side: int = 1000) -> dict | None:
    """A chart as an image block, scaled down so it costs fewer tokens."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            if max(im.size) > max_side:
                im.thumbnail((max_side, max_side))
            buf = io.BytesIO()
            im.save(buf, format="PNG", optimize=True)
    except Exception:
        return None
    data = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": data}}


def tool_result_block(tool_use_id: str, outcome: ToolOutcome, with_images: bool) -> dict:
    """The block that reports a tool's outcome back to the model."""
    content: list[dict] = [{"type": "text", "text": outcome.text or "(no output)"}]
    if with_images and not outcome.is_error:
        content += [b for b in (image_block(p) for p in outcome.images) if b]
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if outcome.is_error:
        block["is_error"] = True
    return block
