"""
End-to-end check of the analysis engine, with no web server and no LLM.

    python tests/smoke_engine.py

Prints what each operation returns. Useful when changing anything in app/analytics/.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analytics.engine import Engine, EngineError  # noqa: E402


def show(title: str, obj, limit: int = 900) -> None:
    text = obj if isinstance(obj, str) else json.dumps(obj, indent=1, default=str)
    print(f"\n=== {title}\n{text[:limit]}{' ...' if len(text) > limit else ''}")


def main() -> None:
    work = ROOT / "workspace" / "_smoke"
    shutil.rmtree(work, ignore_errors=True)
    engine = Engine(work, default_timeout_s=60)
    sample = ROOT / "data" / "sample"
    try:
        t = time.time()
        r = engine.call("load_file", path=str(sample / "customer_churn.csv"),
                        original_name="customer_churn.csv")
        show(f"load ({time.time() - t:.1f}s)", r["datasets"][0]["brief"], 3000)

        r = engine.call("chart", spec={"chart_type": "bar", "x": "contract", "y": "tenure_months",
                                       "agg": "mean"})
        show("chart", r)

        r = engine.call("stat_test", spec={"test": "auto", "x": "contract", "y": "churned"})
        show("stat test", r["plain"])

        code = (
            "clean = df.drop_duplicates().copy()\n"
            "clean['region'] = clean['region'].str.strip().str.title()\n"
            "clean.loc[clean['age'] > 120, 'age'] = np.nan\n"
            "df = clean\n"
            "print(df['region'].value_counts())\n"
            "df.groupby('contract')['churned'].apply(lambda s: (s == 'Yes').mean()).round(3)\n"
        )
        r = engine.call("exec", code=code)
        show("exec", {k: v for k, v in r.items() if k != "tables"})

        r = engine.call("exec", code="import subprocess\nsubprocess.run('dir')")
        show("exec blocked", r)
    except EngineError as e:
        show(f"EngineError [{e.kind}]", str(e))

    try:
        t = time.time()
        r = engine.call("train", timeout_s=300, spec={"target": "churned"})
        show(f"train with the leaky column ({time.time() - t:.1f}s)",
             {"headline": r["headline"], "warnings": r["warnings"],
              "dropped": r["features_dropped"]}, 2500)

        t = time.time()
        r = engine.call("train", timeout_s=300,
                        spec={"target": "churned", "exclude": ["cancellation_reason"]})
        show(f"train without it ({time.time() - t:.1f}s)",
             {"headline": r["headline"], "cv": r["cross_validation"],
              "importance": r["importance"][:8], "warnings": r["warnings"]}, 3500)

        r = engine.call("predict", model_id=r["model_id"])
        show("predict", {k: v for k, v in r.items() if k != "table"})

        r = engine.call("exec", code="import time\nwhile True:\n    time.sleep(1)", timeout_s=4)
    except EngineError as e:
        show(f"EngineError [{e.kind}]", str(e))

    r = engine.call("list")
    show("datasets after the restart", [(d["name"], d["rows"], d["source"]) for d in r["datasets"]])

    r = engine.call("load_file", path=str(sample / "store_sales.csv"), original_name="store_sales.csv")
    r = engine.call("train", timeout_s=300,
                    spec={"target": "units_sold", "time_column": "date", "exclude": ["revenue"]})
    show("time-ordered regression", {"headline": r["headline"], "split": r["split"],
                                     "importance": r["importance"][:6],
                                     "warnings": r["warnings"]}, 2500)
    engine.close()
    print("\nartifacts:", sorted(p.name for p in (work / "artifacts").iterdir()))


if __name__ == "__main__":
    main()
