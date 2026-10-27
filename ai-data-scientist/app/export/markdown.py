"""
A small Markdown reader: text in, a list of blocks out.

It covers what the agent writes: headings, paragraphs, lists, pipe tables, fenced code,
quotes, rules, images, and inline bold, italic, code and links. It mirrors the renderer
in app/static/render.js so the export shows what the chat showed. It does not try to be
a complete Markdown implementation.

A block is a dict with a "type". Inline text is a list of runs:
    {"text": "...", "bold": bool, "italic": bool, "code": bool, "link": url or None}
"""
from __future__ import annotations

import json
import re

RE_LIST = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
RE_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
RE_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
RE_RULE = re.compile(r"^\s*([-*_])\s*\1\s*\1[\s\-*_]*$")
RE_IMAGE = re.compile(r"^\s*!\[([^\]]*)\]\(([^)\s]+)\)\s*$")
RE_INLINE = re.compile(
    r"(`[^`\n]+`)"                                  # code
    r"|(\*\*[^*\n]+?\*\*)"                          # bold
    r"|(?<![*\w])(\*[^*\s][^*\n]*?\*)(?![*\w])"     # italic
    r"|(?<![_\w])(_[^_\s][^_\n]*?_)(?![_\w])"       # italic
    r"|(\[[^\]\n]+\]\(https?://[^)\s]+\))")         # link
FOLLOWUP_LANG = "followups"


def run(text: str, **flags) -> dict:
    return {"text": text, "bold": False, "italic": False, "code": False, "link": None, **flags}


def inline(text: str) -> list[dict]:
    """Inline Markdown as runs."""
    out: list[dict] = []
    pos = 0
    for m in RE_INLINE.finditer(text):
        if m.start() > pos:
            out.append(run(text[pos:m.start()]))
        s = m.group(0)
        if m.group(1):
            out.append(run(s[1:-1], code=True))
        elif m.group(2):
            out.append(run(s[2:-2], bold=True))
        elif m.group(3) or m.group(4):
            out.append(run(s[1:-1], italic=True))
        else:
            label, url = re.match(r"\[([^\]]+)\]\(([^)]+)\)", s).groups()
            out.append(run(label, link=url))
        pos = m.end()
    if pos < len(text):
        out.append(run(text[pos:]))
    return out or [run("")]


def plain(runs: list[dict]) -> str:
    return "".join(r["text"] for r in runs)


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def _is_table_start(lines: list[str], i: int) -> bool:
    return "|" in lines[i] and i + 1 < len(lines) and bool(RE_TABLE_RULE.match(lines[i + 1]))


def parse(source: str) -> list[dict]:
    lines = (source or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if re.match(r"^\s*```", line):                               # fenced code
            lang = re.sub(r"^\s*```", "", line).strip()
            body = []
            i += 1
            while i < len(lines) and not re.match(r"^\s*```", lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            if lang == FOLLOWUP_LANG:
                continue                      # the follow-up buttons are not report content
            out.append({"type": "code", "lang": lang, "text": "\n".join(body)})
            continue
        if not line.strip():
            i += 1
            continue
        m = RE_HEADING.match(line)
        if m:
            out.append({"type": "heading", "level": len(m.group(1)), "runs": inline(m.group(2))})
            i += 1
            continue
        if RE_RULE.match(line):
            out.append({"type": "rule"})
            i += 1
            continue
        m = RE_IMAGE.match(line)
        if m:
            out.append({"type": "image", "file": m.group(2), "title": m.group(1)})
            i += 1
            continue
        if _is_table_start(lines, i):
            head = _split_row(line)
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                cells = _split_row(lines[i])
                rows.append([inline(c) for c in (cells + [""] * len(head))[:len(head)]])
                i += 1
            out.append({"type": "table", "head": [inline(h) for h in head], "rows": rows})
            continue
        if re.match(r"^\s*>", line):
            body = []
            while i < len(lines) and re.match(r"^\s*>", lines[i]):
                body.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append({"type": "quote", "runs": inline(" ".join(body))})
            continue
        if RE_LIST.match(line):
            items: list[dict] = []
            ordered = False
            while i < len(lines) and lines[i].strip() and \
                    (RE_LIST.match(lines[i]) or re.match(r"^\s{2,}\S", lines[i])):
                m = RE_LIST.match(lines[i])
                if m:
                    indent = len(m.group(1).replace("\t", "    "))
                    if not items:
                        ordered = m.group(2)[0].isdigit()
                    items.append({"runs": inline(m.group(3)), "level": min(indent // 2, 3)})
                elif items:                                        # continuation line
                    items[-1]["runs"] += [run(" ")] + inline(lines[i].strip())
                i += 1
            out.append({"type": "list", "ordered": ordered, "items": items})
            continue
        para = []                                                    # paragraph
        while i < len(lines) and lines[i].strip() and not re.match(r"^\s*```", lines[i]) \
                and not RE_HEADING.match(lines[i]) and not RE_LIST.match(lines[i]) \
                and not re.match(r"^\s*>", lines[i]) and not _is_table_start(lines, i) \
                and not RE_IMAGE.match(lines[i]):
            para.append(lines[i].strip())
            i += 1
        if para:
            out.append({"type": "paragraph", "runs": inline(" ".join(para))})
        else:
            i += 1
    return out


def text_of(blocks: list[dict]) -> str:
    """The blocks as plain text, one block per line. For previews and tests."""
    lines = []
    for b in blocks:
        if b["type"] in ("heading", "paragraph", "quote"):
            lines.append(plain(b["runs"]))
        elif b["type"] == "list":
            lines += ["- " + plain(it["runs"]) for it in b["items"]]
        elif b["type"] == "table":
            lines.append(" | ".join(plain(c) for c in b["head"]))
            lines += [" | ".join(plain(c) for c in r) for r in b["rows"]]
        elif b["type"] == "code":
            lines.append(b["text"])
        elif b["type"] == "image":
            lines.append(f"[chart: {b.get('title') or b['file']}]")
    return "\n".join(lines)


def dumps(blocks: list[dict]) -> str:
    return json.dumps(blocks, ensure_ascii=False)
