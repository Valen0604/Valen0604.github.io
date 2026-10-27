"""
Charts. Every chart function returns two things: a PNG on disk, and the numbers behind it.

The numbers matter as much as the picture. The model reads them to describe the chart
accurately, and a user can check the description against them.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display: we only ever write files

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from . import schema as S  # noqa: E402
from .schema import clean, compact, round_sig  # noqa: E402

CHART_TYPES = ["histogram", "bar", "line", "scatter", "box", "heatmap", "missing", "pairs"]
AGGREGATIONS = ["count", "sum", "mean", "median", "min", "max"]

# The categorical palette, in a fixed order that keeps neighbouring colours apart for
# colour-blind readers (validated: adjacent pairs clear a CVD difference of 8 and a
# normal-vision difference of 15 in OKLab). The same eight hues are the --series-N
# variables in styles.css, so a chart in the chat and a chart in the dashboard agree.
# Hues are assigned in this order, never cycled: a ninth group becomes "Other".
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6",
           "#e34948"]
PRIMARY = PALETTE[0]
OTHER = "#898781"
MAX_CATEGORIES = 15
MAX_POINTS = 5000
DPI = 130

# "single": one hue for a chart with one series, the way a careful chart is drawn.
# "varied": a different hue for each category on a bar or box chart, and a new hue for
# each single-series chart in turn, for readers who find all-blue monotonous.
STYLE = {"palette": "single"}
_turn = 0           # which hue the next single-series chart gets in "varied"


class ChartError(ValueError):
    """The chart could not be drawn. The message tells the model how to fix the request."""


def set_style(style: dict | None) -> None:
    """Chosen by the user in the sidebar; the server passes it with every chart request."""
    if style and style.get("palette") in ("single", "varied"):
        STYLE["palette"] = style["palette"]


def varied() -> bool:
    return STYLE["palette"] == "varied"


def series_color() -> str:
    """The hue for a chart with one series."""
    global _turn
    if not varied():
        return PRIMARY
    color = PALETTE[_turn % len(PALETTE)]
    _turn += 1
    return color


def category_colors(order: list) -> list[str] | None:
    """One colour per category, in display order, when the varied palette is on."""
    if not varied():
        return None
    return [OTHER if str(c) == "Other" else PALETTE[i % len(PALETTE)]
            for i, c in enumerate(order)]


def apply_style() -> None:
    sns.set_theme(style="whitegrid", palette=PALETTE)
    plt.rcParams.update({
        "figure.figsize": (8.5, 5), "figure.dpi": 100, "savefig.dpi": DPI,
        "axes.titlesize": 13, "axes.titleweight": "bold", "axes.labelsize": 11,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "font.family": "DejaVu Sans",
    })


def save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _need(df: pd.DataFrame, *columns: str | None) -> None:
    missing = [c for c in columns if c and c not in df.columns]
    if missing:
        raise ChartError(f"No column named {missing}. Columns are: {list(map(str, df.columns))}")


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    s = pd.to_numeric(df[column], errors="coerce").astype(float)
    if s.notna().sum() == 0:
        raise ChartError(f'"{column}" has no numeric values.')
    return s


def _lump(s: pd.Series, keep: int = MAX_CATEGORIES) -> pd.Series:
    """Keep the most common categories and fold the rest into 'Other'."""
    s = s.astype("object").where(s.notna(), "(missing)").astype(str)
    top = s.value_counts().index[:keep]
    return s.where(s.isin(top), "Other")


# ------------------------------------------------------------------------------- charts
def histogram(df, x, color=None, bins=None, title=None, **_):
    _need(df, x, color)
    values = _numeric(df, x)
    fig, ax = plt.subplots()
    data = pd.DataFrame({x: values})
    if color:
        data[color] = _lump(df[color], 6)
    sns.histplot(data=data.dropna(subset=[x]), x=x, hue=color, bins=bins or "auto",
                 ax=ax, color=None if color else series_color(), multiple="layer",
                 alpha=0.55 if color else 0.85, edgecolor="white")
    v = values.dropna()
    ax.axvline(v.median(), color="#111827", ls="--", lw=1.2)
    ax.text(v.median(), ax.get_ylim()[1] * 0.97, " median", fontsize=9, va="top")
    ax.set_title(title or f"Distribution of {x}")
    ax.set_ylabel("Rows")
    summary = {"column": x, "n": int(v.size), "min": round_sig(v.min()),
               "median": round_sig(v.median()), "mean": round_sig(v.mean()),
               "max": round_sig(v.max()), "std": round_sig(v.std()),
               "skew": round_sig(v.skew(), 3) if v.size > 2 else None}
    if color:
        summary["median_by_group"] = clean(
            data.groupby(color)[x].median().round(4).to_dict())
    return fig, summary


def bar(df, x, y=None, agg="count", color=None, top=None, title=None, **_):
    _need(df, x, y, color)
    if agg not in AGGREGATIONS:
        raise ChartError(f"agg must be one of {AGGREGATIONS}.")
    if agg != "count" and not y:
        raise ChartError(f'agg="{agg}" needs a numeric y column.')
    keep = int(top or MAX_CATEGORIES)
    data = pd.DataFrame({x: _lump(df[x], keep)})
    if color:
        data[color] = _lump(df[color], 6)
    keys = [x] + ([color] if color else [])
    if agg == "count" or not y:
        table = data.groupby(keys).size().rename("count").reset_index()
        value, label = "count", "Rows"
    else:
        data[y] = _numeric(df, y)
        table = data.groupby(keys)[y].agg(agg).reset_index()
        value, label = y, f"{agg} of {y}"
    order = (table.groupby(x)[value].sum().sort_values(ascending=False).index.tolist())
    if "Other" in order:                      # 'Other' always last
        order.remove("Other")
        order.append("Other")
    horizontal = len(order) > 6 or max(len(str(o)) for o in order) > 12
    fig, ax = plt.subplots(figsize=(8.5, max(4, 0.38 * len(order) + 1.5) if horizontal else 5))
    kwargs = dict(data=table, hue=color, order=order, ax=ax)
    if not color:
        colors = category_colors(order)
        if colors:          # one hue per category: hue on x itself, no legend
            kwargs.update(hue=x, hue_order=order, palette=colors, legend=False)
        else:
            kwargs["color"] = series_color()
    if horizontal:
        sns.barplot(y=x, x=value, orient="h", **kwargs)
        ax.set_xlabel(label)
        ax.set_ylabel("")
    else:
        sns.barplot(x=x, y=value, **kwargs)
        ax.set_ylabel(label)
    ax.set_title(title or (f"{label} by {x}" if value != "count" else f"Rows by {x}"))
    shown = table.sort_values(value, ascending=False).head(40)
    return fig, {"x": x, "value": label, "categories_shown": len(order),
                 "categories_total": int(df[x].nunique()),
                 "data": clean(shown.to_dict(orient="records"))}


def line(df, x, y, agg="mean", color=None, freq=None, title=None, **_):
    _need(df, x, y, color)
    if agg not in AGGREGATIONS:
        raise ChartError(f"agg must be one of {AGGREGATIONS}.")
    data = pd.DataFrame({x: df[x], y: _numeric(df, y) if agg != "count" else 1.0})
    if color:
        data[color] = _lump(df[color], 8)
    data = data.dropna(subset=[x])
    is_time = S.column_kind(df[x]) == S.DATETIME
    used_freq = None
    if is_time:
        data[x] = pd.to_datetime(data[x])
        span = (data[x].max() - data[x].min()).days
        used_freq = freq or ("D" if span <= 120 else "W" if span <= 730 else
                             "MS" if span <= 3650 else "YS")
        keys = [pd.Grouper(key=x, freq=used_freq)] + ([color] if color else [])
    else:
        keys = [x] + ([color] if color else [])
    how = "sum" if agg == "count" else agg
    table = data.groupby(keys)[y].agg(how).reset_index().dropna(subset=[y]).sort_values(x)
    if table.empty:
        raise ChartError("Nothing to plot after grouping.")
    fig, ax = plt.subplots(figsize=(9.5, 5))
    sns.lineplot(data=table, x=x, y=y, hue=color, ax=ax, marker="o" if len(table) < 60 else None,
                 color=None if color else series_color(), lw=2)
    label = "Rows" if agg == "count" else f"{agg} of {y}"
    ax.set_ylabel(label)
    ax.set_title(title or f"{label} over {x}")
    if is_time:
        fig.autofmt_xdate()
    total = table.groupby(x)[y].sum() if color else table.set_index(x)[y]
    summary = {"x": x, "value": label, "frequency": used_freq, "points": int(len(table)),
               "start": clean(total.index[0]), "end": clean(total.index[-1]),
               "first_value": round_sig(total.iloc[0]), "last_value": round_sig(total.iloc[-1]),
               "min": round_sig(total.min()), "min_at": clean(total.idxmin()),
               "max": round_sig(total.max()), "max_at": clean(total.idxmax())}
    if len(total) >= 3:
        idx = np.arange(len(total))
        slope = np.polyfit(idx, total.to_numpy(dtype=float), 1)[0]
        summary["trend_per_period"] = round_sig(slope)
    return fig, summary


def scatter(df, x, y, color=None, trend=True, title=None, **_):
    _need(df, x, y, color)
    data = pd.DataFrame({x: _numeric(df, x), y: _numeric(df, y)})
    if color:
        if S.column_kind(df[color]) == S.NUMERIC:
            data[color] = _numeric(df, color)
        else:
            data[color] = _lump(df[color], 8)
    data = data.dropna(subset=[x, y])
    if len(data) < 3:
        raise ChartError("Fewer than 3 rows have both values.")
    n_all = len(data)
    plot = data.sample(MAX_POINTS, random_state=0) if n_all > MAX_POINTS else data
    fig, ax = plt.subplots()
    sns.scatterplot(data=plot, x=x, y=y, hue=color, ax=ax, s=26,
                    alpha=0.45 if len(plot) > 800 else 0.75,
                    color=None if color else series_color(), edgecolor="none")
    summary = {"x": x, "y": y, "n": n_all, "points_drawn": int(len(plot)),
               "pearson": round_sig(data[x].corr(data[y]), 3),
               "spearman": round_sig(data[x].corr(data[y], method="spearman"), 3)}
    if trend and data[x].nunique() > 2:
        slope, intercept = np.polyfit(data[x], data[y], 1)
        xs = np.linspace(data[x].min(), data[x].max(), 100)
        ax.plot(xs, slope * xs + intercept, color="#0b0b0b", lw=1.5, ls="--",
                label="linear trend")
        ax.legend()
        summary["trend_slope"] = round_sig(slope)
        summary["trend_intercept"] = round_sig(intercept)
    ax.set_title(title or f"{y} against {x}")
    return fig, summary


def box(df, y, x=None, title=None, **_):
    _need(df, x, y)
    data = pd.DataFrame({y: _numeric(df, y)})
    if x:
        data[x] = _lump(df[x], 12)
        order = data.groupby(x)[y].median().sort_values(ascending=False).index.tolist()
        horizontal = len(order) > 5
        fig, ax = plt.subplots(figsize=(8.5, max(4, 0.45 * len(order) + 1.5) if horizontal else 5))
        colors = category_colors(order)
        paint = (dict(hue=x, hue_order=order, palette=colors, legend=False) if colors
                 else dict(color=series_color()))
        if horizontal:
            sns.boxplot(data=data, y=x, x=y, order=order, ax=ax, fliersize=2.5, **paint)
            ax.set_ylabel("")
        else:
            sns.boxplot(data=data, x=x, y=y, order=order, ax=ax, fliersize=2.5, **paint)
        stats = data.groupby(x)[y].agg(["count", "median", "mean", "std"]).loc[order]
        summary = {"y": y, "by": x, "groups": clean(stats.round(4).reset_index()
                                                     .to_dict(orient="records"))}
        ax.set_title(title or f"{y} by {x}")
    else:
        fig, ax = plt.subplots(figsize=(8.5, 3))
        sns.boxplot(data=data, x=y, ax=ax, color=series_color(), fliersize=2.5)
        v = data[y].dropna()
        summary = {"y": y, "median": round_sig(v.median()), "q1": round_sig(v.quantile(.25)),
                   "q3": round_sig(v.quantile(.75))}
        ax.set_title(title or f"Spread of {y}")
    return fig, summary


def heatmap(df, columns=None, method="spearman", title=None, **_):
    cols = [c for c in (columns or S.columns_of(df, S.NUMERIC, S.BOOLEAN)) if c in df.columns]
    if len(cols) < 2:
        raise ChartError("A correlation heatmap needs at least two numeric columns.")
    cols = cols[:25]
    numeric = df[cols].apply(pd.to_numeric, errors="coerce").astype(float)
    corr = numeric.corr(method=method)
    size = max(5.5, 0.55 * len(cols) + 2)
    fig, ax = plt.subplots(figsize=(size + 1, size))
    sns.heatmap(corr, ax=ax, cmap="RdBu_r", vmin=-1, vmax=1, center=0, square=True,
                annot=len(cols) <= 12, fmt=".2f", annot_kws={"size": 8},
                linewidths=0.5, cbar_kws={"shrink": 0.75, "label": f"{method} correlation"})
    ax.set_title(title or f"Correlation between numeric columns ({method})")
    pairs = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            if pd.notna(corr.loc[a, b]):
                pairs.append({"a": a, "b": b, "r": round(float(corr.loc[a, b]), 3)})
    pairs.sort(key=lambda p: -abs(p["r"]))
    return fig, {"method": method, "columns": cols, "strongest": pairs[:12]}


def missing(df, title=None, **_):
    share = df.isna().mean().sort_values(ascending=False)
    share = share[share > 0]
    if share.empty:
        raise ChartError("No column has missing values, so there is nothing to draw.")
    share = share.head(30)
    fig, ax = plt.subplots(figsize=(8.5, max(3, 0.36 * len(share) + 1.5)))
    sns.barplot(x=share.values * 100, y=[str(i) for i in share.index], orient="h",
                ax=ax, color=PALETTE[7])
    ax.set_xlabel("Missing values (%)")
    ax.set_ylabel("")
    ax.set_xlim(0, 100)
    ax.set_title(title or "Missing values by column")
    return fig, {"columns_with_missing": int((df.isna().mean() > 0).sum()),
                 "missing_share": clean({str(k): round(float(v), 4) for k, v in share.items()})}


def pairs(df, columns=None, color=None, title=None, **_):
    cols = [c for c in (columns or S.columns_of(df, S.NUMERIC)) if c in df.columns][:5]
    if len(cols) < 2:
        raise ChartError("A pairs plot needs at least two numeric columns.")
    _need(df, color)
    data = df[cols].apply(pd.to_numeric, errors="coerce").astype(float)
    if color:
        data[color] = _lump(df[color], 5)
    data = data.dropna(subset=cols)
    if len(data) > 1500:
        data = data.sample(1500, random_state=0)
    grid = sns.pairplot(data, vars=cols, hue=color, corner=True, height=1.9,
                        plot_kws={"s": 12, "alpha": 0.5, "edgecolor": "none"},
                        diag_kws={"alpha": 0.6})
    grid.figure.suptitle(title or "Pairwise relationships", y=1.02, fontweight="bold")
    return grid.figure, {"columns": cols, "rows_drawn": int(len(data))}


_DISPATCH = {"histogram": histogram, "bar": bar, "line": line, "scatter": scatter,
             "box": box, "heatmap": heatmap, "missing": missing, "pairs": pairs}


def make_chart(df: pd.DataFrame, spec: dict, path: Path) -> dict:
    """Draw the chart described by `spec`, save it to `path`, and return its numbers."""
    chart_type = (spec.get("chart_type") or "").lower()
    if chart_type not in _DISPATCH:
        raise ChartError(f"chart_type must be one of {CHART_TYPES}.")
    apply_style()
    args = {k: v for k, v in spec.items() if k != "chart_type" and v not in (None, "")}
    try:
        fig, summary = _DISPATCH[chart_type](df, **args)
    except TypeError as e:
        plt.close("all")
        raise ChartError(f"Wrong arguments for a {chart_type} chart: {e}") from e
    except ChartError:
        plt.close("all")
        raise
    title = fig.axes[0].get_title() if fig.axes else chart_type
    if not title and getattr(fig, "_suptitle", None) is not None:
        title = fig._suptitle.get_text()
    save(fig, path)
    return {"chart_type": chart_type, "title": title, "summary": compact(summary)}


def suggest_charts(df: pd.DataFrame, limit: int = 4) -> list[dict]:
    """A few sensible first charts for a dataset nobody has looked at yet."""
    k = S.kinds(df)
    numeric = [c for c in df.columns if k[str(c)] == S.NUMERIC]
    cats = [c for c in df.columns if k[str(c)] in (S.CATEGORICAL, S.BOOLEAN)]
    dates = [c for c in df.columns if k[str(c)] == S.DATETIME]
    out: list[dict] = []
    if df.isna().any().any():
        out.append({"chart_type": "missing"})
    if dates and numeric:
        out.append({"chart_type": "line", "x": str(dates[0]), "y": str(numeric[0])})
    if len(numeric) >= 3:
        out.append({"chart_type": "heatmap"})
    if numeric:
        widest = max(numeric, key=lambda c: pd.to_numeric(df[c], errors="coerce").nunique())
        out.append({"chart_type": "histogram", "x": str(widest)})
    if cats:
        out.append({"chart_type": "bar", "x": str(cats[0])})
    if cats and numeric:
        out.append({"chart_type": "box", "x": str(cats[0]), "y": str(numeric[0])})
    return out[:limit]
