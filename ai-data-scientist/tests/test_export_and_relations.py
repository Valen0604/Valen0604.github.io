"""
The pieces added for several datasets and for exports, tested on their own:

  * relations.build finds the join key between two tables and does not invent one
  * the Markdown reader turns what the agent writes into blocks
  * the PDF and the slide deck render from the same document
  * the plotting palette is the validated eight-hue order, used in fixed order
"""
from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analytics import plotting, relations
from app.export import document, markdown as md, pdf, slides

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"


# ------------------------------------------------------------------------- relations
@pytest.fixture(scope="module")
def tables(churn):
    rng = np.random.default_rng(3)
    ids = churn["customer_id"].dropna().unique()
    tickets = pd.DataFrame({
        "ticket_id": np.arange(1, 1501),
        "customer_id": rng.choice(ids, 1500),
        "opened": pd.date_range("2023-01-01", periods=1500, freq="8h"),
        "region": rng.choice(["North", "South", "East", "West"], 1500),
        "minutes": rng.integers(1, 90, 1500),
    })
    tickets.loc[:19, "customer_id"] = "C000000"              # 20 tickets with no customer
    plans = pd.DataFrame({"plan": ["Basic", "Standard", "Premium", "Enterprise"],
                          "price": [25, 55, 95, 250]})
    weather = pd.DataFrame({"day": pd.date_range("2024-01-01", periods=60),
                            "rain_mm": rng.random(60) * 10})
    return {"customer_churn": churn, "tickets": tickets, "plans": plans, "weather": weather}


def test_the_customer_id_links_churn_to_tickets(tables):
    rel = relations.build(tables)
    edge = next(e for e in rel["edges"] if {e["a"], e["b"]} == {"customer_churn", "tickets"})
    best = edge["best"]
    assert best["a"]["column"] == "customer_id" == best["b"]["column"]
    assert best["same_name"] and best["role"] == "key" and best["strength"] == "strong"
    # 25 duplicate rows were planted in the churn sample, so the key is nearly unique
    assert best["cardinality"] == "one-to-many" and best["a"]["key"] and not best["a"]["unique"]
    assert best["b"]["rows_matched"] == pytest.approx(1480 / 1500, abs=0.001)
    assert "C000000" in best["b"]["only_here"]
    assert "one customer_churn row matches many tickets rows" in best["explanation"]
    assert 'on="customer_id"' in best["merge"]
    # region is carried by both tables too, but as a dimension, ranked below the key
    region = next(l for l in edge["links"] if l["a"]["column"] == "region")
    assert region["role"] == "dimension" and region["cardinality"] == "many-to-many"


def test_a_lookup_table_links_through_its_category(tables):
    rel = relations.build(tables)
    edge = next(e for e in rel["edges"] if {e["a"], e["b"]} == {"customer_churn", "plans"})
    best = edge["best"]
    assert best["a"]["column"] == "plan" and best["cardinality"] in ("many-to-one", "one-to-many")
    # Enterprise is in the lookup table and never in the data
    lookup = best["a"] if best["a"]["dataset"] == "plans" else best["b"]
    assert lookup["rows_matched"] == 0.75 and lookup["only_here"] == ["Enterprise"]


def test_unrelated_data_is_not_linked_by_chance(tables):
    rel = relations.build(tables)
    assert "weather" in rel["unlinked"]
    # small integer columns (minutes 1 to 90, price, age) must not be read as keys
    for e in rel["edges"]:
        for l in e["links"]:
            assert not {l["a"]["column"], l["b"]["column"]} & {"minutes", "price", "age"}


def test_the_summary_and_dimensions_are_written(tables):
    rel = relations.build(tables)
    text = "\n".join(rel["summary"])
    assert "customer_churn and tickets link through customer_id" in text
    assert "weather shares no column" in text
    assert {"column": "region", "datasets": ["customer_churn", "tickets"], "kinds": ["categorical"]} \
        in rel["dimensions"]
    assert relations.build({"only": tables["plans"]})["summary"][0].startswith("Only one dataset")


def test_same_name_with_no_shared_values_is_reported_not_hidden():
    a = pd.DataFrame({"id": [f"A{i}" for i in range(40)], "x": [i % 5 for i in range(40)]})
    b = pd.DataFrame({"id": list(range(40)), "y": [i % 7 for i in range(40)]})
    rel = relations.build({"a": a, "b": b})
    # "A7" against 7: the same column name with nothing in common is the classic format
    # mismatch, so it is shown as a dashed line rather than hidden
    link = rel["edges"][0]["best"]
    assert link["strength"] == "none" and "share no values" in link["explanation"]
    assert link["merge"] is None and rel["summary"][0].endswith("(none).")
    # x and y are small repeating integers: never a key, never compared
    assert all(l["a"]["column"] == "id" for e in rel["edges"] for l in e["links"])


def test_the_sample_files_made_for_the_tab_link_as_documented():
    from app.analytics import loading
    load = lambda name: next(iter(loading.read_any(SAMPLE / name).values()))[0]
    rel = relations.build({"customer_churn": load("customer_churn.csv"),
                           "support_tickets": load("support_tickets.csv"),
                           "store_sales": load("store_sales.csv"),
                           "store_details": load("store_details.csv")})
    pairs = {frozenset((e["a"], e["b"])): e for e in rel["edges"]}
    tickets = pairs[frozenset(("customer_churn", "support_tickets"))]
    assert tickets["strength"] == "strong" and tickets["best"]["cardinality"] == "one-to-many"
    t_side = tickets["best"]["b"] if tickets["best"]["b"]["dataset"] == "support_tickets" else tickets["best"]["a"]
    assert 0.94 <= t_side["rows_matched"] <= 0.97           # 60 orphans and 45 lower-case ids
    assert any(v.startswith("C2000") or v.startswith("c") for v in t_side["only_here"])
    stores = pairs[frozenset(("store_sales", "store_details"))]
    assert stores["best"]["a"]["column"] == "store" and stores["strength"] == "strong"
    detail = stores["best"]["b"] if stores["best"]["b"]["dataset"] == "store_details" else stores["best"]["a"]
    assert detail["rows_matched"] == 0.8 and detail["only_here"] == ["Harbor"]
    assert not (pairs.keys() & {frozenset(("customer_churn", "store_sales")),
                                frozenset(("support_tickets", "store_details"))})


# -------------------------------------------------------------------------- markdown
SAMPLE_MD = """## Findings

Month-to-month customers churn **most** (41%); see `contract`.

- contract: strongest
- tenure: newer customers leave more
  (continued)

| group | n |
|---|---:|
| Month-to-month | 1,600 |

```python
df.head()
```

![Churn by contract](chart_001.png)

```followups
["q1", "q2"]
```
"""


def test_markdown_becomes_blocks_and_follow_ups_are_dropped():
    blocks = md.parse(SAMPLE_MD)
    assert [b["type"] for b in blocks] == ["heading", "paragraph", "list", "table", "code", "image"]
    runs = blocks[1]["runs"]
    assert [r["text"] for r in runs if r["bold"]] == ["most"]
    assert [r["text"] for r in runs if r["code"]] == ["contract"]
    assert md.plain(blocks[2]["items"][1]["runs"]) == "tenure: newer customers leave more (continued)"
    assert md.plain(blocks[3]["rows"][0][1]) == "1,600"
    assert blocks[5] == {"type": "image", "file": "chart_001.png", "title": "Churn by contract"}
    assert "q1" not in md.text_of(blocks)


def test_cards_become_blocks():
    profile = {"name": "d", "rows": 10, "columns_count": 2, "missing_cells_share": 0.1,
               "duplicate_rows": 0, "warnings": [{"level": "high", "column": "age", "message": "999"}]}
    blocks = document.card_blocks({"type": "profile", "profile": profile}, with_code=False)
    assert blocks[0]["type"] == "paragraph" and "10 rows" in md.plain(blocks[0]["runs"])
    assert blocks[1]["type"] == "list" and "999" in md.plain(blocks[1]["items"][0]["runs"])
    code = {"type": "code", "code": "x = 1", "purpose": "set x", "stdout": "", "error": None, "changes": []}
    assert document.card_blocks(code, with_code=False) == []
    assert [b["type"] for b in document.card_blocks(code, with_code=True)] == ["paragraph", "code"]
    table = {"type": "table", "columns": list("abcdefghij"), "rows": [list(range(10))] * 30,
             "total_rows": 30, "total_columns": 10}
    blocks = document.card_blocks(table, with_code=False)
    assert len(blocks[0]["head"]) == 8 and len(blocks[0]["rows"]) == 25
    assert "25 of 30 rows and 8 of 10 columns" in md.plain(blocks[1]["runs"])


# ----------------------------------------------------------------------- renderers
@pytest.fixture(scope="module")
def doc(tmp_path_factory):
    folder = tmp_path_factory.mktemp("artifacts")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.bar(["a", "b"], [1, 2])
    fig.savefig(folder / "chart_001.png")
    plt.close(fig)
    return document.from_markdown("Churn report", SAMPLE_MD + "\n## Caveats\n\nSmall sample − see notes → next.",
                                  folder, charts=["chart_001.png", "missing.png"],
                                  datasets=[{"name": "customer_churn", "rows": 3025, "columns_count": 13}])


def test_the_document_has_sections_and_only_real_images(doc):
    assert [s["heading"] for s in doc["sections"]] == ["Findings", "Caveats"]
    assert list(doc["images"]) == ["chart_001.png"]
    assert doc["datasets"][0]["name"] == "customer_churn"


def test_the_pdf_renders(doc):
    data = pdf.render(doc)
    assert data[:5] == b"%PDF-" and len(data) > 20_000       # the chart is embedded
    assert b"/Title (Churn report)" in data
    assert data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") >= 1
    assert b"/Subtype /Image" in data                          # the chart
    assert b"DejaVuSans" in data                               # the font with the minus sign


def test_the_slides_render(doc):
    data = slides.render(doc)
    with zipfile.ZipFile(BytesIO(data)) as z:
        names = z.namelist()
        assert "ppt/presentation.xml" in names
        slide_files = [n for n in names if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
        # title, Findings, its table, its chart, Caveats
        assert len(slide_files) == 5
        assert any(n.startswith("ppt/media/") for n in names)
        xml = z.read("ppt/slides/slide2.xml").decode("utf-8")
        assert "Findings" in xml and "Month-to-month" in xml


# ------------------------------------------------------------------------- palette
def test_the_palette_is_the_validated_order_and_single_by_default(churn, tmp_path):
    assert plotting.PALETTE == ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4",
                                "#008300", "#6250d6", "#e34948"]
    plotting.set_style({"palette": "single"})
    assert plotting.series_color() == plotting.PRIMARY == plotting.series_color()
    assert plotting.category_colors(["a", "b"]) is None
    plotting.set_style({"palette": "varied"})
    first, second = plotting.series_color(), plotting.series_color()
    assert first != second and {first, second} <= set(plotting.PALETTE)
    assert plotting.category_colors(["a", "Other"]) == [plotting.PALETTE[0], plotting.OTHER]
    plotting.set_style({"palette": "nonsense"})
    assert plotting.STYLE["palette"] == "varied"
    for spec in ({"chart_type": "bar", "x": "contract"}, {"chart_type": "box", "x": "plan", "y": "age"},
                 {"chart_type": "histogram", "x": "age"}):
        out = tmp_path / (spec["chart_type"] + ".png")
        plotting.make_chart(churn, spec, out)
        assert out.stat().st_size > 5000
    plotting.set_style({"palette": "single"})
