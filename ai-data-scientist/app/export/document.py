"""
A document is what both exporters draw: a title, a few lines of context, and sections of
blocks (see markdown.py), with the chart files the blocks refer to.

Two ways to make one:

    from_session(...)   the answers the user picked from a conversation, charts and all
    from_markdown(...)  a report the agent wrote on purpose with the export_report tool
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from . import markdown as md

MAX_TABLE_ROWS = 25
MAX_TABLE_COLS = 8
MAX_WARNINGS = 10


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        if abs(v) >= 1e4:
            return f"{v:,.0f}"
        return f"{v:.4g}"
    return str(v)


def _cells(values) -> list[list[dict]]:
    return [[md.run(_fmt(v))] for v in values]


def _table(columns, rows, index=None) -> dict:
    cols = list(columns)[:MAX_TABLE_COLS]
    head = ([""] if index else []) + cols
    body = []
    for r, row in enumerate(list(rows)[:MAX_TABLE_ROWS]):
        values = ([index[r]] if index else []) + list(row)[:MAX_TABLE_COLS]
        body.append(_cells(values))
    return {"type": "table", "head": [[md.run(str(h))] for h in head], "rows": body}


def _para(text: str, **flags) -> dict:
    return {"type": "paragraph", "runs": [md.run(text, **flags)]}


def _note(total_rows: int, shown: int, total_cols: int, shown_cols: int) -> dict | None:
    bits = []
    if total_rows > shown:
        bits.append(f"{shown:,} of {total_rows:,} rows")
    if total_cols > shown_cols:
        bits.append(f"{shown_cols} of {total_cols} columns")
    return _para("Showing " + " and ".join(bits) + ".", italic=True) if bits else None


def card_blocks(card: dict, with_code: bool) -> list[dict]:
    """The blocks that stand for one result card in the chat."""
    kind = card.get("type")
    out: list[dict] = []
    if kind == "chart":
        out.append({"type": "image", "file": card["file"], "title": card.get("title") or ""})
    elif kind == "table":
        if card.get("title"):
            out.append(_para(card["title"], bold=True))
        out.append(_table(card["columns"], card["rows"], card.get("index")))
        note = _note(card.get("total_rows", len(card["rows"])), min(len(card["rows"]), MAX_TABLE_ROWS),
                     card.get("total_columns", len(card["columns"])),
                     min(len(card["columns"]), MAX_TABLE_COLS))
        if note:
            out.append(note)
    elif kind == "profile":
        p = card["profile"]
        out.append(_para(f'Profile of {p["name"]}: {p["rows"]:,} rows, {p["columns_count"]} '
                         f'columns, {p["missing_cells_share"]:.1%} of cells missing, '
                         f'{p["duplicate_rows"]:,} duplicate rows.'))
        warnings = [w for w in p.get("warnings", []) if w["level"] != "info"][:MAX_WARNINGS]
        if warnings:
            out.append({"type": "list", "ordered": False, "items": [
                {"level": 0, "runs": [md.run(("Serious: " if w["level"] == "high" else "Check: "), bold=True),
                                      md.run((w["column"] + ": ") if w.get("column") else ""),
                                      md.run(w["message"])]} for w in warnings]})
    elif kind == "stat":
        r = card["result"]
        out.append(_para(r.get("plain", ""), bold=True))
        rows = [["Test", r.get("test", "")]]
        p = r.get("p", r.get("spearman_p"))
        if p is not None:
            rows.append(["p-value", "< 0.001" if p < 0.001 else _fmt(p)])
        for key, label in (("cohens_d", "Cohen's d"), ("eta_squared", "Eta squared"),
                           ("cramers_v", "Cramér's V"), ("spearman_r", "Spearman r"),
                           ("pearson_r", "Pearson r"), ("n", "Rows")):
            if r.get(key) is not None:
                rows.append([label, _fmt(r[key]) + (f" ({r['effect_size']})"
                                                     if key in ("cohens_d", "eta_squared", "cramers_v")
                                                     and r.get("effect_size") else "")])
        out.append(_table(["", ""], rows))
        if r.get("notes"):
            out.append({"type": "list", "ordered": False,
                        "items": [{"level": 0, "runs": [md.run(n)]} for n in r["notes"]]})
    elif kind == "model":
        r = card["result"]
        out.append(_para(f'Model for {r["target"]} ({r["task"]}): {r["headline"]}', bold=True))
        keys = list(r.get("test_metrics", {}))
        out.append(_table(["", *keys], [
            [f'{r["best_model"]} (test set)', *[r["test_metrics"].get(k) for k in keys]],
            ["baseline (test set)", *[r["baseline_test_metrics"].get(k) for k in keys]],
            [f'{r["best_model"]} (training rows)', *[r["train_metrics"].get(k) for k in keys]]]))
        if r.get("warnings"):
            out.append({"type": "list", "ordered": False,
                        "items": [{"level": 0, "runs": [md.run("Warning: ", bold=True), md.run(w)]}
                                  for w in r["warnings"]]})
        for c in r.get("charts", []):
            out.append({"type": "image", "file": c["file"], "title": c.get("title") or ""})
        if r.get("caveat"):
            out.append(_para(r["caveat"], italic=True))
    elif kind == "code":
        if with_code:
            out.append(_para(card.get("purpose") or "Python code", bold=True))
            out.append({"type": "code", "lang": "python", "text": card.get("code", "")})
            if card.get("stdout"):
                out.append({"type": "code", "lang": "", "text": card["stdout"]})
        if card.get("error"):
            out.append(_para("This code failed: " + card["error"].splitlines()[-1], italic=True))
        for c in card.get("changes") or []:
            out.append(_para(f'{c["dataset"]} {c["change"]}: {c["rows"]:,} rows, '
                             f'{c["columns_count"]} columns.', italic=True))
    elif kind in ("notice", "error"):
        out.append(_para(card.get("message", ""), italic=True))
    return out


def turn_blocks(parts: list[dict], with_code: bool) -> list[dict]:
    """The blocks for one assistant message."""
    out: list[dict] = []
    for p in parts:
        if p["type"] == "text":
            out += md.parse(p["text"])
        elif p["type"] == "tool":
            for c in p.get("cards") or []:
                out += card_blocks(c, with_code)
            if p.get("status") == "error" and p.get("error") and not p.get("cards"):
                out.append(_para("A step failed: " + str(p["error"])[:300], italic=True))
        elif p["type"] == "notice":
            out += md.parse(p.get("text", ""))
    return out


def _images(blocks: list[dict], artifacts: Path) -> dict[str, Path]:
    found = {}
    for b in blocks:
        if b["type"] == "image":
            path = artifacts / Path(b["file"]).name
            if path.is_file():
                found[b["file"]] = path
    return found


def _overview(session, with_relations: bool = True) -> list[dict]:
    """What the dashboards found, as text: a short "first look" section."""
    out: list[dict] = []
    for name, d in session.dashboards.items():
        out.append({"type": "heading", "level": 3, "runs": [md.run(f"Dataset {name}")]})
        out.append(_para(f'{d["rows"]:,} rows, {d["columns_count"]} columns, '
                         f'{d.get("missing_cells_share", 0):.1%} of cells missing, '
                         f'{d.get("duplicate_rows", 0):,} duplicate rows.'))
        if d.get("highlights"):
            out.append({"type": "list", "ordered": False, "items": [
                {"level": 0, "runs": md.inline(h["title"].replace("`", "")) + [md.run(". " + h["detail"].replace("`", ""))]}
                for h in d["highlights"]]})
    rel = getattr(session, "relations", None)
    if with_relations and rel and len(rel.get("datasets", [])) >= 2:
        out.append({"type": "heading", "level": 3, "runs": [md.run("How the datasets relate")]})
        out.append({"type": "list", "ordered": False,
                    "items": [{"level": 0, "runs": [md.run(s)]} for s in rel.get("summary", [])]})
    return out


def _question_heading(text: str) -> str:
    """A question as a heading. A message that was a block of code gets its first line."""
    text = text.strip()
    if text.startswith("```"):
        lines = [l for l in text.strip("`").splitlines()[1:] if l.strip()]
        first = lines[0].strip() if lines else "code"
        return "Code: " + (first[:70] + "…" if len(first) > 70 else first)
    text = re.sub(r"\s+", " ", text)
    return text[:160] + "…" if len(text) > 160 else text


def from_session(session, turns: list[int] | None = None, with_code: bool = False,
                 with_overview: bool = False, title: str | None = None, model: str = "") -> dict:
    """
    The chosen answers of a conversation. `turns` are 1-based question numbers as the
    report numbers them; None means every question.
    """
    questions = [t for t in session.transcript if t["role"] == "user"]
    wanted = set(turns) if turns else set(range(1, len(questions) + 1))
    sections = []
    n = 0
    current = None
    for item in session.transcript:
        if item["role"] == "user":
            n += 1
            current = {"heading": _question_heading(item["text"]), "blocks": []} if n in wanted else None
            if current:
                sections.append(current)
        elif item["role"] == "assistant" and current is not None:
            current["blocks"] += turn_blocks(item.get("parts", []), with_code)
    if with_overview:
        sections.insert(0, {"heading": "First look at the data", "blocks": _overview(session)})
    context = [(label, (session.context.get(key) or "").strip()) for key, label in (
        ("description", "What the data is"), ("goal", "Goal"), ("constraints", "Constraints"))]
    datasets = [{"name": d["name"], "rows": d["rows"], "columns_count": d["columns_count"]}
                for d in session.dashboards.values()] if session.dashboards else []
    all_blocks = [b for s in sections for b in s["blocks"]]
    return {
        "title": title or (session.title if getattr(session, "title", "") else "Analysis report"),
        "subtitle": time.strftime("%d %B %Y") + (f"  |  {model}" if model else ""),
        "context": [(k, v) for k, v in context if v],
        "datasets": datasets,
        "sections": sections,
        "images": _images(all_blocks, session.workspace / "artifacts"),
        "footer": "Produced by AI Data Scientist. Every number comes from code that ran on "
                  "the uploaded data.",
    }


def from_markdown(title: str, content: str, artifacts: Path, charts: list[str] | None = None,
                  model: str = "", datasets: list[dict] | None = None) -> dict:
    """A report the agent wrote. Charts named in `charts` but not placed in the text are
    appended at the end, in order."""
    blocks = md.parse(content)
    placed = {b["file"] for b in blocks if b["type"] == "image"}
    extra = [c for c in (charts or []) if c not in placed and (artifacts / Path(c).name).is_file()]
    if extra:
        blocks.append({"type": "heading", "level": 2, "runs": [md.run("Charts")]})
        blocks += [{"type": "image", "file": c, "title": ""} for c in extra]
    # One section per top-level heading, so slides and the PDF have a structure to follow.
    sections: list[dict] = []
    current = {"heading": "", "blocks": []}
    for b in blocks:
        if b["type"] == "heading" and b["level"] <= 2:
            if current["blocks"] or current["heading"]:
                sections.append(current)
            current = {"heading": md.plain(b["runs"]), "blocks": []}
        else:
            current["blocks"].append(b)
    if current["blocks"] or current["heading"]:
        sections.append(current)
    return {
        "title": re.sub(r"\s+", " ", title or "Report").strip()[:120],
        "subtitle": time.strftime("%d %B %Y") + (f"  |  {model}" if model else ""),
        "context": [],
        "datasets": datasets or [],
        "sections": sections,
        "images": _images(blocks, artifacts),
        "footer": "Produced by AI Data Scientist. Every number comes from code that ran on "
                  "the uploaded data.",
    }
