"""
Statistical tests, with the checks a statistician would run before trusting them.

Each result carries an effect size next to the p-value, the assumptions that were
checked, and one plain sentence. A p-value on its own says nothing about how large a
difference is, so none is ever reported alone.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sp

from . import schema as S
from .schema import clean, round_sig

TESTS = ["auto", "correlation", "ttest", "anova", "chi2", "normality"]
ALPHA = 0.05


class StatError(ValueError):
    """The test could not be run. The message tells the model how to fix the request."""


def _need(df: pd.DataFrame, *columns: str | None) -> None:
    missing = [c for c in columns if c and c not in df.columns]
    if missing:
        raise StatError(f"No column named {missing}. Columns are: {list(map(str, df.columns))}")


def _num(df: pd.DataFrame, c: str) -> pd.Series:
    return pd.to_numeric(df[c], errors="coerce").astype(float)


def _p_text(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def _strength(value: float, cuts: tuple[float, float, float], words=None) -> str:
    words = words or ("negligible", "small", "moderate", "large")
    v = abs(value)
    return words[0] if v < cuts[0] else words[1] if v < cuts[1] else words[2] if v < cuts[2] else words[3]


def _looks_normal(x: np.ndarray) -> bool | None:
    if len(x) < 8:
        return None
    sample = x if len(x) <= 5000 else np.random.default_rng(0).choice(x, 5000, replace=False)
    if np.ptp(sample) == 0:
        return None
    return bool(sp.shapiro(sample).pvalue > ALPHA)


# -------------------------------------------------------------------------------- tests
def correlation(df, x, y, **_):
    _need(df, x, y)
    data = pd.DataFrame({"x": _num(df, x), "y": _num(df, y)}).dropna()
    if len(data) < 5:
        raise StatError("Fewer than 5 rows have both values.")
    if data["x"].nunique() < 2 or data["y"].nunique() < 2:
        raise StatError("One of the columns has a single value, so it cannot correlate.")
    pr, pp = sp.pearsonr(data["x"], data["y"])
    sr, spv = sp.spearmanr(data["x"], data["y"])
    strength = _strength(sr, (0.1, 0.3, 0.5), ("no meaningful", "weak", "moderate", "strong"))
    direction = "positive" if sr > 0 else "negative"
    notes = ["Correlation describes association. It does not show that one causes the other."]
    if abs(pr - sr) > 0.15:
        notes.append("Pearson and Spearman disagree by more than 0.15. The relationship is "
                     "curved or driven by outliers, so Spearman is the safer number.")
    return {
        "test": "correlation", "n": int(len(data)),
        "pearson_r": round_sig(pr, 3), "pearson_p": round_sig(pp, 3),
        "spearman_r": round_sig(sr, 3), "spearman_p": round_sig(spv, 3),
        "significant": bool(spv < ALPHA), "notes": notes,
        "plain": f"{x} and {y} have a {strength} {direction} association "
                 f"(Spearman {sr:+.2f}, {_p_text(spv)}, n = {len(data):,}).",
    }


def ttest(df, value, group, **_):
    _need(df, value, group)
    data = pd.DataFrame({"v": _num(df, value), "g": df[group]}).dropna()
    levels = data["g"].value_counts()
    if len(levels) != 2:
        raise StatError(f'"{group}" has {len(levels)} groups. A t-test compares exactly 2; '
                        "use anova for more.")
    a_name, b_name = levels.index[0], levels.index[1]
    a = data.loc[data["g"] == a_name, "v"].to_numpy()
    b = data.loc[data["g"] == b_name, "v"].to_numpy()
    if min(len(a), len(b)) < 3:
        raise StatError("A group has fewer than 3 rows.")
    t, p = sp.ttest_ind(a, b, equal_var=False)          # Welch: no equal-variance assumption
    u, pu = sp.mannwhitneyu(a, b, alternative="two-sided")
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    d = (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0
    normal = [_looks_normal(a), _looks_normal(b)]
    notes = []
    if False in normal and min(len(a), len(b)) < 30:
        notes.append("A group is small and not normally distributed. Trust the "
                     "Mann-Whitney result over the t-test.")
    if min(len(a), len(b)) < 30:
        notes.append("A group has fewer than 30 rows, so the estimate is imprecise.")
    diff = a.mean() - b.mean()
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return {
        "test": "Welch t-test", "groups": {
            str(a_name): {"n": int(len(a)), "mean": round_sig(a.mean()), "median": round_sig(np.median(a)),
                          "std": round_sig(a.std(ddof=1))},
            str(b_name): {"n": int(len(b)), "mean": round_sig(b.mean()), "median": round_sig(np.median(b)),
                          "std": round_sig(b.std(ddof=1))}},
        "difference_in_means": round_sig(diff),
        "difference_ci95": [round_sig(diff - 1.96 * se), round_sig(diff + 1.96 * se)],
        "t": round_sig(t, 4), "p": round_sig(p, 3),
        "mann_whitney_p": round_sig(pu, 3),
        "cohens_d": round_sig(d, 3), "effect_size": _strength(d, (0.2, 0.5, 0.8)),
        "significant": bool(p < ALPHA), "notes": notes,
        "plain": f'Mean {value} is {a.mean():.4g} for "{a_name}" and {b.mean():.4g} for '
                 f'"{b_name}", a {_strength(d, (0.2, 0.5, 0.8))} difference '
                 f"(Cohen's d = {d:.2f}, {_p_text(p)}).",
    }


def anova(df, value, group, **_):
    _need(df, value, group)
    data = pd.DataFrame({"v": _num(df, value), "g": df[group].astype("object")}).dropna()
    counts = data["g"].value_counts()
    keep = counts[counts >= 3].index
    if len(keep) < 2:
        raise StatError("Fewer than 2 groups have at least 3 rows.")
    if len(keep) > 30:
        raise StatError(f'"{group}" has {len(keep)} groups, which is too many to compare.')
    data = data[data["g"].isin(keep)]
    samples = [g["v"].to_numpy() for _, g in data.groupby("g")]
    f, p = sp.f_oneway(*samples)
    h, pk = sp.kruskal(*samples)
    grand = data["v"].mean()
    ss_between = sum(len(s) * (s.mean() - grand) ** 2 for s in samples)
    ss_total = ((data["v"] - grand) ** 2).sum()
    eta2 = ss_between / ss_total if ss_total > 0 else 0.0
    table = (data.groupby("g")["v"].agg(["count", "mean", "median", "std"])
             .sort_values("mean", ascending=False))
    notes = []
    dropped = len(counts) - len(keep)
    if dropped:
        notes.append(f"{dropped} group(s) with fewer than 3 rows were left out.")
    lev = sp.levene(*samples).pvalue
    if lev < ALPHA:
        notes.append("Group variances differ (Levene's test). Trust the Kruskal-Wallis "
                     "result over the ANOVA.")
    notes.append("The test says whether any group differs. It does not say which ones.")
    return {
        "test": "one-way ANOVA", "n": int(len(data)), "groups": int(len(keep)),
        "f": round_sig(f, 4), "p": round_sig(p, 3), "kruskal_p": round_sig(pk, 3),
        "eta_squared": round_sig(eta2, 3),
        "effect_size": _strength(eta2, (0.01, 0.06, 0.14)),
        "group_table": clean(table.round(4).reset_index().rename(columns={"g": group})
                             .to_dict(orient="records")),
        "significant": bool(p < ALPHA), "notes": notes,
        "plain": f"{group} explains {eta2:.1%} of the variation in {value} "
                 f"({_strength(eta2, (0.01, 0.06, 0.14))} effect, {_p_text(p)}). "
                 f'Highest mean: "{table.index[0]}" at {table["mean"].iloc[0]:.4g}; '
                 f'lowest: "{table.index[-1]}" at {table["mean"].iloc[-1]:.4g}.',
    }


def chi2(df, x, y, **_):
    _need(df, x, y)
    data = df[[x, y]].dropna()
    table = pd.crosstab(data[x].astype(str), data[y].astype(str))
    if table.shape[0] < 2 or table.shape[1] < 2:
        raise StatError("Each column needs at least 2 categories.")
    if table.shape[0] > 30 or table.shape[1] > 30:
        raise StatError("A column has more than 30 categories, which is too many.")
    stat, p, dof, expected = sp.chi2_contingency(table)
    n = int(table.to_numpy().sum())
    k = min(table.shape) - 1
    v = float(np.sqrt(stat / (n * k))) if n and k else 0.0
    notes = []
    low = float((expected < 5).mean())
    if low > 0.2:
        notes.append(f"{low:.0%} of cells expect fewer than 5 rows, so the p-value is "
                     "unreliable. Merge rare categories and test again.")
    share = table.div(table.sum(axis=1), axis=0).round(4)
    return {
        "test": "chi-squared test of independence", "n": n,
        "chi2": round_sig(stat, 4), "dof": int(dof), "p": round_sig(p, 3),
        "cramers_v": round_sig(v, 3),
        "effect_size": _strength(v, (0.1, 0.3, 0.5)),
        "row_shares": clean(share.head(15).reset_index().to_dict(orient="records")),
        "significant": bool(p < ALPHA), "notes": notes,
        "plain": f"{x} and {y} have a {_strength(v, (0.1, 0.3, 0.5))} association "
                 f"(Cramér's V = {v:.2f}, {_p_text(p)}, n = {n:,}).",
    }


def normality(df, x, **_):
    _need(df, x)
    v = _num(df, x).dropna().to_numpy()
    if len(v) < 8:
        raise StatError("Fewer than 8 values.")
    if np.ptp(v) == 0:
        raise StatError("Every value is the same.")
    sample = v if len(v) <= 5000 else np.random.default_rng(0).choice(v, 5000, replace=False)
    w, p = sp.shapiro(sample)
    skew, kurt = float(sp.skew(v)), float(sp.kurtosis(v))
    notes = []
    if len(v) > 5000:
        notes.append("Tested on a random sample of 5,000 values.")
    if len(v) > 500:
        notes.append("With this many rows the test flags tiny departures from normal. "
                     "Judge by the skew and a histogram, not by the p-value alone.")
    return {
        "test": "Shapiro-Wilk", "n": int(len(v)), "w": round_sig(w, 4), "p": round_sig(p, 3),
        "skew": round_sig(skew, 3), "excess_kurtosis": round_sig(kurt, 3),
        "looks_normal": bool(p > ALPHA), "notes": notes,
        "plain": f"{x} {'is consistent with' if p > ALPHA else 'departs from'} a normal "
                 f"distribution (skew {skew:+.2f}, {_p_text(p)}).",
    }


def _auto(df: pd.DataFrame, a: str, b: str) -> dict:
    ka, kb = S.column_kind(df[a]), S.column_kind(df[b])
    num = (S.NUMERIC,)
    cat = (S.CATEGORICAL, S.BOOLEAN)
    if ka in num and kb in num:
        return correlation(df, a, b)
    if ka in cat and kb in cat:
        return chi2(df, a, b)
    if (ka in num and kb in cat) or (ka in cat and kb in num):
        value, group = (a, b) if ka in num else (b, a)
        return ttest(df, value, group) if df[group].dropna().nunique() == 2 else anova(df, value, group)
    raise StatError(f'Cannot choose a test for "{a}" ({ka}) and "{b}" ({kb}).')


def run_test(df: pd.DataFrame, spec: dict) -> dict:
    """
    spec: {"test": ..., "x": ..., "y": ..., "value": ..., "group": ...}

    `auto` takes two columns in x and y and picks the test from their kinds.
    """
    test = (spec.get("test") or "auto").lower()
    if test not in TESTS:
        raise StatError(f"test must be one of {TESTS}.")
    x, y = spec.get("x"), spec.get("y")
    value, group = spec.get("value") or y, spec.get("group") or x
    _need(df, x, y, spec.get("value"), spec.get("group"))
    try:
        if test == "auto":
            if not (x and y):
                raise StatError("auto needs two columns, in x and y.")
            result = _auto(df, x, y)
        elif test == "correlation":
            result = correlation(df, x, y)
        elif test == "chi2":
            result = chi2(df, x, y)
        elif test == "normality":
            result = normality(df, x or value)
        elif test == "ttest":
            result = ttest(df, value, group)
        else:
            result = anova(df, value, group)
    except TypeError as e:
        raise StatError(f"Missing a column for the {test} test: {e}") from e
    return clean(result)
