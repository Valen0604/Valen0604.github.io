"""
The whole app through its HTTP API, in offline mode.

This is the path a browser takes: start a session, upload, chat, fetch the charts, export
the report. It runs the real server code and a real analysis worker.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sid(client):
    return client.post("/api/sessions").json()["id"]


def chat(client, sid, message):
    """Send a message and return the streamed events as (name, data) pairs."""
    events = []
    with client.stream("POST", f"/api/sessions/{sid}/chat", json={"message": message}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        name = None
        for line in r.iter_lines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                events.append((name, json.loads(line[5:])))
    return events


def cards(events, kind):
    return [c for name, d in events if name == "tool_done" for c in d["cards"] if c["type"] == kind]


def test_the_page_and_its_files_load(client):
    page = client.get("/")
    assert page.status_code == 200 and "AI Data Scientist" in page.text
    for file in ("styles.css", "render.js", "app.js"):
        assert client.get(f"/static/{file}").status_code == 200


def test_config_never_contains_a_key(client):
    cfg = client.get("/api/config").json()
    assert cfg["live"] is False
    assert not any("key" in k.lower() for k in cfg)
    assert "sk-" not in json.dumps(cfg)


def test_upload_profiles_the_data(client, sid):
    with (SAMPLE / "customer_churn.csv").open("rb") as f:
        r = client.post(f"/api/sessions/{sid}/upload",
                        files={"files": ("customer_churn.csv", f, "text/csv")}).json()
    assert r["errors"] == []
    p = r["loaded"][0]
    assert p["name"] == "customer_churn" and p["rows"] == 3025
    assert any("999" in w["message"] for w in p["warnings"])
    assert r["datasets"][0]["active"]


def test_bad_uploads_are_refused_with_a_reason(client, sid):
    r = client.post(f"/api/sessions/{sid}/upload", files=[
        ("files", ("notes.exe", b"MZ", "application/octet-stream")),
        ("files", ("empty.csv", b"", "text/csv")),
        ("files", ("../../escape.csv", b"a,b\n1,2\n", "text/csv")),
    ]).json()
    assert {e["file"] for e in r["errors"]} == {"notes.exe", "empty.csv"}
    assert [d["name"] for d in r["datasets"]] == ["escape"]          # the path was stripped


def test_a_conversation_end_to_end(client, sid):
    client.post(f"/api/sessions/{sid}/sample", json={"name": "customer_churn.csv"})

    events = chat(client, sid, "give me an overview of the data")
    names = [n for n, _ in events]
    assert names[-1] == "done" and "tool_done" in names
    assert len(cards(events, "profile")) == 1 and len(cards(events, "chart")) == 3

    events = chat(client, sid, "is contract related to churned?")
    assert cards(events, "stat")[0]["result"]["significant"] is True

    events = chat(client, sid, "scatter of tenure months vs total charges")
    chart = cards(events, "chart")[0]
    png = client.get(f"/api/sessions/{sid}/artifacts/{chart['file']}")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"

    events = chat(client, sid, "predict churned without cancellation_reason")
    model = cards(events, "model")[0]["result"]
    assert model["target"] == "churned" and model["best_model"] != "baseline"
    assert client.get(f"/api/sessions/{sid}/artifacts/{model['model_file']}").status_code == 200

    events = chat(client, sid, "```python\ndf.groupby('contract')['monthly_charge'].mean().round(2)\n```")
    assert cards(events, "code")[0]["error"] is None and cards(events, "table")

    state = client.get(f"/api/sessions/{sid}").json()
    assert [t["role"] for t in state["transcript"]] == ["upload"] + ["user", "assistant"] * 5

    report = client.get(f"/api/sessions/{sid}/report")
    assert report.status_code == 200
    assert "attachment" in report.headers["content-disposition"]
    assert report.text.count("data:image/png;base64,") >= 5          # charts are embedded
    assert "/api/sessions/" not in report.text                       # nothing needs the server


def test_upload_builds_a_dashboard_with_highlights(client, sid):
    r = client.post(f"/api/sessions/{sid}/sample", json={"name": "customer_churn.csv"}).json()
    d = r["dashboards"]["customer_churn"]
    assert d["rows"] == 3025 and d["numeric"] and d["categorical"] and d["correlations"]
    kinds = {h["kind"] for h in d["highlights"]}
    assert "target" in kinds and d["target"]["column"] == "churned"
    assert "quality" in kinds                    # the planted 999 placeholder is serious
    assert d["numeric"][0]["bins"] and d["correlations"]["pairs"][0]["points"]
    again = client.get(f"/api/sessions/{sid}/dashboard/customer_churn").json()
    assert again["highlights"] == d["highlights"]
    assert client.get(f"/api/sessions/{sid}/dashboard/nope").status_code == 404
    rebuilt = client.post(f"/api/sessions/{sid}/dashboard/customer_churn").json()
    assert rebuilt["rows"] == 3025


def test_context_and_detail_level_are_kept_on_the_session(client, sid):
    r = client.put(f"/api/sessions/{sid}/context", json={
        "description": "one row per customer", "constraints": "cannot change contracts",
        "level": "technical"}).json()
    assert r["given"] is True and r["level"] == "technical"
    assert client.get(f"/api/sessions/{sid}").json()["context"]["constraints"] == "cannot change contracts"
    assert client.put(f"/api/sessions/{sid}/context", json={"level": "verbose"}).status_code == 400
    assert client.post(f"/api/sessions/{sid}/chat", json={"message": "hi", "level": "huge"}).status_code == 400


def test_offline_mode_still_offers_follow_ups(client, sid):
    client.post(f"/api/sessions/{sid}/sample", json={"name": "store_sales.csv"})
    events = chat(client, sid, "show missing values")
    questions = next(d for n, d in events if n == "suggestions")["questions"]
    assert questions and all(isinstance(q, str) for q in questions)
    assert client.get(f"/api/sessions/{sid}").json()["suggestions"] == questions


def test_the_printable_report_has_the_dashboard_and_the_context(client, sid):
    client.post(f"/api/sessions/{sid}/sample", json={"name": "customer_churn.csv"})
    client.put(f"/api/sessions/{sid}/context", json={"goal": "decide whom to call first"})
    chat(client, sid, "profile the data")
    r = client.get(f"/api/sessions/{sid}/report?print=1")
    assert r.status_code == 200 and "content-disposition" not in r.headers
    assert "window.print()" in r.text and "decide whom to call first" in r.text
    assert '"highlights"' in r.text and "@media print" in r.text
    assert "/api/sessions/" not in r.text


def test_files_outside_the_session_cannot_be_fetched(client, sid):
    for path in ("..%2F..%2F.env", "..%5C..%5Crequirements.txt", "%2Fetc%2Fpasswd"):
        assert client.get(f"/api/sessions/{sid}/artifacts/{path}").status_code == 404


def test_an_unknown_session_is_a_clear_404(client):
    r = client.post("/api/sessions/nope/chat", json={"message": "hi"})
    assert r.status_code == 404 and "Reload" in r.json()["detail"]


def test_an_empty_message_is_refused(client, sid):
    assert client.post(f"/api/sessions/{sid}/chat", json={"message": "   "}).status_code == 400


def test_removing_a_dataset(client, sid):
    client.post(f"/api/sessions/{sid}/sample", json={"name": "store_sales.csv"})
    r = client.delete(f"/api/sessions/{sid}/datasets/store_sales").json()
    assert r["datasets"] == []
