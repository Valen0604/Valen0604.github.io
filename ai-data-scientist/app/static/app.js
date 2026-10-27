/*
 * app.js: the chat page.
 *
 * Talks to the server in app/main.py. A reply arrives as a stream of events; each event
 * updates one piece of the message being built. render.js draws everything.
 *
 * Four views share the page: the chat, a dashboard per dataset, a map of how the
 * datasets relate, and a data-quality report per dataset. The dashboards and the map are
 * computed when a file loads, with no model call, and recomputed when the agent's code
 * changes or creates a dataset.
 *
 * Chats: the sidebar lists every open chat. Each one has its own datasets and its own
 * analysis process; nothing crosses between them unless the user brings a dataset over.
 *
 * Links:
 *   /?sample=customer_churn.csv&q=profile+the+data   load a sample and ask a question
 *   /?session=<id>                                   open a chat the server still has
 */
(() => {
  "use strict";
  const { el, markdown, toolBlock, transcriptItem, num } = Render;
  const $ = (id) => document.getElementById(id);

  const state = {
    sid: null, config: null, datasets: [], profiles: {}, dashboards: {}, relations: null,
    relSel: null, relBusy: false,       // the pair chosen on the map; a model call in progress
    busy: false, level: "standard", context: null, suggestions: [], tab: "chat", shown: null,
    askedContext: false, chats: [], title: "", palette: "single",
  };

  // ------------------------------------------------------------------------ server
  async function api(path, options = {}) {
    const res = await fetch(path, options);
    if (!res.ok) {
      let message = res.statusText;
      try { message = (await res.json()).detail || message; } catch (_) { /* not JSON */ }
      const err = new Error(message);
      err.status = res.status;
      throw err;
    }
    return res.json();
  }
  const send_json = (method, path, body) => api(path, {
    method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}),
  });
  const post = (path, body) => send_json("POST", path, body);

  function toast(message, isError = false) {
    document.querySelectorAll(".toast").forEach((t) => t.remove());
    const t = el("div", { class: "toast" + (isError ? " error" : ""), role: "status" }, message);
    document.body.append(t);
    setTimeout(() => t.remove(), isError ? 7000 : 3500);
  }

  /* Fetch a file the server builds on request and hand it to the browser as a download. */
  async function downloadFile(path, options, fallbackName) {
    const res = await fetch(path, options);
    if (!res.ok) {
      let message = res.statusText;
      try { message = (await res.json()).detail || message; } catch (_) { /* not JSON */ }
      throw new Error(message);
    }
    const blob = await res.blob();
    const disposition = res.headers.get("content-disposition") || "";
    const m = disposition.match(/filename="?([^";]+)"?/);
    const a = el("a", { href: URL.createObjectURL(blob), download: m ? m[1] : fallbackName });
    document.body.append(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
  }

  // ------------------------------------------------------------------------ layout
  const scroller = $("scroll");
  let pinned = true;                          // follow new content unless the user scrolled up
  scroller.addEventListener("scroll", () => {
    pinned = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 120;
  });
  function follow(force = false) {
    if (pinned || force) scroller.scrollTop = scroller.scrollHeight;
  }
  function hideWelcome() {
    const w = $("welcome");
    if (w) w.remove();
  }

  function setBusy(busy) {
    state.busy = busy;
    $("send").classList.toggle("stop", busy);
    $("send").setAttribute("aria-label", busy ? "Stop" : "Send");
    // SVG elements have no .hidden property, so set the attribute.
    $("send-icon").toggleAttribute("hidden", busy);
    $("stop-icon").toggleAttribute("hidden", !busy);
    refreshSend();
  }
  function refreshSend() {
    $("send").disabled = !state.busy && !$("input").value.trim();
  }

  function showUsage(u) {
    if (!u) return;
    $("tokens").textContent = num(u.input_tokens + u.cache_read_tokens + u.cache_write_tokens) +
      " / " + num(u.output_tokens);
    $("cost").textContent = "$" + (u.cost_usd || 0).toFixed(3);
  }

  function hasAnswers() {
    return Boolean(document.querySelector(".msg.assistant"));
  }
  function refreshExportButtons() {
    const answered = hasAnswers();
    $("report").disabled = !answered;
    $("print").disabled = !answered && !state.datasets.length;
    $("export-open").disabled = !answered && !state.datasets.length;
  }

  // ----------------------------------------------------------------------- tabs
  const PER_DATASET = new Set(["dashboard", "quality"]);

  function showTab(tab, dataset) {
    state.tab = tab;
    for (const b of document.querySelectorAll("#tabs .tab")) b.classList.toggle("on", b.dataset.tab === tab);
    for (const p of document.querySelectorAll(".panel")) p.classList.toggle("on", p.id === "panel-" + tab);
    const pick = $("ds-pick");
    pick.hidden = !PER_DATASET.has(tab) || state.datasets.length < 2;
    if (dataset && state.datasets.some((d) => d.name === dataset)) state.shown = dataset;
    if (!state.shown || !state.datasets.some((d) => d.name === state.shown)) {
      const active = state.datasets.find((d) => d.active) || state.datasets[0];
      state.shown = active ? active.name : null;
    }
    pick.value = state.shown || "";
    if (tab === "relations") paintRelations();
    else if (tab !== "chat") paintPanel(tab);
    if (tab === "chat") $("input").focus();
  }
  Render.openTab = (tab, dataset) => showTab(tab, dataset);
  Render.ask = (text) => { showTab("chat"); send(text); };

  const KIND_LABEL = { uploaded: "", modified: ", changed by the agent", created: ", created by the agent" };

  function paintPanel(tab) {
    const name = state.shown;
    const box = $(tab);
    if (!name) {
      box.replaceChildren(el("div", { class: "empty-panel" },
        tab === "dashboard" ? "Upload a dataset to see its dashboard." : "Upload a dataset to see its data-quality report."));
      return;
    }
    const info = state.datasets.find((d) => d.name === name) || {};
    if (tab === "dashboard") {
      const d = state.dashboards[name];
      box.replaceChildren(
        el("div", { class: "panel-head" },
          el("h2", {}, "First look at ", el("code", {}, name)),
          el("div", { class: "muted small" },
            info.kind === "created"
              ? "This dataset was created by the agent during the chat. The dashboard is computed from it as it is now."
              : "Computed from the data" + (info.kind === "modified" ? " as the agent left it" : " as uploaded") +
                ". Hover a bar or a point for its value; click a correlation cell to see the points. The line under each chart says what it shows.",
            " ", el("button", { type: "button", class: "link-btn", onclick: () => rebuildDashboard(name) }, "Recompute"),
            " · ", el("a", { class: "link-btn", href: downloadUrl(name, "csv") }, "Download CSV"))),
        d ? Render.dashboard(d) : el("div", { class: "empty-panel" }, "The dashboard for this dataset is not available. Recompute it."));
    } else {
      const p = state.profiles[name];
      box.replaceChildren(
        el("div", { class: "panel-head" },
          el("h2", {}, "Data quality of ", el("code", {}, name)),
          el("div", { class: "muted small" }, "What a careful analyst would want to know before trusting a result. Ask the agent to fix anything here; it will say what it changed.")),
        p ? Render.quality(p) : el("div", { class: "empty-panel" }, "No profile for this dataset."));
    }
  }

  async function rebuildDashboard(name) {
    if (state.busy) return toast("Wait for the reply to finish.", true);
    toast("Recomputing");
    try {
      state.dashboards[name] = await post(`/api/sessions/${state.sid}/dashboard/${encodeURIComponent(name)}`);
      paintPanel("dashboard");
    } catch (e) { toast(e.message, true); }
  }

  // ---------------------------------------------------------------- relationships
  async function loadRelations(force = false) {
    if (state.datasets.length < 2) { state.relations = null; refreshRelBadge(); return null; }
    try {
      state.relations = force
        ? await post(`/api/sessions/${state.sid}/relations`)
        : await api(`/api/sessions/${state.sid}/relations`);
    } catch (e) { toast(e.message, true); }
    refreshRelBadge();
    return state.relations;
  }

  function refreshRelBadge() {
    const badge = $("rel-badge");
    const n = state.relations ? (state.relations.edges || []).length : 0;
    badge.hidden = !n;
    badge.textContent = n;
    badge.classList.remove("bad");
  }

  async function paintRelations() {
    const box = $("relations");
    if (state.datasets.length < 2) {
      box.replaceChildren(el("div", { class: "empty-panel" },
        "Upload two or more datasets to see how they relate: which columns could join them, and how well the values match."));
      return;
    }
    if (!state.relations) {
      box.replaceChildren(el("div", { class: "empty-panel" }, "Comparing the datasets"));
      await loadRelations();
      if (!state.relations) return;
    }
    const rel = state.relations;
    const live = Boolean(state.config && state.config.live);
    const ideas = rel.ai ? (rel.ai.suggestions || []).length : 0;
    box.replaceChildren(
      el("div", { class: "panel-head rel-head" },
        el("div", {},
          el("h2", {}, "How the ", String(state.datasets.length), " datasets relate"),
          el("div", { class: "muted small" },
            "Solid lines are columns whose values match, found with no model call. Dashed purple lines are ideas from the model, not checked against the values. ",
            el("button", { type: "button", class: "link-btn", onclick: async () => { toast("Recomputing"); await loadRelations(true); paintRelations(); } }, "Recompute"))),
        el("button", { type: "button", class: "btn primary", id: "rel-ai", disabled: !live || state.relBusy,
            title: live ? "Send the column names, types and a few example values to the model and get the relationships it would look for"
                        : "Needs an API key: add one to .env and restart",
            onclick: suggestRelations },
          state.relBusy ? "Asking the model…" : rel.ai ? "Ask the model again" : "Ask the model for relationship ideas")),
      rel.ai ? el("p", { class: "muted small rel-ai-line" },
        ideas ? "The model suggested " + ideas + (ideas === 1 ? " relationship" : " relationships") + " beyond the value check" + (rel.ai.found && rel.ai.found.length ? " and gave a verdict on " + rel.ai.found.length + " found link" + (rel.ai.found.length === 1 ? "" : "s") : "") + "."
              : "The model had nothing to add to the value check.",
        rel.ai.cost_usd ? " That call cost about $" + rel.ai.cost_usd.toFixed(3) + "." : "") : null,
      Render.relations(rel, { selected: state.relSel, onSelect: (s) => { state.relSel = s; },
                              onSuggest: suggestRelations, live }));
  }

  /* One model call, apart from the chat: the schemas go in, suggested links come back
     and are drawn on the map as dashed lines until a dataset changes. */
  async function suggestRelations() {
    if (state.busy) return toast("Wait for the reply to finish.", true);
    if (state.relBusy) return;
    state.relBusy = true;
    paintRelations();
    try {
      const r = await post(`/api/sessions/${state.sid}/relations/suggest`);
      if (r.usage) showUsage(r.usage);
      state.relations = r;
      const n = r.ai ? (r.ai.suggestions || []).length : 0;
      toast(n ? n + (n === 1 ? " idea from the model" : " ideas from the model") : "The model had nothing to add.");
    } catch (e) { toast(e.message, true); }
    state.relBusy = false;
    paintRelations();
  }

  function refreshBadge() {
    const badge = $("quality-badge");
    let high = 0, total = 0;
    for (const d of state.datasets) {
      const p = state.profiles[d.name];
      if (!p) continue;
      const n = Render.issueCounts(p.warnings);
      high += n.high;
      total += n.high + n.medium;
    }
    badge.hidden = !total;
    badge.textContent = total;
    badge.classList.toggle("bad", high > 0);
  }

  // ---------------------------------------------------------------------- datasets
  const downloadUrl = (name, format) =>
    `/api/sessions/${state.sid}/datasets/${encodeURIComponent(name)}/download?format=${format}`;

  function showDatasets(list) {
    state.datasets = list || [];
    const box = $("datasets");
    box.replaceChildren();
    if (!state.datasets.length) {
      box.append(el("div", { class: "empty" }, "Nothing loaded yet."));
    }
    for (const d of state.datasets) {
      const p = state.profiles[d.name];
      const serious = p ? p.warnings.filter((w) => w.level === "high").length : 0;
      const total = p ? p.warnings.filter((w) => w.level !== "info").length : 0;
      box.append(el("div", { class: "ds" + (d.active ? " active" : "") + (d.kind === "created" ? " created" : ""), role: "button", tabindex: "0",
          title: "Show the dashboard", onclick: () => showTab("dashboard", d.name),
          onkeydown: (e) => (e.key === "Enter" || e.key === " ") && showTab("dashboard", d.name) },
        el("div", { class: "ds-main" },
          el("div", { class: "ds-name" }, d.name),
          el("div", { class: "ds-meta" }, num(d.rows) + " rows, " + d.columns_count + " columns" + (KIND_LABEL[d.kind] || ""))),
        total ? el("span", { class: "badge" + (serious ? " bad" : ""), title: "Open the data-quality report",
          onclick: (e) => { e.stopPropagation(); showTab("quality", d.name); } },
          total + (total === 1 ? " issue" : " issues")) : null,
        el("a", { class: "x dl", href: downloadUrl(d.name, "csv"), title: "Download as CSV (right-click for the link; Excel and Parquet from the dashboard)",
          "aria-label": "Download " + d.name, onclick: (e) => { e.stopPropagation(); if (state.busy) { e.preventDefault(); toast("Wait for the reply to finish.", true); } } }, "↓"),
        el("button", { class: "x", "aria-label": "Remove " + d.name, title: "Remove",
          onclick: (e) => { e.stopPropagation(); removeDataset(d.name); } }, "×")));
    }
    const pick = $("ds-pick");
    pick.replaceChildren(...state.datasets.map((d) => el("option", { value: d.name }, d.name)));
    pick.hidden = !PER_DATASET.has(state.tab) || state.datasets.length < 2;
    $("import-open").hidden = state.chats.filter((c) => c.id !== state.sid && c.datasets.length).length === 0;
    refreshExportButtons();
    refreshBadge();
    refreshRelBadge();
    if (state.tab !== "chat") showTab(state.tab, state.shown);
    suggest();
  }

  async function removeDataset(name) {
    if (state.busy) return toast("Wait for the reply to finish.", true);
    try {
      const r = await api(`/api/sessions/${state.sid}/datasets/${encodeURIComponent(name)}`,
        { method: "DELETE" });
      delete state.profiles[name];
      delete state.dashboards[name];
      state.relations = r.relations || null;
      showDatasets(r.datasets);
      refreshChats();
    } catch (e) { toast(e.message, true); }
  }

  function afterLoad(result, file) {
    for (const p of result.loaded) state.profiles[p.name] = p;
    for (const [name, d] of Object.entries(result.dashboards || {})) state.dashboards[name] = d;
    state.relations = result.relations || null;
    if (result.loaded.length) {
      hideWelcome();
      $("chat").append(transcriptItem({ role: "upload", file, datasets: result.loaded }));
      const first = result.loaded[0];
      const n = Render.issueCounts(first.warnings);
      const links = state.relations ? (state.relations.edges || []).length : 0;
      $("chat").append(el("div", { class: "msg system" }, el("div", { class: "card notice" },
        el("span", {}, "The dashboard for ", el("code", {}, first.name), " is ready" +
          (n.high + n.medium ? ", and the data-quality report lists " + (n.high + n.medium) + " things to check." : ".")),
        " ", el("button", { type: "button", class: "link-btn", onclick: () => showTab("dashboard", first.name) }, "Open the dashboard"),
        result.datasets.length >= 2 ? [" · ", el("button", { type: "button", class: "link-btn", onclick: () => showTab("relations") },
          links ? "See how the " + result.datasets.length + " datasets relate (" + links + (links === 1 ? " link)" : " links)") : "Compare the datasets")] : null)));
      follow(true);
    }
    for (const e of result.errors) toast(e.file + ": " + e.error, true);
    showDatasets(result.datasets);
    refreshChats();
    // The first time data arrives, ask what the user knows about it. Once per session,
    // and never in the way: it can be skipped and reopened from the sidebar.
    if (result.loaded.length && !state.askedContext && !(state.context && state.context.given)) {
      state.askedContext = true;
      openContext(true);
    }
  }

  async function upload(files) {
    if (!files || !files.length) return;
    if (state.busy) return toast("Wait for the reply to finish, then upload.", true);
    for (const file of files) {
      const form = new FormData();
      form.append("files", file);
      toast("Reading " + file.name);
      try {
        afterLoad(await api(`/api/sessions/${state.sid}/upload`, { method: "POST", body: form }),
          file.name);
      } catch (e) { toast(file.name + ": " + e.message, true); }
    }
    $("input").focus();
  }

  async function loadSample(name) {
    if (state.busy) return toast("Wait for the reply to finish.", true);
    toast("Loading " + name);
    try { afterLoad(await post(`/api/sessions/${state.sid}/sample`, { name }), name); }
    catch (e) { toast(e.message, true); }
  }

  /* Bring a dataset over from another chat. The only way data crosses between chats. */
  async function importDataset(fromSession, dataset) {
    if (state.busy) return toast("Wait for the reply to finish.", true);
    $("import-dialog").close();
    toast("Copying " + dataset);
    try {
      afterLoad(await post(`/api/sessions/${state.sid}/datasets/import`, { from_session: fromSession, dataset }),
        dataset + " (from another chat)");
    } catch (e) { toast(e.message, true); }
  }

  function openImport() {
    const list = $("import-list");
    list.replaceChildren();
    const others = state.chats.filter((c) => c.id !== state.sid && c.datasets.length);
    if (!others.length) list.append(el("p", { class: "muted small" }, "No other chat has data loaded."));
    for (const c of others) {
      list.append(el("div", { class: "import-chat" },
        el("div", { class: "import-title" }, c.title),
        c.datasets.map((name) => el("button", { type: "button", class: "btn import-btn",
          onclick: () => importDataset(c.id, name) }, name))));
    }
    $("import-dialog").showModal();
  }

  // -------------------------------------------------------------------------- chats
  async function refreshChats() {
    try { state.chats = await api("/api/sessions"); } catch (_) { return; }
    const box = $("chats");
    box.replaceChildren();
    for (const c of state.chats) {
      const here = c.id === state.sid;
      box.append(el("div", { class: "chat-item" + (here ? " active" : ""), role: "button", tabindex: "0",
          title: here ? "This chat" : "Open this chat",
          onclick: () => !here && openChat(c.id),
          onkeydown: (e) => (e.key === "Enter" || e.key === " ") && !here && openChat(c.id) },
        el("div", { class: "ds-main" },
          el("div", { class: "ds-name" }, c.title),
          el("div", { class: "ds-meta" }, (c.datasets.length ? c.datasets.join(", ") : "no data") +
            (c.questions ? " · " + c.questions + (c.questions === 1 ? " question" : " questions") : "") + (c.busy ? " · replying" : ""))),
        here ? null : el("button", { class: "x", "aria-label": "Close chat", title: "Close this chat",
          onclick: (e) => { e.stopPropagation(); closeChat(c); } }, "×")));
    }
    $("import-open").hidden = state.chats.filter((c) => c.id !== state.sid && c.datasets.length).length === 0;
    const me = state.chats.find((c) => c.id === state.sid);
    if (me) { state.title = me.title; $("chat-title").textContent = me.title; }
  }

  function openChat(id) {
    if (state.busy && !confirm("A reply is still being written here. Open the other chat anyway?")) return;
    sessionStorage.setItem("ads-session", id);
    window.location.href = window.location.pathname + "?session=" + encodeURIComponent(id);
  }

  async function newChat() {
    try {
      const { id } = await post("/api/sessions");
      sessionStorage.setItem("ads-session", id);
      window.location.href = window.location.pathname + "?session=" + encodeURIComponent(id);
    } catch (e) { toast(e.message, true); }
  }

  async function closeChat(c) {
    if (!confirm(`Close the chat "${c.title}"? Its conversation will be gone from this page. Files it saved stay on disk.`)) return;
    try {
      await api(`/api/sessions/${c.id}`, { method: "DELETE" });
      refreshChats();
    } catch (e) { toast(e.message, true); }
  }

  async function renameChat() {
    const title = prompt("Name this chat", state.title || "");
    if (title === null) return;
    try {
      const r = await send_json("PATCH", `/api/sessions/${state.sid}`, { title });
      state.title = r.title;
      $("chat-title").textContent = r.title;
      refreshChats();
    } catch (e) { toast(e.message, true); }
  }

  // ---------------------------------------------------------- context and detail
  function showContext(c) {
    state.context = c;
    const box = $("ctx-summary");
    if (c && c.given) {
      const text = [c.description, c.goal, c.constraints, c.notes].filter(Boolean).join(" ");
      box.textContent = text.length > 140 ? text.slice(0, 139) + "…" : text;
      box.classList.add("given");
      $("ctx-open").textContent = "Edit context";
    } else {
      box.textContent = "Tell the agent what the data is and what you want to decide, so it does not suggest what you cannot do.";
      box.classList.remove("given");
      $("ctx-open").textContent = "Add context";
    }
    if (c && c.level) setLevel(c.level, false);
  }

  function openContext(firstTime = false) {
    const form = $("ctx-form");
    for (const key of ["description", "goal", "constraints", "notes"]) {
      form.elements[key].value = (state.context && state.context[key]) || "";
    }
    $("ctx-skip").hidden = !firstTime;
    $("ctx-dialog").showModal();
    form.elements.description.focus();
  }

  async function saveContext() {
    const form = $("ctx-form");
    const body = { level: state.level };
    for (const key of ["description", "goal", "constraints", "notes"]) body[key] = form.elements[key].value;
    try {
      showContext(await send_json("PUT", `/api/sessions/${state.sid}/context`, body));
      if (state.context.given) toast("Saved. The agent reads it with your next message.");
    } catch (e) { toast(e.message, true); }
  }

  function setLevel(level, tell = true) {
    state.level = level;
    for (const b of document.querySelectorAll("#level button")) b.classList.toggle("on", b.dataset.level === level);
    if (tell) {
      send_json("PUT", `/api/sessions/${state.sid}/context`, { ...(state.context || {}), level })
        .then(showContext).catch(() => {});
    }
  }

  /* Chart colours. The dashboard repaints at once; the agent's next chart follows. */
  function setPalette(palette, tell = true) {
    state.palette = palette;
    Render.palette = palette;
    for (const b of document.querySelectorAll("#palette button")) b.classList.toggle("on", b.dataset.palette === palette);
    try { localStorage.setItem("ads-palette", palette); } catch (_) { /* private window */ }
    if (state.tab === "dashboard") paintPanel("dashboard");
    if (tell && state.sid) {
      send_json("PUT", `/api/sessions/${state.sid}/style`, { palette }).catch(() => {});
    }
  }

  // ---------------------------------------------------------------------- export
  function openExport() {
    const questions = [...document.querySelectorAll("#chat .msg.user .bubble")].map((b) => b.textContent);
    const box = $("export-turns");
    box.replaceChildren();
    if (!questions.length) box.append(el("p", { class: "muted small" }, "No answers yet. Tick the first look below to export the dashboards' findings."));
    questions.forEach((q, i) => {
      box.append(el("label", { class: "export-turn" },
        el("input", { type: "checkbox", name: "turn", value: String(i + 1), checked: i === questions.length - 1 }),
        el("span", {}, (i + 1) + ". " + (q.length > 110 ? q.slice(0, 109) + "…" : q))));
    });
    const form = $("export-form");
    form.elements.title.value = state.title && state.title !== "New chat" ? state.title : "";
    form.elements.with_overview.checked = !questions.length;
    $("export-dialog").showModal();
  }

  async function runExport() {
    const form = $("export-form");
    const turns = [...form.querySelectorAll('input[name="turn"]:checked')].map((i) => Number(i.value));
    const format = form.elements.format.value;
    const body = { format, turns: turns.length ? turns : null, with_code: form.elements.with_code.checked,
                   with_overview: form.elements.with_overview.checked, title: form.elements.title.value || null };
    if (!turns.length && !body.with_overview) return toast("Pick at least one answer, or the first look.", true);
    $("export-dialog").close();
    toast("Building the " + (format === "pdf" ? "PDF" : "slides"));
    try {
      await downloadFile(`/api/sessions/${state.sid}/export`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
        "report." + format);
    } catch (e) { toast(e.message, true); }
  }

  // -------------------------------------------------------------------- suggestions
  /* Before the first question: a few openers from the column types. After an answer:
     the follow-up questions the agent wrote. */
  function suggest() {
    const box = $("suggest");
    box.replaceChildren();
    if (state.busy || !state.datasets.length) return;
    let ideas = state.suggestions || [];
    if (!ideas.length) {
      const d = state.datasets.find((x) => x.active) || state.datasets[0];
      const of = (kind) => d.columns.filter((c) => c.kind === kind).map((c) => c.name);
      // A yes/no column is the likeliest thing to predict; failing that, the last category.
      const yesNo = of("boolean"), categories = of("categorical");
      const target = yesNo[yesNo.length - 1] || categories[categories.length - 1];
      const numeric = of("numeric"), dates = of("datetime");
      ideas = ["Give me an overview of this data", "What data-quality problems should I know about?"];
      if (state.datasets.length >= 2) ideas.push("How are the datasets related, and can they be joined?");
      if (target) ideas.push("What drives " + target + "? Build a model and explain it");
      if (dates.length && numeric.length) {
        ideas.push("How has " + numeric[numeric.length - 1] + " changed over time?");
      } else if (numeric.length >= 2) {
        ideas.push("Is " + numeric[0] + " related to " + numeric[1] + "?");
      }
    }
    for (const text of ideas.slice(0, 4)) {
      box.append(el("button", { type: "button", onclick: () => send(text) }, text));
    }
  }

  // --------------------------------------------------------------------------- chat
  /* Reads a text/event-stream body and calls handle(event, data) for each event. */
  async function readStream(response, handle) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        let event = "message";
        const data = [];
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
        }
        if (data.length) handle(event, JSON.parse(data.join("\n")));
      }
    }
  }

  /* After a reply: dashboards the server recomputed for datasets the code changed or
     created, so the sidebar and the tabs show the data as it is now. */
  function applyRefreshed(refreshed, before) {
    const names = Object.keys(refreshed || {});
    if (!names.length) return;
    for (const name of names) {
      state.dashboards[name] = refreshed[name].dashboard;
      state.profiles[name] = refreshed[name].profile;
    }
    state.relations = null;                    // stale: recomputed when the tab is opened
    const created = names.filter((n) => !before.has(n));
    if (created.length) {
      $("chat").append(el("div", { class: "msg system" }, el("div", { class: "card notice" },
        el("span", {}, "New dataset" + (created.length > 1 ? "s" : "") + ": ",
          created.map((n, i) => [i ? ", " : "", el("code", {}, n)]),
          ". It is in the sidebar with a dashboard and a download."),
        " ", el("button", { type: "button", class: "link-btn", onclick: () => showTab("dashboard", created[0]) }, "Open the dashboard"))));
      follow();
    }
  }

  /* Builds one assistant message from the events of a reply. */
  function messageBuilder() {
    const root = el("div", { class: "msg assistant" });
    const status = el("div", { class: "typing" }, el("i"), el("i"), el("i"), el("span", {}, "Thinking"));
    root.append(status);
    $("chat").append(root);

    let current = null;         // the text or thinking block being written
    const tools = {};           // id -> { part, node }
    let frame = 0;
    const before = new Set(state.datasets.map((d) => d.name));

    const place = (node) => { root.insertBefore(node, status); follow(); };

    function paint() {
      frame = 0;
      if (current) current.body.innerHTML = markdown(current.text);
      follow();
    }
    function write(kind, delta) {
      if (!current || current.kind !== kind) {
        const body = el("div", { class: "md" });
        const node = kind === "thinking"
          ? el("details", { class: "thinking", open: true }, el("summary", {}, "Reasoning"), body)
          : body;
        current = { kind, text: "", body, node };
        place(node);
      }
      current.text += delta;
      if (!frame) frame = requestAnimationFrame(paint);      // at most one repaint per frame
    }
    function closeBlock() {
      if (frame) { cancelAnimationFrame(frame); paint(); }
      if (current && current.kind === "thinking") current.node.open = false;
      current = null;
    }
    function tool(id, update) {
      closeBlock();
      const entry = tools[id] || (tools[id] = { part: { type: "tool", id, cards: [] }, node: null });
      Object.assign(entry.part, update);
      const node = toolBlock(entry.part);
      if (entry.node) entry.node.replaceWith(node); else place(node);
      entry.node = node;
      follow();
    }

    return {
      handle(event, d) {
        if (event === "status") status.lastChild.textContent = d.text;
        else if (event === "text_delta") write("text", d.text);
        else if (event === "thinking_delta") write("thinking", d.text);
        else if (event === "tool_start") tool(d.id, { name: d.name, status: "writing" });
        else if (event === "tool_running") tool(d.id, { name: d.name, status: "running", input: d.input });
        else if (event === "tool_done") {
          tool(d.id, { name: d.name, status: d.ok ? "done" : "error", summary: d.summary,
                       cards: d.cards, error: d.error });
          for (const c of d.cards) if (c.type === "profile") state.profiles[c.profile.name] = c.profile;
        }
        else if (event === "notice") {
          closeBlock();
          place(el("div", { class: "card notice " + (d.level || ""), html: markdown(d.text) }));
        }
        else if (event === "usage") showUsage(d);
        else if (event === "suggestions") state.suggestions = d.questions || [];
        else if (event === "done") {
          showUsage(d.usage);
          applyRefreshed(d.refreshed, before);
          showDatasets(d.datasets);
          if (d.title) { state.title = d.title; $("chat-title").textContent = d.title; }
        }
      },
      finish() { closeBlock(); status.remove(); follow(); },
    };
  }

  async function send(text) {
    text = (text ?? $("input").value).trim();
    if (!text || state.busy) return;
    showTab("chat");
    hideWelcome();
    $("input").value = "";
    autosize();
    $("chat").append(transcriptItem({ role: "user", text }));
    pinned = true;
    follow(true);
    setBusy(true);
    state.suggestions = [];
    $("suggest").replaceChildren();

    const builder = messageBuilder();
    try {
      const res = await fetch(`/api/sessions/${state.sid}/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, level: state.level }),
      });
      if (!res.ok) {
        let message = res.statusText;
        try { message = (await res.json()).detail || message; } catch (_) { /* not JSON */ }
        throw new Error(message);
      }
      await readStream(res, builder.handle);
    } catch (e) {
      builder.handle("notice", { level: "error",
        text: "The connection to the app was lost: " + e.message });
    } finally {
      builder.finish();
      setBusy(false);
      refreshExportButtons();
      suggest();
      refreshBadge();
      refreshChats();
      $("input").focus();
    }
  }

  // ------------------------------------------------------------------------ wiring
  function autosize() {
    const t = $("input");
    t.style.height = "auto";
    t.style.height = Math.min(t.scrollHeight, 200) + "px";
    refreshSend();
  }

  function wire() {
    $("input").addEventListener("input", autosize);
    $("input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
    });
    $("form").addEventListener("submit", (e) => {
      e.preventDefault();
      if (state.busy) post(`/api/sessions/${state.sid}/stop`).catch(() => {});
      else send();
    });
    $("attach").addEventListener("click", () => $("file").click());
    $("file").addEventListener("change", (e) => { upload([...e.target.files]); e.target.value = ""; });
    $("dlg-close").addEventListener("click", () => $("dialog").close());
    $("dialog").addEventListener("click", (e) => { if (e.target === $("dialog")) $("dialog").close(); });
    $("menu").addEventListener("click", () => $("side").classList.toggle("open"));
    $("main").addEventListener("click", (e) => {
      if (!e.target.closest("#menu")) $("side").classList.remove("open");
    });
    for (const b of document.querySelectorAll("#tabs .tab")) {
      b.addEventListener("click", () => showTab(b.dataset.tab));
    }
    $("ds-pick").addEventListener("change", (e) => showTab(state.tab, e.target.value));
    for (const b of document.querySelectorAll("#level button")) {
      b.addEventListener("click", () => setLevel(b.dataset.level));
    }
    for (const b of document.querySelectorAll("#palette button")) {
      b.addEventListener("click", () => setPalette(b.dataset.palette));
    }
    $("ctx-open").addEventListener("click", () => openContext(false));
    $("ctx-close").addEventListener("click", () => $("ctx-dialog").close());
    $("ctx-skip").addEventListener("click", () => $("ctx-dialog").close());
    $("ctx-form").addEventListener("submit", (e) => { e.preventDefault(); $("ctx-dialog").close(); saveContext(); });
    $("report").addEventListener("click", () => {
      window.location.href = `/api/sessions/${state.sid}/report`;
    });
    $("print").addEventListener("click", () => {
      window.open(`/api/sessions/${state.sid}/report?print=1`, "_blank");
    });
    $("export-open").addEventListener("click", openExport);
    $("export-close").addEventListener("click", () => $("export-dialog").close());
    $("export-cancel").addEventListener("click", () => $("export-dialog").close());
    $("export-form").addEventListener("submit", (e) => { e.preventDefault(); runExport(); });
    $("export-all").addEventListener("click", () => {
      for (const i of document.querySelectorAll('#export-turns input')) i.checked = true;
    });
    $("export-last").addEventListener("click", () => {
      const all = [...document.querySelectorAll('#export-turns input')];
      all.forEach((i, k) => { i.checked = k === all.length - 1; });
    });
    $("new-chat").addEventListener("click", newChat);
    $("chat-title").addEventListener("click", renameChat);
    $("chat-title").addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && renameChat());
    $("import-open").addEventListener("click", openImport);
    $("import-close").addEventListener("click", () => $("import-dialog").close());

    let depth = 0;                             // dragenter and dragleave fire per child
    const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files");
    window.addEventListener("dragenter", (e) => { if (hasFiles(e)) { depth++; $("overlay").classList.add("show"); } });
    window.addEventListener("dragleave", (e) => { if (hasFiles(e) && --depth <= 0) { depth = 0; $("overlay").classList.remove("show"); } });
    window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
    window.addEventListener("drop", (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth = 0;
      $("overlay").classList.remove("show");
      upload([...e.dataTransfer.files]);
    });
  }

  /* The page can open before the server has finished loading its libraries. Keep
     trying for a while, and say so, instead of failing on the first attempt. */
  async function waitForServer() {
    const note = el("div", { class: "banner", id: "connecting" }, "Connecting to the app");
    const started = Date.now();
    for (let attempt = 0; ; attempt++) {
      try {
        const c = await api("/api/config");
        note.remove();
        return c;
      } catch (e) {
        if (attempt === 2) $("banner").append(note);
        const waited = Math.round((Date.now() - started) / 1000);
        if (waited > 90) { note.remove(); throw new Error("no answer from the server after 90 seconds"); }
        note.textContent = "Connecting to the app (" + waited + "s). It is still loading its libraries; this page will fill in by itself.";
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
  }

  async function start() {
    wire();
    state.config = await waitForServer();
    const c = state.config;
    $("model").textContent = c.live ? c.model : "none";
    $("mode").textContent = c.live ? "Connected to " + c.model : "Offline demo: no API key";
    $("mode").classList.toggle("offline", !c.live);
    $("formats").textContent = c.supported.map((s) => s.slice(1).toUpperCase()).join(", ") +
      ". Up to " + c.max_upload_mb + " MB.";
    if (!c.live) {
      $("banner").append(el("div", { class: "banner", html: markdown(
        "**No API key is configured**, so the app is in offline demo mode: it matches " +
        "keywords and cannot interpret a question. To use the agent, create the file `" +
        c.env_file + "` with the line `ANTHROPIC_API_KEY=your-key` and restart.") }));
    }

    Render.artifactUrl = (file) => `/api/sessions/${state.sid}/artifacts/${encodeURIComponent(file)}`;
    Render.downloadUrl = Render.artifactUrl;

    let palette = "single";
    try { palette = localStorage.getItem("ads-palette") || "single"; } catch (_) { /* blocked */ }
    setPalette(palette, false);

    // Reuse this tab's chat after a reload, if the server still has it.
    const params = new URLSearchParams(window.location.search);
    const saved = params.get("session") || sessionStorage.getItem("ads-session");
    let restored = null;
    if (saved) {
      try { restored = await api("/api/sessions/" + saved); } catch (_) { /* ended */ }
    }
    if (restored) {
      state.sid = restored.id;
      sessionStorage.setItem("ads-session", state.sid);
      state.dashboards = restored.dashboards || {};
      state.profiles = { ...(restored.profiles || {}) };
      state.suggestions = restored.suggestions || [];
      state.title = restored.title || "";
      state.askedContext = true;
      for (const item of restored.transcript) {
        if (item.role === "upload") for (const p of item.datasets) state.profiles[p.name] = state.profiles[p.name] || p;
        hideWelcome();
        $("chat").append(transcriptItem(item));
      }
      showUsage(restored.usage);
      showContext(restored.context);
      if (restored.style && restored.style.palette) setPalette(restored.style.palette, false);
      else if (state.palette !== "single") setPalette(state.palette, true);
      showDatasets(restored.datasets);
      follow(true);
    } else {
      state.sid = (await post("/api/sessions")).id;
      sessionStorage.setItem("ads-session", state.sid);
      if (state.palette !== "single") setPalette(state.palette, true);
    }
    if (params.get("session") && !params.get("tab")) history.replaceState(null, "", window.location.pathname);
    await refreshChats();
    $("chat-title").textContent = state.title || "New chat";

    const samples = await api("/api/samples");
    $("samples").replaceChildren(...(samples.length
      ? samples.map((s) => el("button", { class: "sample", onclick: () => loadSample(s.name) },
          s.name, el("span", {}, s.size_kb + " KB")))
      : [el("div", { class: "empty" }, "Run scripts/make_sample_data.py to create samples.")]));

    if (!restored && params.get("sample")) await loadSample(params.get("sample"));
    if (!restored && params.get("q")) { $("ctx-dialog").close(); await send(params.get("q")); }
    if (params.get("tab")) { $("ctx-dialog").close(); showTab(params.get("tab"), params.get("dataset")); }
    $("input").focus();
  }

  start().catch((e) => {
    $("banner").append(el("div", { class: "banner" },
      "The app could not start: " + e.message + ". Look at the terminal where it was started; " +
      "if it shows an error, run  python -m app --check  there, then reload this page."));
  });
})();
