"""
Shared test setup.

Tests never call the real API. The key is blanked before anything imports the settings,
so the app starts in offline mode no matter what is in your .env.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["ADS_WORKSPACE"] = str(ROOT / "workspace" / "_tests")

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

SAMPLE = ROOT / "data" / "sample"


@pytest.fixture(scope="session", autouse=True)
def _workspace():
    work = Path(os.environ["ADS_WORKSPACE"])
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    if not (SAMPLE / "customer_churn.csv").exists():
        sys.path.insert(0, str(ROOT / "scripts"))
        import make_sample_data
        make_sample_data.main()
    yield
    shutil.rmtree(work, ignore_errors=True)


@pytest.fixture(scope="session")
def churn() -> pd.DataFrame:
    from app.analytics import loading
    (df, _), = loading.read_any(SAMPLE / "customer_churn.csv").values()
    return df


@pytest.fixture(scope="session")
def sales() -> pd.DataFrame:
    from app.analytics import loading
    (df, _), = loading.read_any(SAMPLE / "store_sales.csv").values()
    return df


@pytest.fixture()
def session():
    """A real session with a real analysis worker and the churn sample loaded."""
    from app.config import SETTINGS
    from app.sessions import SessionStore
    store = SessionStore(SETTINGS)
    s = store.create()
    target = s.workspace / "uploads" / "customer_churn.csv"
    target.write_bytes((SAMPLE / "customer_churn.csv").read_bytes())
    loaded = s.engine.call("load_file", timeout_s=120, path=str(target),
                           original_name="customer_churn.csv")["datasets"]
    s.pending_briefs.append(loaded[0]["brief"])
    yield s
    store.close_all()
