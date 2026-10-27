"""
The web server's handle on a worker process.

One Engine per chat session. It starts the worker, sends it one request at a time, and
enforces a time limit. If the worker runs too long or dies, the Engine kills it, starts a
fresh one, and reloads the datasets from disk.
"""
from __future__ import annotations

import multiprocessing as mp
import threading
from pathlib import Path

from .worker import worker_main

START_TIMEOUT_S = 60


class EngineError(Exception):
    """
    An analysis request failed.

    kind = "request":  the request itself was wrong (no such column, too few rows). The
                       message says how to fix it, and the model can try again.
    kind = "timeout":  the work took too long and the worker was restarted.
    kind = "internal": a bug or a crash.
    """

    def __init__(self, message: str, kind: str = "internal", detail: str | None = None):
        super().__init__(message)
        self.kind = kind
        self.detail = detail


class Engine:
    def __init__(self, workspace: Path, default_timeout_s: int = 90):
        self.workspace = Path(workspace)
        self.default_timeout_s = default_timeout_s
        self.manifest: list[dict] = []
        self.restarts = 0
        self._lock = threading.Lock()
        self._ctx = mp.get_context("spawn")
        self._process = None
        self._conn = None

    # --------------------------------------------------------------------- lifecycle
    def _start(self) -> None:
        parent, child = self._ctx.Pipe()
        process = self._ctx.Process(target=worker_main, args=(child, str(self.workspace)),
                                    daemon=True, name=f"analysis-{self.workspace.name}")
        process.start()
        child.close()
        if not parent.poll(START_TIMEOUT_S):
            process.kill()
            raise EngineError("The analysis worker did not start.")
        parent.recv()
        self._process, self._conn = process, parent

    def _stop(self) -> None:
        if self._conn is not None:
            try:
                self._conn.send({"op": "shutdown"})
            except Exception:
                pass
            try:
                self._conn.close()
            except Exception:
                pass
        if self._process is not None:
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.kill()
                self._process.join(timeout=5)
        self._process, self._conn = None, None

    def _restart(self) -> list[str]:
        """Kill the worker, start another, reload the data. Returns what could not reload."""
        self._stop()
        self.restarts += 1
        self._start()
        if not self.manifest:
            return []
        self._conn.send({"op": "restore", "args": {"manifest": self.manifest}})
        if not self._conn.poll(START_TIMEOUT_S * 3):
            return [m["name"] for m in self.manifest]
        reply = self._conn.recv()
        if reply.get("ok"):
            self.manifest = reply["result"].get("manifest", self.manifest)
            return [f["name"] for f in reply["result"].get("failed", [])]
        return [m["name"] for m in self.manifest]

    def close(self) -> None:
        with self._lock:
            self._stop()

    @property
    def alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    # -------------------------------------------------------------------------- calls
    def call(self, op: str, timeout_s: int | None = None, **args) -> dict:
        """Run one operation in the worker and return its result, or raise EngineError."""
        timeout = timeout_s or self.default_timeout_s
        with self._lock:
            if not self.alive:
                self._start() if self._process is None else self._restart()
            try:
                self._conn.send({"op": op, "args": args})
                if not self._conn.poll(timeout):
                    lost = self._restart()
                    message = (f"The analysis ran for more than {timeout} seconds and was "
                               "stopped. Variables from earlier code are gone; datasets were "
                               "reloaded from disk.")
                    if lost:
                        message += f" These could not be reloaded: {lost}."
                    message += (" Try a smaller sample, fewer columns, or a simpler method.")
                    raise EngineError(message, kind="timeout")
                reply = self._conn.recv()
            except (EOFError, BrokenPipeError, ConnectionResetError, OSError) as e:
                lost = self._restart()
                message = ("The analysis process stopped unexpectedly, most likely because "
                           "it ran out of memory. It was restarted and datasets were "
                           "reloaded from disk.")
                if lost:
                    message += f" These could not be reloaded: {lost}."
                raise EngineError(message, kind="internal", detail=str(e)) from e

        if not reply.get("ok"):
            raise EngineError(reply.get("error", "Unknown error"),
                              kind=reply.get("kind", "internal"),
                              detail=reply.get("traceback"))
        result = reply["result"]
        if isinstance(result, dict) and "manifest" in result:
            self.manifest = result.pop("manifest")
        return result
