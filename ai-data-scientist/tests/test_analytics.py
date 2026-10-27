"""
The analysis engine, tested against data with known answers.

The sample data was built with specific relationships and specific flaws (see
data/sample/README.md). These tests check that the engine finds them.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from app.analytics import guard, loading, modeling, plotting, profiling, stats
from app.analytics import schema as S


# ------------------------------------------------------------------------------ loading
def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_leading_zeros_are_kept(tmp_path):
    p = write(tmp_path, "z.csv", "zip,amount\n00501,10\n02134,20\n10001,30\n")
    (df, notes), = loading.read_any(p).values()
    assert list(df["zip"]) == ["00501", "02134", "10001"]
    assert pd.api.types.is_numeric_dtype(df["amount"])
    assert any("leading zeros" in n for n in notes)


def test_money_percent_and_brackets_become_numbers(tmp_path):
    p = write(tmp_path, "m.csv", 'price,growth,net\n"$1,200.50",12%,(300)\n$80,5%,150\n$9,-3%,20\n')
    (df, notes), = loading.read_any(p).values()
    assert df["price"].tolist() == [1200.5, 80.0, 9.0]
    assert df["growth"].tolist() == [12, 5, -3]
    assert df["net"].tolist() == [-300, 150, 20]
    assert any("percent" in n for n in notes)


def test_semicolon_files_and_placeholders(tmp_path):
    p = write(tmp_path, "s.csv", "a;b;c\n1;x;N/A\n2;y;5\n3;;7\n")
    (df, notes), = loading.read_any(p).values()
    assert df.shape == (3, 3)
    assert df["c"].isna().sum() == 1 and df["b"].isna().sum() == 1
    assert any("semicolon" in n for n in notes)


def test_dates_are_parsed_but_plain_text_is_not(tmp_path):
    rows = "\n".join(f"2024-01-{d:02d},note number {d}" for d in range(1, 29))
    (df, _), = loading.read_any(write(tmp_path, "d.csv", "when,what\n" + rows + "\n")).values()
    assert pd.api.types.is_datetime64_any_dtype(df["when"])
    assert not pd.api.types.is_datetime64_any_dtype(df["what"])


def test_excel_gives_one_dataset_per_sheet(tmp_path):
    p = tmp_path / "book.xlsx"
    with pd.ExcelWriter(p) as w:
        pd.DataFrame({"a": [1, 2]}).to_excel(w, sheet_name="First", index=False)
        pd.DataFrame({"b": [3, 4]}).to_excel(w, sheet_name="Second", index=False)
    out = loading.read_any(p)
    assert set(out) == {"book__first", "book__second"}


def test_json_records_under_a_key(tmp_path):
    p = write(tmp_path, "j.json", json.dumps({"meta": 1, "rows": [{"a": 1}, {"a": 2}]}))
    (df, notes), = loading.read_any(p).values()
    assert df["a"].tolist() == [1, 2] and any('"rows"' in n for n in notes)


@pytest.mark.parametrize("name,text", [("e.csv", ""), ("h.csv", "a,b\n"), ("x.exe", "hi")])
def test_bad_files_give_a_clear_error(tmp_path, name, text):
    with pytest.raises(loading.LoadError):
        loading.read_any(write(tmp_path, name, text))


# ---------------------------------------------------------------------------- profiling
def test_column_kinds(churn):
    k = S.kinds(churn)
    assert k["customer_id"] == S.ID
    assert k["signup_date"] == S.DATETIME
    assert k["monthly_charge"] == S.NUMERIC
    assert k["contract"] == S.CATEGORICAL
    assert k["churned"] == S.BOOLEAN


def test_profile_finds_every_planted_flaw(churn):
    p = profiling.profile(churn, "churn")
    text = " | ".join(f'{w["column"]}: {w["message"]}' for w in p["warnings"])
    assert "999" in text and "age" in text                        # placeholder value
    assert "written in more than one way" in text                 # North / north / NORTH
    assert "exact copies" in text                                 # duplicate rows
    assert "identifier" in text                                   # customer_id
    assert "not random" in text and "monthly_charge" in text      # gaps depend on age
    assert "computed" in text and "total_charges" in text         # monthly x tenure
    assert p["duplicate_rows"] == 25


def test_computed_columns_are_found(churn, sales):
    found = {d["column"]: d for d in profiling.derived_columns(churn)}
    assert set(found["total_charges"]["columns"]) == {"monthly_charge", "tenure_months",
                                                      "total_charges"}
    trio = [set(d["columns"]) for d in profiling.derived_columns(sales)]
    assert {"units_sold", "unit_price", "revenue"} in trio


def test_unrelated_columns_are_not_called_computed():
    rng = np.random.default_rng(1)
    df = pd.DataFrame(rng.normal(size=(400, 5)), columns=list("abcde"))
    assert profiling.derived_columns(df) == []


def test_profile_is_valid_json_with_no_nan(churn):
    text = json.dumps(profiling.profile(churn, "churn"), allow_nan=False)
    assert "NaN" not in text


def test_a_price_column_containing_99_is_not_a_placeholder():
    s = pd.Series([19, 29, 49, 79, 99, 99, 59, 39, 89, 69], name="price")
    assert profiling.placeholder_values(s) == []


# -------------------------------------------------------------------------------- stats
def test_tests_are_chosen_from_column_types(churn):
    assert stats.run_test(churn, {"x": "contract", "y": "churned"})["test"].startswith("chi")
    assert stats.run_test(churn, {"x": "tenure_months", "y": "total_charges"})["test"] == "correlation"
    assert "t-test" in stats.run_test(churn, {"x": "churned", "y": "tenure_months"})["test"]
    assert "ANOVA" in stats.run_test(churn, {"x": "contract", "y": "monthly_charge"})["test"]


def test_real_effect_is_found_and_absent_effect_is_not(churn):
    real = stats.run_test(churn, {"x": "contract", "y": "churned"})
    none = stats.run_test(churn, {"x": "region", "y": "churned"})
    assert real["significant"] and real["cramers_v"] > 0.2
    assert none["cramers_v"] < 0.1


def test_every_result_has_an_effect_size_and_a_sentence(churn):
    for spec in ({"x": "contract", "y": "churned"}, {"x": "churned", "y": "tenure_months"},
                 {"x": "contract", "y": "monthly_charge"},
                 {"x": "tenure_months", "y": "total_charges"}):
        r = stats.run_test(churn, spec)
        assert r["plain"]
        assert any(k in r for k in ("cohens_d", "eta_squared", "cramers_v", "spearman_r"))


def test_unknown_column_names_the_real_ones(churn):
    with pytest.raises(stats.StatError, match="contract"):
        stats.run_test(churn, {"x": "contrct", "y": "churned"})


# ------------------------------------------------------------------------------- charts
@pytest.mark.parametrize("spec", [
    {"chart_type": "histogram", "x": "monthly_charge"},
    {"chart_type": "histogram", "x": "monthly_charge", "color": "contract"},
    {"chart_type": "bar", "x": "contract"},
    {"chart_type": "bar", "x": "region", "y": "monthly_charge", "agg": "mean", "color": "plan"},
    {"chart_type": "line", "x": "signup_date", "y": "monthly_charge"},
    {"chart_type": "scatter", "x": "tenure_months", "y": "total_charges", "color": "contract"},
    {"chart_type": "box", "y": "tenure_months", "x": "contract"},
    {"chart_type": "heatmap"},
    {"chart_type": "missing"},
    {"chart_type": "pairs", "columns": ["age", "tenure_months", "monthly_charge"]},
])
def test_every_chart_type_draws(churn, tmp_path, spec):
    out = tmp_path / "c.png"
    r = plotting.make_chart(churn, spec, out)
    assert out.stat().st_size > 5000
    assert r["title"]
    json.dumps(r, allow_nan=False)


def test_chart_errors_are_instructions(churn, tmp_path):
    with pytest.raises(plotting.ChartError, match="Columns are"):
        plotting.make_chart(churn, {"chart_type": "bar", "x": "nope"}, tmp_path / "c.png")
    with pytest.raises(plotting.ChartError, match="must be one of"):
        plotting.make_chart(churn, {"chart_type": "donut"}, tmp_path / "c.png")


# ----------------------------------------------------------------------------- modeling
@pytest.fixture(scope="module")
def churn_model(churn, tmp_path_factory):
    return modeling.train(churn, {"target": "churned"}, tmp_path_factory.mktemp("m"), "model_001")


def test_leak_through_missingness_is_reported(churn_model):
    r, _ = churn_model
    assert any("cancellation_reason" in w and "Leakage" in w for w in r["warnings"])
    assert "cancellation_reason" not in r["features_used"]


def test_identifier_is_left_out(churn_model):
    r, _ = churn_model
    assert "customer_id" not in r["features_used"]
    assert any(d["column"] == "customer_id" for d in r["features_dropped"])


def test_model_beats_baseline_by_a_believable_margin(churn_model):
    r, _ = churn_model
    assert r["best_model"] != "baseline"
    assert 0.70 < r["test_metrics"]["roc_auc"] < 0.95       # good, and not suspiciously so
    assert r["baseline_test_metrics"]["balanced_accuracy"] == 0.5


def test_true_drivers_rank_above_noise(churn_model):
    r, _ = churn_model
    rank = {d["feature"]: i for i, d in enumerate(r["importance"])}
    assert r["importance"][0]["feature"] == "contract"
    assert rank["contract"] < rank["region"]
    assert rank["support_tickets"] < rank["region"]


def test_a_leaky_feature_in_the_model_is_flagged(churn, tmp_path):
    leaky = churn.copy()
    leaky["exit_code"] = np.where(leaky["churned"] == "Yes", 1.0, 0.0) + \
        np.random.default_rng(0).normal(0, 0.01, len(leaky))
    r, _ = modeling.train(leaky, {"target": "churned"}, tmp_path, "model_002")
    assert any(s["column"] == "exit_code" for s in r["leakage_suspects"])
    assert any("exit_code" in w for w in r["warnings"])


def test_a_feature_computed_from_the_target_is_flagged(sales, tmp_path):
    r, _ = modeling.train(sales, {"target": "units_sold", "time_column": "date",
                                  "models": ["ridge_regression"]}, tmp_path, "model_005")
    assert any(s["column"] == "revenue" for s in r["leakage_suspects"])
    assert any("revenue" in w and "Leakage" in w for w in r["warnings"])


def test_time_order_is_respected(sales, tmp_path):
    r, _ = modeling.train(sales, {"target": "units_sold", "time_column": "date",
                                  "exclude": ["revenue"]}, tmp_path, "model_003")
    assert r["task"] == "regression"
    assert "later period" in r["split"]
    assert r["test_metrics"]["rmse"] < r["baseline_test_metrics"]["rmse"]


def test_random_split_on_dated_data_warns(sales, tmp_path):
    r, _ = modeling.train(sales, {"target": "units_sold", "exclude": ["revenue"],
                                  "models": ["ridge_regression"]}, tmp_path, "model_004")
    assert any("time_column" in w for w in r["warnings"])


def test_predictions_match_the_training_rows(churn, churn_model):
    _, bundle = churn_model
    scored, summary = modeling.predict(churn.head(200), bundle)
    assert len(scored) == 200 and "predicted_churned" in scored
    assert set(scored["predicted_churned"]) <= {"Yes", "No"}
    assert scored["probability_Yes"].between(0, 1).all()


def test_prediction_needs_the_training_columns(churn, churn_model):
    _, bundle = churn_model
    with pytest.raises(modeling.ModelError, match="contract"):
        modeling.predict(churn.drop(columns=["contract"]), bundle)


@pytest.mark.parametrize("spec,message", [
    ({"target": "nope"}, "target must be a column"),
    ({"target": "churned", "features": ["ghost"]}, "No column named"),
    ({"target": "churned", "test_size": 0.9}, "test_size"),
    ({"target": "signup_date"}, "date"),
])
def test_bad_requests_explain_themselves(churn, tmp_path, spec, message):
    with pytest.raises(modeling.ModelError, match=message):
        modeling.train(churn, spec, tmp_path, "model_x")


def test_too_few_rows_is_refused(churn, tmp_path):
    with pytest.raises(modeling.ModelError, match="rows"):
        modeling.train(churn.head(30), {"target": "monthly_charge"}, tmp_path, "model_x")


# -------------------------------------------------------------------------------- guard
@pytest.mark.parametrize("code", [
    "import subprocess", "import os\nos.system('dir')", "from os import remove",
    "import socket", "import requests", "eval('1+1')", "exec('x=1')", "__import__('os')",
    "open('../../.env').read()", "().__class__.__bases__[0].__subclasses__()",
    "import os\nos.environ['ANTHROPIC_API_KEY']", "getattr(df, 'x')", "import shutil",
])
def test_dangerous_code_is_refused(code):
    assert guard.check(code), code


@pytest.mark.parametrize("code", [
    "df.groupby('a')['b'].mean()",
    "import numpy as np\nfrom sklearn.linear_model import LinearRegression",
    "import os\nos.path.join('a', 'b')",
    "fig, ax = plt.subplots()\nax.plot([1, 2, 3])",
    "import statsmodels.formula.api as smf\nsmf.ols('y ~ x', data=df).fit().summary()",
    "df['ratio'] = df['a'] / df['b']\nlen(df)",
])
def test_ordinary_analysis_code_is_allowed(code):
    assert guard.check(code) == [], code


def test_syntax_errors_are_reported_with_a_line():
    assert "line 1" in guard.check("x = (1 +")[0]
