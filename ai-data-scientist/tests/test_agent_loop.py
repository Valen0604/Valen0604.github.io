"""
The agent loop, tested with a scripted stand-in for the Claude API.

No key and no network are needed. FakeClient replays replies that are written out below,
in the same shape the real SDK returns them. What is checked is the part we own: that
tools run, that results go back in the right form, and that the conversation sent on the
next request is one the API would accept.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from app.agent.loop import Agent
from app.agent.tools import TOOLS, validate
from app.config import SETTINGS


# ------------------------------------------------------------------- the stand-in client
def text_block(text):
    return NS(type="text", text=text)


def tool_block(tool_id, name, args):
    return NS(type="tool_use", id=tool_id, name=name, input=args)


def reply(blocks, stop_reason="end_turn", tokens=(1000, 200)):
    usage = NS(input_tokens=tokens[0], output_tokens=tokens[1],
               cache_creation_input_tokens=0, cache_read_input_tokens=0)
    return NS(content=blocks, stop_reason=stop_reason, usage=usage)


class FakeStream:
    """Replays one reply as the events the SDK would stream."""

    def __init__(self, message, fail=None):
        self.message, self.fail = message, fail

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        if self.fail:
            raise self.fail
        for block in self.message.content:
            yield NS(type="content_block_start", content_block=block)
            if block.type == "text":
                for word in block.text.split(" "):
                    yield NS(type="text", text=word + " ")
            elif block.type == "thinking":
                yield NS(type="thinking", thinking=block.thinking)

    def get_final_message(self):
        return self.message


class FakeClient:
    def __init__(self, *script):
        self.script = list(script)
        self.requests = []
        self.messages = self

    def stream(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        item = self.script.pop(0)
        return item if isinstance(item, FakeStream) else FakeStream(item)


def run(session, client, text="question"):
    events = []
    parts = Agent(SETTINGS, client=client).run_turn(
        session, text, lambda kind, data: events.append((kind, data)))
    return parts, events


def assert_well_formed(messages):
    """The rules the API enforces on a conversation."""
    assert messages[0]["role"] == "user"
    open_calls = set()
    for m in messages:
        blocks = m["content"] if isinstance(m["content"], list) else []
        if m["role"] == "assistant":
            assert not open_calls, "a tool call was never answered"
            open_calls = {b.id for b in blocks if getattr(b, "type", None) == "tool_use"}
        else:
            answered = {b["tool_use_id"] for b in blocks
                        if isinstance(b, dict) and b.get("type") == "tool_result"}
            assert answered == open_calls, "tool results do not match the tool calls"
            kinds = [b.get("type") for b in blocks if isinstance(b, dict)]
            if "tool_result" in kinds and "text" in kinds:
                assert kinds.index("text") > max(i for i, k in enumerate(kinds)
                                                 if k == "tool_result")
            open_calls = set()
    assert not open_calls


# -------------------------------------------------------------------------------- tests
def test_a_plain_answer(session):
    client = FakeClient(reply([text_block("There are 3,025 rows.")]))
    parts, events = run(session, client, "how many rows?")
    assert parts == [{"type": "text", "text": "There are 3,025 rows. "}]
    assert [m["role"] for m in session.messages] == ["user", "assistant"]
    assert_well_formed(session.messages)


def test_the_upload_description_reaches_the_model_once(session):
    client = FakeClient(reply([text_block("ok")]), reply([text_block("ok")]))
    run(session, client, "first")
    run(session, client, "second")
    first, second = session.messages[0]["content"], session.messages[2]["content"]
    assert "<uploaded_data>" in first and "customer_churn" in first and first.endswith("first")
    assert "First look" in first                                 # the dashboard highlights
    assert "<uploaded_data>" not in second and second.endswith("second")
    assert "<detail_level>" in first and "<detail_level>" in second   # sent every time


def test_the_detail_level_and_context_are_sent_in_the_message(session):
    """Both ride on the user message, never on the system prompt, which must stay fixed."""
    session.level = "brief"
    session.context = {"description": "one row per customer", "goal": "", "constraints":
                       "we cannot change contract types", "notes": ""}
    session.pending_context = True
    client = FakeClient(reply([text_block("ok")]), reply([text_block("ok")]))
    run(session, client, "first")
    run(session, client, "second")
    first, second = session.messages[0]["content"], session.messages[2]["content"]
    assert "BRIEF" in first and "<user_context>" in first
    assert "cannot change contract types" in first
    assert "<user_context>" not in second                        # once, until it changes
    assert "BRIEF" in second
    assert "cannot change contract types" not in client.requests[0]["system"]


def test_follow_up_questions_become_buttons_not_text(session):
    answer = ('Churn is 27%.\n\n```followups\n["Which region churns most?", '
              '"Does tenure matter?"]\n```\n')
    client = FakeClient(reply([text_block(answer)]))
    parts, events = run(session, client, "how much churn?")
    text = next(p for p in parts if p["type"] == "text")["text"]
    assert "followups" not in text and "Churn is 27%" in text
    questions = next(d for k, d in events if k == "suggestions")["questions"]
    assert questions == ["Which region churns most?", "Does tenure matter?"]
    assert session.suggestions == questions


def test_a_malformed_follow_up_block_is_left_alone(session):
    from app.agent.loop import split_followups
    assert split_followups("text\n```followups\nnot json\n```") == ("text\n```followups\nnot json\n```", [])
    assert split_followups("plain answer") == ("plain answer", [])
    text, qs = split_followups("a\n\n```followups\n[\"x\", 3]\n```")
    assert qs == [] and "followups" in text


def test_the_request_is_built_as_documented(session):
    client = FakeClient(reply([text_block("ok")]))
    run(session, client)
    req = client.requests[0]
    assert req["model"] == "claude-sonnet-5"
    assert req["thinking"]["type"] == "adaptive"
    assert "budget_tokens" not in req["thinking"]            # rejected by Sonnet 5
    assert req["output_config"] == {"effort": SETTINGS.effort}
    assert req["cache_control"] == {"type": "ephemeral"}
    assert "temperature" not in req and "top_p" not in req   # rejected by Sonnet 5
    assert req["tools"] is TOOLS
    assert isinstance(req["system"], str) and "data scientist" in req["system"]


def test_the_system_prompt_never_changes(session):
    """A changing prefix would defeat prompt caching and roughly double the cost."""
    client = FakeClient(reply([text_block("a")]), reply([text_block("b")]))
    run(session, client, "one")
    run(session, client, "two")
    assert client.requests[0]["system"] == client.requests[1]["system"]
    assert session.id not in client.requests[0]["system"]


def test_a_tool_is_run_and_its_result_sent_back(session):
    client = FakeClient(
        reply([text_block("Let me look."),
               tool_block("t1", "create_chart", {"chart_type": "bar", "x": "contract"})],
              stop_reason="tool_use"),
        reply([text_block("Most customers are month-to-month.")]))
    parts, events = run(session, client, "chart contracts")

    tool = next(p for p in parts if p["type"] == "tool")
    assert tool["status"] == "done" and tool["cards"][0]["type"] == "chart"
    assert (session.workspace / "artifacts" / tool["cards"][0]["file"]).exists()

    result = session.messages[2]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "t1"
    assert "is_error" not in result
    assert result["content"][0]["type"] == "text" and "Month-to-month" in result["content"][0]["text"]
    assert result["content"][1]["type"] == "image"            # the model sees the chart
    assert result["content"][1]["source"]["media_type"] == "image/png"

    kinds = [k for k, _ in events]
    assert kinds.index("tool_start") < kinds.index("tool_running") < kinds.index("tool_done")
    assert_well_formed(session.messages)


def test_several_tools_are_answered_in_one_message(session):
    client = FakeClient(
        reply([tool_block("a", "create_chart", {"chart_type": "missing"}),
               tool_block("b", "run_statistical_test", {"x": "contract", "y": "churned"}),
               tool_block("c", "preview_rows", {"rows": 3})], stop_reason="tool_use"),
        reply([text_block("Done.")]))
    run(session, client)
    assert [m["role"] for m in session.messages] == ["user", "assistant", "user", "assistant"]
    assert [b["tool_use_id"] for b in session.messages[2]["content"]] == ["a", "b", "c"]
    assert_well_formed(session.messages)


def test_a_failing_tool_reports_the_error_and_the_model_can_retry(session):
    client = FakeClient(
        reply([tool_block("t1", "create_chart", {"chart_type": "bar", "x": "contrct"})],
              stop_reason="tool_use"),
        reply([tool_block("t2", "create_chart", {"chart_type": "bar", "x": "contract"})],
              stop_reason="tool_use"),
        reply([text_block("Here it is.")]))
    parts, _ = run(session, client)
    first = session.messages[2]["content"][0]
    assert first["is_error"] is True
    assert "contract" in first["content"][0]["text"]          # the message lists real columns
    assert [p["status"] for p in parts if p["type"] == "tool"] == ["error", "done"]
    assert_well_formed(session.messages)


def test_python_state_survives_between_calls(session):
    client = FakeClient(
        reply([tool_block("t1", "run_python", {"code": "kept = len(df)\nkept"})],
              stop_reason="tool_use"),
        reply([tool_block("t2", "run_python", {"code": "kept * 2"})], stop_reason="tool_use"),
        reply([text_block("ok")]))
    run(session, client)
    assert "3025" in session.messages[2]["content"][0]["content"][0]["text"]
    assert "6050" in session.messages[4]["content"][0]["content"][0]["text"]


def test_code_that_changes_the_data_is_reported(session):
    code = "df = df.drop_duplicates()\nlen(df)"
    client = FakeClient(reply([tool_block("t1", "run_python", {"code": code, "purpose": "dedupe"})],
                              stop_reason="tool_use"), reply([text_block("ok")]))
    parts, _ = run(session, client)
    card = next(p for p in parts if p["type"] == "tool")["cards"][0]
    assert card["changes"][0]["rows_before"] == 3025 and card["changes"][0]["rows"] == 3000
    assert "dataset_changes" in session.messages[2]["content"][0]["content"][0]["text"]


def test_blocked_code_is_not_run(session):
    client = FakeClient(
        reply([tool_block("t1", "run_python", {"code": "import subprocess\nsubprocess.run('dir')"})],
              stop_reason="tool_use"), reply([text_block("I cannot do that.")]))
    run(session, client)
    result = session.messages[2]["content"][0]
    assert result["is_error"] and "not allowed" in result["content"][0]["text"]


def test_invalid_input_is_rejected_before_anything_runs(session):
    client = FakeClient(
        reply([tool_block("t1", "create_chart", {"chart_type": "donut"}),
               tool_block("t2", "train_model", {}),
               tool_block("t3", "no_such_tool", {})], stop_reason="tool_use"),
        reply([text_block("ok")]))
    run(session, client)
    texts = [b["content"][0]["text"] for b in session.messages[2]["content"]]
    assert all(b["is_error"] for b in session.messages[2]["content"])
    assert "must be one of" in texts[0] and "target" in texts[1] and "no tool named" in texts[2]


def test_a_cut_off_tool_call_is_never_run(session):
    client = FakeClient(
        reply([tool_block("t1", "run_python", {"code": "df.dro"})], stop_reason="max_tokens"),
        reply([text_block("ok")]))
    parts, _ = run(session, client)
    result = session.messages[2]["content"][0]
    assert result["is_error"] and "cut off" in result["content"][0]["text"]
    assert next(p for p in parts if p["type"] == "tool")["cards"] == []
    assert_well_formed(session.messages)


def test_the_tool_limit_forces_an_answer(session):
    import dataclasses
    limit = 3
    agent_settings = dataclasses.replace(SETTINGS, max_tool_rounds=limit)
    looping = [reply([tool_block(f"t{i}", "list_datasets", {})], stop_reason="tool_use")
               for i in range(limit)]
    client = FakeClient(*looping, reply([text_block("Here is what I have.")]))
    Agent(agent_settings, client=client).run_turn(session, "go", lambda *_: None)

    assert len(client.requests) == limit + 1
    assert "tool_choice" not in client.requests[limit - 1]
    assert client.requests[limit]["tool_choice"] == {"type": "none"}
    last = session.messages[-2]["content"]
    assert last[-1]["type"] == "text" and "limit" in last[-1]["text"]
    assert_well_formed(session.messages)


def test_a_refusal_leaves_a_usable_conversation(session):
    client = FakeClient(reply([], stop_reason="refusal"), reply([text_block("ok")]))
    parts, _ = run(session, client, "first")
    assert parts[-1]["type"] == "notice" and parts[-1]["level"] == "error"
    assert session.messages == []
    run(session, client, "second")
    assert_well_formed(session.messages)


def test_stopping_between_tools_still_answers_every_call(session):
    def stop_after_first(kind, data):
        if kind == "tool_done":
            session.cancel.set()

    client = FakeClient(reply([tool_block("a", "list_datasets", {}),
                               tool_block("b", "list_datasets", {})], stop_reason="tool_use"))
    Agent(SETTINGS, client=client).run_turn(session, "go", stop_after_first)
    results = session.messages[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"]
    assert "is_error" not in results[0] and results[1]["is_error"]
    assert len(client.requests) == 1
    assert_well_formed(session.messages)
    session.cancel.clear()


def test_api_errors_become_instructions(session):
    import anthropic
    import httpx2

    def error(cls, status):
        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        response = httpx2.Response(status, request=request, headers={"retry-after": "12"})
        return cls("boom", response=response, body=None)

    for exc, expected in [
        (error(anthropic.AuthenticationError, 401), ".env"),
        (error(anthropic.RateLimitError, 429), "12 seconds"),
        (error(anthropic.NotFoundError, 404), "ADS_MODEL"),
        (error(anthropic.InternalServerError, 529), "busy"),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x")), "internet"),
    ]:
        client = FakeClient(FakeStream(None, fail=exc))
        parts, _ = run(session, client)
        assert parts[-1]["level"] == "error" and expected in parts[-1]["text"], expected


def test_cost_is_counted(session):
    client = FakeClient(reply([text_block("ok")], tokens=(1_000_000, 100_000)))
    _, events = run(session, client)
    usage = next(d for k, d in events if k == "usage")
    assert usage["cost_usd"] == pytest.approx(2.00 + 1.00)     # $2 in, $10 per million out


# ---------------------------------------------------------------------------- the tools
def test_every_tool_has_a_handler_and_a_useful_description():
    from app.agent.tools import Toolbox
    for tool in TOOLS:
        assert hasattr(Toolbox, f"_tool_{tool['name']}"), tool["name"]
        assert len(tool["description"]) > 80, tool["name"]
        assert "Call this" in tool["description"], f"{tool['name']}: say when to call it"
        assert tool["eager_input_streaming"] is True
        for name, prop in tool["input_schema"]["properties"].items():
            assert "description" in prop or "enum" in prop, f"{tool['name']}.{name}"


def test_whole_number_floats_are_accepted_as_integers():
    args = {"rows": 10.0}
    assert validate("preview_rows", args) is None and args["rows"] == 10
    assert validate("preview_rows", {"rows": 2.5}) is not None
    assert validate("preview_rows", {"rows": True}) is not None
