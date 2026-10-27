"""
How the loaded datasets relate to each other.

Given several tables, this finds the columns that could join them (a customer id that is
unique in one table and repeated in another), the dimensions they share (a region or a
month that appears in several), and how well the values actually match. It is computed
with no model call, like the single-dataset dashboard, and comes back as plain numbers
and short sentences that the browser draws as an interactive graph.

Everything here is a heuristic about *values*. Two columns that share 95% of their
values are probably the same thing, but only the user knows whether `id` in one file is
the `customer_id` of the other. The explanations say what was measured, not what it means.
"""
from __future__ import annotations

import re

import pandas as pd

from . import schema as S
from .schema import clean

MAX_DATASETS = 12
MAX_COLUMNS = 80          # per dataset, for the overlap search
MAX_DISTINCT = 50_000     # distinct values kept per column for the overlap test
MAX_LINKS_PER_PAIR = 4
MIN_SHARE = 0.02          # a link below this share of rows on both sides is noise
MIN_SHARE_UNNAMED = 0.3   # columns with different names must match this well to count
MIN_KEY_DISTINCT = 20     # a column with fewer values than this is not a key to a stranger
NEAR_UNIQUE = 0.95        # distinct / rows: a key with a few duplicate rows still counts
EXAMPLES = 3

LINKABLE = (S.ID, S.CATEGORICAL, S.NUMERIC, S.DATETIME, S.BOOLEAN)


def _norm(name: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", str(name).lower())


def _family(kind: str, s: pd.Series) -> str | None:
    """Values are compared as text, so only columns whose text could match are paired."""
    if kind == S.DATETIME:
        return "date"
    if kind == S.NUMERIC:
        v = pd.to_numeric(s.dropna(), errors="coerce").dropna()
        if v.empty or not (v == v.round()).all():
            return None               # fractional numbers never join anything
        return "integer"
    if kind in (S.ID, S.CATEGORICAL, S.BOOLEAN):
        return "text"
    return None


def examples(s: pd.Series, n: int = EXAMPLES, width: int = 40) -> list[str]:
    """A few distinct values of a column, as short text, for a reader or a model."""
    try:
        v = s.dropna().astype(str).str.strip()
    except Exception:
        return []
    v = v[v != ""].drop_duplicates().head(n)
    return [t if len(t) <= width else t[:width - 1] + "…" for t in v]


def _as_text(s: pd.Series, family: str) -> pd.Series:
    s = s.dropna()
    if family == "date":
        return pd.to_datetime(s, errors="coerce").dropna().dt.strftime("%Y-%m-%d")
    if family == "integer":
        return pd.to_numeric(s, errors="coerce").dropna().round().astype("int64").astype(str)
    return s.astype(str).str.strip()


class _Column:
    """One column prepared for comparison: its distinct values and how often each occurs."""

    def __init__(self, dataset: str, name: str, kind: str, family: str, values: pd.Series):
        self.dataset, self.name, self.kind, self.family = dataset, name, kind, family
        self.norm = _norm(name)
        counts = values.value_counts()
        self.non_null = int(counts.sum())
        self.distinct = int(counts.size)
        self.unique_share = self.distinct / self.non_null if self.non_null else 0.0
        self.unique = self.distinct == self.non_null and self.non_null > 0
        # A customer table with a few duplicated rows still has a customer key.
        self.key = self.unique or self.unique_share >= NEAR_UNIQUE
        if counts.size > MAX_DISTINCT:
            counts = counts.iloc[:MAX_DISTINCT]      # the most common values
        self.counts = counts
        self.values = set(counts.index)
        self.min = self.max = None
        if family in ("date", "integer") and counts.size:
            idx = counts.index
            self.min, self.max = str(min(idx)), str(max(idx))


def _prepare(name: str, df: pd.DataFrame) -> list[_Column]:
    kinds = S.kinds(df)
    out = []
    for col in list(df.columns)[:MAX_COLUMNS]:
        kind = kinds[str(col)]
        if kind not in LINKABLE:
            continue
        family = _family(kind, df[col])
        if family is None:
            continue
        values = _as_text(df[col], family)
        if values.empty or values.nunique() < 2:
            continue
        out.append(_Column(name, str(col), kind, family, values))
    return out


def _cardinality(a: _Column, b: _Column) -> str:
    if a.key and b.key:
        return "one-to-one"
    if a.key:
        return "one-to-many"
    if b.key:
        return "many-to-one"
    return "many-to-many"


def _comparable(a: _Column, b: _Column, same_name: bool) -> bool:
    """Columns with different names are compared only when one is a real key: an id or
    a code with many values. Otherwise small integer columns match each other by chance."""
    if same_name:
        return True
    key, other = (a, b) if a.key else (b, a)
    if not key.key:
        return False
    if key.distinct < MIN_KEY_DISTINCT or other.distinct < 5:
        return False
    return key.kind == S.ID or other.kind == S.ID or key.family == "text"


def _link(a: _Column, b: _Column, same_name: bool) -> dict | None:
    inter = a.values & b.values
    matched_a = int(a.counts[a.counts.index.isin(inter)].sum()) if inter else 0
    matched_b = int(b.counts[b.counts.index.isin(inter)].sum()) if inter else 0
    rows_a = matched_a / a.non_null if a.non_null else 0.0
    rows_b = matched_b / b.non_null if b.non_null else 0.0
    if not inter:
        if not same_name:
            return None            # the same name with no shared values is worth reporting
    elif max(rows_a, rows_b) < (MIN_SHARE if same_name else MIN_SHARE_UNNAMED):
        return None
    elif min(rows_a, rows_b) < MIN_SHARE and len(inter) < 10:
        # Two date columns that happen to share one day, a code list that shares one
        # entry: a handful of coincidences, not a link.
        return None
    key = a.key or b.key
    cardinality = _cardinality(a, b)
    coverage = max(rows_a, rows_b)
    if not inter:
        strength = "none"
    elif key and min(rows_a, rows_b) >= 0.8:
        strength = "strong"
    elif key and coverage >= 0.8:
        strength = "strong"
    elif coverage >= 0.3:
        strength = "partial"
    else:
        strength = "weak"
    # Prefer a key to a dimension, and a dimension with many values to one with few: the
    # customer id links two tables; the region they both carry only groups them.
    richness = 1.0 if key else (0.8 if min(a.distinct, b.distinct) >= MIN_KEY_DISTINCT else 0.5)
    score = coverage * (1.0 if same_name else 0.85) * richness
    only_a = [v for v in a.counts.index if v not in inter][:EXAMPLES]
    only_b = [v for v in b.counts.index if v not in inter][:EXAMPLES]
    link = {
        "a": {"dataset": a.dataset, "column": a.name, "kind": a.kind, "distinct": a.distinct,
              "unique": a.unique, "key": a.key, "rows_matched": round(rows_a, 4),
              "rows": a.non_null, "min": a.min, "max": a.max, "only_here": only_a},
        "b": {"dataset": b.dataset, "column": b.name, "kind": b.kind, "distinct": b.distinct,
              "unique": b.unique, "key": b.key, "rows_matched": round(rows_b, 4),
              "rows": b.non_null, "min": b.min, "max": b.max, "only_here": only_b},
        "same_name": same_name,
        "shared_values": len(inter),
        "role": "key" if key else "dimension",
        "cardinality": cardinality,
        "strength": strength,
        "score": round(score, 4),
    }
    link["explanation"] = explain(link)
    link["merge"] = _merge_code(link) if key and strength in ("strong", "partial") else None
    return link


def _pct(x: float) -> str:
    return f"{x:.0%}" if x >= 0.01 or x == 0 else "under 1%"


def _uniq(side: dict) -> str:
    if side["unique"]:
        return "unique"
    return f'nearly unique ({side["distinct"]:,} distinct values in {side["rows"]:,} rows)'


def explain(link: dict) -> str:
    """Plain sentences about one link, written from the numbers alone."""
    a, b = link["a"], link["b"]
    A, B = a["dataset"], b["dataset"]
    ca, cb = f'"{a["column"]}"', f'"{b["column"]}"'
    both = ca if link["same_name"] else f"{ca} and {cb}"
    parts = []
    if link["strength"] == "none":
        parts.append(f"{both} appears in both {A} and {B}, but the two share no values. "
                     "Check the formats: one side may carry a prefix, a different date "
                     "layout, or a different unit.")
        return " ".join(parts)
    if link["cardinality"] == "one-to-one":
        parts.append(f"{both} is {_uniq(a)} in {A} and {_uniq(b)} in {B}: each row on one "
                     "side matches at most one row on the other, so the tables describe "
                     "the same things.")
    elif link["cardinality"] == "one-to-many":
        parts.append(f"{ca} is {_uniq(a)} in {A} and {cb} repeats in {B}: one {A} row "
                     f"matches many {B} rows. {A} looks like the lookup table and {B} the "
                     "detail.")
    elif link["cardinality"] == "many-to-one":
        parts.append(f"{cb} is {_uniq(b)} in {B} and {ca} repeats in {A}: one {B} row "
                     f"matches many {A} rows. {B} looks like the lookup table and {A} the "
                     "detail.")
    else:
        parts.append(f"{both} repeats on both sides, so it is a shared dimension rather "
                     "than a join key: use it to group both tables the same way, not to "
                     "match rows one to one.")
    for side, other in ((a, B), (b, A)):
        share = side["rows_matched"]
        unmatched = side["rows"] - round(share * side["rows"])
        if share >= 0.999:
            parts.append(f'Every {side["dataset"]} row has a match in {other}.')
        else:
            ex = ", ".join(str(v) for v in side["only_here"][:EXAMPLES])
            parts.append(f'{_pct(share)} of {side["dataset"]} rows have a match in {other}; '
                         f'{unmatched:,} do not' + (f" (for example {ex})." if ex else "."))
    if a["kind"] == S.DATETIME and a["min"] and b["min"]:
        parts.append(f'{A} covers {a["min"]} to {a["max"]}; {B} covers {b["min"]} to {b["max"]}.')
    return " ".join(parts)


def _merge_code(link: dict) -> str:
    a, b = link["a"], link["b"]
    if link["same_name"] and a["column"] == b["column"]:
        on = f'on="{a["column"]}"'
    else:
        on = f'left_on="{a["column"]}", right_on="{b["column"]}"'
    return f'merged = pd.merge(datasets["{a["dataset"]}"], datasets["{b["dataset"]}"], {on}, how="left")'


def build(datasets: dict[str, pd.DataFrame], sources: dict[str, str] | None = None) -> dict:
    """The relationship map for every loaded dataset."""
    names = list(datasets)[:MAX_DATASETS]
    prepared = {n: _prepare(n, datasets[n]) for n in names}
    sources = sources or {}

    nodes = []
    for n in names:
        df = datasets[n]
        k = S.kinds(df)
        nodes.append({"name": n, "rows": int(len(df)), "columns_count": int(df.shape[1]),
                      "source": sources.get(n, "upload"),
                      "columns": [{"name": str(c), "kind": k[str(c)], "examples": examples(df[c])}
                                  for c in df.columns],
                      "keys": [c.name for c in prepared[n] if c.key]})

    edges = []
    for i, A in enumerate(names):
        for B in names[i + 1:]:
            links = []
            seen = set()
            for a in prepared[A]:
                for b in prepared[B]:
                    if a.family != b.family:
                        continue
                    same = a.norm == b.norm
                    if not _comparable(a, b, same):
                        continue
                    link = _link(a, b, same)
                    if link and (a.name, b.name) not in seen:
                        seen.add((a.name, b.name))
                        links.append(link)
            if not links:
                continue
            links.sort(key=lambda l: (-l["score"], not l["same_name"]))
            links = links[:MAX_LINKS_PER_PAIR]
            best = links[0]
            edges.append({"a": A, "b": B, "links": links, "best": best,
                          "strength": best["strength"], "score": best["score"]})
    edges.sort(key=lambda e: -e["score"])

    # Columns that several datasets share by name: the dimensions of the whole collection.
    by_norm: dict[str, list[tuple[str, str, str]]] = {}
    for n in names:
        for c in prepared[n]:
            by_norm.setdefault(c.norm, []).append((n, c.name, c.kind))
    dimensions = [{"column": members[0][1], "datasets": [m[0] for m in members],
                   "kinds": sorted({m[2] for m in members})}
                  for members in by_norm.values() if len(members) >= 2]
    dimensions.sort(key=lambda d: (-len(d["datasets"]), d["column"]))

    linked = {e["a"] for e in edges} | {e["b"] for e in edges}
    result = {
        "datasets": nodes,
        "edges": edges,
        "dimensions": dimensions,
        "unlinked": [n for n in names if n not in linked],
        "merges": [e["best"]["merge"] for e in edges if e["best"].get("merge")],
        "truncated": len(datasets) > MAX_DATASETS,
    }
    result["summary"] = summary_lines(result)
    return clean(result)


def summary_lines(rel: dict) -> list[str]:
    """The map as short lines, for the model and for the top of the panel."""
    lines = []
    n = len(rel["datasets"])
    if n < 2:
        return ["Only one dataset is loaded, so there is nothing to relate it to."]
    if not rel["edges"]:
        lines.append(f"{n} datasets are loaded and none of them shares a column with "
                     "another, by name or by values.")
    for e in rel["edges"]:
        b = e["best"]
        col = b["a"]["column"] if b["same_name"] else f'{b["a"]["column"]} / {b["b"]["column"]}'
        lines.append(f'{e["a"]} and {e["b"]} link through {col}: {b["cardinality"]}, '
                     f'{_pct(b["a"]["rows_matched"])} of {e["a"]} rows and '
                     f'{_pct(b["b"]["rows_matched"])} of {e["b"]} rows match ({b["strength"]}).')
    hubs = [d for d in rel["dimensions"] if len(d["datasets"]) >= 3]
    for d in hubs[:3]:
        lines.append(f'"{d["column"]}" appears in {len(d["datasets"])} datasets: '
                     + ", ".join(d["datasets"]) + ".")
    for u in rel["unlinked"]:
        lines.append(f"{u} shares no column with the other datasets.")
    return lines
