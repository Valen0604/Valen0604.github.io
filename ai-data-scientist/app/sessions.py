"""
Chat sessions. One per chat in the sidebar.

A session owns a workspace folder, an analysis worker, the conversation as the model sees
it (`messages`) and the conversation as the user sees it (`transcript`). Its datasets live
in its own worker, so two chats never see each other's data unless the user brings a
dataset across on purpose (POST /api/sessions/{id}/datasets/import).

Sessions live in memory. Restarting the server ends them; the files stay on disk under
workspace/<session id>/ until you delete them.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .agent.tools import Toolbox
from .analytics.engine import Engine
from .config import Settings


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    requests: int = 0
    cost_usd: float = 0.0

    def add(self, usage, settings: Settings) -> float:
        """Add one API response's usage. Returns what that response cost."""
        i = int(getattr(usage, "input_tokens", 0) or 0)
        o = int(getattr(usage, "output_tokens", 0) or 0)
        w = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        r = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cost = (i * settings.price_input + o * settings.price_output
                + w * settings.price_cache_write + r * settings.price_cache_read) / 1e6
        self.input_tokens += i
        self.output_tokens += o
        self.cache_write_tokens += w
        self.cache_read_tokens += r
        self.requests += 1
        self.cost_usd += cost
        return cost

    def public(self) -> dict:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cache_write_tokens": self.cache_write_tokens,
                "cache_read_tokens": self.cache_read_tokens, "requests": self.requests,
                "cost_usd": round(self.cost_usd, 4)}


@dataclass
class Session:
    id: str
    workspace: Path
    engine: Engine
    toolbox: Toolbox
    created: float = field(default_factory=time.time)
    messages: list = field(default_factory=list)      # what the model sees
    transcript: list = field(default_factory=list)    # what the user sees
    pending_briefs: list[str] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    cancel: threading.Event = field(default_factory=threading.Event)
    busy: threading.Lock = field(default_factory=threading.Lock)
    # What the user told us about the data and themselves (see /api/sessions/{id}/context).
    # `context` is the latest version; `pending_context` is True until the model has seen it.
    context: dict = field(default_factory=dict)
    pending_context: bool = False
    level: str = "standard"                           # brief | standard | technical
    dashboards: dict = field(default_factory=dict)    # dataset name -> first-look dashboard
    profiles: dict = field(default_factory=dict)      # dataset name -> latest profile
    # The worker's version of each dataset when its dashboard was computed. A dataset
    # whose version moved on (code changed it, or created it) gets a fresh dashboard.
    dashboard_versions: dict = field(default_factory=dict)
    relations: dict | None = None                     # how the datasets relate (cached)
    relations_versions: dict = field(default_factory=dict)
    # What the model suggested about the relationships, kept while no dataset changes.
    relations_ai: dict | None = None
    relations_ai_versions: dict = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)  # follow-up questions offered last
    title: str = ""                                   # shown in the chat list; renameable
    style: dict = field(default_factory=lambda: {"palette": "single"})

    def take_briefs(self) -> list[str]:
        briefs, self.pending_briefs = self.pending_briefs, []
        return briefs

    def take_context(self) -> dict | None:
        """The user's context, once, the first time it is sent after it changed."""
        if not self.pending_context:
            return None
        self.pending_context = False
        return self.context or None


class SessionStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        sid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        workspace = self.settings.workspace / sid
        for sub in ("uploads", "artifacts"):
            (workspace / sub).mkdir(parents=True, exist_ok=True)
        engine = Engine(workspace, default_timeout_s=self.settings.code_timeout_s)
        session = Session(id=sid, workspace=workspace, engine=engine,
                          toolbox=Toolbox(engine, self.settings))

        def datasets_for_report() -> list[dict]:
            try:
                return [{"name": d["name"], "rows": d["rows"], "columns_count": d["columns_count"]}
                        for d in engine.call("list")["datasets"]]
            except Exception:
                return []
        session.toolbox.datasets_for_report = datasets_for_report
        with self._lock:
            self._sessions[sid] = session
        return session

    def get(self, sid: str) -> Session | None:
        return self._sessions.get(sid)

    def list(self) -> list[Session]:
        """Every open chat, newest first."""
        with self._lock:
            return sorted(self._sessions.values(), key=lambda s: -s.created)

    def delete(self, sid: str) -> bool:
        """Close a chat. Its files stay on disk under workspace/<id>/."""
        with self._lock:
            session = self._sessions.pop(sid, None)
        if session is None:
            return False
        session.engine.close()
        return True

    def close_all(self) -> None:
        with self._lock:
            sessions, self._sessions = list(self._sessions.values()), {}
        for s in sessions:
            s.engine.close()
