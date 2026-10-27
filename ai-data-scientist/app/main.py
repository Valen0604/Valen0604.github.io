"""
The web server: a thin layer between the browser and the agent.

    GET  /                                     the chat page
    GET  /api/config                           model name, live or offline
    GET  /api/samples                          sample datasets that can be loaded
    GET  /api/sessions                         the open chats
    POST /api/sessions                         start a chat
    GET  /api/sessions/{id}                    datasets, transcript, usage
    PATCH /api/sessions/{id}                   rename a chat
    DELETE /api/sessions/{id}                  close a chat
    POST /api/sessions/{id}/upload             upload files
    POST /api/sessions/{id}/sample             load a sample dataset
    POST /api/sessions/{id}/datasets/import    bring a dataset over from another chat
    GET  /api/sessions/{id}/datasets/{name}/download   the dataset as it is now (csv, xlsx, parquet)
    DELETE /api/sessions/{id}/datasets/{name}  remove a dataset
    POST /api/sessions/{id}/chat               send a message; the reply is streamed
    POST /api/sessions/{id}/stop               stop the reply in progress
    PUT  /api/sessions/{id}/context            what the user knows about the data; detail level
    PUT  /api/sessions/{id}/style              chart colours
    GET  /api/sessions/{id}/dashboard/{name}   the first-look dashboard of a dataset
    POST /api/sessions/{id}/dashboard/{name}   recompute it after the data changed
    GET  /api/sessions/{id}/relations          how the datasets relate (POST recomputes)
    POST /api/sessions/{id}/relations/suggest  ask the model for relationship ideas
    GET  /api/sessions/{id}/artifacts/{file}   a chart, CSV, report or model file
    GET  /api/sessions/{id}/report             the conversation as one HTML file
                                               (?print=1 opens the print dialog)
    POST /api/sessions/{id}/export             chosen answers as a PDF or a slide deck
"""
from __future__ import annotations

import json
import queue
import re
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
import anthropic

from .agent import relations_ai
from .agent.loop import Agent, explain
from .agent.offline import OfflineAgent
from .analytics.engine import EngineError
from .analytics.loading import SUPPORTED
from .analytics.worker import EXPORT_FORMATS
from .config import ENV_FILE, ROOT, SETTINGS
from .export import document, pdf, slides
from .report import build_report
from .sessions import Session, SessionStore

STATIC = Path(__file__).parent / "static"
SAMPLES = ROOT / "data" / "sample"
HEARTBEAT_S = 15
MEDIA = {"csv": "text/csv", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         "parquet": "application/vnd.apache.parquet", "pdf": "application/pdf",
         "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}


def _asset_version() -> str:
    """A short hash of the static files, put on their URLs so a browser that cached the
    old stylesheet or script fetches the new one after an update."""
    import hashlib
    h = hashlib.md5()
    for f in sorted(STATIC.iterdir()):
        if f.suffix in (".css", ".js"):
            h.update(f.read_bytes())
    return h.hexdigest()[:10]


ASSET_VERSION = _asset_version()

store = SessionStore(SETTINGS)
agent = Agent(SETTINGS) if SETTINGS.live else OfflineAgent(SETTINGS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    store.close_all()


app = FastAPI(title="AI Data Scientist", version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class ChatRequest(BaseModel):
    message: str
    level: str | None = None       # brief | standard | technical; sticks until changed


class SampleRequest(BaseModel):
    name: str


class ContextRequest(BaseModel):
    description: str = ""
    goal: str = ""
    constraints: str = ""
    notes: str = ""
    level: str | None = None


class RenameRequest(BaseModel):
    title: str


class StyleRequest(BaseModel):
    palette: str                   # single | varied


class ImportRequest(BaseModel):
    from_session: str
    dataset: str


class ExportRequest(BaseModel):
    format: str = "pdf"            # pdf | pptx
    turns: list[int] | None = None # 1-based question numbers; None means all
    with_code: bool = False
    with_overview: bool = False
    title: str | None = None


LEVELS = ("brief", "standard", "technical")
PALETTES = ("single", "varied")


def _session(sid: str) -> Session:
    session = store.get(sid)
    if session is None:
        raise HTTPException(404, "This session has ended. Reload the page to start a new one.")
    return session


def _safe_name(name: str) -> str:
    """A file name with nothing that could climb out of the folder it is saved in."""
    name = Path(name or "upload").name
    name = re.sub(r"[^0-9A-Za-z._ ()-]+", "_", name).strip(" .")
    return name or "upload"


def _datasets(session: Session) -> list[dict]:
    try:
        return session.engine.call("list")["datasets"]
    except EngineError:
        return []


def _register(session: Session, path: Path, original: str, note: str | None = None) -> list[dict]:
    """Load a file into the session. Returns the datasets it produced."""
    loaded = session.engine.call("load_file", timeout_s=180, path=str(path),
                                 original_name=original)["datasets"]
    for d in loaded:
        session.pending_briefs.append((note + "\n" if note else "") + d["brief"])
        session.dashboards[d["name"]] = d["dashboard"]
        session.profiles[d["name"]] = d["profile"]
        session.dashboard_versions[d["name"]] = d.get("version", 1)
    session.transcript.append({"role": "upload", "file": original, "time": time.time(),
                               "datasets": [d["profile"] for d in loaded]})
    _relations(session, brief=True)
    return [d["profile"] for d in loaded]


def _refresh(session: Session) -> tuple[list[dict], dict]:
    """
    Dashboards for datasets that changed since theirs was computed, including datasets
    that analysis code created. Returns the dataset list and what was recomputed.
    """
    listing = _datasets(session)
    refreshed = {}
    for d in listing:
        if session.dashboard_versions.get(d["name"]) == d["version"]:
            continue
        try:
            r = session.engine.call("dashboard", timeout_s=180, dataset=d["name"])
        except EngineError:
            continue
        session.dashboards[d["name"]] = r["dashboard"]
        session.profiles[d["name"]] = r["profile"]
        session.dashboard_versions[d["name"]] = r["version"]
        refreshed[d["name"]] = {"dashboard": r["dashboard"], "profile": r["profile"]}
    names = {d["name"] for d in listing}
    for gone in set(session.dashboards) - names:
        for box in (session.dashboards, session.profiles, session.dashboard_versions):
            box.pop(gone, None)
    return listing, refreshed


def _relations(session: Session, force: bool = False, brief: bool = False) -> dict | None:
    """How the datasets relate, recomputed only when a dataset changed."""
    listing = _datasets(session)
    versions = {d["name"]: d["version"] for d in listing}
    if not force and session.relations is not None and session.relations_versions == versions:
        return session.relations
    if len(listing) < 2:
        session.relations, session.relations_versions = None, versions
        return None
    try:
        r = session.engine.call("relations", timeout_s=120)
    except EngineError:
        return session.relations
    session.relations, session.relations_versions = r["relations"], versions
    if brief and r["relations"].get("summary"):
        session.pending_briefs.append(
            "How the loaded datasets relate, computed by the application from shared column "
            "names and values (use these keys when the user asks to join or compare them):\n"
            + "\n".join("- " + line for line in r["relations"]["summary"]))
    return session.relations


def _relations_with_ai(session: Session) -> dict | None:
    """The map, with the model's suggestions attached while they are still current."""
    rel = session.relations
    if rel is None:
        return None
    if session.relations_ai and session.relations_ai_versions == session.relations_versions:
        return {**rel, "ai": session.relations_ai}
    return rel


def _public_context(session: Session) -> dict:
    return {**{k: session.context.get(k, "") for k in
               ("description", "goal", "constraints", "notes")},
            "level": session.level, "given": bool(any(session.context.values()))}


def _public_session(s: Session) -> dict:
    datasets = _datasets(s)
    return {"id": s.id, "title": s.title or _default_title(s), "created": s.created,
            "datasets": [d["name"] for d in datasets], "busy": s.busy.locked(),
            "questions": sum(1 for t in s.transcript if t["role"] == "user")}


def _default_title(s: Session) -> str:
    questions = [t["text"] for t in s.transcript if t["role"] == "user"]
    # The first question names the chat, unless it was a block of code.
    first = next((q for q in questions if not q.lstrip().startswith("```")), "")
    first = re.sub(r"\s+", " ", first).strip()
    if first:
        return (first[:57] + "…") if len(first) > 60 else first
    uploads = [t["file"] for t in s.transcript if t["role"] == "upload"]
    return uploads[0] if uploads else "New chat"


# ------------------------------------------------------------------------------- pages
@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace('/static/styles.css"', f'/static/styles.css?v={ASSET_VERSION}"')
    html = html.replace('.js"></script>', f'.js?v={ASSET_VERSION}"></script>')
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


@app.middleware("http")
async def _no_stale_assets(request, call_next):
    """Static files are revalidated on every load, so an update never shows half-applied."""
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/config")
def config() -> dict:
    return {**SETTINGS.public(), "version": __version__,
            "supported": sorted(SUPPORTED), "palettes": list(PALETTES)}


@app.get("/api/samples")
def samples() -> list[dict]:
    if not SAMPLES.exists():
        return []
    return [{"name": p.name, "size_kb": round(p.stat().st_size / 1024)}
            for p in sorted(SAMPLES.iterdir()) if p.suffix.lower() in SUPPORTED]


# ---------------------------------------------------------------------------- sessions
@app.get("/api/sessions")
def list_sessions() -> list[dict]:
    return [_public_session(s) for s in store.list()]


@app.post("/api/sessions")
def create_session() -> dict:
    return {"id": store.create().id}


@app.get("/api/sessions/{sid}")
def get_session(sid: str) -> dict:
    s = _session(sid)
    return {"id": s.id, "title": s.title or _default_title(s), "datasets": _datasets(s),
            "transcript": s.transcript, "usage": s.usage.public(), "busy": s.busy.locked(),
            "context": _public_context(s), "dashboards": s.dashboards,
            "profiles": s.profiles, "suggestions": s.suggestions, "style": s.style}


@app.patch("/api/sessions/{sid}")
def rename_session(sid: str, req: RenameRequest) -> dict:
    s = _session(sid)
    s.title = req.title.strip()[:80]
    return _public_session(s)


@app.delete("/api/sessions/{sid}")
def delete_session(sid: str) -> dict:
    s = _session(sid)
    if s.busy.locked():
        raise HTTPException(409, "A reply is still in progress. Stop it first.")
    store.delete(sid)
    return {"closed": sid}


@app.put("/api/sessions/{sid}/context")
def set_context(sid: str, req: ContextRequest) -> dict:
    """What the user knows about the data, and how much detail they want."""
    s = _session(sid)
    fields = {k: (getattr(req, k) or "").strip()[:4000]
              for k in ("description", "goal", "constraints", "notes")}
    if fields != s.context:
        s.context = fields
        s.pending_context = True                 # the model sees it with the next message
    if req.level:
        if req.level not in LEVELS:
            raise HTTPException(400, f"level must be one of {list(LEVELS)}.")
        s.level = req.level
    return _public_context(s)


@app.put("/api/sessions/{sid}/style")
def set_style(sid: str, req: StyleRequest) -> dict:
    """Chart colours for charts the agent draws: one hue, or a varied palette."""
    s = _session(sid)
    if req.palette not in PALETTES:
        raise HTTPException(400, f"palette must be one of {list(PALETTES)}.")
    s.style = {"palette": req.palette}
    s.toolbox.style = s.style
    return s.style


@app.get("/api/sessions/{sid}/dashboard/{name}")
def dashboard(sid: str, name: str) -> dict:
    s = _session(sid)
    if name not in s.dashboards:
        raise HTTPException(404, "No dashboard for that dataset.")
    return s.dashboards[name]


@app.post("/api/sessions/{sid}/dashboard/{name}")
def rebuild_dashboard(sid: str, name: str) -> dict:
    """Recompute the dashboard, for a dataset that analysis code has changed."""
    s = _session(sid)
    if s.busy.locked():
        raise HTTPException(409, "A reply is still in progress. Wait for it or stop it.")
    try:
        d = s.engine.call("dashboard", timeout_s=180, dataset=name)
    except EngineError as e:
        raise HTTPException(400, str(e)) from e
    s.dashboards[d["name"]] = d["dashboard"]
    s.profiles[d["name"]] = d["profile"]
    s.dashboard_versions[d["name"]] = d["version"]
    return d["dashboard"]


@app.get("/api/sessions/{sid}/relations")
def relations(sid: str) -> dict:
    """How the loaded datasets relate: join keys, shared columns, how well values match."""
    s = _session(sid)
    rel = _relations(s)
    if rel is None:
        return {"datasets": [{"name": d["name"], "rows": d["rows"], "columns_count": d["columns_count"]}
                             for d in _datasets(s)],
                "edges": [], "dimensions": [], "unlinked": [], "merges": [],
                "summary": ["Load at least two datasets to see how they relate."]}
    return _relations_with_ai(s)


@app.post("/api/sessions/{sid}/relations")
def rebuild_relations(sid: str) -> dict:
    s = _session(sid)
    if s.busy.locked():
        raise HTTPException(409, "A reply is still in progress. Wait for it or stop it.")
    _relations(s, force=True)
    return relations(sid)


@app.post("/api/sessions/{sid}/relations/suggest")
def suggest_relations(sid: str) -> dict:
    """
    Ask the model which relationships it would look for, from the column names, types and
    example values plus what the value check found. One request, no tools, apart from the
    chat. Needs an API key; the result stays on the map until a dataset changes.
    """
    s = _session(sid)
    if not SETTINGS.live:
        raise HTTPException(400, "Relationship ideas need the model. Add an API key to "
                                 f"{ENV_FILE.name} and restart.")
    if s.busy.locked():
        raise HTTPException(409, "A reply is still in progress. Wait for it or stop it.")
    rel = _relations(s)
    if rel is None:
        raise HTTPException(400, "Load at least two datasets first.")
    try:
        result, usage = relations_ai.suggest(agent.client, SETTINGS, rel, s.context)
    except anthropic.APIError as e:
        raise HTTPException(502, explain(e, SETTINGS)) from e
    except relations_ai.BadReply as e:
        raise HTTPException(502, f"{e} Try again.") from e
    result["cost_usd"] = round(s.usage.add(usage, SETTINGS), 4)
    s.relations_ai, s.relations_ai_versions = result, dict(s.relations_versions)
    s.pending_briefs.append(relations_ai.brief(result))
    return {**_relations_with_ai(s), "usage": s.usage.public()}


@app.post("/api/sessions/{sid}/upload")
async def upload(sid: str, files: list[UploadFile] = File(...)) -> dict:
    s = _session(sid)
    limit = SETTINGS.max_upload_mb * 1024 * 1024
    loaded, errors = [], []
    for f in files:
        name = _safe_name(f.filename)
        if Path(name).suffix.lower() not in SUPPORTED:
            errors.append({"file": name, "error": f"{Path(name).suffix or 'This'} files are "
                           f"not supported. Supported: {', '.join(sorted(SUPPORTED))}."})
            continue
        target = s.workspace / "uploads" / name
        if target.exists():
            target = target.with_name(f"{target.stem}_{int(time.time())}{target.suffix}")
        size = 0
        with target.open("wb") as out:
            while chunk := await f.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    break
                out.write(chunk)
        if size > limit:
            target.unlink(missing_ok=True)
            errors.append({"file": name, "error": f"Larger than the {SETTINGS.max_upload_mb} "
                           "MB limit. Raise ADS_MAX_UPLOAD_MB in .env, or upload a sample."})
            continue
        try:
            loaded += _register(s, target, name)
        except EngineError as e:
            target.unlink(missing_ok=True)
            errors.append({"file": name, "error": str(e)})
    return _loaded(s, loaded, errors)


def _loaded(s: Session, loaded: list[dict], errors: list[dict]) -> dict:
    return {"loaded": loaded, "errors": errors, "datasets": _datasets(s),
            "dashboards": {p["name"]: s.dashboards[p["name"]] for p in loaded
                           if p["name"] in s.dashboards},
            "relations": s.relations}


@app.post("/api/sessions/{sid}/sample")
def load_sample(sid: str, req: SampleRequest) -> dict:
    s = _session(sid)
    source = SAMPLES / _safe_name(req.name)
    if not source.is_file():
        raise HTTPException(404, "No such sample.")
    target = s.workspace / "uploads" / source.name
    target.write_bytes(source.read_bytes())
    try:
        loaded = _register(s, target, source.name)
    except EngineError as e:
        raise HTTPException(400, str(e)) from e
    return _loaded(s, loaded, [])


@app.post("/api/sessions/{sid}/datasets/import")
def import_dataset(sid: str, req: ImportRequest) -> dict:
    """
    Bring a dataset from another chat into this one, as it is there now. This is the only
    way data crosses between chats, and the user has to ask for it.
    """
    s = _session(sid)
    if req.from_session == sid:
        raise HTTPException(400, "That dataset is already in this chat.")
    other = store.get(req.from_session)
    if other is None:
        raise HTTPException(404, "That chat has ended.")
    if other.busy.locked():
        raise HTTPException(409, "The other chat is still replying. Wait for it to finish.")
    try:
        r = other.engine.call("export", dataset=req.dataset, format="parquet")
    except EngineError as e:
        raise HTTPException(400, str(e)) from e
    source = other.workspace / "artifacts" / r["download"]
    target = s.workspace / "uploads" / f"{req.dataset}.parquet"
    if target.exists():
        target = target.with_name(f"{target.stem}_{int(time.time())}{target.suffix}")
    target.write_bytes(source.read_bytes())
    note = (f'The user brought the dataset "{req.dataset}" over from another chat, where it '
            f'was {r["kind"]}. It is now part of this chat.')
    try:
        loaded = _register(s, target, target.name, note=note)
    except EngineError as e:
        target.unlink(missing_ok=True)
        raise HTTPException(400, str(e)) from e
    return _loaded(s, loaded, [])


@app.get("/api/sessions/{sid}/datasets/{name}/download")
def download_dataset(sid: str, name: str, format: str = "csv") -> FileResponse:
    """The dataset as it is now, including changes made and datasets the agent created."""
    s = _session(sid)
    if format not in EXPORT_FORMATS:
        raise HTTPException(400, f"format must be one of {list(EXPORT_FORMATS)}.")
    if s.busy.locked():
        raise HTTPException(409, "A reply is still in progress. Wait for it or stop it.")
    try:
        r = s.engine.call("export", dataset=name, format=format)
    except EngineError as e:
        raise HTTPException(400 if e.kind == "request" else 500, str(e)) from e
    path = s.workspace / "artifacts" / r["download"]
    return FileResponse(path, filename=r["download"], media_type=MEDIA.get(format))


@app.delete("/api/sessions/{sid}/datasets/{name}")
def remove_dataset(sid: str, name: str) -> dict:
    s = _session(sid)
    try:
        s.engine.call("remove", dataset=name)
    except EngineError as e:
        raise HTTPException(400, str(e)) from e
    s.pending_briefs.append(f'The user removed the dataset "{name}".')
    for box in (s.dashboards, s.profiles, s.dashboard_versions):
        box.pop(name, None)
    _relations(s)
    return {"datasets": _datasets(s), "relations": s.relations}


@app.get("/api/sessions/{sid}/artifacts/{file}")
def artifact(sid: str, file: str) -> FileResponse:
    s = _session(sid)
    for folder in ("artifacts", "models"):
        root = (s.workspace / folder).resolve()
        path = (root / Path(file).name).resolve()
        if path.is_relative_to(root) and path.is_file():
            return FileResponse(path, filename=path.name if path.suffix != ".png" else None)
    raise HTTPException(404, "File not found.")


@app.get("/api/sessions/{sid}/report", response_class=HTMLResponse)
def report(sid: str, print: int = 0, code: int = 1) -> HTMLResponse:
    """
    The report. As a download by default; with ?print=1 it opens in the tab and shows the
    print dialog, which is how it becomes a PDF (every browser has "Save as PDF" there).
    ?code=0 leaves the code blocks out, for readers who only want the findings.
    """
    s = _session(sid)
    html = build_report(s, SETTINGS, STATIC, print_mode=bool(print), with_code=bool(code))
    headers = {} if print else {
        "Content-Disposition": f'attachment; filename="analysis-{s.id}.html"'}
    return HTMLResponse(html, headers=headers)


@app.post("/api/sessions/{sid}/export")
def export(sid: str, req: ExportRequest) -> Response:
    """The chosen answers as a PDF or a slide deck: the report, without the chat around it."""
    s = _session(sid)
    if req.format not in ("pdf", "pptx"):
        raise HTTPException(400, "format must be pdf or pptx.")
    questions = sum(1 for t in s.transcript if t["role"] == "user")
    if req.turns is not None and any(not 1 <= t <= questions for t in req.turns):
        raise HTTPException(400, f"turns must be between 1 and {questions}.")
    if not questions and not req.with_overview:
        raise HTTPException(400, "There is no answer to export yet. Ask a question first, or "
                                 "include the first look.")
    if req.with_overview and s.relations is None:
        _relations(s)
    doc = document.from_session(s, req.turns, with_code=req.with_code,
                                with_overview=req.with_overview, title=req.title,
                                model=SETTINGS.model if SETTINGS.live else "")
    data = pdf.render(doc) if req.format == "pdf" else slides.render(doc)
    name = re.sub(r"[^0-9A-Za-z]+", "-", doc["title"]).strip("-").lower()[:40] or "report"
    return Response(data, media_type=MEDIA[req.format], headers={
        "Content-Disposition": f'attachment; filename="{name}.{req.format}"'})


# -------------------------------------------------------------------------------- chat
@app.post("/api/sessions/{sid}/stop")
def stop(sid: str) -> dict:
    _session(sid).cancel.set()
    return {"stopping": True}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@app.post("/api/sessions/{sid}/chat")
def chat(sid: str, req: ChatRequest) -> StreamingResponse:
    s = _session(sid)
    message = req.message.strip()
    if not message:
        raise HTTPException(400, "The message is empty.")
    if req.level and req.level not in LEVELS:
        raise HTTPException(400, f"level must be one of {list(LEVELS)}.")
    if not s.busy.acquire(blocking=False):
        raise HTTPException(409, "A reply is still in progress. Wait for it or stop it.")
    if req.level:
        s.level = req.level

    events: queue.Queue = queue.Queue()
    s.cancel.clear()
    s.transcript.append({"role": "user", "text": message, "time": time.time()})

    def work() -> None:
        parts: list[dict] = []
        try:
            parts = agent.run_turn(s, message, lambda kind, data: events.put((kind, data)))
        except Exception as e:                       # never leave the browser waiting
            events.put(("notice", {"level": "error",
                                   "text": f"Internal error: {type(e).__name__}: {e}"}))
            parts = [{"type": "notice", "level": "error", "text": f"Internal error: {e}"}]
        finally:
            s.transcript.append({"role": "assistant", "parts": parts, "time": time.time()})
            try:
                events.put(("status", {"text": "Updating the dashboards"}))
                datasets, refreshed = _refresh(s)
            except Exception:                        # a dashboard must never lose a reply
                datasets, refreshed = _datasets(s), {}
            events.put(("done", {"usage": s.usage.public(), "datasets": datasets,
                                 "refreshed": refreshed,
                                 "title": s.title or _default_title(s)}))
            events.put(None)
            s.busy.release()

    threading.Thread(target=work, daemon=True, name=f"turn-{sid}").start()

    def stream():
        while True:
            try:
                item = events.get(timeout=HEARTBEAT_S)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if item is None:
                return
            yield _sse(*item)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
