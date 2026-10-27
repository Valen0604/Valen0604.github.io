"""
The agent loop.

One user message starts one "turn". Inside a turn:

    1. send the conversation to Claude, with the tool definitions
    2. stream the reply to the browser as it is written
    3. if Claude asked for tools, run them and send the results back
    4. repeat from 1 until Claude answers without asking for a tool

This is written as an explicit loop on purpose, without the SDK's tool-runner helper. The
loop is the core of the system, and a team that is going to extend it should be able to
read every step. It follows the manual-loop pattern from the Anthropic SDK documentation.
"""
from __future__ import annotations

import json
import re
import threading
from typing import Callable

import anthropic

from ..config import Settings
from ..sessions import Session
from . import prompts
from .tools import TOOLS, ToolOutcome, tool_result_block

Emit = Callable[[str, dict], None]

MAX_JSON_RETRIES = 2
LIMIT_NOTICE = ("[Notice from the application: the limit on tool calls for one message has "
                "been reached. Answer now with what you have, and say plainly what is left "
                "undone.]")


class Recorder:
    """
    Sends each event to the browser, and keeps a copy for the transcript.

    The transcript lets a reloaded page and the exported report show the same thing the
    user saw live.
    """

    def __init__(self, emit: Emit):
        self._emit = emit
        self.parts: list[dict] = []

    def _tail(self, kind: str) -> dict:
        if not self.parts or self.parts[-1]["type"] != kind:
            self.parts.append({"type": kind, "text": ""})
        return self.parts[-1]

    def text(self, delta: str) -> None:
        self._tail("text")["text"] += delta
        self._emit("text_delta", {"text": delta})

    def thinking(self, delta: str) -> None:
        self._tail("thinking")["text"] += delta
        self._emit("thinking_delta", {"text": delta})

    def tool_start(self, tool_id: str, name: str) -> None:
        self.parts.append({"type": "tool", "id": tool_id, "name": name, "input": None,
                           "status": "writing", "cards": [], "summary": ""})
        self._emit("tool_start", {"id": tool_id, "name": name})

    def _tool(self, tool_id: str, name: str) -> dict:
        for p in reversed(self.parts):
            if p["type"] == "tool" and p["id"] == tool_id:
                return p
        self.tool_start(tool_id, name)
        return self.parts[-1]

    def tool_running(self, tool_id: str, name: str, args: dict) -> None:
        part = self._tool(tool_id, name)
        part.update(input=args, status="running")
        self._emit("tool_running", {"id": tool_id, "name": name, "input": args})

    def tool_done(self, tool_id: str, name: str, outcome: ToolOutcome) -> None:
        part = self._tool(tool_id, name)
        part.update(status="error" if outcome.is_error else "done", cards=outcome.cards,
                    summary=outcome.summary, error=outcome.text if outcome.is_error else None)
        self._emit("tool_done", {"id": tool_id, "name": name, "ok": not outcome.is_error,
                                 "summary": outcome.summary, "cards": outcome.cards,
                                 "error": part["error"]})

    def notice(self, message: str, level: str = "info") -> None:
        self.parts.append({"type": "notice", "level": level, "text": message})
        self._emit("notice", {"level": level, "text": message})

    def status(self, text: str) -> None:
        self._emit("status", {"text": text})

    def usage(self, payload: dict) -> None:
        self._emit("usage", payload)

    def suggestions(self, questions: list[str]) -> None:
        self._emit("suggestions", {"questions": questions})


FOLLOWUP_RE = re.compile(r"```" + prompts.FOLLOWUP_LANG + r"[ \t]*\n(.*?)```\s*$", re.S)


def split_followups(text: str) -> tuple[str, list[str]]:
    """
    Take the follow-up block off the end of an answer.

    Returns the answer without the block, and the questions in it. A block that is not a
    JSON array of strings is treated as part of the text, so a malformed one shows rather
    than vanishes.
    """
    m = FOLLOWUP_RE.search(text)
    if not m:
        return text, []
    try:
        items = json.loads(m.group(1))
    except ValueError:
        return text, []
    if not isinstance(items, list) or not all(isinstance(q, str) for q in items):
        return text, []
    questions = [q.strip() for q in items if q.strip()][:4]
    return text[:m.start()].rstrip() + "\n", questions


def explain(error: Exception, settings: Settings) -> str:
    """Turn an API error into something the user can act on. Most specific first."""
    if isinstance(error, anthropic.AuthenticationError):
        return ("The API key was rejected. Check ANTHROPIC_API_KEY in the .env file, then "
                "restart the app.")
    if isinstance(error, anthropic.PermissionDeniedError):
        return (f"This API key is not allowed to use {settings.model}. Check the key's "
                "workspace in the Anthropic Console.")
    if isinstance(error, anthropic.NotFoundError):
        return (f'The model "{settings.model}" was not found. Check ADS_MODEL in .env.')
    if isinstance(error, anthropic.RateLimitError):
        wait = error.response.headers.get("retry-after", "a few")
        return f"Rate limit reached. Wait {wait} seconds and send the message again."
    if isinstance(error, anthropic.BadRequestError):
        return f"The API refused the request: {error.message}"
    if isinstance(error, anthropic.APIStatusError):
        if error.status_code >= 500:
            return ("Anthropic's servers are busy or unavailable "
                    f"(status {error.status_code}). Try again in a moment.")
        return f"API error {error.status_code}: {error.message}"
    if isinstance(error, anthropic.APITimeoutError):
        return "The request to the API timed out. Try again."
    if isinstance(error, anthropic.APIConnectionError):
        return "Could not reach the API. Check the internet connection."
    return f"Unexpected error: {type(error).__name__}: {error}"


class Agent:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        # The key is passed in, not read from the environment, so it never has to be
        # present in os.environ where the analysis worker could inherit it.
        self.client = client or anthropic.Anthropic(api_key=settings.api_key)

    # ------------------------------------------------------------------ one request
    def _request(self, session: Session, rec: Recorder, cancel: threading.Event,
                 allow_tools: bool):
        """Stream one reply. Returns the final message, or None if the user stopped it."""
        s = self.settings
        thinking = {"type": "adaptive"}
        if s.show_thinking:
            thinking["display"] = "summarized"   # the default on Sonnet 5 is no text at all
        kwargs = dict(
            model=s.model,
            max_tokens=s.max_tokens,
            system=prompts.SYSTEM_PROMPT,
            tools=TOOLS,
            messages=session.messages,
            thinking=thinking,
            output_config={"effort": s.effort},
            cache_control={"type": "ephemeral"},   # cache the conversation so far
        )
        if not allow_tools:
            kwargs["tool_choice"] = {"type": "none"}

        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                if cancel.is_set():
                    return None
                kind = event.type
                if kind == "text":
                    rec.text(event.text)
                elif kind == "thinking":
                    rec.thinking(event.thinking)
                elif kind == "content_block_start" and event.content_block.type == "tool_use":
                    rec.tool_start(event.content_block.id, event.content_block.name)
            return stream.get_final_message()

    # --------------------------------------------------------------------- one turn
    def run_turn(self, session: Session, text: str, emit: Emit) -> list[dict]:
        """Answer one user message. Returns the parts shown to the user."""
        rec = Recorder(emit)
        cancel = session.cancel
        session.messages.append(
            {"role": "user",
             "content": prompts.dataset_context(session.take_briefs())
                        + prompts.user_context(session.take_context())
                        + prompts.detail_level(session.level) + text})

        rounds, json_retries = 0, 0
        while True:
            allow_tools = rounds < self.settings.max_tool_rounds
            rec.status("Thinking" if rounds == 0 else "Reading the results")
            try:
                response = self._request(session, rec, cancel, allow_tools)
                json_retries = 0
            except ValueError:
                # The SDK could not parse a tool input at all. Nothing was run and there
                # is no tool call to answer, so ask again. API errors are not ValueError.
                json_retries += 1
                if json_retries > MAX_JSON_RETRIES:
                    rec.notice("The model kept producing a tool call that could not be "
                               "read. Try rephrasing the request.", "error")
                    break
                continue
            except anthropic.APIError as e:
                rec.notice(explain(e, self.settings), "error")
                break

            if response is None:                                    # stopped by the user
                said = "".join(p["text"] for p in rec.parts if p["type"] == "text")
                session.messages.append(
                    {"role": "assistant", "content": said or "(stopped by the user)"})
                rec.notice("Stopped.")
                break

            cost = session.usage.add(response.usage, self.settings)
            rec.usage({"last_cost_usd": round(cost, 4), **session.usage.public()})

            reason = response.stop_reason
            if reason == "refusal":
                # Nothing usable came back. Remove the question so the conversation that
                # is sent next time is still well formed.
                session.messages.pop()
                rec.notice("The model declined to answer this request.", "error")
                break

            session.messages.append({"role": "assistant", "content": response.content})
            calls = [b for b in response.content if b.type == "tool_use"]

            if reason == "pause_turn":
                continue
            if not calls:
                if reason == "max_tokens":
                    rec.notice("The answer was cut off because it reached the length "
                               "limit. Ask for the rest, or raise ADS_MAX_TOKENS.", "warning")
                break

            results = []
            for call in calls:
                if reason == "max_tokens":
                    # A cut-off input still parses as a valid, shorter object. Never run it.
                    outcome = ToolOutcome(
                        text="This tool call was cut off before it was complete, so it was "
                             "not run. Send it again, shorter.",
                        is_error=True, summary="cut off")
                elif cancel.is_set():
                    outcome = ToolOutcome(text="Not run: the user stopped the analysis.",
                                          is_error=True, summary="stopped")
                else:
                    args = call.input if isinstance(call.input, dict) else {}
                    rec.tool_running(call.id, call.name, args)
                    rec.status(f"Running {call.name}")
                    try:
                        outcome = session.toolbox.run(call.name, call.input)
                    except Exception as e:   # a bug in a tool must not break the history
                        outcome = ToolOutcome(
                            text=f"The tool failed: {type(e).__name__}: {e}",
                            is_error=True, summary="tool failed")
                rec.tool_done(call.id, call.name, outcome)
                results.append(tool_result_block(call.id, outcome,
                                                 self.settings.send_charts_to_model))

            rounds += 1
            if rounds >= self.settings.max_tool_rounds:
                results.append({"type": "text", "text": LIMIT_NOTICE})
            # All results go back in one message. Splitting them teaches the model to
            # stop asking for several tools at once.
            session.messages.append({"role": "user", "content": results})

            if cancel.is_set():
                rec.notice("Stopped.")
                break

        # The follow-up questions ride on the end of the last text block. Take them off
        # what the user keeps; they were already streamed, and the page hides the block.
        session.suggestions = []
        for part in reversed(rec.parts):
            if part["type"] == "text":
                part["text"], questions = split_followups(part["text"])
                if questions:
                    session.suggestions = questions
                    rec.suggestions(questions)
                break
        return rec.parts
