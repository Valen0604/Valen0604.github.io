"""
Read an uploaded file into one or more DataFrames.

The rule that drives this file: **never silently change what a value means.**
CSV text is read as text first and types are inferred afterwards, so `00501` stays a ZIP
code and does not become the number 501. Every conversion that is made is written to a
list of notes, and those notes are shown to the user and to the model.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.api import types as pt

SUPPORTED = {".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls", ".json", ".jsonl",
             ".ndjson", ".parquet"}

# Share of non-empty values that must convert before a column changes type.
NUMERIC_THRESHOLD = 0.98
DATE_THRESHOLD = 0.95

_MISSING = {"", "na", "n/a", "nan", "null", "none", "nil", "-", "--", "?", "#n/a",
            "#na", "missing", "undefined"}
_NUMERIC_JUNK = re.compile(r"[,$€£\s]")
_DATE_HINT = re.compile(
    r"(?:\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})|(?:\d{1,2}:\d{2})|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.I)


class LoadError(ValueError):
    """The file could not be read. The message is safe to show to the user."""


def dataset_name(filename: str, sheet: str | None = None) -> str:
    """`Q3 Sales (final).xlsx` + `Sheet 1` -> `q3_sales_final__sheet_1`"""
    def slug(text: str) -> str:
        text = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
        return text or "data"
    base = slug(Path(filename).stem)
    if base[0].isdigit():
        base = "d_" + base
    return f"{base}__{slug(sheet)}" if sheet else base


# ------------------------------------------------------------------------------ readers
def _decode(raw: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise LoadError("The file is not text in an encoding this app recognises.")


def _sniff_delimiter(text: str, default: str = ",") -> str:
    sample = "\n".join(text.splitlines()[:50])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in (",", ";", "\t", "|")}
        best = max(counts, key=counts.get)
        return best if counts[best] else default


def _read_delimited(path: Path, notes: list[str]) -> pd.DataFrame:
    text, enc = _decode(path.read_bytes())
    if enc not in ("utf-8", "utf-8-sig"):
        notes.append(f"Read with the {enc} text encoding, because the file is not UTF-8.")
    sep = "\t" if path.suffix.lower() == ".tsv" else _sniff_delimiter(text)
    if sep != "," and path.suffix.lower() == ".csv":
        shown = {"\t": "tab", ";": "semicolon", "|": "pipe"}.get(sep, sep)
        notes.append(f"Columns are separated by {shown}, not comma.")
    try:
        # dtype=str: read everything as text; types are inferred below, with notes.
        return pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False,
                           na_values=[], skip_blank_lines=True, on_bad_lines="warn")
    except pd.errors.EmptyDataError as e:
        raise LoadError("The file is empty.") from e
    except pd.errors.ParserError as e:
        raise LoadError(f"The file could not be parsed as a table: {e}") from e


def _read_json(path: Path, notes: list[str]) -> pd.DataFrame:
    text, _ = _decode(path.read_bytes())
    if path.suffix.lower() in (".jsonl", ".ndjson"):
        return pd.read_json(io.StringIO(text), lines=True)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        try:
            return pd.read_json(io.StringIO(text), lines=True)
        except ValueError as e:
            raise LoadError(f"The file is not valid JSON: {e}") from e
    if isinstance(obj, dict):
        # {"data": [...]} or {"records": [...]}: use the one list of records inside.
        lists = {k: v for k, v in obj.items()
                 if isinstance(v, list) and v and isinstance(v[0], dict)}
        if len(lists) == 1:
            key, obj = next(iter(lists.items()))
            notes.append(f'Used the list of records under the key "{key}".')
    try:
        return pd.json_normalize(obj)
    except Exception as e:  # json_normalize raises several unrelated types
        raise LoadError(f"The JSON is not a table of records: {e}") from e


def read_any(path: str | Path, original_name: str | None = None
             ) -> dict[str, tuple[pd.DataFrame, list[str]]]:
    """
    Read a file. Returns {dataset_name: (frame, notes)}.

    An Excel workbook gives one dataset per non-empty sheet.
    """
    path = Path(path)
    shown = original_name or path.name
    ext = Path(shown).suffix.lower()
    if ext not in SUPPORTED:
        raise LoadError(f"{ext or 'This'} files are not supported. "
                        f"Supported: {', '.join(sorted(SUPPORTED))}.")

    out: dict[str, tuple[pd.DataFrame, list[str]]] = {}
    if ext in (".xlsx", ".xlsm", ".xls"):
        try:
            sheets = pd.read_excel(path, sheet_name=None)
        except Exception as e:
            raise LoadError(f"The workbook could not be opened: {e}") from e
        real = {k: v for k, v in sheets.items() if not v.dropna(how="all").empty}
        if not real:
            raise LoadError("The workbook has no sheet with data in it.")
        for sheet, frame in real.items():
            notes: list[str] = []
            name = dataset_name(shown, sheet if len(real) > 1 else None)
            out[name] = (tidy(frame, notes, infer_text=True), notes)
        if len(real) > 1:
            first = next(iter(out.values()))[1]
            first.insert(0, f"The workbook has {len(real)} sheets with data. "
                            "Each one was loaded as its own dataset.")
        return out

    notes = []
    if ext == ".parquet":
        try:
            frame = pd.read_parquet(path)
        except Exception as e:
            raise LoadError(f"The parquet file could not be read: {e}") from e
        infer = False
    elif ext in (".json", ".jsonl", ".ndjson"):
        frame = _read_json(path, notes)
        infer = True
    else:
        frame = _read_delimited(path, notes)
        infer = True

    out[dataset_name(shown)] = (tidy(frame, notes, infer_text=infer), notes)
    return out


# ------------------------------------------------------------------------ type inference
def _unique_names(columns) -> list[str]:
    seen: dict[str, int] = {}
    names = []
    for i, c in enumerate(columns):
        name = str(c).strip()
        if not name or name.lower().startswith("unnamed:"):
            name = f"column_{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        names.append(name)
    return names


def _to_number(s: pd.Series) -> tuple[pd.Series | None, str | None]:
    """Try to read a text column as numbers. Returns (converted or None, note or None)."""
    text = s.dropna().astype(str).str.strip()
    if text.empty:
        return None, None

    # Digit strings with a leading zero are codes (ZIP, FIPS, account numbers).
    digits = text[text.str.fullmatch(r"\d+")]
    if len(digits) and (digits.str.len() > 1).any() and (
            digits[digits.str.len() > 1].str.startswith("0").any()):
        if len(digits) / len(text) > 0.9:
            return None, "kept as text because values have leading zeros (looks like a code)"

    percent = text.str.endswith("%")
    is_percent = percent.mean() > 0.9
    negative = text.str.fullmatch(r"\(.*\)")          # accounting style: (1,234)
    cleaned = text.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    cleaned = cleaned.str.replace("%", "", regex=False)
    cleaned = cleaned.str.replace(_NUMERIC_JUNK, "", regex=True)
    nums = pd.to_numeric(cleaned, errors="coerce")
    share = nums.notna().mean()
    if share < NUMERIC_THRESHOLD:
        return None, None

    full = pd.Series(np.nan, index=s.index, dtype="float64")
    full.loc[nums.index] = nums
    detail = []
    if is_percent:
        detail.append("percent signs removed; 45% is stored as 45, not 0.45")
    if text.str.contains(r"[$€£]").any():
        detail.append("currency symbols removed")
    if text.str.contains(",").any():
        detail.append("thousands separators removed")
    if negative.any():
        detail.append("values in brackets read as negative")
    failed = int(nums.isna().sum())
    if failed:
        detail.append(f"{failed} value(s) that are not numbers became missing")

    whole = nums.dropna()
    if len(whole) and (whole % 1 == 0).all() and whole.abs().max() < 2**53:
        full = full.astype("Int64")
    return full, "; ".join(detail) or None


def _to_datetime(s: pd.Series) -> pd.Series | None:
    text = s.dropna().astype(str).str.strip()
    if text.empty or text.str.len().mean() < 6:
        return None
    sample = text.sample(min(len(text), 200), random_state=0)
    if sample.str.contains(_DATE_HINT).mean() < 0.9:
        return None
    parsed = pd.to_datetime(text, errors="coerce", format="mixed")
    if parsed.notna().mean() < DATE_THRESHOLD:
        return None
    if getattr(parsed.dt, "tz", None) is not None:
        parsed = parsed.dt.tz_convert("UTC").dt.tz_localize(None)
    years = parsed.dropna().dt.year
    if len(years) and (years.min() < 1800 or years.max() > 2200):
        return None
    full = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    full.loc[parsed.index] = parsed
    return full


def tidy(df: pd.DataFrame, notes: list[str], infer_text: bool = True) -> pd.DataFrame:
    """Clean column names, drop empty rows and columns, and infer types. Notes what it did."""
    df = df.copy()
    before = list(map(str, df.columns))
    df.columns = _unique_names(df.columns)
    renamed = [(b, a) for b, a in zip(before, df.columns) if b != a]
    if renamed:
        shown = ", ".join(f'"{b}" to "{a}"' for b, a in renamed[:5])
        more = f" and {len(renamed) - 5} more" if len(renamed) > 5 else ""
        notes.append(f"Renamed columns: {shown}{more}.")

    text_cols = [c for c in df.columns
                 if pt.is_string_dtype(df[c]) or pt.is_object_dtype(df[c])]

    # Markers like "N/A" and "-" become real missing values.
    swapped = 0
    for c in text_cols:
        as_text = df[c].astype("object")
        mask = as_text.map(lambda v: isinstance(v, str) and v.strip().lower() in _MISSING)
        swapped += int(mask.sum())
        df[c] = as_text.where(~mask, other=np.nan)
    if swapped:
        notes.append(f'{swapped:,} empty or placeholder cell(s) such as "" and "N/A" '
                     "are treated as missing.")

    rows0, cols0 = df.shape
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if df.shape[0] < rows0:
        notes.append(f"Dropped {rows0 - df.shape[0]:,} completely empty row(s).")
    if df.shape[1] < cols0:
        notes.append(f"Dropped {cols0 - df.shape[1]} completely empty column(s).")
    df = df.reset_index(drop=True)

    if infer_text:
        for c in [c for c in text_cols if c in df.columns]:
            col = df[c].map(lambda v: v.strip() if isinstance(v, str) else v)
            number, why = _to_number(col)
            if number is not None:
                df[c] = number
                if why:
                    notes.append(f'"{c}" read as a number ({why}).')
                continue
            if why:
                notes.append(f'"{c}" {why}.')
                df[c] = col
                continue
            dates = _to_datetime(col)
            if dates is not None:
                lost = int(dates.isna().sum() - col.isna().sum())
                df[c] = dates
                notes.append(f'"{c}" read as dates'
                             + (f"; {lost} value(s) that are not dates became missing."
                                if lost else "."))
                continue
            df[c] = col

    if df.empty:
        raise LoadError("The file has column names but no rows of data.")
    return df


def describe_load(name: str, df: pd.DataFrame, notes: list[str]) -> str:
    """One paragraph for the model: what was loaded and what was changed on the way in."""
    lines = [f'Dataset "{name}": {len(df):,} rows, {df.shape[1]} columns.']
    lines += [f"- {n}" for n in notes]
    return "\n".join(lines)
