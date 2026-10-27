"""
Export a conversation as one HTML file, or as a printable page that becomes a PDF.

The file is self-contained: styles, the renderer and every chart are inside it, so it can
be emailed or submitted and opens with no server. It reuses the front-end's renderer, so
the report shows exactly what the chat showed, plus the first-look dashboard and the
data-quality report for each dataset.

With print_mode the page opens the browser's print dialog, where "Save as PDF" is one of
the destinations in every browser. That is the PDF export: no PDF library, nothing to
install, and the layout is the same one the page uses.
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

from . import __version__
from .agent.prompts import CONTEXT_FIELDS
from .config import Settings
from .sessions import Session


def _collect_files(obj, found: set[str]) -> None:
    if isinstance(obj, dict):
        if obj.get("type") == "chart" and obj.get("file"):
            found.add(obj["file"])
        if obj.get("type") == "model":
            found.update(c["file"] for c in obj.get("result", {}).get("charts", []))
        for v in obj.values():
            _collect_files(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _collect_files(v, found)


PRINT_CSS = """
body.report { position: static; display:block; height:auto; overflow:auto; }
.report-wrap { max-width: 920px; margin: 0 auto; padding: 32px 20px 80px; }
.report-head { border-bottom: 1px solid var(--line); padding-bottom: 16px; margin-bottom: 20px; }
.report-head h1 { margin: 0 0 6px; font-size: 28px; letter-spacing: -.02em; }
.report-head p { margin: 2px 0; color: var(--muted); font-size: 13px; }
.report h2.sec { font-size: 20px; margin: 36px 0 12px; padding-top: 18px; border-top: 1px solid var(--line); letter-spacing: -.01em; }
.report h3.ds { font-size: 16px; margin: 18px 0 8px; }
.report .ctx { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 12px 16px; }
.report .ctx dt { font-weight: 600; font-size: 13px; color: var(--muted); margin-top: 8px; }
.report .ctx dd { margin: 2px 0 0; white-space: pre-wrap; }
.report .toc { columns: 2; column-gap: 24px; font-size: 14px; }
.report .toc li { break-inside: avoid; margin: 2px 0; }
.report .qa { margin-top: 28px; }
.report .qa-q { font-weight: 650; font-size: 16px; margin: 0 0 10px; padding-left: 12px; border-left: 3px solid var(--accent); }
.report .no-code details.code-card, .report .no-code details.tool-input, .report .no-code details.thinking { display: none; }
.print-bar { position: sticky; top: 0; z-index: 5; display: flex; gap: 10px; align-items: center; justify-content: space-between;
             background: var(--panel); border-bottom: 1px solid var(--line); padding: 10px 20px; font-size: 13.5px; }
.print-bar .btn { font-size: 13px; }
details.code-card, details.tool-input { break-inside: avoid; }
@media print {
  :root { --bg: #fff; --panel: #fff; --panel-2: #f3f4f6; --text: #111; --muted: #555; --shadow: none; }
  body { background: #fff; color: #111; font-size: 12.5px; }
  .print-bar, .link-btn, .picks, figcaption a, a.download, .typing { display: none !important; }
  .report-wrap { max-width: none; padding: 0; }
  .msg, .card, .hl, .cat, .q-card, section.dash-sec, .qa { break-inside: avoid; }
  h2.sec { break-before: page; }
  h2.sec:first-of-type { break-before: auto; }
  details { break-inside: avoid; }
  details.code-card[open] pre.code { max-height: none; white-space: pre-wrap; }
  .table-wrap { max-height: none; overflow: visible; }
  pre.code, pre.output { max-height: none; overflow: visible; white-space: pre-wrap; }
  figure.chart img { max-width: 85%; }
  .chart-svg { max-height: 260px; }
  .heat-row { grid-template-columns: 1fr; }
  a { color: inherit; text-decoration: none; }
}
"""


def build_report(session: Session, settings: Settings, static: Path,
                 print_mode: bool = False, with_code: bool = True) -> str:
    files: set[str] = set()
    _collect_files(session.transcript, files)
    images = {}
    for name in sorted(files):
        path = session.workspace / "artifacts" / Path(name).name
        if path.is_file():
            images[name] = ("data:image/png;base64,"
                            + base64.standard_b64encode(path.read_bytes()).decode("ascii"))

    context = [(label, (session.context.get(key) or "").strip())
               for key, label in CONTEXT_FIELDS]
    payload = {
        "transcript": session.transcript,
        "images": images,
        "dashboards": session.dashboards,
        "profiles": session.profiles,
        "relations": session.relations if len(session.dashboards) >= 2 else None,
        "context": [(label, value) for label, value in context if value],
        "meta": {
            "created": time.strftime("%d %B %Y, %H:%M"),
            "model": settings.model if settings.live else "offline demo (no LLM)",
            "usage": session.usage.public(),
            "version": __version__,
            "level": session.level,
            "palette": session.style.get("palette", "single"),
            "title": session.title or "Analysis report",
            "with_code": with_code,
            "print": print_mode,
        },
    }
    # "</" inside a <script> would end it early. Escaping the slash is valid JSON.
    data = json.dumps(payload, ensure_ascii=False, default=str).replace("</", "<\\/")
    css = (static / "styles.css").read_text(encoding="utf-8")
    render = (static / "render.js").read_text(encoding="utf-8")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analysis report</title>
<style>{css}
{PRINT_CSS}</style>
</head>
<body class="report">
<div class="print-bar" id="print-bar" hidden>
  <span>This is the printable report. Choose "Save as PDF" as the printer to keep it as a file.</span>
  <span>
    <label><input type="checkbox" id="toggle-code"> include code</label>
    <button class="btn primary" onclick="window.print()">Print / Save as PDF</button>
  </span>
</div>
<div class="report-wrap report" id="wrap">
  <div class="report-head">
    <h1>Analysis report</h1>
    <p id="meta"></p>
    <p>Produced by AI Data Scientist. Every number comes from code that ran on the
       uploaded data. Open a "Ran Python" block to see the code.</p>
  </div>
  <div id="body"></div>
</div>
<script id="data" type="application/json">{data}</script>
<script>{render}</script>
<script>
  const DATA = JSON.parse(document.getElementById("data").textContent);
  const {{ el }} = Render;
  Render.artifactUrl = (file) => DATA.images[file] || "";
  Render.downloadUrl = () => null;
  const m = DATA.meta;
  Render.palette = m.palette || "single";
  document.title = m.title;
  document.querySelector(".report-head h1").textContent = m.title;
  document.getElementById("meta").textContent =
    m.created + "  |  model: " + m.model + "  |  detail level: " + m.level +
    (m.usage.requests ? "  |  estimated API cost: $" + m.usage.cost_usd.toFixed(3) : "");
  const body = document.getElementById("body");
  const wrap = document.getElementById("wrap");
  wrap.classList.toggle("no-code", !m.with_code);

  // 1. What the user told us
  if (DATA.context.length) {{
    body.append(el("h2", {{ class: "sec" }}, "About the data"),
      el("dl", {{ class: "ctx" }}, DATA.context.map(([k, v]) => [el("dt", {{}}, k), el("dd", {{}}, v)])));
  }}

  // 2. Dashboards and data quality, one per dataset
  const uploads = DATA.transcript.filter((t) => t.role === "upload");
  const profiles = {{ ...(DATA.profiles || {{}}) }};
  for (const u of uploads) for (const p of u.datasets) profiles[p.name] = profiles[p.name] || p;
  const names = Object.keys(DATA.dashboards);
  if (names.length) {{
    body.append(el("h2", {{ class: "sec" }}, "First look"));
    for (const name of names) {{
      body.append(el("h3", {{ class: "ds" }}, "Dataset: ", el("code", {{}}, name)), Render.dashboard(DATA.dashboards[name]));
    }}
    if (DATA.relations) {{
      body.append(el("h2", {{ class: "sec" }}, "How the datasets relate"), Render.relations(DATA.relations));
    }}
    body.append(el("h2", {{ class: "sec" }}, "Data quality"));
    for (const name of names) {{
      if (profiles[name]) body.append(el("h3", {{ class: "ds" }}, "Dataset: ", el("code", {{}}, name)), Render.quality(profiles[name]));
    }}
  }}

  // 3. The conversation, as questions and answers
  const questions = DATA.transcript.filter((t) => t.role === "user");
  if (questions.length) {{
    body.append(el("h2", {{ class: "sec" }}, "Questions and answers"),
      el("ol", {{ class: "toc" }}, questions.map((q, i) => el("li", {{}},
        el("a", {{ href: "#q" + (i + 1) }}, q.text.length > 90 ? q.text.slice(0, 89) + "…" : q.text)))));
    let n = 0;
    for (const item of DATA.transcript) {{
      if (item.role === "user") {{
        n++;
        body.append(el("div", {{ class: "qa", id: "q" + n }}, el("p", {{ class: "qa-q" }}, n + ". " + item.text)));
      }} else if (item.role === "assistant") {{
        body.append(Render.transcriptItem(item));
      }} else if (item.role === "upload") {{
        body.append(el("p", {{ class: "muted small" }}, "Uploaded " + item.file));
      }}
    }}
  }}

  if (m.print) {{
    const bar = document.getElementById("print-bar");
    bar.hidden = false;
    const box = document.getElementById("toggle-code");
    box.checked = m.with_code;
    box.addEventListener("change", () => wrap.classList.toggle("no-code", !box.checked));
    setTimeout(() => window.print(), 600);
  }}
</script>
</body>
</html>"""
