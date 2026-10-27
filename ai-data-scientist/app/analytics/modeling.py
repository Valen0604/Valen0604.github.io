"""
Predictive modelling, with the guard rails a careful analyst would insist on.

What this does that a quick `model.fit(X, y)` does not:

  * compares every model against a do-nothing baseline, so "85% accuracy" on a dataset
    that is 85% one class is reported as no better than guessing
  * keeps a test set the models never see, and reports that number as the headline
  * respects time order when the data has one, so the future never predicts the past
  * screens each feature for leakage: a column that predicts the target almost perfectly
    on its own is usually a copy of the answer
  * drops identifiers and free text, and says so
  * compares training and test scores to flag overfitting
  * returns permutation importance, which is measured on held-out data

What it does not do is decide whether the question is worth asking. See LIMITATIONS.md.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix,
                             f1_score, mean_absolute_error, r2_score, roc_auc_score, roc_curve)
from sklearn.model_selection import (KFold, StratifiedKFold, TimeSeriesSplit, cross_validate,
                                     train_test_split)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from . import plotting, profiling
from . import schema as S
from .schema import clean, round_sig

CLASSIFICATION = "classification"
REGRESSION = "regression"
SEED = 42

MIN_ROWS = 50
MAX_CLASSES = 30
MIN_CLASS_ROWS = 8
MAX_MISSING_SHARE = 0.6
LEAKAGE_SCORE = 0.98
DEFAULT_MAX_ROWS = 100_000

_TRUE = {"true", "yes", "y", "1", "t"}
_FALSE = {"false", "no", "n", "0", "f"}


class ModelError(ValueError):
    """The model could not be trained. The message tells the model how to fix the request."""


@dataclass
class Bundle:
    """Everything needed to score new rows with a trained model."""
    model_id: str
    task: str
    target: str
    pipeline: Pipeline
    plan: dict                      # how each source column is turned into features
    feature_columns: list[str]      # columns of X, in order
    classes: list[str] = field(default_factory=list)
    best_model: str = ""
    trained_on: str = ""


# ---------------------------------------------------------------------- feature building
def _to01(s: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(s):
        return s.astype("float64")
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce").astype("float64")
    low = s.astype("object").map(lambda v: str(v).strip().lower() if pd.notna(v) else None)
    return low.map(lambda v: 1.0 if v in _TRUE else 0.0 if v in _FALSE else np.nan)


def build_features(df: pd.DataFrame, plan: dict) -> pd.DataFrame:
    """Turn source columns into the feature table, the same way at train and predict time."""
    missing = [c for c in plan["source_columns"] if c not in df.columns]
    if missing:
        raise ModelError(f"The data is missing column(s) the model was trained on: {missing}")
    out = {}
    for c in plan["numeric"]:
        out[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    for c in plan["boolean"]:
        out[c] = _to01(df[c])
    for c, start in plan["datetime"].items():
        d = pd.to_datetime(df[c], errors="coerce")
        out[f"{c}__year"] = d.dt.year.astype("float64")
        out[f"{c}__month"] = d.dt.month.astype("float64")
        out[f"{c}__dayofweek"] = d.dt.dayofweek.astype("float64")
        out[f"{c}__days_since_start"] = (d - pd.Timestamp(start)).dt.days.astype("float64")
    for c in plan["categorical"]:
        out[c] = df[c].astype("object").map(lambda v: str(v) if pd.notna(v) else np.nan)
    return pd.DataFrame(out, index=df.index)


def plan_features(df: pd.DataFrame, target: str, features: list[str] | None,
                  exclude: list[str] | None) -> tuple[dict, list[dict]]:
    """Decide which columns become features. Returns (plan, dropped-with-reasons)."""
    exclude = set(exclude or [])
    candidates = [c for c in (features or df.columns) if c != target and c not in exclude]
    unknown = [c for c in candidates if c not in df.columns]
    if unknown:
        raise ModelError(f"No column named {unknown}. Columns are: {list(map(str, df.columns))}")

    plan = {"numeric": [], "boolean": [], "categorical": [], "datetime": {},
            "source_columns": []}
    dropped = [{"column": c, "reason": "excluded on request"} for c in exclude if c in df.columns]
    for c in candidates:
        s = df[c]
        kind = S.column_kind(s)
        share = float(s.isna().mean())
        if kind == S.EMPTY:
            dropped.append({"column": c, "reason": "no values"})
        elif s.dropna().nunique() <= 1:
            dropped.append({"column": c, "reason": "every value is the same"})
        elif share > MAX_MISSING_SHARE:
            dropped.append({"column": c, "reason": f"{share:.0%} missing"})
        elif kind == S.ID:
            dropped.append({"column": c, "reason": "identifier: unique per row, so it "
                                                   "cannot generalise"})
        elif kind == S.TEXT:
            dropped.append({"column": c, "reason": "free text, which this tool does not model"})
        elif kind == S.NUMERIC:
            plan["numeric"].append(c)
        elif kind == S.BOOLEAN:
            plan["boolean"].append(c)
        elif kind == S.DATETIME:
            plan["datetime"][c] = str(pd.to_datetime(s, errors="coerce").min())
        else:
            plan["categorical"].append(c)
    plan["source_columns"] = (plan["numeric"] + plan["boolean"] + plan["categorical"]
                              + list(plan["datetime"]))
    if not plan["source_columns"]:
        raise ModelError("No usable feature columns are left after screening. "
                         f"Dropped: {dropped}")
    return plan, dropped


def _preprocessor(X: pd.DataFrame, plan: dict, scale: bool) -> ColumnTransformer:
    categorical = [c for c in plan["categorical"] if c in X.columns]
    numeric = [c for c in X.columns if c not in categorical]
    num_steps = [("impute", SimpleImputer(strategy="median", add_indicator=True))]
    if scale:
        num_steps.append(("scale", StandardScaler()))
    parts = []
    if numeric:
        parts.append(("num", Pipeline(num_steps), numeric))
    if categorical:
        parts.append(("cat", Pipeline([
            ("impute", SimpleImputer(strategy="constant", fill_value="(missing)")),
            ("onehot", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=0.01,
                                     max_categories=30, sparse_output=False)),
        ]), categorical))
    return ColumnTransformer(parts, remainder="drop", verbose_feature_names_out=False)


# ------------------------------------------------------------------------- task and data
def detect_task(y: pd.Series) -> tuple[str, str | None]:
    kind = S.column_kind(y)
    distinct = y.dropna().nunique()
    if kind in (S.BOOLEAN, S.CATEGORICAL, S.ID, S.TEXT):
        return CLASSIFICATION, None
    if kind == S.DATETIME:
        raise ModelError("The target is a date. Predicting a date is not supported.")
    if distinct <= 10 and (pd.to_numeric(y, errors="coerce").dropna() % 1 == 0).all():
        return CLASSIFICATION, (
            f"The target has only {distinct} distinct whole-number values, so it was treated "
            'as classes. Pass task="regression" if it is a quantity.')
    return REGRESSION, None


def _candidates(task: str, n: int, imbalanced: bool) -> dict:
    trees = 200 if n <= 20_000 else 100
    weight = "balanced" if imbalanced else None
    if task == CLASSIFICATION:
        return {
            "baseline": (DummyClassifier(strategy="prior"), False),
            "logistic_regression": (LogisticRegression(max_iter=2000, class_weight=weight), True),
            "random_forest": (RandomForestClassifier(
                n_estimators=trees, min_samples_leaf=2, class_weight=weight,
                n_jobs=-1, random_state=SEED), False),
            "gradient_boosting": (HistGradientBoostingClassifier(
                class_weight=weight, random_state=SEED), False),
        }
    return {
        "baseline": (DummyRegressor(strategy="mean"), False),
        "ridge_regression": (Ridge(alpha=1.0), True),
        "random_forest": (RandomForestRegressor(
            n_estimators=trees, min_samples_leaf=2, n_jobs=-1, random_state=SEED), False),
        "gradient_boosting": (HistGradientBoostingRegressor(random_state=SEED), False),
    }


def _leakage_suspects(X: pd.DataFrame, y: np.ndarray, task: str, plan: dict) -> list[dict]:
    """Score each feature on its own. Near-perfect alone usually means it is the answer."""
    if len(X) > 5000:
        idx = np.random.default_rng(SEED).choice(len(X), 5000, replace=False)
        X, y = X.iloc[idx], y[idx]
    suspects = []
    tree = (DecisionTreeClassifier(max_depth=4, random_state=SEED) if task == CLASSIFICATION
            else DecisionTreeRegressor(max_depth=4, random_state=SEED))
    scoring = "balanced_accuracy" if task == CLASSIFICATION else "r2"
    cv = (StratifiedKFold(3, shuffle=True, random_state=SEED) if task == CLASSIFICATION
          else KFold(3, shuffle=True, random_state=SEED))
    for c in X.columns:
        one = X[[c]]
        sub = {**plan, "categorical": [c] if c in plan["categorical"] else []}
        pipe = Pipeline([("prep", _preprocessor(one, sub, scale=False)), ("model", tree)])
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                score = cross_validate(pipe, one, y, cv=cv, scoring=scoring)["test_score"].mean()
        except Exception:
            continue
        if np.isfinite(score) and score >= LEAKAGE_SCORE:
            suspects.append({"column": c, "score_alone": round(float(score), 4),
                             "metric": scoring})
    return suspects


def _gap_leaks(df: pd.DataFrame, y: np.ndarray, task: str, target: str) -> list[dict]:
    """
    Does the mere presence of a value give the answer away?

    `cancellation_reason` is only filled in for customers who cancelled. Its content does
    not matter: whether it is blank predicts the target. Checked for every column, used or
    not, because the usual response to a mostly-empty column is to fill it in, and that
    would bring the leak into the model.
    """
    out = []
    for c in df.columns:
        if c == target:
            continue
        gap = df[c].isna().to_numpy()
        share = gap.mean()
        if share < 0.01 or share > 0.99:
            continue
        if task == CLASSIFICATION:
            labels = np.unique(y)
            score = max(balanced_accuracy_score(y, np.where(gap, a, b))
                        for a in labels for b in labels if a != b)
            metric = "balanced accuracy"
        else:
            if np.std(y) == 0:
                continue
            score = abs(float(np.corrcoef(gap.astype(float), y)[0, 1]))
            metric = "correlation"
        if score >= 0.95:
            out.append({"column": str(c), "score": round(float(score), 4), "metric": metric,
                        "missing_share": round(float(share), 4)})
    return out


# ------------------------------------------------------------------------------- charts
def _chart_comparison(cv_table: list[dict], metric: str, higher_better: bool, path: Path):
    plotting.apply_style()
    t = pd.DataFrame(cv_table).sort_values("cv_mean", ascending=not higher_better)
    fig, ax = plt.subplots(figsize=(8, 0.6 * len(t) + 2))
    colors = ["#94a3b8" if m == "baseline" else plotting.PRIMARY for m in t["model"]]
    ax.barh(t["model"], t["cv_mean"], xerr=t["cv_std"], color=colors, capsize=4)
    ax.invert_yaxis()
    ax.set_xlabel(f"{metric} (cross-validation, mean and spread)")
    ax.set_title("Model comparison" + ("" if higher_better else " (lower is better)"))
    plotting.save(fig, path)


def _chart_importance(imp: list[dict], path: Path):
    plotting.apply_style()
    t = pd.DataFrame(imp[:15])
    fig, ax = plt.subplots(figsize=(8, 0.4 * len(t) + 2))
    ax.barh(t["feature"], t["importance"], xerr=t["std"], color=plotting.PRIMARY, capsize=3)
    ax.invert_yaxis()
    ax.set_xlabel("Drop in test score when the column is shuffled")
    ax.set_title("What the model relies on (permutation importance)")
    plotting.save(fig, path)


def _chart_classification(y_true, y_pred, proba, classes: list[str], path: Path):
    plotting.apply_style()
    binary = len(classes) == 2 and proba is not None
    fig, axes = plt.subplots(1, 2 if binary else 1, figsize=(12 if binary else 6.5, 5))
    ax = axes[0] if binary else axes
    cm = confusion_matrix(y_true, y_pred, labels=range(len(classes)))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False, ax=ax,
                xticklabels=classes, yticklabels=classes, annot_kws={"size": 10})
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Confusion matrix (test set)")
    if binary:
        fpr, tpr, _ = roc_curve(y_true, proba[:, 1])
        axes[1].plot(fpr, tpr, color=plotting.PRIMARY, lw=2,
                     label=f"model (AUC {roc_auc_score(y_true, proba[:, 1]):.3f})")
        axes[1].plot([0, 1], [0, 1], color="#94a3b8", ls="--", label="guessing")
        axes[1].set_xlabel("False positive rate")
        axes[1].set_ylabel("True positive rate")
        axes[1].set_title("ROC curve (test set)")
        axes[1].legend(loc="lower right")
    plotting.save(fig, path)


def _chart_regression(y_true, y_pred, path: Path):
    plotting.apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].scatter(y_true, y_pred, s=16, alpha=0.5, color=plotting.PRIMARY, edgecolor="none")
    lo, hi = float(min(y_true.min(), y_pred.min())), float(max(y_true.max(), y_pred.max()))
    axes[0].plot([lo, hi], [lo, hi], color="#111827", ls="--", lw=1.2, label="perfect")
    axes[0].set_xlabel("Actual")
    axes[0].set_ylabel("Predicted")
    axes[0].set_title("Predicted against actual (test set)")
    axes[0].legend()
    sns.histplot(y_true - y_pred, ax=axes[1], color=plotting.PRIMARY, edgecolor="white")
    axes[1].axvline(0, color="#111827", ls="--", lw=1.2)
    axes[1].set_xlabel("Actual minus predicted")
    axes[1].set_ylabel("Rows")
    axes[1].set_title("Errors (test set)")
    plotting.save(fig, path)


# --------------------------------------------------------------------------------- train
def _metrics(task, y_true, y_pred, proba, n_classes) -> dict:
    if task == REGRESSION:
        err = y_true - y_pred
        return {"rmse": round_sig(float(np.sqrt(np.mean(err ** 2)))),
                "mae": round_sig(mean_absolute_error(y_true, y_pred)),
                "r2": round_sig(r2_score(y_true, y_pred), 4)}
    out = {"accuracy": round_sig(accuracy_score(y_true, y_pred), 4),
           "balanced_accuracy": round_sig(balanced_accuracy_score(y_true, y_pred), 4),
           "f1_macro": round_sig(f1_score(y_true, y_pred, average="macro", zero_division=0), 4)}
    if proba is not None:
        try:
            out["roc_auc"] = round_sig(
                roc_auc_score(y_true, proba[:, 1]) if n_classes == 2 else
                roc_auc_score(y_true, proba, multi_class="ovr", average="macro",
                              labels=range(n_classes)), 4)
        except ValueError:
            pass
    return out


def train(df: pd.DataFrame, spec: dict, out_dir: Path, model_id: str,
          dataset_name: str = "") -> tuple[dict, Bundle]:
    target = spec.get("target")
    if not target or target not in df.columns:
        raise ModelError(f'target must be a column name. Columns are: '
                         f'{list(map(str, df.columns))}')
    notes: list[str] = []
    warn: list[str] = []

    data = df.copy()
    missing_target = int(data[target].isna().sum())
    if missing_target:
        data = data[data[target].notna()]
        notes.append(f"{missing_target:,} rows with no {target} were left out.")

    task = (spec.get("task") or "auto").lower()
    if task == "auto":
        task, why = detect_task(data[target])
        if why:
            notes.append(why)
    if task not in (CLASSIFICATION, REGRESSION):
        raise ModelError('task must be "auto", "classification" or "regression".')

    # ---- time order
    time_column = spec.get("time_column")
    if time_column:
        if time_column not in data.columns:
            raise ModelError(f'No column named "{time_column}".')
        when = pd.to_datetime(data[time_column], errors="coerce")
        data = data[when.notna()].assign(**{time_column: when[when.notna()]})
        data = data.sort_values(time_column)

    # ---- size
    max_rows = int(spec.get("max_rows") or DEFAULT_MAX_ROWS)
    if len(data) > max_rows:
        before = len(data)
        data = data.tail(max_rows) if time_column else data.sample(max_rows, random_state=SEED)
        notes.append(f"Used {max_rows:,} of {before:,} rows to keep training fast"
                     + (" (the most recent ones)." if time_column else " (a random sample)."))

    # ---- target
    classes: list[str] = []
    if task == CLASSIFICATION:
        labels = data[target].astype(str)
        counts = labels.value_counts()
        rare = counts[counts < MIN_CLASS_ROWS]
        if len(rare):
            data = data[~labels.isin(rare.index)]
            labels = data[target].astype(str)
            notes.append(f"{len(rare)} class(es) with fewer than {MIN_CLASS_ROWS} rows were "
                         f"left out: {list(rare.index[:8])}.")
            counts = labels.value_counts()
        if len(counts) < 2:
            raise ModelError("The target needs at least 2 classes with enough rows.")
        if len(counts) > MAX_CLASSES:
            raise ModelError(f"The target has {len(counts)} classes; the limit is "
                             f"{MAX_CLASSES}. Is it really a category?")
        classes = sorted(counts.index.tolist())
        y = labels.map({c: i for i, c in enumerate(classes)}).to_numpy()
        minority = counts.min() / counts.sum()
        imbalanced = bool(minority < 0.2)
        if imbalanced:
            warn.append(f'Classes are unbalanced: "{counts.idxmin()}" is {minority:.1%} of rows. '
                        "Accuracy is misleading here; read balanced accuracy, F1 and ROC AUC. "
                        "Models were trained with class weights.")
    else:
        y_series = pd.to_numeric(data[target], errors="coerce")
        bad = int(y_series.isna().sum())
        if bad:
            data, y_series = data[y_series.notna()], y_series.dropna()
            notes.append(f"{bad:,} rows with a non-numeric {target} were left out.")
        y = y_series.to_numpy(dtype=float)
        imbalanced = False

    n = len(data)
    if n < MIN_ROWS:
        raise ModelError(f"Only {n} usable rows. At least {MIN_ROWS} are needed to train "
                         "and test a model.")
    if n < 300:
        warn.append(f"Only {n} rows. Scores will move a lot from one split to another, "
                    "so treat them as rough.")

    # ---- features
    exclude = list(spec.get("exclude") or [])
    plan, dropped = plan_features(data, target, spec.get("features"), exclude)
    if time_column and time_column in plan["datetime"] and len(plan["source_columns"]) > 1:
        # The calendar parts stay as features; the raw ordering is used for the split.
        notes.append(f"{time_column} was used to order the split. Its year, month and "
                     "weekday are also features.")
    X = build_features(data, plan)

    gap_leaks = _gap_leaks(data, y, task, target)
    used = set(plan["source_columns"])
    for g in gap_leaks:
        state = ("It is in the model" if g["column"] in used else
                 "It was left out of the model, which is the right call")
        warn.append(f'Leakage: whether "{g["column"]}" is filled in predicts {target} almost '
                    f'perfectly ({g["metric"]} {g["score"]:.2f}). It is recorded after the '
                    f"outcome is known. {state}. Do not fill in its gaps and add it back.")
    leaky = [g["column"] for g in gap_leaks if g["column"] in used]
    if leaky:
        notes.append(f"Train again with exclude={leaky} for an honest score.")

    # A feature that is arithmetic on the target: revenue = units_sold x unit_price.
    formula_leaks = []
    if task == REGRESSION:
        for d in profiling.derived_columns(data, [target] + plan["numeric"]):
            if target not in d["columns"]:
                continue
            if d["column"] != target:
                # The target is an input of the formula, so the computed column is
                # calculated from the target and cannot be known before it.
                leaks = [d["column"]] if d["column"] in used else []
                why = (f'"{d["column"]}" is computed from {target} (it is close to '
                       f'{d["formula"]}, correlation {d["r"]:.3f}), so it is not known '
                       f"before {target} is.")
            else:
                # The target is the computed column. Its inputs together give it away.
                leaks = [c for c in d["columns"] if c != target and c in used]
                if len(leaks) < 2:
                    continue
                why = (f"{target} is close to {d['formula']} (correlation {d['r']:.3f}). "
                       "If either of those is only known once the outcome has happened, "
                       "the model is being given the answer.")
            if not leaks:
                continue
            formula_leaks += [{"column": c, "score_alone": d["r"],
                               "metric": "correlation of a formula with the target"}
                              for c in leaks]
            warn.append(f"Leakage: {why} Train again with exclude={leaks[:1]} unless that "
                        "column is known in advance.")

    suspects = _leakage_suspects(X, y, task, plan)
    flagged = {g["column"] for g in gap_leaks} | {f["column"] for f in formula_leaks}
    suspects = [s for s in suspects if s["column"] not in flagged]
    for s in suspects:
        warn.append(f'Possible leakage: "{s["column"]}" predicts {target} almost perfectly on '
                    f'its own ({s["metric"]} {s["score_alone"]:.2f}). If it is recorded after '
                    f"the outcome, or derived from it, train again with it excluded.")

    # ---- split
    test_size = float(spec.get("test_size") or 0.2)
    if not 0.05 <= test_size <= 0.5:
        raise ModelError("test_size must be between 0.05 and 0.5.")
    folds = 5 if n >= 250 else 3
    if n > 50_000:
        folds = 3
    if time_column:
        cut = int(round(n * (1 - test_size)))
        X_train, X_test, y_train, y_test = X.iloc[:cut], X.iloc[cut:], y[:cut], y[cut:]
        cv = TimeSeriesSplit(n_splits=folds)
        split_text = (f"Ordered by {time_column}. The first {1 - test_size:.0%} of rows train "
                      f"the model and the last {test_size:.0%} test it, so the model is "
                      "always tested on a later period than it learned from.")
        if task == CLASSIFICATION and len(np.unique(y_train)) < len(classes):
            raise ModelError("The training period does not contain every class. Use a "
                             "larger training share or drop time_column.")
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=SEED,
            stratify=y if task == CLASSIFICATION else None)
        cv = (StratifiedKFold(folds, shuffle=True, random_state=SEED) if task == CLASSIFICATION
              else KFold(folds, shuffle=True, random_state=SEED))
        split_text = (f"Random split: {1 - test_size:.0%} of rows train the model and "
                      f"{test_size:.0%} are held back to test it.")
        if plan["datetime"]:
            warn.append("The data has a date column but the split is random. If rows are "
                        "ordered in time, pass time_column so the test set is a later period.")

    # ---- compare models
    if task == CLASSIFICATION:
        binary = len(classes) == 2
        scoring = {"accuracy": "accuracy", "balanced_accuracy": "balanced_accuracy",
                   "f1_macro": "f1_macro"}
        if binary:
            scoring["roc_auc"] = "roc_auc"
        primary, higher_better = ("roc_auc" if binary else "f1_macro"), True
    else:
        scoring = {"rmse": "neg_root_mean_squared_error", "mae": "neg_mean_absolute_error",
                   "r2": "r2"}
        primary, higher_better = "rmse", False

    wanted = spec.get("models")
    candidates = _candidates(task, len(X_train), imbalanced)
    if wanted:
        unknown = [m for m in wanted if m not in candidates]
        if unknown:
            raise ModelError(f"Unknown model(s) {unknown}. Choose from {list(candidates)}.")
        candidates = {k: v for k, v in candidates.items() if k in wanted or k == "baseline"}

    cv_table, fitted = [], {}
    for name, (estimator, scale) in candidates.items():
        pipe = Pipeline([("prep", _preprocessor(X_train, plan, scale)), ("model", estimator)])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = cross_validate(pipe, X_train, y_train, cv=cv, scoring=scoring,
                                 error_score=np.nan)
        row = {"model": name}
        for metric in scoring:
            v = res[f"test_{metric}"]
            v = -v if metric in ("rmse", "mae") else v
            row[metric] = round_sig(np.nanmean(v), 4)
            if metric == primary:
                row["cv_mean"], row["cv_std"] = float(np.nanmean(v)), float(np.nanstd(v))
        row["fit_seconds"] = round(float(np.sum(res["fit_time"])), 2)
        cv_table.append(row)
        fitted[name] = pipe

    usable = [r for r in cv_table if np.isfinite(r["cv_mean"])]
    if not usable:
        raise ModelError("Every model failed during cross-validation.")
    ranked = sorted(usable, key=lambda r: r["cv_mean"], reverse=higher_better)
    best_row = ranked[0]
    best_name = best_row["model"]
    base_row = next(r for r in cv_table if r["model"] == "baseline")

    # ---- final fit and the held-out test
    best = fitted[best_name]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        best.fit(X_train, y_train)
        base = fitted["baseline"].fit(X_train, y_train)
    proba = best.predict_proba(X_test) if task == CLASSIFICATION else None
    pred = best.predict(X_test)
    test = _metrics(task, y_test, pred, proba, len(classes))
    train_scores = _metrics(task, y_train, best.predict(X_train),
                            best.predict_proba(X_train) if task == CLASSIFICATION else None,
                            len(classes))
    base_test = _metrics(task, y_test, base.predict(X_test),
                         base.predict_proba(X_test) if task == CLASSIFICATION else None,
                         len(classes))

    # ---- does it beat doing nothing, and does it overfit?
    if best_name == "baseline":
        warn.append("No model beat the baseline. The features do not predict the target "
                    "in a way these models can use.")
    if task == REGRESSION:
        gain = 1 - test["rmse"] / base_test["rmse"] if base_test["rmse"] else 0.0
        headline = (f"{best_name} predicts {target} with a typical error (RMSE) of "
                    f"{test['rmse']:.4g} on the test set, {gain:.0%} lower than always "
                    f"guessing the mean ({base_test['rmse']:.4g}). R² = {test['r2']:.3f}.")
        if gain < 0.05 and best_name != "baseline":
            warn.append("The best model is less than 5% better than guessing the mean.")
        gap = train_scores["r2"] - test["r2"]
        if gap > 0.15:
            warn.append(f"Overfitting: R² is {train_scores['r2']:.2f} on the training rows "
                        f"and {test['r2']:.2f} on the test rows.")
    else:
        key = "roc_auc" if "roc_auc" in test else "balanced_accuracy"
        headline = (f"{best_name} predicts {target} with {test['accuracy']:.1%} accuracy and "
                    f"{test['balanced_accuracy']:.1%} balanced accuracy on the test set. "
                    f"Always guessing the most common class gives {base_test['accuracy']:.1%}"
                    + (f". ROC AUC = {test['roc_auc']:.3f}." if "roc_auc" in test else "."))
        if test["balanced_accuracy"] - base_test["balanced_accuracy"] < 0.03 and best_name != "baseline":
            warn.append("The best model is barely better than guessing the most common class.")
        gap = train_scores[key] - test[key]
        if gap > 0.1:
            warn.append(f"Overfitting: {key} is {train_scores[key]:.2f} on the training rows "
                        f"and {test[key]:.2f} on the test rows.")

    # ---- what drives it
    importance: list[dict] = []
    if best_name != "baseline":
        Xi, yi = X_test, y_test
        if len(Xi) > 3000:
            idx = np.random.default_rng(SEED).choice(len(Xi), 3000, replace=False)
            Xi, yi = Xi.iloc[idx], yi[idx]
        imp_scoring = ("neg_root_mean_squared_error" if task == REGRESSION else
                       "roc_auc" if len(classes) == 2 else "f1_macro")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pi = permutation_importance(best, Xi, yi, n_repeats=5, random_state=SEED,
                                        scoring=imp_scoring, n_jobs=1)
        importance = sorted(
            ({"feature": c, "importance": round_sig(float(m), 4), "std": round_sig(float(s), 4)}
             for c, m, s in zip(X.columns, pi.importances_mean, pi.importances_std)),
            key=lambda d: -d["importance"])

    # ---- charts
    charts = []
    out_dir.mkdir(parents=True, exist_ok=True)
    _chart_comparison(usable, primary, higher_better, out_dir / f"{model_id}_comparison.png")
    charts.append({"file": f"{model_id}_comparison.png", "title": "Model comparison"})
    if task == CLASSIFICATION:
        _chart_classification(y_test, pred, proba, classes, out_dir / f"{model_id}_diagnostics.png")
    else:
        _chart_regression(y_test, pred, out_dir / f"{model_id}_diagnostics.png")
    charts.append({"file": f"{model_id}_diagnostics.png", "title": "Test set diagnostics"})
    if importance:
        _chart_importance(importance, out_dir / f"{model_id}_importance.png")
        charts.append({"file": f"{model_id}_importance.png", "title": "Feature importance"})

    for r in cv_table:
        r["cv_mean"], r["cv_std"] = round_sig(r["cv_mean"], 4), round_sig(r["cv_std"], 4)

    result = {
        "model_id": model_id, "task": task, "target": target, "dataset": dataset_name,
        "rows_used": int(n), "rows_train": int(len(X_train)), "rows_test": int(len(X_test)),
        "split": split_text, "cv_folds": folds, "primary_metric": primary,
        "classes": classes,
        "features_used": list(X.columns), "features_dropped": dropped,
        "cross_validation": cv_table, "best_model": best_name,
        "test_metrics": test, "train_metrics": train_scores, "baseline_test_metrics": base_test,
        "importance": importance[:20],
        "leakage_suspects": suspects + formula_leaks
                            + [{"column": g["column"], "score_alone": g["score"],
                                         "metric": g["metric"] + " from presence alone"}
                                        for g in gap_leaks],
        "warnings": warn, "notes": notes, "headline": headline, "charts": charts,
        "caveat": "Importance shows what the model relies on to predict. It is not evidence "
                  "that changing a feature would change the outcome.",
    }
    bundle = Bundle(model_id=model_id, task=task, target=target, pipeline=best, plan=plan,
                    feature_columns=list(X.columns), classes=classes, best_model=best_name,
                    trained_on=dataset_name)
    return clean(result), bundle


def predict(df: pd.DataFrame, bundle: Bundle) -> tuple[pd.DataFrame, dict]:
    """Score new rows. Returns the rows with prediction columns added, and a summary."""
    X = build_features(df, bundle.plan)[bundle.feature_columns]
    out = df.copy()
    name = f"predicted_{bundle.target}"
    raw = bundle.pipeline.predict(X)
    if bundle.task == CLASSIFICATION:
        out[name] = [bundle.classes[int(i)] for i in raw]
        proba = bundle.pipeline.predict_proba(X)
        if len(bundle.classes) == 2:
            out[f"probability_{bundle.classes[1]}"] = np.round(proba[:, 1], 4)
        else:
            out["probability_of_prediction"] = np.round(proba.max(axis=1), 4)
        summary = {"predicted_counts": clean(out[name].value_counts().to_dict())}
    else:
        out[name] = raw
        summary = {"predicted_mean": round_sig(float(np.mean(raw))),
                   "predicted_min": round_sig(float(np.min(raw))),
                   "predicted_max": round_sig(float(np.max(raw)))}
    notes = []
    for c in bundle.plan["categorical"]:
        known = set()
        try:
            enc = bundle.pipeline.named_steps["prep"].named_transformers_["cat"].named_steps["onehot"]
            cats = dict(zip(enc.feature_names_in_, enc.categories_))
            known = set(map(str, cats.get(c, [])))
        except (KeyError, AttributeError):
            pass
        if known:
            unseen = set(X[c].dropna().astype(str)) - known
            if unseen:
                notes.append(f'"{c}" has {len(unseen)} value(s) the model never saw in '
                             f"training, for example {sorted(unseen)[:3]}.")
    summary.update({"rows": int(len(out)), "model_id": bundle.model_id,
                    "prediction_column": name, "notes": notes})
    return out, clean(summary)
