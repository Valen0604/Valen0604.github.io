"""
Several chats, several files, and the exports, through the HTTP API in offline mode.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from test_api import cards, chat


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sid(client):
    return client.post("/api/sessions").json()["id"]


def test_chats_are_listed_renamed_and_closed(client):
    a = client.post("/api/sessions").json()["id"]
    b = client.post("/api/sessions").json()["id"]
    listed = client.get("/api/sessions").json()
    assert [s["id"] for s in listed][:2] == [b, a]            # newest first
    assert listed[0]["title"] == "New chat" and listed[0]["datasets"] == []
    client.post(f"/api/sessions/{a}/sample", json={"name": "store_sales.csv"})
    me = next(s for s in client.get("/api/sessions").json() if s["id"] == a)
    assert me["title"] == "store_sales.csv" and me["datasets"] == ["store_sales"]
    assert client.patch(f"/api/sessions/{a}", json={"title": "  Sales  "}).json()["title"] == "Sales"
    assert client.get(f"/api/sessions/{a}").json()["title"] == "Sales"
    assert client.delete(f"/api/sessions/{b}").json() == {"closed": b}
    assert client.get(f"/api/sessions/{b}").status_code == 404
    assert b not in [s["id"] for s in client.get("/api/sessions").json()]


def test_chats_do_not_share_data_unless_a_dataset_is_brought_over(client):
    a = client.post("/api/sessions").json()["id"]
    b = client.post("/api/sessions").json()["id"]
    client.post(f"/api/sessions/{a}/sample", json={"name": "customer_churn.csv"})
    assert client.get(f"/api/sessions/{b}").json()["datasets"] == []
    r = client.post(f"/api/sessions/{b}/datasets/import",
                    json={"from_session": a, "dataset": "customer_churn"}).json()
    assert r["errors"] == [] and r["loaded"][0]["name"] == "customer_churn"
    assert [d["name"] for d in client.get(f"/api/sessions/{b}").json()["datasets"]] == ["customer_churn"]
    assert "customer_churn" in r["dashboards"]
    # the copy is independent: removing it in b leaves a untouched
    client.delete(f"/api/sessions/{b}/datasets/customer_churn")
    assert [d["name"] for d in client.get(f"/api/sessions/{a}").json()["datasets"]] == ["customer_churn"]
    assert client.post(f"/api/sessions/{b}/datasets/import",
                       json={"from_session": a, "dataset": "nope"}).status_code == 400
    assert client.post(f"/api/sessions/{b}/datasets/import",
                       json={"from_session": "gone", "dataset": "x"}).status_code == 404


def test_datasets_can_be_downloaded_in_three_formats(client, sid):
    client.post(f"/api/sessions/{sid}/sample", json={"name": "store_sales.csv"})
    csv = client.get(f"/api/sessions/{sid}/datasets/store_sales/download")
    assert csv.status_code == 200 and csv.text.startswith("date,store,")
    assert 'filename="store_sales.csv"' in csv.headers["content-disposition"]
    xlsx = client.get(f"/api/sessions/{sid}/datasets/store_sales/download?format=xlsx")
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    parquet = client.get(f"/api/sessions/{sid}/datasets/store_sales/download?format=parquet")
    assert parquet.status_code == 200 and parquet.content[:4] == b"PAR1"
    assert client.get(f"/api/sessions/{sid}/datasets/store_sales/download?format=exe").status_code == 400
    assert client.get(f"/api/sessions/{sid}/datasets/nope/download").status_code == 400


def test_a_dataset_the_code_creates_gets_a_dashboard_and_a_download(client, sid):
    client.post(f"/api/sessions/{sid}/sample", json={"name": "customer_churn.csv"})
    code = ("```python\nby_plan = df.groupby('plan', as_index=False)['monthly_charge'].mean()\n"
            "save_dataset('charge_by_plan', by_plan)\n```")
    events = chat(client, sid, code)
    done = next(d for n, d in events if n == "done")
    names = {d["name"]: d for d in done["datasets"]}
    assert names["charge_by_plan"]["kind"] == "created" and names["customer_churn"]["kind"] == "uploaded"
    assert "charge_by_plan" in done["refreshed"]
    assert done["refreshed"]["charge_by_plan"]["dashboard"]["rows"] == 3
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["dashboards"]["charge_by_plan"]["columns_count"] == 2
    assert state["profiles"]["charge_by_plan"]["rows"] == 3
    assert client.get(f"/api/sessions/{sid}/dashboard/charge_by_plan").status_code == 200
    csv = client.get(f"/api/sessions/{sid}/datasets/charge_by_plan/download")
    assert csv.status_code == 200 and csv.text.splitlines()[0] == "plan,monthly_charge"
    # the uploaded dataset was not touched, so its dashboard was not recomputed
    assert "customer_churn" not in done["refreshed"]
    events = chat(client, sid, "```python\ndf = df.drop_duplicates()\n```")
    done = next(d for n, d in events if n == "done")
    assert {d["name"]: d["kind"] for d in done["datasets"]}["customer_churn"] == "modified"
    assert done["refreshed"]["customer_churn"]["dashboard"]["rows"] == 3000


def test_the_relationships_between_datasets(client, sid):
    assert client.get(f"/api/sessions/{sid}/relations").json()["edges"] == []
    client.post(f"/api/sessions/{sid}/sample", json={"name": "customer_churn.csv"})
    r = client.post(f"/api/sessions/{sid}/sample", json={"name": "store_sales.csv"}).json()
    assert r["relations"]["edges"] == []
    assert set(r["relations"]["unlinked"]) == {"customer_churn", "store_sales"}
    code = ("```python\nt = datasets['customer_churn'][['customer_id', 'plan']].head(500).copy()\n"
            "t['ticket'] = range(500)\nsave_dataset('tickets', t)\n```")
    events = chat(client, sid, code)
    assert next(d for n, d in events if n == "done")["refreshed"]["tickets"]
    rel = client.get(f"/api/sessions/{sid}/relations").json()
    edge = next(e for e in rel["edges"] if {e["a"], e["b"]} == {"customer_churn", "tickets"})
    assert edge["best"]["a"]["column"] == "customer_id" and edge["strength"] == "strong"
    assert any("customer_id" in line for line in rel["summary"])
    again = client.post(f"/api/sessions/{sid}/relations").json()
    assert again["edges"][0]["best"]["a"]["column"] == edge["best"]["a"]["column"]
    # offline mode answers the question from the same numbers
    events = chat(client, sid, "how are the datasets related?")
    text = "".join(d["text"] for n, d in events if n == "text_delta")
    assert "customer_id" in text and "pd.merge" in text
    report = client.get(f"/api/sessions/{sid}/report?print=1").text
    assert '"relations"' in report and "Render.relations" in report


def test_the_report_exports_as_pdf_and_slides(client, sid):
    assert client.post(f"/api/sessions/{sid}/export", json={"format": "pdf"}).status_code == 400
    client.post(f"/api/sessions/{sid}/sample", json={"name": "customer_churn.csv"})
    chat(client, sid, "profile the data")
    chat(client, sid, "histogram of age")
    r = client.post(f"/api/sessions/{sid}/export", json={"format": "pdf", "turns": [2], "title": "Age"})
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert r.headers["content-disposition"] == 'attachment; filename="age.pdf"'
    assert b"/Subtype /Image" in r.content                     # the histogram is in it
    r = client.post(f"/api/sessions/{sid}/export", json={"format": "pptx", "with_overview": True})
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert r.headers["content-disposition"].endswith('.pptx"')
    assert client.post(f"/api/sessions/{sid}/export", json={"format": "pdf", "turns": [9]}).status_code == 400
    assert client.post(f"/api/sessions/{sid}/export", json={"format": "docx"}).status_code == 400
    # the agent's own tool writes the same files; offline mode calls it for "make a pdf"
    events = chat(client, sid, "make a pdf of this")
    card = cards(events, "download")[0]
    assert card["file"] == "report_001.pdf" and "PDF" in card["label"]
    pdf = client.get(f"/api/sessions/{sid}/artifacts/{card['file']}")
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    events = chat(client, sid, "make slides")
    assert cards(events, "download")[0]["file"] == "report_002.pptx"


def test_chart_colours_are_a_session_setting(client, sid):
    assert client.get("/api/config").json()["palettes"] == ["single", "varied"]
    assert client.put(f"/api/sessions/{sid}/style", json={"palette": "varied"}).json() == {"palette": "varied"}
    assert client.get(f"/api/sessions/{sid}").json()["style"] == {"palette": "varied"}
    assert client.put(f"/api/sessions/{sid}/style", json={"palette": "rainbow"}).status_code == 400
    client.post(f"/api/sessions/{sid}/sample", json={"name": "customer_churn.csv"})
    events = chat(client, sid, "bar chart of contract")
    chart = cards(events, "chart")[0]
    assert client.get(f"/api/sessions/{sid}/artifacts/{chart['file']}").content[:4] == b"\x89PNG"
