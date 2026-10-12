"""
County name -> FIPS crosswalk, and helpers for the block_geoid field.

Why this file exists
--------------------
The Food Group writes county names as free text and uses 91 distinct labels
for Minnesota's 87 counties (Hennepin and Ramsey are split into city/suburbs,
St. Louis is spelled two ways). Public data (Map the Meal Gap, Census, USDA,
BLS, DHS) is keyed on the 5-digit county FIPS code. Nothing joins until the
labels are mapped, so every table in this project carries a `fips` column and
we join on that, never on a name.

The authoritative list of the 87 MN counties and their FIPS codes is read out
of the Map the Meal Gap file rather than typed by hand, so it cannot drift.
"""
from __future__ import annotations

import re
import pandas as pd

from config import F_MMG_2026, STATE_FIPS_MN

# TFG labels that are a sub-area of a county rather than a county.
# We roll them up for every join and keep the original label in `county_label`
# in case the organizers score Q7 on the split version.
SUBCOUNTY_LABELS = {
    "Hennepin-Minneapolis": "Hennepin",
    "Hennepin-Suburbs": "Hennepin",
    "Ramsey-Saint Paul": "Ramsey",
    "Ramsey-Suburbs": "Ramsey",
}

# Spelling variants seen in the TFG extracts.
SPELLING_FIXES = {
    "saint louis": "st. louis",
    "st louis": "st. louis",
    "st. louis": "st. louis",
    "lac qui parle": "lac qui parle",
    "lake of the woods": "lake of the woods",
    "otter tail": "otter tail",
    "mille lacs": "mille lacs",
    "yellow medicine": "yellow medicine",
    "blue earth": "blue earth",
    "le sueur": "le sueur",
    "red lake": "red lake",
}

# Typos and doubled-paste values observed in the call-centre County field.
# These are free-text entries by call takers. Anything genuinely ambiguous
# (e.g. "Cottonwood/Brown") is deliberately left unmatched rather than guessed.
TYPO_FIXES = {
    "hennipen": "hennepin",
    "hennhennepin": "hennepin",
    "h": None,
    "filmorefillmore": "fillmore",
    "sterns": "stearns",
    "ramesy": "ramsey",
    "rasmey": "ramsey",
    "aanoka": "anoka",
    "dakotadakota": "dakota",
    "rroseau": "roseau",
    "usa": None,
    "cottonwood/brown": None,   # ambiguous on purpose: two counties, we do not guess
}

# Labels that are not a Minnesota county at all.
NON_COUNTY_LABELS = {"", "nan", "none", "(unknown)", "unknown", "out of state",
                     "( out of state )", "other", "n/a"}


def _normalize(name: str) -> str:
    """Lowercase, strip punctuation noise, drop the word 'county'."""
    s = str(name).strip()
    s = SUBCOUNTY_LABELS.get(s, s)          # roll up before normalizing
    s = s.lower()
    s = re.sub(r"\bcounty\b", "", s)
    s = re.sub(r",\s*(mn|minnesota)\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = SPELLING_FIXES.get(s, s)
    if s in TYPO_FIXES:
        fixed = TYPO_FIXES[s]
        s = "" if fixed is None else fixed
    return s


def mn_county_fips() -> pd.DataFrame:
    """The 87 Minnesota counties with FIPS, read from Map the Meal Gap."""
    d = pd.read_excel(F_MMG_2026, sheet_name="County", usecols=["FIPS", "State", "County, State"])
    d = d[d["State"] == "MN"].copy()
    d["fips"] = d["FIPS"].astype(int).astype(str).str.zfill(5)
    d["county_name"] = d["County, State"].str.replace(r" County, Minnesota$", "", regex=True)
    d["_key"] = d["county_name"].map(_normalize)
    return d[["fips", "county_name", "_key"]].sort_values("fips").reset_index(drop=True)


def build_crosswalk(labels) -> pd.DataFrame:
    """
    Map an iterable of raw TFG county labels to FIPS.

    Returns one row per distinct raw label with columns:
        county_label (raw), county_name (canonical), fips, match_status
    match_status is one of: matched, rolled_up, unmatched, missing.
    """
    ref = mn_county_fips().set_index("_key")
    rows = []
    for raw in pd.unique(pd.Series(list(labels))):
        raw_s = "" if pd.isna(raw) else str(raw).strip()
        key = _normalize(raw_s)
        if key in NON_COUNTY_LABELS or raw_s == "":
            rows.append((raw, None, None, "missing"))
            continue
        if key in ref.index:
            status = "rolled_up" if str(raw).strip() in SUBCOUNTY_LABELS else "matched"
            rows.append((raw, ref.loc[key, "county_name"], ref.loc[key, "fips"], status))
        else:
            rows.append((raw, None, None, "unmatched"))
    return pd.DataFrame(rows, columns=["county_label", "county_name", "fips", "match_status"])


def attach_fips(df: pd.DataFrame, label_col: str = "County") -> pd.DataFrame:
    """Add canonical `county_name`, `fips`, `county_match` columns to a frame."""
    xw = build_crosswalk(df[label_col])
    out = df.merge(xw, left_on=label_col, right_on="county_label", how="left")
    return out.rename(columns={"match_status": "county_match"}).drop(columns=["county_label"])


# ------------------------------------------------------------------ block_geoid
def split_block_geoid(series: pd.Series) -> pd.DataFrame:
    """
    Split a 15-digit 2020 Census block GEOID into its nested parts.

    A block GEOID is built by concatenation, not by lookup:

        27   053   026807   7009
        |    |     |        |
        |    |     |        +-- block         (4 digits)
        |    |     +----------- tract         (6 digits)
        |    +----------------- county        (3 digits)
        +---------------------- state         (2 digits)

    So every larger geography is just a prefix of the string. Truncate, never
    parse. See docs/BLOCK_GEOID.md for the full explanation.
    """
    s = clean_geoid(series)
    return pd.DataFrame({
        "block_geoid": s,
        "state_fips": s.str[:2],
        "fips": s.str[:5],          # county FIPS - our universal join key
        "tract_geoid": s.str[:11],  # 2020 census tract - the grain USDA LILA uses
        "bg_geoid": s.str[:12],     # block group - the grain ACS detail tables use
    })


def clean_geoid(series: pd.Series) -> pd.Series:
    """
    Read a block_geoid safely.

    Excel and pandas will happily read this column as a float, which appends
    '.0' and (for other states) can eat a leading zero. Always coerce to a
    zero-padded 15-character string before using it.
    """
    s = series.astype("string").str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)
    s = s.where(s.str.fullmatch(r"\d{1,15}"), pd.NA)
    return s.str.zfill(15)


def is_minnesota(block_geoid: pd.Series) -> pd.Series:
    return clean_geoid(block_geoid).str[:2].eq(STATE_FIPS_MN)
