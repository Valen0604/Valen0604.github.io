"""
Relationship ideas from the model.

The Relationships tab finds join keys by comparing values, with no model call. That misses
anything that needs reading: `cust_ref` and `customer_id` with a prefix on one side, an
`order_date` that matches a `month` column once it is truncated, a `store` that is the
`location` of another file. This module sends the model the schemas (names, types, a few
example values) and what the value check already found, and asks for the relationships it
would look for, each with a reason and the transform a join would need.

It is one request with no tools, kept apart from the chat so it does not grow the
conversation. The reply is JSON; anything that names a column that does not exist is
dropped, so the map never shows a link to a column the user cannot find.
"""
from __future__ import annotations

import json
import re

from ..config import Settings

MAX_SUGGESTIONS = 12
MAX_EXAMPLES = 3

SYSTEM = """\
You are a data engineer looking at several tables that a user loaded into an analysis tool. \
You see each table's column names, column types and a few example values, plus the joins an \
automatic check already found by comparing values. Propose how the tables relate.

Reply with one JSON object and nothing else, in this shape:

{
  "suggestions": [
    {"a": "<table>", "a_column": "<column>", "b": "<table>", "b_column": "<column>",
     "kind": "join" | "dimension" | "time" | "derived",
     "confidence": "high" | "medium" | "low",
     "reason": "<one or two short sentences, from the names, types and examples>",
     "transform": "<what must change for the values to match, or null>"}
  ],
  "found": [
    {"a": "<table>", "a_column": "<column>", "b": "<table>", "b_column": "<column>",
     "verdict": "agree" | "doubt", "reason": "<short>"}
  ],
  "notes": ["<a sentence about how the tables fit together as a whole, if useful>"]
}

Rules:
- kind: "join" when the columns identify the same thing (an id, a code, a name used as a \
key); "dimension" when both tables carry the same grouping (region, product type); "time" \
when a date in one table lines up with a period in another; "derived" when one column is \
computed from the other (a total from a price and a quantity, a year from a date).
- Suggest what the automatic check could not see: pairs with different names, pairs that \
need a transform (a prefix removed, lower-casing, a date truncated to the month, a code \
padded with zeros), and pairs whose values do not overlap yet but clearly should.
- Do not repeat a pair the check already found under the same two columns; instead give \
your verdict on it in "found": "agree", or "doubt" with the reason (two tables both having \
an "id" column does not make them the same ids).
- Use table and column names exactly as given. Never invent a column.
- At most 12 suggestions, the most useful first. Short reasons. No prose outside the JSON.
"""


class BadReply(Exception):
    """The model's reply could not be read as the JSON asked for."""


def _norm(name: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", str(name).lower())


def schema_text(rel: dict) -> str:
    """The tables as the model sees them: one line per column with its type and examples."""
    lines = []
    for d in rel.get("datasets", []):
        lines.append(f'## {d["name"]} ({d["rows"]:,} rows, {d["columns_count"]} columns)')
        for c in d.get("columns", []):
            ex = ", ".join(str(v) for v in (c.get("examples") or [])[:MAX_EXAMPLES])
            lines.append(f'- {c["name"]} ({c["kind"]})' + (f"  e.g. {ex}" if ex else ""))
        lines.append("")
    return "\n".join(lines).strip()


def found_text(rel: dict) -> str:
    lines = []
    for e in rel.get("edges", []):
        for l in e.get("links", []):
            a, b = l["a"], l["b"]
            lines.append(f'- {a["dataset"]}.{a["column"]} = {b["dataset"]}.{b["column"]}: '
                         f'{l["cardinality"]}, {l["strength"]}; '
                         f'{a["rows_matched"]:.0%} of {a["dataset"]} rows and '
                         f'{b["rows_matched"]:.0%} of {b["dataset"]} rows match')
    return "\n".join(lines) if lines else "- nothing: no column pair shares values by name"


def user_text(rel: dict, context: dict | None) -> str:
    parts = ["<tables>", schema_text(rel), "</tables>", "",
             "<found_by_comparing_values>", found_text(rel), "</found_by_comparing_values>"]
    ctx = {k: (v or "").strip() for k, v in (context or {}).items()}
    told = [f"{k}: {v}" for k, v in ctx.items() if v and k in
            ("description", "goal", "constraints", "notes")]
    if told:
        parts += ["", "<user_context>", "What the user said about the data:",
                  *told, "</user_context>"]
    parts += ["", "Which relationships would you look for between these tables? JSON only."]
    return "\n".join(parts)


def _extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise BadReply("The model did not answer with JSON.")
    try:
        data = json.loads(text[start:end + 1])
    except ValueError as e:
        raise BadReply(f"The model's JSON could not be read: {e}") from e
    if not isinstance(data, dict):
        raise BadReply("The model's reply was not a JSON object.")
    return data


def _merge_code(a: str, ca: str, b: str, cb: str) -> str:
    on = f'on="{ca}"' if ca == cb else f'left_on="{ca}", right_on="{cb}"'
    return f'merged = pd.merge(datasets["{a}"], datasets["{b}"], {on}, how="left")'


def validate(data: dict, rel: dict) -> dict:
    """
    Keep only suggestions that name real tables and columns, with the names spelled as
    the tables spell them. Pairs the value check already found are moved to "found".
    """
    tables: dict[str, dict[str, str]] = {}
    canon: dict[str, str] = {}
    for d in rel.get("datasets", []):
        canon[_norm(d["name"])] = d["name"]
        tables[d["name"]] = {_norm(c["name"]): c["name"] for c in d.get("columns", [])}

    def resolve(item: dict) -> tuple[str, str, str, str] | None:
        if not isinstance(item, dict):
            return None
        a = canon.get(_norm(item.get("a", "")))
        b = canon.get(_norm(item.get("b", "")))
        if not a or not b or a == b:
            return None
        ca = tables[a].get(_norm(item.get("a_column", "")))
        cb = tables[b].get(_norm(item.get("b_column", "")))
        if not ca or not cb:
            return None
        return a, ca, b, cb

    known = set()
    for e in rel.get("edges", []):
        for l in e.get("links", []):
            known.add(frozenset(((l["a"]["dataset"], l["a"]["column"]),
                                 (l["b"]["dataset"], l["b"]["column"]))))

    suggestions, found, skipped = [], [], 0
    seen = set()
    for item in data.get("suggestions") or []:
        r = resolve(item)
        if r is None:
            skipped += 1
            continue
        a, ca, b, cb = r
        pair = frozenset(((a, ca), (b, cb)))
        if pair in seen:
            continue
        seen.add(pair)
        kind = str(item.get("kind", "join")).lower()
        kind = kind if kind in ("join", "dimension", "time", "derived") else "join"
        conf = str(item.get("confidence", "medium")).lower()
        conf = conf if conf in ("high", "medium", "low") else "medium"
        entry = {"a": a, "a_column": ca, "b": b, "b_column": cb, "kind": kind,
                 "confidence": conf, "reason": str(item.get("reason") or "").strip()[:400],
                 "transform": (str(item["transform"]).strip()[:200]
                               if item.get("transform") else None)}
        if pair in known:
            # The model repeated a link the values already proved: that is a verdict.
            found.append({**{k: entry[k] for k in ("a", "a_column", "b", "b_column")},
                          "verdict": "agree", "reason": entry["reason"]})
            continue
        entry["merge"] = _merge_code(a, ca, b, cb) if kind == "join" else None
        suggestions.append(entry)
    for item in data.get("found") or []:
        r = resolve(item)
        if r is None:
            continue
        a, ca, b, cb = r
        verdict = str(item.get("verdict", "")).lower()
        if verdict not in ("agree", "doubt"):
            continue
        found.append({"a": a, "a_column": ca, "b": b, "b_column": cb, "verdict": verdict,
                      "reason": str(item.get("reason") or "").strip()[:400]})
    notes = [str(n).strip()[:400] for n in (data.get("notes") or [])
             if isinstance(n, str) and n.strip()][:5]
    return {"suggestions": suggestions[:MAX_SUGGESTIONS], "found": found, "notes": notes,
            "skipped": skipped}


def suggest(client, settings: Settings, rel: dict, context: dict | None = None) -> tuple[dict, object]:
    """
    Ask the model. Returns (result, usage): the validated suggestions and the API usage
    object, so the caller can add the cost to the session. API errors are raised as they
    are; the server turns them into a message the user can act on.
    """
    response = client.messages.create(
        model=settings.model,
        max_tokens=6000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user_text(rel, context)}],
    )
    text = "".join(getattr(b, "text", "") for b in response.content
                   if getattr(b, "type", "") == "text")
    result = validate(_extract_json(text), rel)
    result["model"] = settings.model
    return result, response.usage


def brief(result: dict) -> str:
    """What the chat agent is told, so it knows what the user has seen on the map."""
    lines = []
    for s in result.get("suggestions", []):
        line = (f'- {s["a"]}.{s["a_column"]} and {s["b"]}.{s["b_column"]} ({s["kind"]}, '
                f'{s["confidence"]} confidence): {s["reason"]}')
        if s.get("transform"):
            line += f' Needs: {s["transform"]}'
        lines.append(line)
    for f in result.get("found", []):
        if f["verdict"] == "doubt":
            lines.append(f'- doubt about the value match {f["a"]}.{f["a_column"]} = '
                         f'{f["b"]}.{f["b_column"]}: {f["reason"]}')
    if not lines:
        return ("The user asked the model for relationship ideas between the datasets; it "
                "had nothing to add to the value check.")
    return ("The user asked for relationship ideas between the datasets; a separate model "
            "call read the schemas and suggested these (unverified: check the values before "
            "relying on one):\n" + "\n".join(lines))
