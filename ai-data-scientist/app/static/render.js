/*
 * render.js: turns data into DOM.
 *
 * Shared by the live chat (app.js) and the exported report (app/report.py), so the two
 * always look the same. No dependencies.
 *
 * To add a card for a new tool: write a function that returns an element, and register
 * it in CARDS at the bottom.
 */
const Render = (() => {
  "use strict";

  // ------------------------------------------------------------------ small helpers
  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "html") node.innerHTML = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? "" : v);
    }
    for (const child of children.flat(Infinity)) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child.nodeType ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function num(v, digits = 4) {
    if (v === null || v === undefined || v === "") return "";
    if (typeof v !== "number") return String(v);
    if (Number.isInteger(v)) return v.toLocaleString("en-US");
    const abs = Math.abs(v);
    if (abs !== 0 && (abs < 0.001 || abs >= 1e9)) return v.toExponential(2);
    return v.toLocaleString("en-US", { maximumSignificantDigits: digits });
  }
  const pct = (v, d = 1) => (v === null || v === undefined ? "" : (v * 100).toFixed(d) + "%");

  // ------------------------------------------------------------------------ markdown
  // A small, safe Markdown renderer. All text is escaped before any tag is added, and
  // links are limited to http and https, so model output cannot inject script.
  function inline(text) {
    const codes = [];
    text = text.replace(/`([^`\n]+)`/g, (_, c) => {
      codes.push(c);
      return "\u0000" + (codes.length - 1) + "\u0000";
    });
    text = esc(text);
    text = text.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    text = text.replace(/\*\*([^*\n]+?)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/(^|[^*\w])\*([^*\s][^*\n]*?)\*(?![*\w])/g, "$1<em>$2</em>");
    text = text.replace(/(^|[^_\w])_([^_\s][^_\n]*?)_(?![_\w])/g, "$1<em>$2</em>");
    text = text.replace(/\u0000(\d+)\u0000/g, (_, i) => "<code>" + esc(codes[+i]) + "</code>");
    return text;
  }

  const RE_LIST = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
  const RE_TABLE_RULE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

  function splitRow(line) {
    let s = line.trim();
    if (s.startsWith("|")) s = s.slice(1);
    if (s.endsWith("|")) s = s.slice(0, -1);
    return s.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|"));
  }

  function list(lines) {
    // Build nested lists from indentation.
    let html = "";
    const stack = [];            // [{indent, tag}]
    for (const line of lines) {
      const m = line.match(RE_LIST);
      if (!m) {                  // continuation of the previous item
        html += " " + inline(line.trim());
        continue;
      }
      const indent = m[1].replace(/\t/g, "    ").length;
      const tag = /\d/.test(m[2]) ? "ol" : "ul";
      while (stack.length && indent < stack[stack.length - 1].indent) {
        html += "</li></" + stack.pop().tag + ">";
      }
      if (!stack.length || indent > stack[stack.length - 1].indent) {
        stack.push({ indent, tag });
        html += "<" + tag + "><li>";
      } else {
        html += "</li><li>";
      }
      html += inline(m[3]);
    }
    while (stack.length) html += "</li></" + stack.pop().tag + ">";
    return html;
  }

  function markdown(source) {
    const lines = String(source ?? "").replace(/\r\n?/g, "\n").split("\n");
    const out = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];

      if (/^\s*```/.test(line)) {                                   // fenced code
        const lang = line.replace(/^\s*```/, "").trim();
        const body = [];
        i++;
        while (i < lines.length && !/^\s*```/.test(lines[i])) body.push(lines[i++]);
        i++;
        if (lang === "followups") continue;   // the follow-up questions become buttons, not text
        out.push('<pre class="code"' + (lang ? ' data-lang="' + esc(lang) + '"' : "") +
          "><code>" + esc(body.join("\n")) + "</code></pre>");
        continue;
      }
      if (!line.trim()) { i++; continue; }

      const h = line.match(/^(#{1,6})\s+(.*?)\s*#*$/);               // heading
      if (h) {
        const level = Math.min(h[1].length + 1, 6);     // "#" becomes h2: h1 is the page
        out.push("<h" + level + ">" + inline(h[2]) + "</h" + level + ">");
        i++;
        continue;
      }
      if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(line)) {           // rule
        out.push("<hr>");
        i++;
        continue;
      }
      if (line.includes("|") && i + 1 < lines.length && RE_TABLE_RULE.test(lines[i + 1])) {
        const head = splitRow(line);
        const align = splitRow(lines[i + 1]).map((c) =>
          c.endsWith(":") ? (c.startsWith(":") ? "center" : "right") : "");
        i += 2;
        const rows = [];
        while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
          rows.push(splitRow(lines[i++]));
        }
        const cell = (tag, c, k) => "<" + tag + (align[k] ? ' style="text-align:' +
          align[k] + '"' : "") + ">" + inline(c ?? "") + "</" + tag + ">";
        out.push('<div class="table-wrap"><table><thead><tr>' +
          head.map((c, k) => cell("th", c, k)).join("") + "</tr></thead><tbody>" +
          rows.map((r) => "<tr>" + head.map((_, k) => cell("td", r[k], k)).join("") +
            "</tr>").join("") + "</tbody></table></div>");
        continue;
      }
      if (/^\s*>/.test(line)) {                                     // quote
        const body = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) {
          body.push(lines[i++].replace(/^\s*>\s?/, ""));
        }
        out.push("<blockquote>" + markdown(body.join("\n")) + "</blockquote>");
        continue;
      }
      if (RE_LIST.test(line)) {                                     // list
        const body = [];
        while (i < lines.length && lines[i].trim() &&
               (RE_LIST.test(lines[i]) || /^\s{2,}\S/.test(lines[i]))) {
          body.push(lines[i++]);
        }
        out.push(list(body));
        continue;
      }
      const para = [];                                              // paragraph
      while (i < lines.length && lines[i].trim() && !/^\s*```/.test(lines[i]) &&
             !/^#{1,6}\s/.test(lines[i]) && !RE_LIST.test(lines[i]) &&
             !/^\s*>/.test(lines[i]) &&
             !(lines[i].includes("|") && i + 1 < lines.length &&
               RE_TABLE_RULE.test(lines[i + 1]))) {
        para.push(lines[i++]);
      }
      out.push("<p>" + inline(para.join("\n")).replace(/\n/g, "<br>") + "</p>");
    }
    return out.join("\n");
  }

  // --------------------------------------------------------------------------- cards
  const api = {
    artifactUrl: (file) => file,     // replaced by the page
    downloadUrl: (file) => file,     // returns null where downloads are not possible
    openTab: null,                   // (tab, dataset) => void on the live page; null in the report
    ask: null,                       // (text) => void: send a question to the agent; null in the report
    palette: "single",               // "single": one hue per chart. "varied": a hue per category.
  };
  // The eight categorical hues, in the fixed order that keeps neighbours apart for
  // colour-blind readers. Defined as --series-N in styles.css; the same hexes are used
  // for the PNG charts in app/analytics/plotting.py.
  const series = (i) => "var(--series-" + ((i % 8) + 1) + ")";
  const seriesColor = (i) => (api.palette === "varied" ? series(i) : series(0));

  function details(summary, body, cls = "", open = false) {
    return el("details", { class: cls, open }, el("summary", {}, summary), body);
  }

  function chart(card) {
    const src = api.artifactUrl(card.file);
    const link = api.downloadUrl(card.file);
    return el("figure", { class: "card chart" },
      el("img", { src, alt: card.title || "Chart", loading: "lazy",
                  onclick: () => src && !src.startsWith("data:") && window.open(src, "_blank") }),
      el("figcaption", {}, card.title || "",
        link ? el("a", { href: link, download: card.file, class: "quiet" }, "Download") : null));
  }

  function table(card) {
    const head = el("tr", {},
      card.index ? el("th", {}, "") : null,
      card.columns.map((c) => el("th", { title: c }, c)));
    const body = card.rows.map((row, r) => el("tr", {},
      card.index ? el("th", { class: "row-head" }, String(card.index[r] ?? "")) : null,
      row.map((v) => el("td", { class: typeof v === "number" ? "n" : "" },
        v === null || v === undefined ? el("span", { class: "null" }, "empty") : num(v, 6)))));
    const foot = card.truncated
      ? el("div", { class: "table-foot" },
          "Showing " + card.rows.length.toLocaleString() + " of " +
          card.total_rows.toLocaleString() + " rows" +
          (card.total_columns > card.columns.length
            ? " and " + card.columns.length + " of " + card.total_columns + " columns" : "") + ".")
      : null;
    return el("div", { class: "card" },
      card.title ? el("div", { class: "card-title" }, card.title) : null,
      el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, head),
        el("tbody", {}, body))), foot);
  }

  const LEVEL_LABEL = { high: "Serious", medium: "Check", info: "Note" };

  function warnings(items) {
    if (!items || !items.length) return null;
    return el("ul", { class: "warnings" }, items.map((w) => el("li", { class: "w-" + w.level },
      el("span", { class: "tag" }, LEVEL_LABEL[w.level] || w.level),
      el("span", {}, w.column ? el("code", {}, w.column) : null, w.column ? " " : "", w.message))));
  }

  function columnSummary(c) {
    if (c.kind === "numeric") {
      return "median " + num(c.median) + ", range " + num(c.min) + " to " + num(c.max);
    }
    if (c.kind === "datetime") {
      return String(c.min || "").slice(0, 10) + " to " + String(c.max || "").slice(0, 10);
    }
    if (c.top) return c.top.slice(0, 3).map((t) => t.value + " (" + pct(t.share, 0) + ")").join(", ");
    if (c.examples) return "e.g. " + c.examples.slice(0, 2).join(", ");
    return "";
  }

  function issueCounts(items) {
    const n = { high: 0, medium: 0, info: 0 };
    for (const w of items || []) n[w.level] = (n[w.level] || 0) + 1;
    return n;
  }

  /* One line that says how clean the data is, with a button to the full list. */
  function issueLine(p) {
    const n = issueCounts(p.warnings);
    const parts = [];
    if (n.high) parts.push(el("span", { class: "pill bad" }, n.high + " serious"));
    if (n.medium) parts.push(el("span", { class: "pill warn" }, n.medium + " to check"));
    if (n.info) parts.push(el("span", { class: "pill" }, n.info + (n.info === 1 ? " note" : " notes")));
    if (!parts.length) return el("div", { class: "ok-line" }, "No data-quality problems were detected.");
    return el("div", { class: "issue-line" }, parts,
      api.openTab ? el("button", { type: "button", class: "link-btn",
        onclick: () => api.openTab("quality", p.name) }, "See the data-quality report") : null);
  }

  function profile(card) {
    const p = card.profile;
    const kinds = Object.entries(p.kinds).map(([k, n]) => el("span", { class: "chip" }, n + " " + k));
    const columns = el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ["Column", "Type", "Missing", "Distinct", "Summary"]
        .map((h) => el("th", {}, h)))),
      el("tbody", {}, p.columns.map((c) => el("tr", {},
        el("td", {}, el("code", {}, c.name)),
        el("td", {}, el("span", { class: "kind k-" + c.kind }, c.kind)),
        el("td", { class: "n" + (c.missing_share >= 0.05 ? " warn" : "") }, pct(c.missing_share, 0)),
        el("td", { class: "n" }, num(c.distinct)),
        el("td", { class: "muted" }, columnSummary(c)))))));
    // The full warning list lives in the data-quality tab; the chat card only counts them,
    // so a messy file does not open with a wall of text. Without tabs (the report), the
    // list is shown here, collapsed.
    const quality = api.openTab
      ? issueLine(p)
      : (p.warnings.length
          ? el("div", {}, issueLine(p),
              details("Data quality (" + p.warnings.length + ")", warnings(p.warnings)))
          : issueLine(p));
    return el("div", { class: "card profile" },
      el("div", { class: "card-title" }, "Profile of ", el("code", {}, p.name),
        api.openTab ? el("button", { type: "button", class: "link-btn",
          onclick: () => api.openTab("dashboard", p.name) }, "Open the dashboard") : null),
      el("div", { class: "stats" },
        stat("Rows", num(p.rows)), stat("Columns", num(p.columns_count)),
        stat("Missing cells", pct(p.missing_cells_share)),
        stat("Duplicate rows", num(p.duplicate_rows))),
      el("div", { class: "chips" }, kinds),
      quality,
      details("Columns (" + p.columns.length + ")", columns),
      p.load_notes && p.load_notes.length
        ? details("Changes made while loading (" + p.load_notes.length + ")",
            el("ul", { class: "plain" }, p.load_notes.map((n) => el("li", {}, n))))
        : null,
      p.preview ? details("First rows", table(p.preview).querySelector(".table-wrap")) : null);
  }

  // ------------------------------------------------------------------ data quality
  const LEVEL_HEAD = {
    high: ["Serious", "Fix or set aside before trusting a result that uses the column."],
    medium: ["Worth checking", "Usually a cleaning step; the agent can do it in Python."],
    info: ["Notes", "Nothing to fix. Good to know when reading a result."],
  };

  /* The data-quality report for one dataset: the warnings grouped by how serious they
     are, one card each, with the column and the missing-value picture. */
  function quality(p) {
    const n = issueCounts(p.warnings);
    const groups = ["high", "medium", "info"].filter((l) => n[l]);
    const sections = groups.map((level) => {
      const items = p.warnings.filter((w) => w.level === level);
      return el("section", { class: "q-group q-" + level },
        el("h3", {}, el("span", { class: "tag" }, LEVEL_HEAD[level][0]), " ",
          el("span", { class: "count" }, items.length)),
        el("p", { class: "muted small" }, LEVEL_HEAD[level][1]),
        el("div", { class: "q-cards" }, items.map((w) => el("div", { class: "q-card" },
          w.column ? el("code", { class: "q-col" }, w.column) : el("span", { class: "q-col muted" }, "whole table"),
          el("div", { class: "q-msg" }, w.message)))));
    });
    const gaps = p.columns.filter((c) => c.missing_share > 0)
      .sort((a, b) => b.missing_share - a.missing_share).slice(0, 20);
    const notes = (p.load_notes || []);
    return el("div", { class: "quality" },
      el("div", { class: "stats" },
        stat("Serious", n.high), stat("To check", n.medium), stat("Notes", n.info),
        stat("Missing cells", pct(p.missing_cells_share)),
        stat("Duplicate rows", num(p.duplicate_rows))),
      groups.length ? sections : el("div", { class: "ok-line" }, "No data-quality problems were detected."),
      gaps.length ? el("section", { class: "q-group" },
        el("h3", {}, "Missing values by column"),
        svgBars(gaps.map((c) => ({ label: c.name, value: c.missing_share, text: pct(c.missing_share),
          say: c.name + " is missing in " + pct(c.missing_share) + " of rows." })),
          { max: 1, color: "var(--bad)", format: (v) => pct(v) })) : null,
      notes.length ? el("section", { class: "q-group" },
        el("h3", {}, "Changes made while loading"),
        el("ul", { class: "plain" }, notes.map((t) => el("li", {}, t)))) : null);
  }

  // --------------------------------------------------------------- small SVG charts
  // Enough charting for the dashboard, with no library: bars, a histogram, a line, a
  // heatmap and a scatter. Every mark has a hover tooltip. Sizes are a viewBox, so the
  // charts scale with the page and print cleanly.
  const NS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs = {}, ...children) {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    }
    for (const c of children.flat(Infinity)) {
      if (c === null || c === undefined || c === false) continue;
      node.append(c.nodeType ? c : document.createTextNode(String(c)));
    }
    return node;
  }
  let tipNode = null;
  function tip(show, text, e) {
    if (!tipNode) {
      tipNode = el("div", { class: "tip", hidden: true });
      document.body.append(tipNode);
    }
    if (!show) { tipNode.hidden = true; tipAt = null; return; }
    // Placed once, where the pointer entered the mark, and left alone until the pointer
    // has moved well away: a tooltip that chases the pointer is impossible to read.
    const same = tipNode.textContent === text && !tipNode.hidden && tipAt &&
      Math.abs(e.clientX - tipAt[0]) < 48 && Math.abs(e.clientY - tipAt[1]) < 48;
    if (same) return;
    tipNode.textContent = text;
    tipNode.hidden = false;
    tipAt = [e.clientX, e.clientY];
    const x = Math.min(e.clientX + 16, window.innerWidth - tipNode.offsetWidth - 8);
    const below = e.clientY + 18 + tipNode.offsetHeight < window.innerHeight;
    tipNode.style.left = x + "px";
    tipNode.style.top = (below ? e.clientY + 18 : e.clientY - tipNode.offsetHeight - 10) + "px";
  }
  let tipAt = null;
  /* Tooltip on every mark, and a sentence for the chart's narration line when the
     chart has one: `say` gets the sentence while the mark is hovered, null after.
     A click pins the sentence so it can be read with the pointer anywhere. */
  const hover = (text, say, sentence) => ({
    onmouseenter: (e) => { tip(true, text, e); if (say) say(sentence || text); },
    onmousemove: (e) => { tip(true, text, e); if (say) say(sentence || text); },
    onmouseleave: () => { tip(false); if (say) say(null); },
    onclick: say ? (e) => { e.stopPropagation(); say.pin(sentence || text); } : null,
  });

  /* The line under a chart that says what it shows, in words. It starts with a sentence
     about the whole chart and changes to describe whatever the user is pointing at. The
     sentence stays a few seconds after the pointer leaves, so there is time to read it,
     and a click on a mark pins it until the next click. */
  const HOLD_MS = 4000;
  function narrator(base, topic) {
    const text = el("span", {}, base);
    const pinNote = el("span", { class: "explain-pin", hidden: true }, "pinned");
    const ask = api.ask
      ? el("button", { type: "button", class: "link-btn", onclick: () =>
          api.ask((topic ? "About " + topic + ": " : "") + text.textContent + " What does this mean, and should I act on it?") },
          "Ask the agent")
      : null;
    const node = el("p", { class: "explain", "aria-live": "polite" },
      el("span", { class: "explain-ic", "aria-hidden": "true" }, "i"), text, pinNote, ask);
    let timer = 0, pinned = null;
    const show = (t) => { text.textContent = t || base; };
    const say = (t) => {
      clearTimeout(timer);
      if (pinned) return;                       // a pinned sentence stays put
      if (t) { show(t); return; }
      timer = setTimeout(() => show(null), HOLD_MS);
    };
    say.pin = (t) => {
      clearTimeout(timer);
      pinned = pinned === t ? null : t;         // click the same mark again to unpin
      pinNote.hidden = !pinned;
      node.classList.toggle("pinned", Boolean(pinned));
      show(pinned || t);
      if (!pinned) timer = setTimeout(() => show(null), HOLD_MS);
    };
    node.addEventListener("click", (e) => {      // click the line itself to unpin
      if (pinned && !e.target.closest("button")) say.pin(pinned);
    });
    return { node, say, base: (b) => { base = b; if (!pinned) show(b); } };
  }
  const fmtPct = (v) => (v * 100).toFixed(v * 100 < 10 ? 1 : 0) + "%";
  const times = (a, b) => (b ? (a / b).toFixed(a / b < 10 ? 1 : 0) : "many");
  const short = (s, n = 18) => (String(s).length > n ? String(s).slice(0, n - 1) + "…" : String(s));
  const fmtAxis = (v) => (Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(1) + "M"
    : Math.abs(v) >= 1e4 ? (v / 1e3).toFixed(0) + "k" : num(v, 3));

  /* Horizontal bars. items: [{label, value, text}]. */
  function svgBars(items, opts = {}) {
    // compact: a narrow viewBox, so the labels stay readable inside a small card
    const W = opts.compact ? 320 : 600, rowH = opts.compact ? 18 : 22;
    const left = opts.compact ? 92 : 150, right = opts.right || (opts.compact ? 64 : 70), top = 6;
    const H = top + rowH * items.length + 6;
    const max = opts.max || Math.max(...items.map((i) => i.value), 1e-9);
    const fmt = opts.format || ((v) => num(v, 4));
    const bars = items.map((it, i) => {
      const y = top + i * rowH, w = Math.max(0, (W - left - right) * it.value / max);
      return svg("g", hover(it.label + ": " + (it.text || fmt(it.value)), opts.say, it.say),
        svg("text", { x: left - 8, y: y + 15, "text-anchor": "end", class: "lbl" }, short(it.label, opts.compact ? 14 : 22)),
        svg("rect", { x: left, y: y + 4, width: w, height: rowH - 8, rx: 3,
          fill: it.color || opts.color || seriesColor(0), class: it.active ? "active" : "" }),
        svg("text", { x: left + w + 6, y: y + 15, class: "val" }, it.text || fmt(it.value)));
    });
    return svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart-svg", role: "img" }, bars);
  }

  /* A histogram from bins [{x0, x1, n}]. */
  function svgHist(bins, opts = {}) {
    const W = 600, H = 200, left = 46, right = 10, top = 10, bottom = 28;
    const max = Math.max(...bins.map((b) => b.n), 1);
    const x0 = bins[0].x0, x1 = bins[bins.length - 1].x1;
    const span = x1 - x0 || 1;
    const px = (v) => left + (W - left - right) * (v - x0) / span;
    const single = bins.every((b) => b.x0 === b.x1);
    const bw = single ? Math.max(4, (W - left - right) / bins.length - 2) : null;
    const rects = bins.map((b, i) => {
      const h = (H - top - bottom) * b.n / max;
      const x = single ? left + (W - left - right) * (i + 0.5) / bins.length - bw / 2 : px(b.x0);
      const w = single ? bw : Math.max(1, px(b.x1) - px(b.x0) - 1);
      const label = single ? num(b.x0) : num(b.x0, 4) + " to " + num(b.x1, 4);
      return svg("rect", { x, y: H - bottom - h, width: w, height: h, fill: opts.color || seriesColor(0),
        ...hover(label + ": " + num(b.n) + " rows", opts.say, opts.explain && opts.explain(b, i, label)) });
    });
    const ticks = single ? [] : [0, 0.25, 0.5, 0.75, 1].map((f) => svg("text", {
      x: px(x0 + span * f), y: H - 8, "text-anchor": f === 0 ? "start" : f === 1 ? "end" : "middle",
      class: "lbl" }, fmtAxis(x0 + span * f)));
    const ymax = svg("text", { x: left - 6, y: top + 10, "text-anchor": "end", class: "lbl" }, fmtAxis(max));
    const axis = svg("line", { x1: left, x2: W - right, y1: H - bottom, y2: H - bottom, class: "axis" });
    const marks = [];
    if (opts.median !== undefined && opts.median !== null && !single) {
      marks.push(svg("line", { x1: px(opts.median), x2: px(opts.median), y1: top, y2: H - bottom, class: "ref" }));
      marks.push(svg("text", { x: px(opts.median) + 4, y: top + 10, class: "lbl" }, "median"));
    }
    return svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart-svg", role: "img" }, rects, axis, ticks, ymax, marks);
  }

  /* A line over time. points: [{t, value}]. */
  function svgLine(points, opts = {}) {
    const W = 600, H = 200, left = 52, right = 12, top = 10, bottom = 28;
    const vals = points.map((p) => p.value).filter((v) => v !== null && v !== undefined);
    const min = Math.min(0, ...vals), max = Math.max(...vals, 1e-9);
    const px = (i) => left + (W - left - right) * (points.length > 1 ? i / (points.length - 1) : 0.5);
    const py = (v) => H - bottom - (H - top - bottom) * (v - min) / (max - min || 1);
    let d = "";
    points.forEach((p, i) => { if (p.value !== null) d += (d ? " L" : "M") + px(i).toFixed(1) + " " + py(p.value).toFixed(1); });
    const color = opts.color || seriesColor(0);
    const dots = points.map((p, i) => p.value === null ? null : svg("circle", {
      cx: px(i), cy: py(p.value), r: points.length > 80 ? 2 : 3.5, fill: color,
      ...hover(p.t + ": " + num(p.value, 5) + (opts.unit ? " " + opts.unit : ""), opts.say,
               opts.explain && opts.explain(p, i)) }));
    const grid = [0, 0.5, 1].map((f) => {
      const v = min + (max - min) * f;
      return svg("g", {}, svg("line", { x1: left, x2: W - right, y1: py(v), y2: py(v), class: "grid" }),
        svg("text", { x: left - 6, y: py(v) + 4, "text-anchor": "end", class: "lbl" }, fmtAxis(v)));
    });
    const labels = [0, Math.floor((points.length - 1) / 2), points.length - 1].filter((v, i, a) => a.indexOf(v) === i)
      .map((i) => svg("text", { x: px(i), y: H - 8, class: "lbl",
        "text-anchor": i === 0 ? "start" : i === points.length - 1 ? "end" : "middle" }, points[i].t));
    return svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart-svg", role: "img" }, grid,
      svg("path", { d, fill: "none", stroke: color, "stroke-width": 2 }), dots, labels);
  }

  /* A correlation heatmap. */
  /* How strong a correlation is, in words. */
  function corrWords(a, b, r) {
    if (r === null || r === undefined) return a + " and " + b + ": not enough values to compare.";
    const s = Math.abs(r);
    const strength = s >= 0.7 ? "a strong" : s >= 0.4 ? "a moderate" : s >= 0.2 ? "a weak" : "little or no";
    const dir = r > 0 ? "when one is higher, the other tends to be higher too"
                      : "when one is higher, the other tends to be lower";
    return a + " and " + b + ": Spearman " + r.toFixed(2) + ", " + strength + " relationship" +
      (s >= 0.2 ? ": " + dir + "." : ".");
  }

  function svgHeat(cols, matrix, onPick, opts = {}) {
    const n = cols.length, cell = Math.max(22, Math.min(40, 480 / n)), left = 110, top = 6;
    const W = left + cell * n + 10, H = top + cell * n + 90;
    // Diverging: blue for positive, red for negative, fading to the surface at zero.
    const color = (r) => {
      if (r === null) return "var(--panel-2)";
      const a = Math.min(1, Math.abs(r));
      return r > 0 ? `rgba(42, 120, 214, ${0.08 + 0.85 * a})` : `rgba(227, 73, 72, ${0.08 + 0.85 * a})`;
    };
    const cells = [];
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const r = matrix[i][j];
      const sentence = i === j ? cols[i] + " against itself is always 1." : corrWords(cols[i], cols[j], r);
      cells.push(svg("rect", {
        ...hover(cols[i] + " and " + cols[j] + ": " + (r === null ? "n/a" : r.toFixed(2)), opts.say, sentence),
        x: left + j * cell, y: top + i * cell, width: cell - 1, height: cell - 1,
        fill: color(r), class: i !== j && onPick ? "pick" : "",
        // a click shows the pair's points and pins its sentence
        onclick: () => { if (i !== j && onPick) onPick(cols[i], cols[j]); if (opts.say) opts.say.pin(sentence); } }));
      if (cell >= 30 && r !== null && i !== j) {
        cells.push(svg("text", { x: left + j * cell + cell / 2, y: top + i * cell + cell / 2 + 4,
          "text-anchor": "middle", class: "cellv", "pointer-events": "none" }, r.toFixed(2)));
      }
    }
    const rows = cols.map((c, i) => svg("text", { x: left - 6, y: top + i * cell + cell / 2 + 4,
      "text-anchor": "end", class: "lbl" }, short(c, 16)));
    const heads = cols.map((c, j) => svg("text", { x: left + j * cell + cell / 2, y: top + n * cell + 8,
      class: "lbl", transform: `rotate(45 ${left + j * cell + cell / 2} ${top + n * cell + 8})` }, short(c, 16)));
    return svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart-svg heat", role: "img" }, cells, rows, heads);
  }

  /* A scatter of sampled points. */
  const median = (arr) => {
    const v = [...arr].sort((x, y) => x - y);
    return v.length ? (v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2) : 0;
  };

  function svgScatter(points, a, b, opts = {}) {
    const W = 600, H = 220, left = 52, right = 12, top = 10, bottom = 30;
    const xs = points.map((p) => p[0]), ys = points.map((p) => p[1]);
    const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin = Math.min(...ys), ymax = Math.max(...ys);
    const mx = median(xs), my = median(ys);
    const px = (v) => left + (W - left - right) * (v - xmin) / (xmax - xmin || 1);
    const py = (v) => H - bottom - (H - top - bottom) * (v - ymin) / (ymax - ymin || 1);
    const side = (v, m) => (v > m ? "above" : v < m ? "below" : "at");
    const dots = points.map((p) => svg("circle", { cx: px(p[0]), cy: py(p[1]), r: 3, class: "pt",
      style: "fill:" + (opts.color || seriesColor(0)),
      ...hover(a + " " + num(p[0], 4) + ", " + b + " " + num(p[1], 4), opts.say,
        "One row: " + a + " " + num(p[0], 4) + " (" + side(p[0], mx) + " the median " + num(mx, 4) + "), " +
        b + " " + num(p[1], 4) + " (" + side(p[1], my) + " the median " + num(my, 4) + ").") }));
    return svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart-svg", role: "img" }, dots,
      svg("text", { x: W / 2, y: H - 6, "text-anchor": "middle", class: "lbl" }, a),
      svg("text", { x: 12, y: H / 2, class: "lbl", transform: `rotate(-90 12 ${H / 2})`, "text-anchor": "middle" }, b),
      svg("text", { x: left - 6, y: py(ymax) + 4, "text-anchor": "end", class: "lbl" }, fmtAxis(ymax)),
      svg("text", { x: left - 6, y: py(ymin) + 4, "text-anchor": "end", class: "lbl" }, fmtAxis(ymin)),
      svg("text", { x: px(xmin), y: H - bottom + 14, class: "lbl" }, fmtAxis(xmin)),
      svg("text", { x: px(xmax), y: H - bottom + 14, "text-anchor": "end", class: "lbl" }, fmtAxis(xmax)));
  }

  // ---------------------------------------------------------------------- dashboard
  const HL_ICON = { target: "◎", quality: "!", leak: "⚠", correlation: "↗", group: "≠", time: "↝", missing: "◌" };

  /* A row of chips the user can click to change what a panel shows. */
  function picker(options, current, onPick) {
    return el("div", { class: "picks" }, options.map((o) => el("button", {
      type: "button", class: "pick" + (o === current ? " on" : ""), onclick: () => onPick(o) }, o)));
  }

  /* The first-look dashboard for one dataset. Interactive: pick a column, a metric, a
     pair; hover any mark. Under every chart a line says what it shows, and changes to
     describe the mark under the pointer. */
  function dashboard(d) {
    const root = el("div", { class: "dash" });
    const n = d.quality || {};
    const rows = d.sampled_rows || d.rows;
    root.append(el("div", { class: "stats" },
      stat("Rows", num(d.rows), d.sampled_rows ? "charts use " + num(d.sampled_rows) : null),
      stat("Columns", num(d.columns_count)),
      stat("Missing cells", pct(d.missing_cells_share)),
      stat("Duplicate rows", num(d.duplicate_rows)),
      stat("Issues", (n.high || 0) + (n.medium || 0), n.high ? n.high + " serious" : null)));

    // Highlights
    if (d.highlights && d.highlights.length) {
      root.append(el("section", { class: "dash-sec" },
        el("h3", {}, "What stands out"),
        el("div", { class: "hl-grid" }, d.highlights.map((h) => el("div", { class: "hl hl-" + h.kind },
          el("span", { class: "hl-ic" }, HL_ICON[h.kind] || "•"),
          el("div", {}, el("div", { class: "hl-t", html: inline(h.title) }),
            el("div", { class: "hl-d", html: inline(h.detail) })))))));
    } else {
      root.append(el("p", { class: "muted" }, "Nothing stood out on its own. Ask a question."));
    }

    // Numeric columns: one histogram, a picker to change the column
    if (d.numeric && d.numeric.length) {
      const sec = el("section", { class: "dash-sec" }, el("h3", {}, "Distributions"));
      const body = el("div", {});
      const draw = (c) => {
        const total = c.bins.reduce((a, b) => a + b.n, 0) || 1;
        const tallest = c.bins.reduce((best, b) => (b.n > best.n ? b : best), { n: -1 });
        const single = c.bins.every((b) => b.x0 === b.x1);
        const shape = c.mean === null || c.median === null ? ""
          : c.mean > c.median * 1.1 ? " The mean (" + num(c.mean) + ") is above the median, so a few large values pull it up: a long right tail."
          : c.mean < c.median * 0.9 ? " The mean (" + num(c.mean) + ") is below the median, so a few small values pull it down."
          : " The mean (" + num(c.mean) + ") is close to the median, so the values are fairly symmetric.";
        const common = tallest.n > 0 ? " The most common " + (single ? "value is " + num(tallest.x0)
          : "range is " + num(tallest.x0, 4) + " to " + num(tallest.x1, 4)) + " (" + fmtPct(tallest.n / total) + " of rows)." : "";
        const nar = narrator(c.name + " runs from " + num(c.min) + " to " + num(c.max) + ". Half of the rows are below the median, " +
          num(c.median) + "." + shape + common + (c.missing_share ? " " + pct(c.missing_share, 0) + " of rows have no value." : ""),
          "the distribution of " + c.name + " in " + d.name);
        body.replaceChildren(
          picker(d.numeric.map((x) => x.name), c.name, (name) => draw(d.numeric.find((x) => x.name === name))),
          el("div", { class: "stats small" }, stat("Min", num(c.min)), stat("Median", num(c.median)),
            stat("Mean", num(c.mean)), stat("Max", num(c.max)),
            c.missing_share ? stat("Missing", pct(c.missing_share)) : null),
          c.bins.length ? svgHist(c.bins, { median: c.median, say: nar.say, explain: (b, i, label) =>
            num(b.n) + " rows (" + fmtPct(b.n / total) + ") have " + c.name + (single ? " equal to " : " between ") + label +
            (c.median === null ? "." : b.x1 < c.median ? ", below the median." : b.x0 > c.median ? ", above the median." : ", around the median.") })
            : el("p", { class: "muted" }, "No values."),
          c.bins.length ? nar.node : null);
      };
      draw(d.numeric[0]);
      sec.append(body);
      root.append(sec);
    }

    // Categories: one card per column, its own hue when the palette is varied
    if (d.categorical && d.categorical.length) {
      root.append(el("section", { class: "dash-sec" }, el("h3", {}, "Categories"),
        el("div", { class: "cat-grid" }, d.categorical.map((c, k) => {
          const top = c.top[0], second = c.top[1];
          const nar = narrator(top ? top.value + " is the most common " + c.name + " (" + fmtPct(top.share) + " of rows)" +
            (second ? ", then " + second.value + " (" + fmtPct(second.share) + ")" : "") + ". " + num(c.distinct) +
            (c.distinct === 1 ? " distinct value." : " distinct values.") : "No values.", c.name + " in " + d.name);
          return el("div", { class: "cat" },
            el("div", { class: "cat-h" }, el("code", {}, c.name),
              el("span", { class: "muted small" }, num(c.distinct) + " values")),
            svgBars(c.top.map((t) => ({ label: t.value, value: t.share, text: pct(t.share, 0) + " (" + num(t.count) + ")",
              say: t.value + ": " + num(t.count) + " rows, " + fmtPct(t.share) + " of the rows" +
                (top && t !== top && t.share > 0 ? ", " + times(top.share, t.share) + " times less common than " + top.value + "." : ".") })),
              { max: 1, compact: true, color: seriesColor(k), say: nar.say }),
            nar.node);
        }))));
    }

    // Time
    if (d.time) {
      const sec = el("section", { class: "dash-sec" }, el("h3", {}, "Over time"));
      const body = el("div", {});
      const metrics = ["rows", ...d.time.metrics];
      const unit = { D: "day", W: "week", MS: "month", QS: "quarter", YS: "year" }[d.time.freq] || "period";
      const draw = (m) => {
        const label = m === "rows" ? "Rows" : "Average " + m;
        const pts = d.time.points.map((p) => ({ t: p.t, value: p[m] === undefined ? null : p[m] }));
        const vals = pts.filter((p) => p.value !== null);
        const first = vals[0], last = vals[vals.length - 1];
        const avg = vals.reduce((a, p) => a + p.value, 0) / (vals.length || 1);
        const hi = vals.reduce((b, p) => (p.value > b.value ? p : b), vals[0] || { value: 0, t: "" });
        const lo = vals.reduce((b, p) => (p.value < b.value ? p : b), vals[0] || { value: 0, t: "" });
        const change = first && first.value ? (last.value - first.value) / Math.abs(first.value) : null;
        const nar = narrator(vals.length < 2 ? "Not enough periods to describe." :
          label + " per " + unit + " went from " + num(first.value, 4) + " (" + first.t + ") to " + num(last.value, 4) + " (" + last.t + ")" +
          (change === null ? "." : change > 0.02 ? ", up " + fmtPct(change) + "." : change < -0.02 ? ", down " + fmtPct(-change) + "." : ", about the same.") +
          " Highest in " + hi.t + " (" + num(hi.value, 4) + "), lowest in " + lo.t + " (" + num(lo.value, 4) + ").",
          label.toLowerCase() + " over " + d.time.column + " in " + d.name);
        body.replaceChildren(
          picker(metrics, m, draw),
          el("p", { class: "muted small" }, label + " per " + unit + ", by " + d.time.column + ", " + d.time.start + " to " + d.time.end + "."),
          svgLine(pts, { say: nar.say, explain: (p) => {
            const diff = avg ? (p.value - avg) / Math.abs(avg) : 0;
            return p.t + ": " + num(p.value, 4) + ", " + (Math.abs(diff) < 0.02 ? "about the period average" :
              fmtPct(Math.abs(diff)) + (diff > 0 ? " above" : " below") + " the period average") + " of " + num(avg, 4) + ".";
          } }),
          nar.node);
      };
      draw("rows");
      sec.append(body);
      root.append(sec);
    }

    // Correlations: the heatmap, and a scatter for the picked pair
    if (d.correlations) {
      const c = d.correlations;
      const sec = el("section", { class: "dash-sec" }, el("h3", {}, "How the numbers move together"));
      const scatterBox = el("div", { class: "scatter-box" });
      const strongest = c.pairs[0];
      const nar = narrator(strongest ? "The strongest relationship is " + corrWords(strongest.a, strongest.b, strongest.r) +
        " Association, not cause." : "No pair of numeric columns moves together.", "the correlations in " + d.name);
      const showPair = (a, b) => {
        const pair = c.pairs.find((p) => (p.a === a && p.b === b) || (p.a === b && p.b === a));
        if (!pair) {
          const i = c.columns.indexOf(a), j = c.columns.indexOf(b);
          const r = i >= 0 && j >= 0 ? c.matrix[i][j] : null;
          scatterBox.replaceChildren(el("p", { class: "muted small" },
            a + " and " + b + ": correlation " + (r === null ? "n/a" : r.toFixed(2)) +
            ". Ask for a scatter of these two to see the points."));
          return;
        }
        const pnar = narrator("Each point is one row (" + pair.points.length + " sampled). " + corrWords(pair.a, pair.b, pair.r),
          pair.a + " against " + pair.b + " in " + d.name);
        scatterBox.replaceChildren(
          el("p", { class: "small" }, el("code", {}, pair.a), " against ", el("code", {}, pair.b),
            ": Spearman " + pair.r.toFixed(2) + (pair.points.length ? ", " + pair.points.length + " sampled rows" : "")),
          pair.points.length ? svgScatter(pair.points, pair.a, pair.b, { say: pnar.say, color: seriesColor(1) }) : null,
          pair.points.length ? pnar.node : null);
      };
      sec.append(el("p", { class: "muted small" }, "Spearman correlation. Blue rises together, red moves opposite. Click a cell to see the points."),
        el("div", { class: "heat-row" }, el("div", { class: "heat-wrap" }, svgHeat(c.columns, c.matrix, showPair, { say: nar.say }), nar.node), scatterBox));
      if (c.pairs.length) showPair(c.pairs[0].a, c.pairs[0].b);
      root.append(sec);
    }

    // Group differences
    if (d.groups && d.groups.length) {
      const sec = el("section", { class: "dash-sec" }, el("h3", {}, "Biggest differences between groups"));
      const body = el("div", {});
      const draw = (g) => {
        const hi = g.groups[0], lo = g.groups[g.groups.length - 1];
        const total = g.groups.reduce((a, x) => a + x.n, 0) || 1;
        const grand = g.groups.reduce((a, x) => a + x.mean * x.n, 0) / total;
        const nar = narrator("Average " + g.metric + " is highest for " + hi.value + " (" + num(hi.mean, 4) + ") and lowest for " +
          lo.value + " (" + num(lo.mean, 4) + ")" + (lo.mean > 0 ? ", " + times(hi.mean, lo.mean) + " times as high." : ".") +
          " " + pct(g.eta_squared, 0) + " of the variation in " + g.metric + " is between these groups; the rest is within them. Association, not cause.",
          g.metric + " by " + g.category + " in " + d.name);
        body.replaceChildren(
          d.groups.length > 1 ? picker(d.groups.map((x) => x.category + " → " + x.metric), g.category + " → " + g.metric,
            (label) => draw(d.groups.find((x) => x.category + " → " + x.metric === label))) : null,
          el("p", { class: "muted small" }, "Average " + g.metric + " by " + g.category + "."),
          svgBars(g.groups.map((x, k) => {
            const diff = grand ? (x.mean - grand) / Math.abs(grand) : 0;
            return { label: x.value, value: Math.max(0, x.mean), text: num(x.mean, 4) + " (n " + num(x.n) + ")",
              color: seriesColor(k),
              say: x.value + ": average " + g.metric + " " + num(x.mean, 4) + " from " + num(x.n) + " rows, " +
                (Math.abs(diff) < 0.02 ? "about the overall average" : fmtPct(Math.abs(diff)) + (diff > 0 ? " above" : " below") + " the overall average") +
                " of " + num(grand, 4) + "." };
          }), { say: nar.say }),
          nar.node);
      };
      draw(d.groups[0]);
      sec.append(body);
      root.append(sec);
    }
    return root;
  }

  // -------------------------------------------------------------- relationships
  const STRENGTH = { strong: ["Strong link", "var(--series-1)"], partial: ["Partial link", "var(--series-4)"],
                     weak: ["Weak link", "var(--muted)"], none: ["Same name, no shared values", "var(--muted)"] };
  const AI_COLOR = "var(--series-7)";
  const CARD_LABEL = { "one-to-one": "one to one", "one-to-many": "one to many", "many-to-one": "many to one",
                       "many-to-many": "shared dimension" };
  const AI_KIND = { join: "join key", dimension: "shared dimension", time: "time alignment", derived: "derived column" };
  const pairKey = (a, b) => [a, b].sort().join("\u0000");
  const sameCols = (x, a, ca, b, cb) =>
    (x.a === a && x.a_column === ca && x.b === b && x.b_column === cb) ||
    (x.a === b && x.a_column === cb && x.b === a && x.b_column === ca);

  /* One link between two columns: what it is, how well it matches, how to join. */
  function linkCard(link, open, verdict) {
    const a = link.a, b = link.b;
    const matched = svgBars([
      { label: a.dataset, value: a.rows_matched, text: fmtPct(a.rows_matched) + " of " + num(a.rows) + " rows",
        say: fmtPct(a.rows_matched) + " of " + a.dataset + " rows have a matching value in " + b.dataset + "." },
      { label: b.dataset, value: b.rows_matched, text: fmtPct(b.rows_matched) + " of " + num(b.rows) + " rows",
        say: fmtPct(b.rows_matched) + " of " + b.dataset + " rows have a matching value in " + a.dataset + "." },
    ], { max: 1, compact: true, right: 118, color: STRENGTH[link.strength][1] });
    const merge = link.merge ? el("div", {},
      el("pre", { class: "code small-code" }, el("code", {}, link.merge)),
      api.ask ? el("button", { type: "button", class: "btn", onclick: () => api.ask(
        "Merge " + a.dataset + " and " + b.dataset + " on " + (link.same_name ? a.column : a.column + " = " + b.column) +
        ", keep every row of " + a.dataset + ", save the result as a dataset, and tell me how many rows matched.") },
        "Ask the agent to merge them") : null) : null;
    const said = verdict ? el("p", { class: "small ai-verdict" },
      el("span", { class: "pill " + (verdict.verdict === "agree" ? "good" : "warn") },
        verdict.verdict === "agree" ? "AI agrees" : "AI doubts this"),
      verdict.reason ? " " + verdict.reason : "") : null;
    return details(
      el("span", {}, el("code", {}, a.column), link.same_name ? "" : [" = ", el("code", {}, b.column)], " ",
        el("span", { class: "pill " + (link.strength === "strong" ? "good" : link.strength === "partial" ? "warn" : "") }, STRENGTH[link.strength][0]),
        " ", el("span", { class: "chip" }, CARD_LABEL[link.cardinality] || link.cardinality)),
      el("div", { class: "link-body" },
        el("p", { class: "small" }, link.explanation),
        said,
        el("div", { class: "muted tiny" }, "Rows with a match on the other side"),
        matched, merge),
      "link-card", open);
  }

  /* One relationship the model proposed: unverified, so the card says why and offers to
     have the agent check it on the data. */
  function aiCard(s, open) {
    const ask = api.ask ? el("button", { type: "button", class: "btn", onclick: () => api.ask(
      "The relationship map suggests that " + s.a + "." + s.a_column + " and " + s.b + "." + s.b_column +
      " may be the same " + (s.kind === "join" ? "key" : "thing") + (s.transform ? " once this is applied: " + s.transform : "") +
      ". Check on the data whether they match" + (s.kind === "join"
        ? ", and if they do, merge " + s.a + " and " + s.b + " on it, keep every row of " + s.a + ", save the result as a dataset, and tell me how many rows matched."
        : ", and tell me how well they line up.")) },
      s.kind === "join" ? "Ask the agent to check and merge" : "Ask the agent to check") : null;
    return details(
      el("span", {}, el("code", {}, s.a_column), " = ", el("code", {}, s.b_column), " ",
        el("span", { class: "pill ai" }, "AI idea"), " ",
        el("span", { class: "chip" }, AI_KIND[s.kind] || s.kind), " ",
        el("span", { class: "pill " + (s.confidence === "high" ? "good" : s.confidence === "medium" ? "warn" : "") }, s.confidence + " confidence")),
      el("div", { class: "link-body" },
        el("p", { class: "small" }, el("code", {}, s.a + "." + s.a_column), " and ", el("code", {}, s.b + "." + s.b_column), ". ", s.reason),
        s.transform ? el("p", { class: "small muted" }, "To make the values match: " + s.transform) : null,
        s.merge ? el("pre", { class: "code small-code" }, el("code", {}, s.merge)) : null,
        ask),
      "link-card ai-card", open);
  }

  /* Places the datasets so that linked ones sit near each other: a few hundred rounds of
     push-apart, pull-together and un-overlap, from the same start every time, so the same
     data always gives the same picture. Boxes are wide, so overlap is checked on the
     boxes, not on points. */
  const BOX_H = 46;
  const boxWidth = (name) => Math.max(130, Math.min(220, 16 + 8 * name.length));
  function forceLayout(names, links, W, H) {
    const n = names.length, pos = {}, cx = W / 2, cy = H / 2;
    const padX = 120, padY = 42;
    if (n === 2) {
      pos[names[0]] = { x: cx - W * 0.27, y: cy };
      pos[names[1]] = { x: cx + W * 0.27, y: cy };
      return pos;
    }
    const R = Math.min(W * 0.4, H * 0.38);
    names.forEach((nm, i) => {
      const t = -Math.PI / 2 + 2 * Math.PI * i / n;
      pos[nm] = { x: cx + R * Math.cos(t), y: cy + R * Math.sin(t) };
    });
    const idx = Object.fromEntries(names.map((nm, i) => [nm, i]));
    const widths = names.map(boxWidth);
    const k = 190, L = 230;                      // repulsion range, preferred link length
    const separate = (rounds) => {
      for (let r = 0; r < rounds; r++) {
        for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
          const a = pos[names[i]], b = pos[names[j]];
          const ox = (widths[i] + widths[j]) / 2 + 28 - Math.abs(a.x - b.x);
          const oy = BOX_H + 22 - Math.abs(a.y - b.y);
          if (ox <= 0 || oy <= 0) continue;
          if (oy < ox) { const s = (a.y < b.y ? -1 : 1) * oy / 2; a.y += s; b.y -= s; }
          else { const s = (a.x < b.x ? -1 : 1) * ox / 2; a.x += s; b.x -= s; }
        }
      }
    };
    let temp = 40;
    for (let it = 0; it < 300; it++) {
      const disp = names.map(() => ({ x: 0, y: 0 }));
      for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
        const a = pos[names[i]], b = pos[names[j]];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d = Math.hypot(dx, dy) || 0.01, f = (k * k) / d;
        disp[i].x += dx / d * f; disp[i].y += dy / d * f;
        disp[j].x -= dx / d * f; disp[j].y -= dy / d * f;
      }
      for (const l of links) {
        const i = idx[l.a], j = idx[l.b];
        if (i === undefined || j === undefined) continue;
        const a = pos[l.a], b = pos[l.b];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d = Math.hypot(dx, dy) || 0.01, f = (d - L) * 0.6 * (l.weight || 1);
        disp[i].x -= dx / d * f; disp[i].y -= dy / d * f;
        disp[j].x += dx / d * f; disp[j].y += dy / d * f;
      }
      names.forEach((nm, i) => {
        const p = pos[nm];
        disp[i].x += (cx - p.x) * 0.02; disp[i].y += (cy - p.y) * 0.02;
        const d = Math.hypot(disp[i].x, disp[i].y) || 0.01, m = Math.min(d, temp);
        p.x += disp[i].x / d * m;
        p.y += disp[i].y / d * m;
      });
      separate(1);
      temp = Math.max(0.5, temp * 0.97);
    }
    // Stretch the result to the drawing area, so a tight cluster and a wide one both
    // use the space, then push apart anything the stretch brought together.
    const xs = names.map((nm) => pos[nm].x), ys = names.map((nm) => pos[nm].y);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    for (const nm of names) {
      const p = pos[nm];
      p.x = x1 - x0 > 1 ? padX + (p.x - x0) / (x1 - x0) * (W - 2 * padX) : cx;
      p.y = y1 - y0 > 1 ? padY + (p.y - y0) / (y1 - y0) * (H - 2 * padY) : cy;
    }
    separate(20);
    for (const nm of names) {
      pos[nm].x = Math.min(W - padX, Math.max(padX, pos[nm].x));
      pos[nm].y = Math.min(H - padY, Math.max(padY, pos[nm].y));
    }
    return pos;
  }

  /* The relationships panel. A map of the datasets that can be zoomed, panned and
     rearranged, a picker for the two datasets to compare, and below it the links between
     the chosen pair: the ones found in the values, and the ones the model suggested.
     opts: selected {a, b} to start on; onSelect(sel) to remember the choice;
     onSuggest() to ask the model, with live false when there is no key. */
  function relations(rel, opts = {}) {
    const root = el("div", { class: "rel" });
    const nodes = rel.datasets || [];
    const edges = rel.edges || [];
    const ai = rel.ai || null;
    if (nodes.length < 2) {
      root.append(el("div", { class: "empty-panel" }, (rel.summary || [])[0] || "Load at least two datasets to see how they relate."));
      return root;
    }
    const names = nodes.map((d) => d.name);
    const byName = Object.fromEntries(nodes.map((d) => [d.name, d]));
    const autoByPair = new Map(edges.map((e) => [pairKey(e.a, e.b), e]));
    const aiByPair = new Map();
    for (const s of (ai && ai.suggestions) || []) {
      const k = pairKey(s.a, s.b);
      if (!aiByPair.has(k)) aiByPair.set(k, []);
      aiByPair.get(k).push(s);
    }
    const verdictFor = (l) => ai ? (ai.found || []).find((f) =>
      sameCols(f, l.a.dataset, l.a.column, l.b.dataset, l.b.column)) : null;
    // What is drawn: a line per pair the values link, and a dashed one per pair only the
    // model proposed.
    const drawn = edges.map((e) => ({ kind: "auto", a: e.a, b: e.b, edge: e, strength: e.strength,
                                      weight: { strong: 1.6, partial: 1.1, weak: 0.7, none: 0.5 }[e.strength] || 1 }));
    for (const [k, list] of aiByPair) {
      if (!autoByPair.has(k)) drawn.push({ kind: "ai", a: list[0].a, b: list[0].b, list, strength: "ai", weight: 0.8 });
    }
    const linkedWith = (name) => drawn.filter((d) => d.a === name || d.b === name)
      .map((d) => (d.a === name ? d.b : d.a));

    // ---- the map
    const W = 1000, H = nodes.length <= 2 ? 260 : Math.max(500, Math.min(760, 260 + 55 * nodes.length));
    const pos = forceLayout(names, drawn, W, H);
    const nar = narrator(drawn.length
      ? "Hover a line to read how two datasets connect; click it to see the matched and unmatched rows and the code to join them. Scroll to zoom, drag the background to move, drag a box to rearrange."
      : "No column links these datasets by name or by values. They can still be compared side by side, or the model can look for links the values hide.",
      "how the datasets relate");
    const view = { x: 0, y: 0, k: 1 };
    const layer = svg("g", { class: "rel-view" });
    const map = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart-svg rel-svg", role: "img",
                             "aria-label": "Map of the datasets and the columns that link them" }, layer);
    const applyView = () => layer.setAttribute("transform", `translate(${view.x} ${view.y}) scale(${view.k})`);
    const toUser = (e) => {
      const r = map.getBoundingClientRect();
      const scale = Math.min(r.width / W, r.height / H) || 1;   // the SVG is letterboxed inside its box
      return [(e.clientX - r.left - (r.width - W * scale) / 2) / scale,
              (e.clientY - r.top - (r.height - H * scale) / 2) / scale];
    };
    const zoomAt = (factor, px, py) => {
      const k2 = Math.min(5, Math.max(0.3, view.k * factor));
      view.x = px - (px - view.x) * (k2 / view.k);
      view.y = py - (py - view.y) * (k2 / view.k);
      view.k = k2;
      applyView();
    };
    const resetView = () => { view.x = 0; view.y = 0; view.k = 1; applyView(); };
    map.addEventListener("wheel", (e) => {
      e.preventDefault();
      const [px, py] = toUser(e);
      zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, px, py);
    }, { passive: false });

    let sel = null;              // { a, b } for a pair, { node } for one dataset
    const width = (d) => ({ strong: 5, partial: 3, weak: 1.5, none: 1.5, ai: 2.5 }[d.strength] || 1.5);
    const color = (d) => (d.kind === "ai" ? AI_COLOR : STRENGTH[d.strength][1]);
    const edgeLabel = (d) => {
      if (d.kind === "ai") return d.list.length === 1 ? d.list[0].a_column + " = " + d.list[0].b_column + " ?" : d.list.length + " AI ideas";
      const b = d.edge.best;
      return b.same_name ? b.a.column : b.a.column + " = " + b.b.column;
    };
    const edgeSentence = (d) => {
      if (d.kind === "ai") {
        const s = d.list[0];
        return "The model suggests " + s.a + "." + s.a_column + " may match " + s.b + "." + s.b_column +
          (d.list.length > 1 ? " (and " + (d.list.length - 1) + " more idea" + (d.list.length > 2 ? "s" : "") + ")" : "") +
          ". Not checked against the values yet. Click for the reasons.";
      }
      const e = d.edge, b = e.best;
      return e.a + " and " + e.b + " link through " + edgeLabel(d) + ": " + CARD_LABEL[b.cardinality] + ", " +
        fmtPct(b.a.rows_matched) + " of " + e.a + " rows and " + fmtPct(b.b.rows_matched) + " of " + e.b + " rows match." +
        (aiByPair.has(pairKey(e.a, e.b)) ? " The model has more ideas for this pair." : "") + " Click for the details.";
    };
    const fewLabels = drawn.length <= 7;
    const edgeEls = drawn.map((d) => {
      const halo = svg("line", { class: "edge-halo", "stroke-linecap": "round" });
      const hit = svg("line", { class: "edge-hit", "stroke-width": width(d) + 10, stroke: "transparent" });
      const vis = svg("line", { class: "edge-vis", "stroke-width": width(d), stroke: color(d), "stroke-linecap": "round",
                                "stroke-dasharray": d.kind === "ai" ? "7 5" : d.strength === "none" ? "5 4" : null });
      const lbl = svg("text", { "text-anchor": "middle", class: "lbl edge-lbl" }, short(edgeLabel(d), 28));
      const tipText = d.kind === "ai" ? edgeLabel(d) + " (suggested by the model)" : edgeLabel(d) + " (" + STRENGTH[d.strength][0].toLowerCase() + ")";
      const g = svg("g", { ...hover(tipText, nar.say, edgeSentence(d)),
                           class: "rel-edge rel-" + d.strength + (d.kind === "ai" ? " ai" : ""),
                           onclick: () => { if (dragged) return; setPair(d.a, d.b); nar.say.pin(edgeSentence(d)); } },
        halo, hit, vis, lbl);
      g.addEventListener("mouseenter", () => { lbl.style.display = ""; });
      g.addEventListener("mouseleave", () => { if (!fewLabels && !involved(d)) lbl.style.display = "none"; });
      return { d, g, halo, hit, vis, lbl };
    });
    const nodeEls = nodes.map((d) => {
      const w = boxWidth(d.name), h = BOX_H;
      const with_ = linkedWith(d.name);
      const about = d.name + " has " + num(d.rows) + " rows and " + d.columns_count + " columns" +
        (d.keys && d.keys.length ? "; " + d.keys.slice(0, 3).join(", ") + (d.keys.length === 1 ? " identifies" : " identify") + " a row." : ".") +
        (with_.length ? " Linked to " + with_.join(", ") + ". Click to see its links." : " Nothing links it to the other datasets.");
      const rect = svg("rect", { width: w, height: h, rx: 10 });
      const name = svg("text", { "text-anchor": "middle", class: "node-name" }, short(d.name, 26));
      const meta = svg("text", { "text-anchor": "middle", class: "lbl" }, num(d.rows) + " rows · " + d.columns_count + " cols");
      const g = svg("g", { ...hover(d.name + ": " + num(d.rows) + " rows, " + d.columns_count + " columns", nar.say, about),
                           class: "rel-node" + (with_.length ? "" : " alone"), "data-name": d.name,
                           onclick: () => { if (dragged) return; setNode(d.name); } },
        rect, name, meta);
      return { d, g, rect, name, meta, w, h };
    });
    const place = () => {
      for (const e of edgeEls) {
        const p = pos[e.d.a], q = pos[e.d.b];
        for (const line of [e.halo, e.hit, e.vis]) {
          line.setAttribute("x1", p.x); line.setAttribute("y1", p.y);
          line.setAttribute("x2", q.x); line.setAttribute("y2", q.y);
        }
        e.lbl.setAttribute("x", (p.x + q.x) / 2);
        e.lbl.setAttribute("y", (p.y + q.y) / 2 - 7);
      }
      for (const n of nodeEls) {
        const p = pos[n.d.name];
        n.rect.setAttribute("x", p.x - n.w / 2); n.rect.setAttribute("y", p.y - n.h / 2);
        n.name.setAttribute("x", p.x); n.name.setAttribute("y", p.y - 3);
        n.meta.setAttribute("x", p.x); n.meta.setAttribute("y", p.y + 14);
      }
    };
    layer.append(...edgeEls.map((e) => e.g), ...nodeEls.map((n) => n.g));
    place();

    // Dragging: the background pans, a box moves. A click that followed a drag is ignored.
    let drag = null, dragged = false;
    map.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      const [px, py] = toUser(e);
      const box = e.target.closest(".rel-node");
      const name = box ? box.getAttribute("data-name") : null;
      drag = { name, px, py, vx: view.x, vy: view.y, ox: name ? pos[name].x : 0, oy: name ? pos[name].y : 0, moved: false };
      map.setPointerCapture(e.pointerId);
      map.classList.add("dragging");
    });
    map.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const [px, py] = toUser(e);
      const dx = px - drag.px, dy = py - drag.py;
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
      if (!drag.moved) return;
      if (drag.name) {
        pos[drag.name].x = drag.ox + dx / view.k;
        pos[drag.name].y = drag.oy + dy / view.k;
        place();
      } else {
        view.x = drag.vx + dx; view.y = drag.vy + dy; applyView();
      }
    });
    const endDrag = () => {
      if (!drag) return;
      dragged = drag.moved;
      drag = null;
      map.classList.remove("dragging");
      setTimeout(() => { dragged = false; }, 0);
    };
    map.addEventListener("pointerup", endDrag);
    map.addEventListener("pointercancel", endDrag);

    // ---- what is selected
    const involved = (d) => {
      if (!sel) return false;
      if (sel.node) return d.a === sel.node || d.b === sel.node;
      return pairKey(d.a, d.b) === pairKey(sel.a, sel.b);
    };
    const highlight = () => {
      const onNodes = new Set(sel ? (sel.node ? [sel.node, ...linkedWith(sel.node)] : [sel.a, sel.b]) : []);
      for (const e of edgeEls) {
        const on = involved(e.d);
        e.g.classList.toggle("sel", on);
        e.g.classList.toggle("dim", Boolean(sel) && !on);
        e.lbl.style.display = fewLabels || on ? "" : "none";
      }
      for (const n of nodeEls) {
        const on = sel && (sel.node ? n.d.name === sel.node : onNodes.has(n.d.name));
        n.g.classList.toggle("sel", Boolean(on));
        n.g.classList.toggle("near", Boolean(sel && !on && onNodes.has(n.d.name)));
        n.g.classList.toggle("dim", Boolean(sel) && !onNodes.has(n.d.name));
      }
    };

    // ---- the picker and the detail below the map
    const pickA = el("select", { class: "ds-pick", "aria-label": "First dataset" });
    const pickB = el("select", { class: "ds-pick", "aria-label": "Second dataset" });
    pickA.replaceChildren(...names.map((n) => el("option", { value: n }, n)));
    const fill = () => {              // the second list offers everything but the first choice
      const cur = pickB.value;
      pickB.replaceChildren(el("option", { value: "" }, "everything it links to"),
        ...names.map((n) => el("option", { value: n, disabled: n === pickA.value }, n)));
      pickB.value = cur === pickA.value ? "" : cur;
    };
    fill();
    const detail = el("div", { class: "rel-detail" });
    const compareBtn = (a, b) => el("button", { type: "button", class: "link-btn", onclick: () => setPair(a, b) }, "Compare " + a + " with " + b);
    const askAi = () => opts.onSuggest
      ? el("button", { type: "button", class: "btn", disabled: opts.live === false,
          title: opts.live === false ? "Needs an API key" : "Send the column names, types and a few example values to the model",
          onclick: opts.onSuggest }, ai ? "Ask the model again" : "Ask the model for ideas")
      : null;
    const cards = (list) => el("div", { class: "rel-cards" + (list.length === 1 ? " one" : "") }, list);
    const showPair = (a, b) => {
      const e = autoByPair.get(pairKey(a, b));
      const ideas = aiByPair.get(pairKey(a, b)) || [];
      const links = e ? (e.a === a ? e.links : e.links.map(flip)) : [];
      const parts = [el("h4", {}, el("code", {}, a), " and ", el("code", {}, b),
        el("span", { class: "muted small" }, " ", links.length ? links.length + (links.length === 1 ? " link found in the values" : " links found in the values") : "no link found in the values",
          ideas.length ? ", " + ideas.length + (ideas.length === 1 ? " idea from the model" : " ideas from the model") : ""))];
      if (links.length) parts.push(cards(links.map((l, i) => linkCard(l, i === 0, verdictFor(l)))));
      if (ideas.length) {
        parts.push(el("h5", { class: "rel-sub" }, el("span", { class: "pill ai" }, "AI ideas"), " Read from the names, types and examples, not checked against the values."),
          cards(ideas.map((s, i) => aiCard(s, i === 0 && !links.length))));
      }
      if (!links.length && !ideas.length) {
        parts.push(el("p", { class: "muted small" }, "No column links these two by name or by values.",
          ai ? " The model had no idea for this pair either." : " The model can look for links the values hide, such as a key with a prefix on one side."), askAi());
      }
      detail.replaceChildren(el("div", {}, parts));
    };
    const flip = (l) => ({ ...l, a: l.b, b: l.a });
    const showNode = (name) => {
      const d = byName[name];
      const mine = drawn.filter((x) => x.a === name || x.b === name);
      detail.replaceChildren(el("div", {},
        el("h4", {}, el("code", {}, name), " ", el("span", { class: "muted small" }, num(d.rows) + " rows, " + d.columns_count + " columns, " + d.source)),
        d.keys && d.keys.length ? el("p", { class: "small" }, "Columns that identify a row: ", d.keys.map((k, i) => [i ? " " : "", el("code", {}, k)])) : null,
        mine.length
          ? el("ul", { class: "plain rel-links" }, mine.map((x) => {
              const other = x.a === name ? x.b : x.a;
              const line = x.kind === "ai"
                ? [el("span", { class: "pill ai" }, "AI idea"), " " + x.list.map((s) => s.a_column + " = " + s.b_column).join(", ")]
                : [el("span", { class: "pill " + (x.strength === "strong" ? "good" : x.strength === "partial" ? "warn" : "") }, STRENGTH[x.strength][0]),
                   " through ", el("code", {}, edgeLabel(x)), ", " + CARD_LABEL[x.edge.best.cardinality]];
              return el("li", {}, el("strong", {}, other), ": ", line, " · ", compareBtn(name, other));
            }))
          : el("p", { class: "muted small" }, "No link to the other datasets.", ai ? "" : " ", ai ? null : askAi())));
    };
    const setPair = (a, b) => {
      if (a === b) return;
      sel = { a, b };
      pickA.value = a; fill(); pickB.value = b;
      highlight(); showPair(a, b);
      if (opts.onSelect) opts.onSelect(sel);
    };
    const setNode = (name) => {
      sel = { node: name };
      pickA.value = name; fill(); pickB.value = "";
      highlight(); showNode(name);
      if (opts.onSelect) opts.onSelect(sel);
    };
    pickA.addEventListener("change", () => { if (pickB.value && pickB.value !== pickA.value) setPair(pickA.value, pickB.value); else setNode(pickA.value); });
    pickB.addEventListener("change", () => { if (pickB.value) setPair(pickA.value, pickB.value); else setNode(pickA.value); });

    const zoomBtn = (label, title, fn) => el("button", { type: "button", class: "btn zoom-btn", title, "aria-label": title, onclick: fn }, label);
    const tools = el("div", { class: "rel-tools" },
      el("label", {}, "Compare ", pickA), el("label", {}, "with ", pickB),
      el("span", { class: "zoom" },
        zoomBtn("−", "Zoom out", () => zoomAt(1 / 1.3, W / 2, H / 2)),
        zoomBtn("+", "Zoom in", () => zoomAt(1.3, W / 2, H / 2)),
        zoomBtn("Fit", "Show everything", resetView)));
    const legend = el("div", { class: "legend small muted" },
      Object.entries(STRENGTH).map(([k, v]) => el("span", {}, svg("svg", { width: 22, height: 8 },
        svg("line", { x1: 1, y1: 4, x2: 21, y2: 4, "stroke-width": 3, stroke: v[1], "stroke-dasharray": k === "none" ? "4 3" : null })), " " + v[0])),
      el("span", {}, svg("svg", { width: 22, height: 8 },
        svg("line", { x1: 1, y1: 4, x2: 21, y2: 4, "stroke-width": 3, stroke: AI_COLOR, "stroke-dasharray": "5 3" })), " Suggested by the model, not checked"));
    root.append(tools, el("div", { class: "rel-graph" }, map, nar.node, legend), detail);

    // Start on what the caller remembers, else the strongest link, else the first dataset.
    const s0 = opts.selected;
    if (s0 && s0.node && byName[s0.node]) setNode(s0.node);
    else if (s0 && s0.a && s0.b && byName[s0.a] && byName[s0.b]) setPair(s0.a, s0.b);
    else if (drawn.length) setPair(drawn[0].a, drawn[0].b);
    else setNode(names[0]);

    // ---- the rest: what the model said overall, shared columns, loners
    if (ai && ai.notes && ai.notes.length) {
      root.append(el("section", { class: "dash-sec" }, el("h3", {}, "What the model noticed about the whole collection"),
        el("ul", { class: "plain notes" }, ai.notes.map((t) => el("li", {}, t))),
        el("p", { class: "muted tiny" }, "From the column names, types and a few example values" + (ai.model ? ", by " + ai.model : "") + ". Nothing here was checked against the data.")));
    }
    if (rel.dimensions && rel.dimensions.length) {
      root.append(details("Columns several datasets share (" + rel.dimensions.length + ")",
        el("div", {},
          el("p", { class: "muted small" }, "The same column name in several files. A key joins rows; a dimension groups them the same way."),
          el("div", { class: "table-wrap" }, el("table", {},
            el("thead", {}, el("tr", {}, ["Column", "In", "Kind"].map((h) => el("th", {}, h)))),
            el("tbody", {}, rel.dimensions.map((d) => el("tr", {},
              el("td", {}, el("code", {}, d.column)),
              el("td", {}, d.datasets.join(", ")),
              el("td", {}, d.kinds.join(", ")))))))),
        "rel-more"));
    }
    if (rel.unlinked && rel.unlinked.length) {
      root.append(el("p", { class: "muted small" }, "Not linked to anything: " + rel.unlinked.join(", ") + "."));
    }
    return root;
  }

  function stat(label, value, note) {
    return el("div", { class: "stat" }, el("div", { class: "stat-v" }, value),
      el("div", { class: "stat-l" }, label), note ? el("div", { class: "stat-n" }, note) : null);
  }

  function statTest(card) {
    const r = card.result;
    const stats = [];
    const p = r.p ?? r.spearman_p;
    if (p !== undefined && p !== null) stats.push(stat("p-value", p < 0.001 ? "< 0.001" : num(p, 3)));
    if (r.cohens_d !== undefined) stats.push(stat("Cohen's d", num(r.cohens_d, 3), r.effect_size));
    if (r.eta_squared !== undefined) stats.push(stat("Eta squared", num(r.eta_squared, 3), r.effect_size));
    if (r.cramers_v !== undefined) stats.push(stat("Cramér's V", num(r.cramers_v, 3), r.effect_size));
    if (r.spearman_r !== undefined) stats.push(stat("Spearman", num(r.spearman_r, 3)));
    if (r.pearson_r !== undefined) stats.push(stat("Pearson", num(r.pearson_r, 3)));
    if (r.n !== undefined) stats.push(stat("Rows", num(r.n)));
    let groups = null;
    if (r.groups && typeof r.groups === "object") {
      const names = Object.keys(r.groups);
      groups = table({ columns: ["group", "n", "mean", "median", "std"],
        rows: names.map((g) => [g, r.groups[g].n, r.groups[g].mean, r.groups[g].median, r.groups[g].std]) });
    } else if (r.group_table) {
      const cols = Object.keys(r.group_table[0] || {});
      groups = table({ columns: cols, rows: r.group_table.map((row) => cols.map((c) => row[c])) });
    }
    return el("div", { class: "card stat-card" },
      el("div", { class: "card-title" }, r.test),
      el("p", { class: "lead" }, r.plain),
      el("div", { class: "stats" }, stats),
      groups ? details("Group summary", groups.querySelector(".table-wrap")) : null,
      r.notes && r.notes.length
        ? el("ul", { class: "plain notes" }, r.notes.map((n) => el("li", {}, n))) : null);
  }

  const METRIC_LABEL = { accuracy: "Accuracy", balanced_accuracy: "Balanced accuracy",
    f1_macro: "F1 (macro)", roc_auc: "ROC AUC", rmse: "RMSE", mae: "MAE", r2: "R²" };
  const AS_PERCENT = new Set(["accuracy", "balanced_accuracy"]);
  const fmtMetric = (k, v) => (v === null || v === undefined ? "" : AS_PERCENT.has(k) ? pct(v) : num(v, 4));

  function model(card) {
    const r = card.result;
    const keys = Object.keys(r.test_metrics);
    const compare = table({
      columns: ["", ...keys.map((k) => METRIC_LABEL[k] || k)],
      rows: [
        [r.best_model + " (test set)", ...keys.map((k) => fmtMetric(k, r.test_metrics[k]))],
        ["baseline (test set)", ...keys.map((k) => fmtMetric(k, r.baseline_test_metrics[k]))],
        [r.best_model + " (training rows)", ...keys.map((k) => fmtMetric(k, r.train_metrics[k]))],
      ],
    });
    const cvKeys = Object.keys(r.cross_validation[0] || {})
      .filter((k) => !["model", "cv_mean", "cv_std", "fit_seconds"].includes(k));
    const cv = table({
      columns: ["model", ...cvKeys.map((k) => METRIC_LABEL[k] || k), "seconds"],
      rows: r.cross_validation.map((m) => [m.model, ...cvKeys.map((k) => fmtMetric(k, m[k])),
        m.fit_seconds]),
    });
    const warn = (r.warnings || []).map((m) => ({
      level: /leak|overfit|no model beat|barely better/i.test(m) ? "high" : "medium", message: m }));
    const link = r.model_file ? api.downloadUrl(r.model_file) : null;
    return el("div", { class: "card model" },
      el("div", { class: "card-title" }, "Model for ", el("code", {}, r.target),
        el("span", { class: "chip" }, r.task), el("span", { class: "chip" }, r.model_id)),
      el("p", { class: "lead" }, r.headline),
      warn.length ? warnings(warn) : null,
      compare.querySelector(".table-wrap"),
      el("p", { class: "muted small" }, r.split + " " + num(r.rows_train) +
        " training rows, " + num(r.rows_test) + " test rows."),
      el("div", { class: "chart-row" }, (r.charts || []).map((c) => chart(c))),
      details("All models, cross-validated (" + r.cv_folds + " folds)", cv.querySelector(".table-wrap")),
      r.features_dropped && r.features_dropped.length
        ? details("Columns left out (" + r.features_dropped.length + ")",
            el("ul", { class: "plain" }, r.features_dropped.map((d) =>
              el("li", {}, el("code", {}, d.column), " ", d.reason))))
        : null,
      r.notes && r.notes.length
        ? el("ul", { class: "plain notes" }, r.notes.map((n) => el("li", {}, n))) : null,
      el("p", { class: "muted small" }, r.caveat),
      link ? el("a", { href: link, download: r.model_file, class: "quiet" },
        "Download the trained model (.joblib)") : null);
  }

  function code(card) {
    const changes = (card.changes || []).map((c) => el("li", {},
      el("code", {}, c.dataset), " " + c.change + ": " +
      (c.rows_before !== null && c.rows_before !== undefined
        ? num(c.rows_before) + " to " + num(c.rows) + " rows, " +
          c.columns_before + " to " + c.columns_count + " columns"
        : num(c.rows) + " rows, " + c.columns_count + " columns")));
    const body = el("div", {},
      el("pre", { class: "code", "data-lang": "python" }, el("code", {}, card.code)),
      card.stdout ? el("pre", { class: "output" }, card.stdout) : null,
      card.value ? el("pre", { class: "output" }, card.value) : null,
      card.error ? el("pre", { class: "output error" }, card.error) : null);
    return el("div", { class: "card code-wrap" },
      details((card.purpose || "Python code") + (card.error ? "  (failed)" : ""), body,
        "code-card" + (card.error ? " failed" : ""), Boolean(card.error)),
      changes.length ? el("ul", { class: "plain changes" }, changes) : null);
  }

  function download(card) {
    const link = api.downloadUrl(card.file);
    if (!link) return el("div", { class: "card notice" }, card.label + " (not included in the report)");
    return el("a", { class: "card download", href: link, download: card.file }, card.label);
  }

  const notice = (card) => el("div", { class: "card notice" }, card.message);
  const error = (card) => el("div", { class: "card notice error" }, card.message);

  const CARDS = { chart, table, profile, stat: statTest, model, code, download, notice, error };

  function card(c) {
    const make = CARDS[c.type];
    try {
      return make ? make(c) : el("pre", { class: "output" }, JSON.stringify(c, null, 1));
    } catch (e) {
      return el("div", { class: "card notice error" }, "Could not display this result: " + e.message);
    }
  }

  // ------------------------------------------------------------------ message pieces
  const TOOL_LABEL = {
    profile_dataset: ["Profiling the data", "Profiled the data"],
    preview_rows: ["Reading rows", "Read rows"],
    create_chart: ["Drawing a chart", "Drew a chart"],
    run_statistical_test: ["Running a statistical test", "Ran a statistical test"],
    train_model: ["Training models", "Trained models"],
    predict: ["Scoring rows", "Scored rows"],
    run_python: ["Writing and running Python", "Ran Python"],
    list_datasets: ["Checking the datasets", "Checked the datasets"],
    reset_dataset: ["Resetting the dataset", "Reset the dataset"],
    export_dataset: ["Exporting data", "Exported data"],
    export_report: ["Writing the report file", "Wrote the report file"],
  };

  function toolBlock(part) {
    const labels = TOOL_LABEL[part.name] || [part.name, part.name];
    const running = part.status === "writing" || part.status === "running";
    const head = el("div", { class: "tool-head " + part.status },
      el("span", { class: "dot" }),
      el("span", { class: "tool-name" }, running ? labels[0] : labels[1]),
      part.summary ? el("span", { class: "tool-summary" }, part.summary) : null);
    const hasCode = (part.cards || []).some((c) => c.type === "code");
    const input = part.input && Object.keys(part.input).length && !hasCode
      ? details("Request", el("pre", { class: "output" }, JSON.stringify(part.input, null, 1)),
          "tool-input")
      : null;
    const fail = part.status === "error" && part.error && !hasCode
      ? el("pre", { class: "output error" }, part.error) : null;
    return el("div", { class: "tool", "data-tool": part.id || "" }, head, input, fail,
      (part.cards || []).map(card));
  }

  function part(p) {
    if (p.type === "text") return el("div", { class: "md", html: markdown(p.text) });
    if (p.type === "thinking") {
      return p.text.trim()
        ? details("Reasoning", el("div", { class: "md", html: markdown(p.text) }), "thinking")
        : null;
    }
    if (p.type === "tool") return toolBlock(p);
    if (p.type === "notice") {
      return el("div", { class: "card notice " + (p.level || ""), html: markdown(p.text) });
    }
    return null;
  }

  function transcriptItem(item) {
    if (item.role === "user") {
      return el("div", { class: "msg user" }, el("div", { class: "bubble" }, item.text));
    }
    if (item.role === "upload") {
      return el("div", { class: "msg system" },
        el("div", { class: "upload-line" }, "Uploaded ", el("strong", {}, item.file)),
        item.datasets.map((p) => profile({ profile: p })));
    }
    return el("div", { class: "msg assistant" }, (item.parts || []).map(part));
  }

  return Object.assign(api, { el, esc, num, pct, markdown, inline, card, part, toolBlock,
                              transcriptItem, profile, quality, dashboard, relations, issueCounts });
})();
