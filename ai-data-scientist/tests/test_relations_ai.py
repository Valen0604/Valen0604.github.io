"""
Relationship ideas from the model, tested with a scripted reply.

What is checked is the part we own: the schemas the model is shown carry example values,
a reply that names a column that does not exist is dropped rather than drawn, a pair the
values already proved becomes a verdict instead of a duplicate, and the endpoint refuses
politely without a key.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app.agent import relations_ai
from app.analytics import loading, relations
from app.config import SETTINGS

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"


@pytest.fixture(scope="module")
def rel():
    load = lambda name: next(iter(loading.read_any(SAMPLE / name).values()))[0]
    return relations.build({"customer_churn": load("customer_churn.csv"),
                            "support_tickets": load("support_tickets.csv"),
                            "store_sales": load("store_sales.csv")})


REPLY = """Here you go:
```json
{"suggestions": [
  {"a": "Store_Sales", "a_column": "STORE", "b": "support_tickets", "b_column": "channel",
   "kind": "dimension", "confidence": "low", "reason": "Both look like a place or channel label.",
   "transform": "lower-case both"},
  {"a": "customer_churn", "a_column": "signup_date", "b": "store_sales", "b_column": "date",
   "kind": "time", "confidence": "medium", "reason": "Both are dates in the same years.", "transform": null},
  {"a": "customer_churn", "a_column": "customer_id", "b": "support_tickets", "b_column": "customer_id",
   "kind": "join", "confidence": "high", "reason": "Same id format on both sides."},
  {"a": "customer_churn", "a_column": "made_up", "b": "store_sales", "b_column": "units_sold",
   "kind": "derived", "confidence": "high", "reason": "invented"},
  {"a": "customer_churn", "a_column": "plan", "b": "customer_churn", "b_column": "monthly_charge",
   "kind": "derived", "confidence": "high", "reason": "same table, not a relationship"}
 ],
 "found": [
  {"a": "customer_churn", "a_column": "support_tickets", "b": "support_tickets", "b_column": "ticket_id",
   "verdict": "doubt", "reason": "A count of tickets is not a ticket id."},
  {"a": "nope", "a_column": "x", "b": "store_sales", "b_column": "store", "verdict": "agree", "reason": ""}
 ],
 "notes": ["Churn and tickets are one customer universe; sales is a separate store universe.", 7]
}
```"""


class FakeClient:
    def __init__(self, text):
        self.text, self.requests = text, []
        self.messages = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return NS(content=[NS(type="text", text=self.text)],
                  usage=NS(input_tokens=900, output_tokens=300,
                           cache_creation_input_tokens=0, cache_read_input_tokens=0))


def test_the_model_is_shown_names_types_and_examples(rel):
    text = relations_ai.user_text(rel, {"goal": "find who churns", "constraints": ""})
    assert "## customer_churn (" in text and "- customer_id (id)  e.g. C" in text
    assert "customer_churn.customer_id = support_tickets.customer_id" in text
    assert "What the user said about the data:\ngoal: find who churns" in text
    # every column in the map carries its examples, for the model and for the browser
    assert all("examples" in c for d in rel["datasets"] for c in d["columns"])


def test_a_reply_is_checked_against_the_real_columns(rel):
    client = FakeClient(REPLY)
    result, usage = relations_ai.suggest(client, SETTINGS, rel, None)
    assert usage.input_tokens == 900 and client.requests[0]["system"] == relations_ai.SYSTEM
    got = {(s["a"], s["a_column"], s["b"], s["b_column"]) for s in result["suggestions"]}
    # names are spelled as the tables spell them, whatever case the model used
    assert ("store_sales", "store", "support_tickets", "channel") in got
    assert ("customer_churn", "signup_date", "store_sales", "date") in got
    # an invented column and a same-table pair are dropped, and counted
    assert not any(s["a_column"] == "made_up" or s["a"] == s["b"] for s in result["suggestions"])
    assert result["skipped"] == 2
    # the customer_id pair was already proved by the values: it becomes a verdict, not a line
    assert not any(s["a_column"] == "customer_id" for s in result["suggestions"])
    verdicts = {(f["a_column"], f["verdict"]) for f in result["found"]}
    assert ("customer_id", "agree") in verdicts and ("support_tickets", "doubt") in verdicts
    assert len(result["found"]) == 2                       # the one with a made-up table is gone
    # a join gets code; a dimension does not; transforms are kept
    store = next(s for s in result["suggestions"] if s["a_column"] == "store")
    assert store["merge"] is None and store["transform"] == "lower-case both"
    assert result["notes"] == ["Churn and tickets are one customer universe; sales is a separate store universe."]
    assert result["model"] == SETTINGS.model
    brief = relations_ai.brief(result)
    assert "store_sales.store and support_tickets.channel (dimension, low confidence)" in brief
    assert "doubt about the value match customer_churn.support_tickets" in brief


def test_a_join_suggestion_gets_merge_code(rel):
    reply = ('{"suggestions": [{"a": "store_sales", "a_column": "store", "b": "support_tickets", '
             '"b_column": "channel", "kind": "join", "confidence": "medium", "reason": "r"}]}')
    result, _ = relations_ai.suggest(FakeClient(reply), SETTINGS, rel, None)
    assert result["suggestions"][0]["merge"] == \
        'merged = pd.merge(datasets["store_sales"], datasets["support_tickets"], left_on="store", right_on="channel", how="left")'


@pytest.mark.parametrize("text", ["I cannot tell.", "{not json", "[1, 2]"])
def test_a_reply_that_is_not_the_json_asked_for_is_an_error(rel, text):
    with pytest.raises(relations_ai.BadReply):
        relations_ai.suggest(FakeClient(text), SETTINGS, rel, None)


def test_without_a_key_the_endpoint_says_so():
    from app.main import app
    with TestClient(app) as client:
        sid = client.post("/api/sessions").json()["id"]
        client.post(f"/api/sessions/{sid}/sample", json={"name": "customer_churn.csv"})
        client.post(f"/api/sessions/{sid}/sample", json={"name": "support_tickets.csv"})
        r = client.post(f"/api/sessions/{sid}/relations/suggest")
        assert r.status_code == 400 and "API key" in r.json()["detail"]
        rel = client.get(f"/api/sessions/{sid}/relations").json()
        assert "ai" not in rel and rel["datasets"][0]["columns"][0]["examples"]
