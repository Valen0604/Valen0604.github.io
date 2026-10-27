"""
Describe a dataset: what is in it, and what is wrong with it.

The output is a plain dict. It goes to the model as JSON and to the front-end as a card,
so it has to stay small. Wide tables are summarised, not dumped.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sp

from . import schema as S
from .schema import clean, round_sig

MAX_DETAILED_COLUMNS = 60
TOP_VALUES = 6

# Numbers that are often typed in to mean "unknown".
SENTINELS = {-1, -9, -99, -999, -9999, 99, 999, 9999, 99999, 999999}


def placeholder_values(s: pd.Series) -> list[dict]:
    """
    Find values like 999 or -1 that stand in for "unknown".

    A value counts only when it sits alone at the edge of the range: the largest value is
    999 and the next largest is 90. A column of prices that happens to include 99 is left
    alone.
    """
    x = pd.to_numeric(s, errors="coerce").dropna().astype(float)
    if x.nunique() < 5:
        return []
    found = []
    values = np.sort(x.unique())
    for edge, neighbour in ((values[-1], values[-2]), (values[0], values[1])):
        if edge not in SENTINELS:
            continue
        rest = x[x != edge]
        spread = rest.quantile(0.99) - rest.quantile(0.01)
        if spread > 0 and abs(edge - neighbour) > 2 * spread:
            found.append({"value": clean(edge), "count": int((x == edge).sum()),
                          "rest_min": round_sig(rest.min()), "rest_max": round_sig(rest.max())})
    return found


def missing_patterns(df: pd.DataFrame, kinds: dict[str, str]) -> list[dict]:
    """
    Is a column missing at random, or does it depend on something else?

    For each column with gaps, compare the rows where it is missing with the rows where it
    is not, on every other numeric column. Reports the strongest difference, as the chance
    that a row with the gap has a higher value than a row without it (0.5 = no pattern).
    """
    gaps = [c for c in df.columns if 0.02 <= df[c].isna().mean() <= 0.6][:12]
    numeric = [c for c in df.columns if kinds[str(c)] == S.NUMERIC][:30]
    out = []
    for c in gaps:
        is_missing = df[c].isna().to_numpy()
        best = None
        for other in numeric:
            if other == c:
                continue
            v = pd.to_numeric(df[other], errors="coerce").astype(float).to_numpy()
            a, b = v[is_missing & ~np.isnan(v)], v[~is_missing & ~np.isnan(v)]
            if len(a) < 20 or len(b) < 20:
                continue
            u, p = sp.mannwhitneyu(a, b, alternative="two-sided")
            auc = u / (len(a) * len(b))
            if p < 0.001 and abs(auc - 0.5) >= 0.08 and (
                    best is None or abs(auc - 0.5) > abs(best[1] - 0.5)):
                best = (other, float(auc), float(np.median(a)), float(np.median(b)))
        if best:
            out.append({"column": str(c), "related_to": str(best[0]), "auc": round(best[1], 3),
                        "median_when_missing": round_sig(best[2]),
                        "median_when_present": round_sig(best[3])})
    return out


def _numeric_stats(s: pd.Series) -> dict:
    x = pd.to_numeric(s, errors="coerce").dropna().astype(float)
    if x.empty:
        return {}
    q1, med, q3 = x.quantile([0.25, 0.5, 0.75])
    iqr = q3 - q1
    outliers = int(((x < q1 - 1.5 * iqr) | (x > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
    out = {
        "min": round_sig(x.min()), "q1": round_sig(q1), "median": round_sig(med),
        "mean": round_sig(x.mean()), "q3": round_sig(q3), "max": round_sig(x.max()),
        "std": round_sig(x.std()) if len(x) > 1 else None,
        "zeros": int((x == 0).sum()),
        "negative": int((x < 0).sum()),
        "outliers_iqr": outliers,
    }
    if len(x) > 2 and x.std() > 0:
        out["skew"] = round_sig(x.skew(), 3)
    return out


def _top_values(s: pd.Series, n: int = TOP_VALUES) -> list[dict]:
    counts = s.dropna().astype(str).value_counts()
    total = int(counts.sum())
    return [{"value": str(v)[:60], "count": int(c), "share": round(c / total, 4)}
            for v, c in counts.head(n).items()]


def _column(s: pd.Series, kind: str, n_rows: int) -> dict:
    non_null = s.dropna()
    info = {
        "name": str(s.name),
        "kind": kind,
        "dtype": str(s.dtype),
        "missing": int(s.isna().sum()),
        "missing_share": round(float(s.isna().mean()), 4) if n_rows else 0.0,
        "distinct": int(non_null.nunique()),
    }
    if kind == S.NUMERIC:
        info.update(_numeric_stats(s))
        found = placeholder_values(s)
        if found:
            info["placeholders"] = found
    elif kind == S.DATETIME:
        dates = pd.to_datetime(non_null, errors="coerce").dropna()
        if len(dates):
            info["min"] = clean(dates.min())
            info["max"] = clean(dates.max())
            info["span_days"] = int((dates.max() - dates.min()).days)
    elif kind in (S.CATEGORICAL, S.BOOLEAN):
        info["top"] = _top_values(s)
    elif kind in (S.TEXT, S.ID):
        info["examples"] = [str(v)[:60] for v in non_null.head(3)]
        if kind == S.TEXT:
            info["mean_length"] = round_sig(non_null.astype(str).str.len().mean(), 3)
    return info


def _correlations(df: pd.DataFrame, numeric: list[str], top: int = 8) -> list[dict]:
    if len(numeric) < 2:
        return []
    cols = numeric[:40]
    corr = df[cols].apply(pd.to_numeric, errors="coerce").astype(float).corr(method="spearman")
    pairs = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.loc[a, b]
            if pd.notna(r):
                pairs.append((abs(r), a, b, r))
    pairs.sort(reverse=True)
    return [{"a": a, "b": b, "spearman": round(float(r), 3)} for _, a, b, r in pairs[:top]]


DERIVED_R = 0.99
_OPS = {"x": lambda a, b: a * b, "+": lambda a, b: a + b, "-": lambda a, b: a - b}


def derived_columns(df: pd.DataFrame, columns: list[str] | None = None,
                    max_columns: int = 12) -> list[dict]:
    """
    Find numeric columns that are computed from two others: revenue = units x price.

    Tries the product, sum and difference of every pair against every other column, and
    reports a match when the correlation is 0.99 or more and neither column of the pair
    reaches that alone. Also reports two columns that are near copies of each other.

    This matters for modelling. A feature that is arithmetic on the target gives the
    answer away, and it can do so while looking only moderately predictive on its own.
    """
    k = S.kinds(df)
    cols = [c for c in (columns or df.columns) if c in df.columns and k[str(c)] == S.NUMERIC]
    cols = cols[:max_columns]
    if len(cols) < 2:
        return []
    data = df[cols].apply(pd.to_numeric, errors="coerce").astype(float).dropna()
    if len(data) < 30:
        return []
    if len(data) > 5000:
        data = data.sample(5000, random_state=0)
    data = data.loc[:, data.std() > 0]
    cols = list(data.columns)
    corr = data.corr().abs()

    found: dict[frozenset, dict] = {}
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            if corr.loc[a, b] >= 0.995:
                found[frozenset((a, b))] = {"column": str(b), "formula": str(a), "kind": "copy",
                                            "r": round(float(corr.loc[a, b]), 4),
                                            "columns": [str(a), str(b)]}
    copies = {c for key in found for c in key}
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            if a in copies and b in copies and frozenset((a, b)) in found:
                continue
            for symbol, op in _OPS.items():
                combined = op(data[a], data[b])
                if combined.std() == 0:
                    continue
                for c in cols:
                    if c in (a, b) or max(corr.loc[a, c], corr.loc[b, c]) >= 0.98:
                        continue
                    r = abs(float(np.corrcoef(combined, data[c])[0, 1]))
                    key = frozenset((a, b, c))
                    if r >= DERIVED_R and (key not in found or r > found[key]["r"]):
                        found[key] = {"column": str(c), "formula": f"{a} {symbol} {b}",
                                      "kind": "computed", "r": round(r, 4),
                                      "columns": [str(a), str(b), str(c)]}
    return sorted(found.values(), key=lambda d: -d["r"])


def quality_warnings(df: pd.DataFrame, columns: list[dict],
                     patterns: list[dict] | None = None,
                     derived: list[dict] | None = None) -> list[dict]:
    """Things a careful analyst would want to know before trusting the data."""
    out: list[dict] = []
    n = len(df)

    def warn(level: str, column: str | None, message: str) -> None:
        out.append({"level": level, "column": column, "message": message})

    dup = int(df.duplicated().sum())
    if dup:
        warn("medium", None,
             f"{dup:,} rows ({dup / n:.1%}) are exact copies of another row.")

    for c in columns:
        name, kind = c["name"], c["kind"]
        share = c["missing_share"]
        if kind == S.EMPTY:
            warn("high", name, "The column has no values at all.")
            continue
        if share >= 0.5:
            warn("high", name, f"{share:.0%} of values are missing.")
        elif share >= 0.05:
            warn("medium", name, f"{share:.0%} of values are missing.")
        if c["distinct"] == 1:
            warn("medium", name,
                 "Every value is the same, so the column carries no information.")
        if kind == S.ID:
            warn("info", name, "Looks like an identifier. It should not be used as a "
                               "predictor in a model.")
        if kind == S.NUMERIC:
            for ph in c.get("placeholders", []):
                warn("high", name,
                     f'{ph["count"]} row(s) have the value {ph["value"]:g}, while every other '
                     f'value is between {ph["rest_min"]:g} and {ph["rest_max"]:g}. It looks '
                     'like a code for "unknown". Treat it as missing before computing a mean.')
            share_out = c.get("outliers_iqr", 0) / max(n - c["missing"], 1)
            if share_out > 0.05:
                warn("info", name, f"{share_out:.0%} of values are far from the rest "
                                   "(outside 1.5 times the interquartile range).")
            skew = c.get("skew")
            if skew is not None and abs(skew) > 2:
                direction = "right" if skew > 0 else "left"
                warn("info", name, f"Strongly skewed to the {direction} (skew {skew}). "
                                   "The mean is a poor summary; prefer the median.")
        if kind == S.CATEGORICAL and c.get("top"):
            top = c["top"][0]
            if top["share"] > 0.95 and c["distinct"] > 1:
                warn("info", name, f'{top["share"]:.0%} of rows have the value '
                                   f'"{top["value"]}".')
            lowered: dict[str, set] = {}
            for v in df[name].dropna().astype(str).unique()[:500]:
                lowered.setdefault(v.strip().lower(), set()).add(v)
            clashes = [sorted(v) for v in lowered.values() if len(v) > 1]
            if clashes:
                example = " / ".join(f'"{x}"' for x in clashes[0][:3])
                warn("medium", name, f"{len(clashes)} categor"
                     f"{'y is' if len(clashes) == 1 else 'ies are'} written in more than "
                     f"one way, for example {example}.")
    for d in derived or []:
        if d["kind"] == "copy":
            warn("medium", d["column"],
                 f'Almost identical to {d["formula"]} (correlation {d["r"]:.3f}). Keep one.')
        else:
            a, b = [c for c in d["columns"] if c != d["column"]]
            warn("medium", d["column"],
                 f'Looks computed from other columns: close to {d["formula"]} '
                 f'(correlation {d["r"]:.3f}). Of {a}, {b} and {d["column"]}, any two give '
                 "the third, so a model that predicts one must not be given the other two.")
    for p in patterns or []:
        higher = "higher" if p["auc"] > 0.5 else "lower"
        warn("medium", p["column"],
             f'Missing values are not random: rows with no {p["column"]} have {higher} '
             f'{p["related_to"]} (median {p["median_when_missing"]:g} against '
             f'{p["median_when_present"]:g}). Dropping those rows, or filling them with the '
             "average, would bias the result.")
    order = {"high": 0, "medium": 1, "info": 2}
    return sorted(out, key=lambda w: order[w["level"]])


def profile(df: pd.DataFrame, name: str, notes: list[str] | None = None) -> dict:
    """The full description of one dataset."""
    n_rows, n_cols = df.shape
    k = S.kinds(df)
    detailed = list(df.columns[:MAX_DETAILED_COLUMNS])
    columns = [_column(df[c], k[str(c)], n_rows) for c in detailed]

    by_kind: dict[str, int] = {}
    for v in k.values():
        by_kind[v] = by_kind.get(v, 0) + 1

    numeric = [c for c in df.columns if k[str(c)] == S.NUMERIC]
    patterns = missing_patterns(df, k)
    derived = derived_columns(df)
    result = {
        "name": name,
        "rows": int(n_rows),
        "columns_count": int(n_cols),
        "memory_mb": round(float(df.memory_usage(deep=True).sum()) / 1e6, 2),
        "kinds": by_kind,
        "missing_cells_share": round(float(df.isna().to_numpy().mean()), 4) if df.size else 0.0,
        "duplicate_rows": int(df.duplicated().sum()),
        "columns": columns,
        "strongest_correlations": _correlations(df, [str(c) for c in numeric]),
        "missing_patterns": patterns,
        "derived_columns": derived,
        "warnings": quality_warnings(df, columns, patterns, derived),
        "load_notes": list(notes or []),
        "preview": S.table_payload(df.head(8), max_rows=8, max_cols=20),
    }
    if n_cols > MAX_DETAILED_COLUMNS:
        result["columns_not_detailed"] = [str(c) for c in df.columns[MAX_DETAILED_COLUMNS:]]
    return clean(result)


def brief(p: dict) -> str:
    """
    A compact text version of a profile, for the model's context.

    Text is cheaper than the JSON and the model reads it just as well.
    """
    lines = [f'Dataset "{p["name"]}": {p["rows"]:,} rows x {p["columns_count"]} columns, '
             f'{p["missing_cells_share"]:.1%} of cells missing, '
             f'{p["duplicate_rows"]:,} duplicate rows.',
             "Columns (name | kind | missing | distinct | summary):"]
    for c in p["columns"]:
        kind = c["kind"]
        if kind == S.NUMERIC:
            summary = (f'min {c.get("min")}, median {c.get("median")}, mean {c.get("mean")}, '
                       f'max {c.get("max")}')
        elif kind == S.DATETIME:
            summary = f'{str(c.get("min"))[:10]} to {str(c.get("max"))[:10]}'
        elif kind in (S.CATEGORICAL, S.BOOLEAN):
            summary = ", ".join(f'{t["value"]} ({t["share"]:.0%})' for t in c.get("top", [])[:4])
        else:
            summary = "e.g. " + ", ".join(c.get("examples", [])[:2])
        lines.append(f'- {c["name"]} | {kind} | {c["missing_share"]:.0%} | '
                     f'{c["distinct"]} | {summary}')
    if p.get("columns_not_detailed"):
        lines.append(f'...and {len(p["columns_not_detailed"])} more columns: '
                     + ", ".join(p["columns_not_detailed"][:40]))
    if p["strongest_correlations"]:
        lines.append("Strongest correlations (Spearman): " + "; ".join(
            f'{c["a"]} ~ {c["b"]} {c["spearman"]:+.2f}' for c in p["strongest_correlations"][:6]))
    if p["warnings"]:
        lines.append("Data quality warnings:")
        lines += [f'- [{w["level"]}] {w["column"] + ": " if w["column"] else ""}{w["message"]}'
                  for w in p["warnings"][:25]]
    if p["load_notes"]:
        lines.append("Changes made while loading:")
        lines += [f"- {n}" for n in p["load_notes"]]
    return "\n".join(lines)
