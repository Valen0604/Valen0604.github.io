"""
The analysis worker: one process per chat session.

It holds the datasets and trained models in memory, and runs every analysis, including
code the model writes. The web server talks to it over a pipe (see engine.py).

Why a separate process:
  * a runaway computation can be killed without taking the web server down
  * variables persist between questions, like cells in a notebook
  * the API key never enters this process, so generated code cannot read it
"""
from __future__ import annotations

import ast
import builtins
import contextlib
import io
import os
import re
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------------------
# Nothing above this line may import pandas or matplotlib: secrets are removed first.
# ---------------------------------------------------------------------------------------


def _strip_secrets() -> None:
    for key in list(os.environ):
        if key.startswith(("ANTHROPIC_", "OPENAI_", "AWS_", "AZURE_", "GOOGLE_")) or \
                "API_KEY" in key or "TOKEN" in key or "SECRET" in key:
            os.environ.pop(key, None)


class ToolError(ValueError):
    """A request the worker refuses. The message is written for the model to act on."""


MAX_STDOUT = 8000
MAX_VALUE = 4000
MAX_FIGURES = 8
HASH_CELL_LIMIT = 3_000_000


class State:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.uploads = workspace / "uploads"
        self.artifacts = workspace / "artifacts"
        self.snapshots = workspace / "datasets"
        self.models_dir = workspace / "models"
        for d in (self.uploads, self.artifacts, self.snapshots, self.models_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.datasets: dict = {}
        self.notes: dict[str, list[str]] = {}
        self.origin: dict[str, dict] = {}
        # Goes up every time a dataset is loaded, changed or created, so the server can
        # tell which dashboards are stale without comparing data.
        self.versions: dict[str, int] = {}
        self.active: str | None = None
        self.models: dict = {}
        self.namespace: dict = {}
        self.pending_tables: list[dict] = []
        # Continue numbering from what is already on disk, so a restarted worker never
        # overwrites a chart or model from earlier in the session.
        used = [int(m.group(1)) for f in list(self.artifacts.iterdir()) + list(self.models_dir.iterdir())
                if (m := re.search(r"_(\d{3,})", f.stem))]
        self.counter = max(used, default=0)

    # ------------------------------------------------------------------ helpers
    def next_id(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}_{self.counter:03d}"

    def get(self, name: str | None, activate: bool = True):
        """A dataset by name, or the active one. A tool call makes the dataset it names
        the active one; a request from the interface (a dashboard, a download) does not."""
        if not self.datasets:
            raise ToolError("No dataset is loaded. Ask the user to upload a file.")
        if not name:
            name = self.active or next(iter(self.datasets))
        if name not in self.datasets:
            raise ToolError(f'No dataset named "{name}". Loaded datasets: '
                            f"{list(self.datasets)}")
        if activate:
            self.active = name
        return name, self.datasets[name]

    def unique_name(self, name: str) -> str:
        if name not in self.datasets:
            return name
        i = 2
        while f"{name}_{i}" in self.datasets:
            i += 1
        return f"{name}_{i}"

    def manifest(self) -> list[dict]:
        return [{"name": n, **self.origin[n], "notes": self.notes.get(n, []),
                 "version": self.versions.get(n, 0)}
                for n in self.datasets]

    def bump(self, name: str) -> None:
        self.versions[name] = self.versions.get(name, 0) + 1

    def kind_of(self, name: str) -> str:
        """uploaded: as the file was. modified: an upload that code changed. created: made
        during the session (a merge, an aggregate, predictions)."""
        origin = self.origin.get(name, {})
        if origin.get("source") == "upload":
            return "uploaded"
        return "modified" if origin.get("upload_origin") else "created"

    def listing(self) -> list[dict]:
        from . import schema as S
        out = []
        for name, df in self.datasets.items():
            k = S.kinds(df)
            out.append({"name": name, "rows": int(len(df)), "columns_count": int(df.shape[1]),
                        "active": name == self.active,
                        "source": self.origin[name].get("source"),
                        "kind": self.kind_of(name),
                        "version": self.versions.get(name, 0),
                        "columns": [{"name": str(c), "kind": k[str(c)]} for c in df.columns]})
        return out

    def snapshot(self, name: str) -> None:
        """Save a changed or derived dataset, so it survives a worker restart."""
        df = self.datasets[name]
        path = self.snapshots / f"{name}.parquet"
        try:
            df.to_parquet(path, index=False)
        except Exception:
            path = self.snapshots / f"{name}.pkl"
            df.to_pickle(path)
        self.origin[name] = {"source": "derived", "path": str(path)}
        self.bump(name)


def _fingerprint(df) -> tuple:
    """
    (kind, shape, ...) A cheap signature used to tell whether code changed a dataset.

    Small frames are hashed by content, so `df = df.dropna()` on data with nothing to drop
    is correctly seen as no change. Large frames fall back to object identity.
    """
    import pandas as pd
    shape = (df.shape, tuple(map(str, df.columns)), tuple(map(str, df.dtypes)))
    if df.size <= HASH_CELL_LIMIT:
        try:
            return ("hash", *shape, int(pd.util.hash_pandas_object(df, index=True).sum()))
        except Exception:
            pass
    return ("id", *shape, id(df))


# ---------------------------------------------------------------------------- handlers
def _describe(df, name: str, notes) -> dict:
    """Profile, dashboard and the text brief for one dataset, in one place."""
    from . import dashboard, profiling
    p = profiling.profile(df, name, notes)
    d = dashboard.build(df, name, p)
    brief = profiling.brief(p)
    lines = dashboard.summary_lines(d)
    if lines:
        brief += ("\nFirst look (computed by the application; say which of these matter):\n"
                  + "\n".join(lines))
    return {"name": name, "profile": p, "dashboard": d, "brief": brief}


def op_load_file(state: State, path: str, original_name: str) -> dict:
    from . import loading
    loaded = loading.read_any(path, original_name)
    out = []
    for key, (df, notes) in loaded.items():
        name = state.unique_name(key)
        state.datasets[name] = df
        state.notes[name] = notes
        state.origin[name] = {"source": "upload", "path": path,
                              "original_name": original_name, "key": key}
        state.bump(name)
        state.active = name
        out.append({**_describe(df, name, notes), "version": state.versions[name]})
    return {"datasets": out}


def op_dashboard(state: State, dataset: str | None = None) -> dict:
    """Recompute the profile and dashboard, for a dataset that code has changed."""
    name, df = state.get(dataset, activate=False)
    return {**_describe(df, name, state.notes.get(name)),
            "version": state.versions.get(name, 0), "kind": state.kind_of(name)}


def op_relations(state: State) -> dict:
    """How the loaded datasets relate: join keys, shared dimensions, value overlap."""
    from . import relations
    rel = relations.build(state.datasets, {n: state.kind_of(n) for n in state.datasets})
    return {"relations": rel, "versions": dict(state.versions)}


def op_restore(state: State, manifest: list[dict]) -> dict:
    """Reload datasets after a restart. Originals come from the upload, the rest from disk."""
    import pandas as pd
    from . import loading
    restored, failed = [], []
    cache: dict[str, dict] = {}
    for item in manifest:
        name = item["name"]
        try:
            if item["source"] == "upload":
                if item["path"] not in cache:
                    cache[item["path"]] = loading.read_any(item["path"], item["original_name"])
                df, notes = cache[item["path"]][item["key"]]
            else:
                p = Path(item["path"])
                df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_pickle(p)
                notes = item.get("notes", [])
            state.datasets[name] = df
            state.notes[name] = notes
            state.origin[name] = {k: v for k, v in item.items()
                                  if k not in ("name", "notes", "version")}
            state.versions[name] = int(item.get("version", 0)) or 1
            state.active = name
            restored.append(name)
        except Exception as e:
            failed.append({"name": name, "error": str(e)})
    return {"restored": restored, "failed": failed}


def op_list(state: State) -> dict:
    return {"datasets": state.listing()}


def op_profile(state: State, dataset: str | None = None) -> dict:
    from . import profiling
    name, df = state.get(dataset)
    p = profiling.profile(df, name, state.notes.get(name))
    return {"profile": p, "brief": profiling.brief(p)}


def op_preview(state: State, dataset: str | None = None, rows: int = 20) -> dict:
    from . import schema as S
    name, df = state.get(dataset)
    return {"dataset": name, "table": S.table_payload(df.head(rows), max_rows=rows)}


def op_chart(state: State, dataset: str | None = None, spec: dict | None = None,
             style: dict | None = None) -> dict:
    from . import plotting
    name, df = state.get(dataset)
    plotting.set_style(style)
    file = f"{state.next_id('chart')}.png"
    result = plotting.make_chart(df, spec or {}, state.artifacts / file)
    return {"dataset": name, "file": file, **result}


def op_suggest_charts(state: State, dataset: str | None = None) -> dict:
    from . import plotting
    name, df = state.get(dataset)
    return {"dataset": name, "specs": plotting.suggest_charts(df)}


def op_stat_test(state: State, dataset: str | None = None, spec: dict | None = None) -> dict:
    from . import stats
    name, df = state.get(dataset)
    return {"dataset": name, **stats.run_test(df, spec or {})}


def op_train(state: State, dataset: str | None = None, spec: dict | None = None) -> dict:
    import joblib
    from . import modeling
    name, df = state.get(dataset)
    model_id = state.next_id("model")
    result, bundle = modeling.train(df, spec or {}, state.artifacts, model_id, name)
    state.models[model_id] = bundle
    joblib.dump(bundle, state.models_dir / f"{model_id}.joblib")
    result["model_file"] = f"{model_id}.joblib"
    return result


def op_predict(state: State, model_id: str, dataset: str | None = None) -> dict:
    from . import modeling
    from . import schema as S
    if model_id not in state.models:
        saved = state.models_dir / f"{model_id}.joblib"
        if not saved.exists():
            known = sorted(p.stem for p in state.models_dir.glob("*.joblib"))
            raise ToolError(f'No model "{model_id}". Trained models: {known}')
        import joblib
        state.models[model_id] = joblib.load(saved)      # survives a worker restart
    name, df = state.get(dataset)
    scored, summary = modeling.predict(df, state.models[model_id])
    new = state.unique_name(f"{name}_predictions")
    state.datasets[new] = scored
    state.notes[new] = [f'Rows of "{name}" scored with {model_id}.']
    state.snapshot(new)
    file = f"{new}.csv"
    scored.to_csv(state.artifacts / file, index=False)
    lead = [summary["prediction_column"]] + [c for c in scored.columns if c.startswith("probability_")]
    shown = scored[lead + [c for c in scored.columns if c not in lead]]
    return {**summary, "new_dataset": new, "download": file,
            "table": S.table_payload(shown.head(15), max_rows=15), "manifest": state.manifest()}


EXPORT_FORMATS = ("csv", "xlsx", "parquet")


def op_export(state: State, dataset: str | None = None, format: str = "csv") -> dict:
    """Write a dataset as it is now to the artifacts folder, for download or hand-over."""
    name, df = state.get(dataset, activate=False)
    if format not in EXPORT_FORMATS:
        raise ToolError(f"format must be one of {EXPORT_FORMATS}.")
    file = f"{name}.{format}"
    path = state.artifacts / file
    if format == "csv":
        df.to_csv(path, index=False)
    elif format == "xlsx":
        df.to_excel(path, index=False, sheet_name=name[:31] or "data")
    else:
        try:
            df.to_parquet(path, index=False)
        except Exception:
            # Mixed-type object columns do not fit parquet; text does.
            df.astype({c: str for c in df.columns if df[c].dtype == object}).to_parquet(path, index=False)
    return {"dataset": name, "download": file, "rows": int(len(df)), "format": format,
            "kind": state.kind_of(name)}


def op_reset(state: State, dataset: str) -> dict:
    from . import loading
    if dataset not in state.datasets:
        raise ToolError(f'No dataset named "{dataset}".')
    origin = state.origin[dataset]
    original = origin.get("upload_origin") or (origin if origin["source"] == "upload" else None)
    if not original:
        raise ToolError(f'"{dataset}" was created during the session, so there is no '
                        "uploaded file to reset it to.")
    df, notes = loading.read_any(original["path"], original["original_name"])[original["key"]]
    state.datasets[dataset] = df
    state.notes[dataset] = notes
    state.origin[dataset] = original
    state.bump(dataset)
    return {"dataset": dataset, "rows": int(len(df)), "columns_count": int(df.shape[1]),
            "manifest": state.manifest()}


def op_remove(state: State, dataset: str) -> dict:
    if dataset not in state.datasets:
        raise ToolError(f'No dataset named "{dataset}".')
    for d in (state.datasets, state.notes, state.origin, state.versions):
        d.pop(dataset, None)
    if state.active == dataset:
        state.active = next(iter(state.datasets), None)
    return {"removed": dataset, "manifest": state.manifest()}


# ------------------------------------------------------------------- running model code
def _safe_open(state: State):
    real_open = builtins.open
    root = state.workspace.resolve()

    def opener(file, mode="r", *args, **kwargs):
        target = Path(file)
        target = (root / target if not target.is_absolute() else target).resolve()
        if not target.is_relative_to(root):
            raise PermissionError("Files outside the session folder cannot be opened.")
        return real_open(target, mode, *args, **kwargs)
    return opener


def _make_namespace(state: State) -> dict:
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import scipy.stats as scipy_stats
    import seaborn as sns
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    from . import schema as S

    def show(obj, title: str | None = None) -> None:
        """Display a table in the chat. Use for any DataFrame the user should see."""
        if isinstance(obj, pd.Series):
            obj = obj.to_frame()
        if not isinstance(obj, pd.DataFrame):
            raise TypeError("show() takes a DataFrame or a Series.")
        state.pending_tables.append({"title": title or "Table",
                                     **S.table_payload(obj, max_rows=50)})

    def save_dataset(name: str, frame) -> str:
        """Keep a DataFrame as a named dataset, so later questions can use it."""
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("save_dataset() takes a DataFrame.")
        clean_name = re.sub(r"[^0-9a-zA-Z_]+", "_", str(name)).strip("_").lower() or "data"
        state.datasets[clean_name] = frame.reset_index(drop=True)
        state.notes.setdefault(clean_name, ["Created during the session by analysis code."])
        return clean_name

    safe_builtins = {k: v for k, v in vars(builtins).items()
                     if k not in {"eval", "exec", "compile", "input", "breakpoint", "exit",
                                  "quit", "help", "open", "memoryview"}}
    safe_builtins["open"] = _safe_open(state)
    real_import = builtins.__import__

    from . import guard

    def limited_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.split(".")[0] in guard.BLOCKED_MODULES:
            raise ImportError(f"import of '{name}' is not allowed in analysis code")
        return real_import(name, globals, locals, fromlist, level)

    safe_builtins["__import__"] = limited_import
    return {"__builtins__": safe_builtins, "__name__": "__analysis__",
            "pd": pd, "np": np, "plt": plt, "sns": sns, "stats": scipy_stats,
            "sm": sm, "smf": smf, "show": show, "save_dataset": save_dataset}


def _short_traceback(code: str) -> str:
    """The traceback with only the lines that point into the model's own code."""
    import sys
    etype, value, tb = sys.exc_info()
    lines = code.splitlines()
    frames = [f for f in traceback.extract_tb(tb) if f.filename == "<analysis>"]
    out = []
    for f in frames[-3:]:
        src = lines[f.lineno - 1].strip() if 0 < f.lineno <= len(lines) else ""
        out.append(f"  line {f.lineno}: {src}")
    out.append(f"{etype.__name__}: {value}")
    return "\n".join(out)


def _trim(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    head = limit * 2 // 3
    return (text[:head] + f"\n... [{len(text) - limit:,} characters left out] ...\n"
            + text[-(limit - head):]), True


def op_exec(state: State, code: str, style: dict | None = None) -> dict:
    import matplotlib.pyplot as plt
    import pandas as pd
    from . import guard, plotting
    from . import schema as S

    plotting.set_style(style)
    problems = guard.check(code)
    if problems:
        raise ToolError("The code was not run. " + "; ".join(problems)
                        + ". Rewrite it without these, using pandas, numpy, scipy, "
                          "statsmodels, scikit-learn, matplotlib and seaborn.")

    if not state.namespace:
        state.namespace = _make_namespace(state)
    ns = state.namespace
    ns["datasets"] = state.datasets
    active = state.active if state.active in state.datasets else next(iter(state.datasets), None)
    if active:
        ns["df"] = state.datasets[active]
    else:
        ns.pop("df", None)

    before = {n: _fingerprint(d) for n, d in state.datasets.items()}
    state.pending_tables = []
    plt.close("all")
    plotting.apply_style()

    tree = ast.parse(code, filename="<analysis>")
    last = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last = ast.Expression(tree.body.pop().value)
        ast.fix_missing_locations(last)

    out, err = io.StringIO(), io.StringIO()
    value, error = None, None
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                builtins.exec(builtins.compile(tree, "<analysis>", "exec"), ns)
                if last is not None:
                    value = builtins.eval(builtins.compile(last, "<analysis>", "eval"), ns)
    except BaseException as e:  # user code may raise anything, including SystemExit
        if isinstance(e, KeyboardInterrupt):
            raise
        error = _short_traceback(code)

    # ---- figures the code drew
    figures = []
    for num in plt.get_fignums()[:MAX_FIGURES]:
        fig = plt.figure(num)
        if not fig.axes:
            continue
        title = (fig._suptitle.get_text() if getattr(fig, "_suptitle", None) is not None
                 else "") or fig.axes[0].get_title() or "Chart"
        file = f"{state.next_id('figure')}.png"
        plotting.save(fig, state.artifacts / file)
        figures.append({"file": file, "title": title})
    plt.close("all")

    # ---- the value of the last line, notebook style
    value_text = None
    if value is not None:
        if isinstance(value, (pd.DataFrame, pd.Series)):
            frame = value.to_frame() if isinstance(value, pd.Series) else value
            state.pending_tables.append({"title": "Result", **S.table_payload(frame, 50)})
            with pd.option_context("display.max_rows", 30, "display.max_columns", 30,
                                   "display.width", 200):
                value_text = repr(value)
        else:
            value_text = repr(value)
        value_text, _ = _trim(value_text, MAX_VALUE)

    # ---- did the code change a dataset?
    if isinstance(ns.get("df"), pd.DataFrame) and active and ns["df"] is not state.datasets.get(active):
        state.datasets[active] = ns["df"]
    changes = []
    for name, df in list(state.datasets.items()):
        if not isinstance(df, pd.DataFrame):
            state.datasets.pop(name)
            continue
        old = before.get(name)
        if old is not None and old == _fingerprint(df):
            continue
        if old is None:
            state.notes.setdefault(name, ["Created during the session by analysis code."])
        elif state.origin.get(name, {}).get("source") == "upload":
            keep = state.origin[name]
            state.snapshot(name)
            state.origin[name]["upload_origin"] = keep      # so reset_dataset can undo it
            changes.append({"dataset": name, "change": "modified",
                            "rows_before": old[1][0], "rows": int(len(df)),
                            "columns_before": old[1][1], "columns_count": int(df.shape[1])})
            continue
        prior = state.origin.get(name, {}).get("upload_origin")
        state.snapshot(name)
        if prior:
            state.origin[name]["upload_origin"] = prior
        changes.append({"dataset": name, "change": "created" if old is None else "modified",
                        "rows_before": old[1][0] if old else None, "rows": int(len(df)),
                        "columns_before": old[1][1] if old else None,
                        "columns_count": int(df.shape[1])})

    stdout, cut = _trim(out.getvalue(), MAX_STDOUT)
    return {"stdout": stdout, "stdout_truncated": cut, "stderr": _trim(err.getvalue(), 1500)[0],
            "value": value_text, "error": error, "figures": figures,
            "tables": state.pending_tables, "dataset_changes": changes,
            "manifest": state.manifest()}


HANDLERS = {
    "load_file": op_load_file, "restore": op_restore, "list": op_list,
    "profile": op_profile, "preview": op_preview, "chart": op_chart,
    "suggest_charts": op_suggest_charts, "dashboard": op_dashboard,
    "relations": op_relations,
    "stat_test": op_stat_test, "train": op_train,
    "predict": op_predict, "export": op_export, "reset": op_reset, "remove": op_remove,
    "exec": op_exec,
}


def worker_main(conn, workspace: str) -> None:
    """Entry point of the worker process. Loops until the pipe closes."""
    _strip_secrets()
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)

    from .loading import LoadError
    from .modeling import ModelError
    from .plotting import ChartError
    from .stats import StatError
    expected = (ToolError, LoadError, ChartError, StatError, ModelError)

    state = State(root)
    conn.send({"ok": True, "result": {"ready": True}})
    while True:
        try:
            message = conn.recv()
        except (EOFError, OSError):
            break
        op = message.get("op")
        if op == "shutdown":
            break
        handler = HANDLERS.get(op)
        try:
            if handler is None:
                raise ToolError(f"Unknown operation: {op}")
            result = handler(state, **message.get("args", {}))
            if op in ("load_file", "restore"):
                result["manifest"] = state.manifest()
            conn.send({"ok": True, "result": result})
        except expected as e:
            conn.send({"ok": False, "kind": "request", "error": str(e)})
        except MemoryError:
            conn.send({"ok": False, "kind": "internal",
                       "error": "Out of memory. Work on a sample or fewer columns."})
        except Exception as e:
            conn.send({"ok": False, "kind": "internal",
                       "error": f"{type(e).__name__}: {e}",
                       "traceback": traceback.format_exc(limit=6)})
    with contextlib.suppress(Exception):
        conn.close()
