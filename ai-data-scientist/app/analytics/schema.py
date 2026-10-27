"""
What kind of column is this?

One shared answer, used by profiling, plotting, statistics and modelling, so they never
disagree about whether `zip_code` is a number.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from pandas.api import types as pt

NUMERIC = "numeric"
CATEGORICAL = "categorical"
BOOLEAN = "boolean"
DATETIME = "datetime"
TEXT = "text"
ID = "id"
EMPTY = "empty"

# A string column with more distinct values than this, relative to its length, is free
# text or an identifier and not a category.
MAX_CATEGORY_LEVELS = 50
ID_NAME_HINTS = ("id", "uuid", "guid", "key", "code", "number", "no", "num")


def _looks_like_id_name(name: str) -> bool:
    n = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    parts = n.split("_")
    return n in ID_NAME_HINTS or parts[-1] in ID_NAME_HINTS or parts[0] in ("id", "uuid")


def column_kind(s: pd.Series) -> str:
    """Classify one column. See the constants above for the possible answers."""
    non_null = s.dropna()
    n = len(non_null)
    if n == 0:
        return EMPTY

    if pt.is_bool_dtype(s):
        return BOOLEAN
    if pt.is_datetime64_any_dtype(s):
        return DATETIME
    if pt.is_timedelta64_dtype(s):
        return NUMERIC

    n_unique = non_null.nunique()

    if pt.is_numeric_dtype(s):
        if n_unique == 2 and set(pd.unique(non_null)) <= {0, 1}:
            return BOOLEAN
        # Whole numbers that are all different and named like a key: an identifier.
        if (pt.is_integer_dtype(s) and n > 20 and n_unique == n
                and _looks_like_id_name(s.name)):
            return ID
        return NUMERIC

    # Strings and everything else.
    if n_unique == 2:
        lowered = {str(v).strip().lower() for v in pd.unique(non_null)}
        if lowered <= {"true", "false"} or lowered <= {"yes", "no"} or lowered <= {"y", "n"}:
            return BOOLEAN
    if n_unique <= MAX_CATEGORY_LEVELS and (n_unique / n <= 0.5 or n <= 20):
        return CATEGORICAL
    if n_unique / n > 0.9 and n > 20:
        mean_len = non_null.astype(str).str.len().mean()
        return TEXT if mean_len > 40 else ID
    mean_len = non_null.astype(str).str.len().mean()
    return TEXT if mean_len > 40 else CATEGORICAL


def kinds(df: pd.DataFrame) -> dict[str, str]:
    return {str(c): column_kind(df[c]) for c in df.columns}


def columns_of(df: pd.DataFrame, *wanted: str) -> list[str]:
    k = kinds(df)
    return [c for c in df.columns if k[str(c)] in wanted]


# --------------------------------------------------------------------------- JSON safety
def clean(value: Any) -> Any:
    """
    Make a value safe for json.dumps: numpy scalars, NaN, timestamps and so on.

    NaN and infinity become None, because JSON has neither and browsers reject them.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return [clean(v) for v in value.tolist()]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        ts = pd.Timestamp(value)
        return None if pd.isna(ts) else ts.isoformat()
    if isinstance(value, (pd.Timedelta, np.timedelta64)):
        return str(pd.Timedelta(value))
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (int, str)):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def round_sig(x: Any, sig: int = 4) -> Any:
    """Round to significant figures, so 0.000123456 and 123456.789 both stay readable."""
    x = clean(x)
    if not isinstance(x, float) or x == 0:
        return x
    return round(x, sig - int(math.floor(math.log10(abs(x)))) - 1)


def compact(value: Any, sig: int = 5) -> Any:
    """clean(), and round every float to `sig` significant figures. Saves tokens."""
    value = clean(value)
    if isinstance(value, dict):
        return {k: compact(v, sig) for k, v in value.items()}
    if isinstance(value, list):
        return [compact(v, sig) for v in value]
    return round_sig(value, sig)


def table_payload(df: pd.DataFrame, max_rows: int = 50, max_cols: int = 30) -> dict:
    """A small slice of a frame in a shape the front-end can draw as a table."""
    shown = df.iloc[:max_rows, :max_cols]
    if isinstance(shown.index, pd.RangeIndex):
        index = None
    else:
        index = [clean(i) if not isinstance(i, tuple) else " / ".join(map(str, i))
                 for i in shown.index]
    return {
        "columns": [str(c) if not isinstance(c, tuple) else " / ".join(map(str, c))
                    for c in shown.columns],
        "rows": [[round_sig(v, 6) for v in row]
                 for row in shown.itertuples(index=False, name=None)],
        "index": index,
        "total_rows": int(len(df)),
        "total_columns": int(df.shape[1]),
        "truncated": bool(len(df) > max_rows or df.shape[1] > max_cols),
    }
