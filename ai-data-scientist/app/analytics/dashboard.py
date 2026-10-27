"""
The first-look dashboard: what a data scientist would show you before you asked anything.

It is computed once when a file is loaded, with no model call, and it comes back as plain
numbers (bins, counts, a correlation matrix, a few sampled points). The browser draws it
as interactive charts, and the same numbers go to the model as a short list of
"highlights", so its first answer can point at what matters.

Everything here is a heuristic. The highlights say what is *large* in the data; only the
user knows what is *important*.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import schema as S
from .schema import clean, round_sig

MAX_NUMERIC = 8
MAX_CATEGORICAL = 6
MAX_TOP_VALUES = 8
MAX_HEATMAP = 12
MAX_PAIRS = 4
SCATTER_POINTS = 300
MAX_GROUPS = 3
MAX_HIGHLIGHTS = 6
BINS = 24
SAMPLE_ROWS = 50_000


def _numeric_frame(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return df[cols].apply(pd.to_numeric, errors="coerce").astype(float)


def _bins(x: pd.Series) -> list[dict]:
    v = x.dropna().to_numpy(dtype=float)
    if v.size == 0:
        return []
    if np.unique(v).size <= BINS and np.allclose(v, np.round(v)):
        # Small whole-number columns (ratings, counts) get one bar per value.
        counts = pd.Series(v).value_counts().sort_index()
        return [{"x0": float(k), "x1": float(k), "n": int(n)} for k, n in counts.items()]
    lo, hi = np.percentile(v, [0.5, 99.5])          # clip the extreme tails
    if hi <= lo:
        lo, hi = float(v.min()), float(v.max())
    if hi <= lo:
        return [{"x0": float(lo), "x1": float(hi), "n": int(v.size)}]
    counts, edges = np.histogram(np.clip(v, lo, hi), bins=BINS, range=(lo, hi))
    return [{"x0": round_sig(float(edges[i]), 5), "x1": round_sig(float(edges[i + 1]), 5),
             "n": int(c)} for i, c in enumerate(counts)]


def _by_name(profile: dict) -> dict[str, dict]:
    return {c["name"]: c for c in profile.get("columns", [])}


def _numeric_cards(df: pd.DataFrame, numeric: list[str], info: dict[str, dict],
                   featured: list[str]) -> list[dict]:
    # Featured columns (from highlights) first, then the rest by how much they vary.
    order = [c for c in featured if c in numeric]
    rest = [c for c in numeric if c not in order]
    rest.sort(key=lambda c: -(info.get(c, {}).get("distinct") or 0))
    out = []
    for c in (order + rest)[:MAX_NUMERIC]:
        x = pd.to_numeric(df[c], errors="coerce").astype(float)
        i = info.get(c, {})
        out.append({"name": c, "missing_share": i.get("missing_share", 0.0),
                    "min": i.get("min"), "q1": i.get("q1"), "median": i.get("median"),
                    "mean": i.get("mean"), "q3": i.get("q3"), "max": i.get("max"),
                    "bins": _bins(x)})
    return out


def _categorical_cards(df: pd.DataFrame, cats: list[str], info: dict[str, dict],
                       featured: list[str]) -> list[dict]:
    order = [c for c in featured if c in cats] + [c for c in cats if c not in featured]
    out = []
    for c in order[:MAX_CATEGORICAL]:
        counts = df[c].dropna().astype(str).value_counts()
        total = int(counts.sum()) or 1
        top = [{"value": str(v)[:40], "count": int(n), "share": round(n / total, 4)}
               for v, n in counts.head(MAX_TOP_VALUES).items()]
        other = int(counts.iloc[MAX_TOP_VALUES:].sum())
        if other:
            top.append({"value": "(other)", "count": other, "share": round(other / total, 4)})
        out.append({"name": c, "distinct": int(counts.size),
                    "missing_share": info.get(c, {}).get("missing_share", 0.0), "top": top})
    return out


def _time_card(df: pd.DataFrame, dates: list[str], numeric: list[str]) -> dict | None:
    if not dates:
        return None
    col = dates[0]
    t = pd.to_datetime(df[col], errors="coerce")
    if t.notna().sum() < 3:
        return None
    span = (t.max() - t.min()).days
    freq = "D" if span <= 120 else "W" if span <= 730 else "MS" if span <= 3650 else "YS"
    metrics = numeric[:3]
    data = pd.DataFrame({"t": t})
    for m in metrics:
        data[m] = pd.to_numeric(df[m], errors="coerce").astype(float)
    data = data.dropna(subset=["t"])
    grouped = data.groupby(pd.Grouper(key="t", freq=freq))
    table = grouped.size().rename("rows").to_frame()
    # Averages, not totals: a total of `age` per month means nothing, an average always
    # means something. The row count carries the volume.
    for m in metrics:
        table[m] = grouped[m].mean()
    table = table[table["rows"] > 0]
    if len(table) < 2:
        return None
    points = [{"t": ts.strftime("%Y-%m-%d"), "rows": int(r["rows"]),
               **{m: round_sig(r[m], 5) for m in metrics}} for ts, r in table.iterrows()]
    return {"column": col, "freq": freq, "metrics": metrics, "points": points[:400],
            "start": str(t.min().date()), "end": str(t.max().date())}


def _correlation_card(numeric_frame: pd.DataFrame, cols: list[str]) -> dict | None:
    cols = cols[:MAX_HEATMAP]
    if len(cols) < 2:
        return None
    corr = numeric_frame[cols].corr(method="spearman")
    pairs = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.loc[a, b]
            if pd.notna(r):
                pairs.append({"a": a, "b": b, "r": round(float(r), 3)})
    pairs.sort(key=lambda p: -abs(p["r"]))
    for p in pairs[:MAX_PAIRS]:
        both = numeric_frame[[p["a"], p["b"]]].dropna()
        if len(both) > SCATTER_POINTS:
            both = both.sample(SCATTER_POINTS, random_state=0)
        p["points"] = [[round_sig(x, 4), round_sig(y, 4)] for x, y in both.itertuples(index=False)]
    matrix = [[(round(float(corr.iloc[i, j]), 3) if pd.notna(corr.iloc[i, j]) else None)
               for j in range(len(cols))] for i in range(len(cols))]
    return {"columns": cols, "matrix": matrix, "pairs": pairs[:MAX_PAIRS]}


def _group_cards(df: pd.DataFrame, cats: list[str], numeric: list[str]) -> list[dict]:
    """Category x metric pairs where the group means differ most (largest eta squared)."""
    found = []
    for c in cats[:8]:
        g = df[c].astype("object").where(df[c].notna(), None)
        levels = g.dropna().astype(str)
        if not (2 <= levels.nunique() <= 12):
            continue
        for m in numeric[:6]:
            x = pd.to_numeric(df[m], errors="coerce").astype(float)
            d = pd.DataFrame({"g": levels, "x": x}).dropna()
            if len(d) < 30 or d["x"].std() == 0:
                continue
            means = d.groupby("g")["x"].agg(["mean", "size"])
            means = means[means["size"] >= 5]
            if len(means) < 2:
                continue
            grand = d["x"].mean()
            between = float((means["size"] * (means["mean"] - grand) ** 2).sum())
            total = float(((d["x"] - grand) ** 2).sum())
            eta = between / total if total > 0 else 0.0
            found.append((eta, c, m, means))
    found.sort(key=lambda t: -t[0])
    out, used = [], set()
    for eta, c, m, means in found:
        if c in used or len(out) >= MAX_GROUPS:
            continue
        used.add(c)
        rows = means.sort_values("mean", ascending=False)
        out.append({"category": c, "metric": m, "eta_squared": round(eta, 3),
                    "groups": [{"value": str(k)[:40], "n": int(r["size"]), "mean": round_sig(r["mean"], 5)}
                               for k, r in rows.head(12).iterrows()]})
    return out


def _target_card(df: pd.DataFrame, kinds: dict[str, str]) -> dict | None:
    """The column a model would most likely be asked to predict: a yes/no column, or a
    category with a handful of levels, preferring the last such column."""
    candidates = [c for c in df.columns if kinds[str(c)] == S.BOOLEAN]
    if not candidates:
        candidates = [c for c in df.columns if kinds[str(c)] == S.CATEGORICAL
                      and 2 <= df[c].nunique() <= 5]
    if not candidates:
        return None
    col = str(candidates[-1])
    counts = df[col].dropna().astype(str).value_counts(normalize=True)
    return {"column": col, "classes": [{"value": str(v)[:40], "share": round(float(s), 4)}
                                       for v, s in counts.head(5).items()]}


def highlights(profile: dict, corr: dict | None, groups: list[dict], time: dict | None,
               target: dict | None) -> list[dict]:
    """The six things most worth saying first, in the order they are worth saying."""
    out: list[dict] = []
    warnings = profile.get("warnings", [])
    rows = profile.get("rows", 0)

    if target:
        top = target["classes"][0]
        out.append({"kind": "target", "columns": [target["column"]],
                    "title": f'`{target["column"]}` looks like the outcome to predict',
                    "detail": f'"{top["value"]}" in {top["share"]:.0%} of rows'
                              + (": classes are unbalanced, so compare any model to the "
                                 "baseline" if top["share"] >= 0.8 else "")})

    serious = [w for w in warnings if w["level"] == "high"]
    computed = [w for w in warnings if "computed from other columns" in w["message"]
                or "Almost identical" in w["message"]]
    if serious:
        w = serious[0]
        out.append({"kind": "quality", "columns": [w["column"]] if w["column"] else [],
                    "title": f'{len(serious)} serious data-quality issue'
                             f'{"s" if len(serious) > 1 else ""}',
                    "detail": (f'`{w["column"]}`: ' if w["column"] else "") + w["message"]})
    if computed:
        w = computed[0]
        out.append({"kind": "leak", "columns": [w["column"]],
                    "title": f'`{w["column"]}` is computed from other columns',
                    "detail": "Leave it out of any model that predicts one of its inputs."})

    for p in (corr or {}).get("pairs", [])[:2]:
        if abs(p["r"]) >= 0.5:
            word = "rise together" if p["r"] > 0 else "move in opposite directions"
            out.append({"kind": "correlation", "columns": [p["a"], p["b"]],
                        "title": f'`{p["a"]}` and `{p["b"]}` {word}',
                        "detail": f'Spearman correlation {p["r"]:+.2f}. Association, not cause.'})

    for g in groups[:1]:
        if g["eta_squared"] >= 0.1 and len(g["groups"]) >= 2:
            hi, lo = g["groups"][0], g["groups"][-1]
            out.append({"kind": "group", "columns": [g["category"], g["metric"]],
                        "title": f'`{g["metric"]}` differs most by `{g["category"]}`',
                        "detail": f'{hi["value"]}: {round_sig(hi["mean"], 4):,} against '
                                  f'{lo["value"]}: {round_sig(lo["mean"], 4):,} on average '
                                  f'({g["eta_squared"]:.0%} of the variation is between groups)'})

    if time and len(time["points"]) >= 6:
        # Volume over time: compare the first and last quarter of the periods, so one odd
        # period at either end does not decide the story.
        k = max(1, len(time["points"]) // 4)
        first = sum(p["rows"] for p in time["points"][:k]) / k
        last = sum(p["rows"] for p in time["points"][-k:]) / k
        if first > 0:
            change = (last - first) / first
            if abs(change) >= 0.25:
                unit = {"D": "day", "W": "week", "MS": "month", "YS": "year"}[time["freq"]]
                out.append({"kind": "time", "columns": [time["column"]],
                            "title": f'Rows per {unit} {"rose" if change > 0 else "fell"} '
                                     f'about {abs(change):.0%} over the period',
                            "detail": f'{time["start"]} to {time["end"]}, by `{time["column"]}`; '
                                      f'from about {first:,.0f} to {last:,.0f} per {unit}'})

    gaps = [c for c in profile.get("columns", []) if c.get("missing_share", 0) >= 0.2]
    if gaps:
        c = max(gaps, key=lambda c: c["missing_share"])
        out.append({"kind": "missing", "columns": [c["name"]],
                    "title": f'{len(gaps)} column{"s" if len(gaps) > 1 else ""} with a fifth '
                             "or more of values missing",
                    "detail": f'`{c["name"]}` is missing in {c["missing_share"]:.0%} of '
                              f"{rows:,} rows"})
    return out[:MAX_HIGHLIGHTS]


def build(df: pd.DataFrame, name: str, profile: dict) -> dict:
    """The dashboard for one dataset. `profile` is the output of profiling.profile."""
    work = df.sample(SAMPLE_ROWS, random_state=0) if len(df) > SAMPLE_ROWS else df
    kinds = S.kinds(work)
    numeric = [str(c) for c in work.columns if kinds[str(c)] == S.NUMERIC]
    cats = [str(c) for c in work.columns if kinds[str(c)] in (S.CATEGORICAL, S.BOOLEAN)]
    dates = [str(c) for c in work.columns if kinds[str(c)] == S.DATETIME]
    info = _by_name(profile)

    numeric_frame = _numeric_frame(work, numeric) if numeric else pd.DataFrame()
    # Columns that vary are the ones worth a correlation; constants would give NaN.
    varying = [c for c in numeric if numeric_frame[c].std() > 0] if numeric else []
    corr = _correlation_card(numeric_frame, varying)
    groups = _group_cards(work, cats, varying)
    time = _time_card(work, dates, varying)
    target = _target_card(work, kinds)
    marks = highlights(profile, corr, groups, time, target)
    featured = list(dict.fromkeys(c for h in marks for c in h["columns"]))   # unique, in order

    result = {
        "name": name,
        "rows": int(len(df)),
        "sampled_rows": int(len(work)) if len(work) < len(df) else None,
        "columns_count": int(df.shape[1]),
        "missing_cells_share": profile.get("missing_cells_share", 0.0),
        "duplicate_rows": profile.get("duplicate_rows", 0),
        "kinds": profile.get("kinds", {}),
        "quality": {level: sum(1 for w in profile.get("warnings", []) if w["level"] == level)
                    for level in ("high", "medium", "info")},
        "highlights": marks,
        "target": target,
        "numeric": _numeric_cards(work, numeric, info, featured),
        "categorical": _categorical_cards(work, cats, info, featured),
        "time": time,
        "correlations": corr,
        "groups": groups,
    }
    return clean(result)


def summary_lines(dash: dict) -> list[str]:
    """The highlights as text, for the model."""
    lines = []
    for h in dash.get("highlights", []):
        title = h["title"].replace("`", "")
        lines.append(f"- {title}. {h['detail']}".replace("`", ""))
    if dash.get("sampled_rows"):
        lines.append(f"- (computed on a random sample of {dash['sampled_rows']:,} rows)")
    return lines
