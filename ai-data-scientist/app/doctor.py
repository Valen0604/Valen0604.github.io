"""
Self-check: says whether this computer can run the app, and why not if it cannot.

    python -m app --check

Each check prints one line, OK or FAIL, with the reason and what to do. It runs the same
steps the app runs at start: load the settings, import the analysis libraries, bind the
port, start one analysis worker and talk to it. Nothing calls the API.
"""
from __future__ import annotations

import importlib
import platform
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARIES = ["fastapi", "uvicorn", "pandas", "numpy", "scipy", "sklearn", "statsmodels",
             "matplotlib", "seaborn", "pyarrow", "openpyxl", "reportlab", "pptx", "anthropic"]


def port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def run(verbose: bool = True) -> dict:
    """Run every check. Returns {"ok": bool, "problems": [str], "notes": [str]}."""
    problems: list[str] = []
    notes: list[str] = []

    def say(ok: bool, text: str, fix: str | None = None) -> None:
        if verbose:
            print(("  OK    " if ok else "  FAIL  ") + text)
            if fix and not ok:
                print("        " + fix)
        if not ok:
            problems.append(text + (" " + fix if fix else ""))

    # 1. Python
    v = sys.version_info
    say(v >= (3, 10), f"Python {v.major}.{v.minor}.{v.micro} on {platform.system()} "
                      f"{platform.machine()} ({sys.executable})",
        "Python 3.10 or newer is required. Run setup again with a newer Python.")
    in_venv = Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()
    if not in_venv:
        notes.append("Not running from the project's .venv. Start with run.sh or run.bat so "
                     "the packages installed by setup are the ones used.")

    # 2. Settings and .env
    try:
        from .config import ENV_FILE, SETTINGS
        say(True, f"Settings loaded. {'API key found' if SETTINGS.live else 'No API key (offline demo mode)'}; "
                  f"workspace {SETTINGS.workspace}")
        if not ENV_FILE.exists():
            notes.append(f"No .env file at {ENV_FILE}. Setup creates one; the app runs without it.")
    except Exception as e:  # pragma: no cover - only on a broken install
        say(False, f"Settings could not load: {type(e).__name__}: {e}", "Run setup again.")
        return {"ok": False, "problems": problems, "notes": notes}

    # 3. Libraries, with timing: the first import of matplotlib on a new computer builds a
    #    font cache and can take a minute. That is the usual "it hangs on a Mac".
    for name in LIBRARIES:
        t = time.time()
        try:
            importlib.import_module(name)
            took = time.time() - t
            say(True, f"{name} imports ({took:.1f}s)" if took > 2 else f"{name} imports")
            if name == "matplotlib" and took > 10:
                notes.append("matplotlib took a while: it builds a font cache the first time. "
                             "The next start will be fast.")
        except Exception as e:
            say(False, f"{name} failed to import: {type(e).__name__}: {e}",
                "Run setup again (bash setup.sh or .\\setup.bat) to reinstall the packages.")

    # 4. Static files and samples
    static = Path(__file__).parent / "static"
    for f in ("index.html", "app.js", "render.js", "styles.css"):
        say((static / f).is_file(), f"static file {f}", "The repository is incomplete. Pull it again.")
    samples = ROOT / "data" / "sample"
    say((samples / "customer_churn.csv").is_file(), "sample data present",
        "Run: python scripts/make_sample_data.py")

    # 5. Port
    free = port_free(SETTINGS.host, SETTINGS.port)
    say(free, f"port {SETTINGS.port} on {SETTINGS.host} is free",
        f"Something is already listening there, probably an earlier copy of this app. Open "
        f"http://{SETTINGS.host}:{SETTINGS.port} in the browser, or stop it, or set ADS_PORT=8001 "
        "in .env.")

    # 6. One analysis worker, end to end
    try:
        from .analytics.engine import Engine
        work = SETTINGS.workspace / "_doctor"
        work.mkdir(parents=True, exist_ok=True)
        t = time.time()
        engine = Engine(work, default_timeout_s=60)
        engine.call("list")
        engine.close()
        say(True, f"analysis worker starts and answers ({time.time() - t:.1f}s)")
    except Exception as e:
        say(False, f"the analysis worker did not start: {type(e).__name__}: {e}",
            "Send this message to the team. It is the process that runs the analysis.")

    ok = not problems
    if verbose:
        print()
        print("Everything needed to run the app is in place." if ok
              else f"{len(problems)} problem(s). Fix the FAIL lines above, then try again.")
        for n in notes:
            print("  note  " + n)
    return {"ok": ok, "problems": problems, "notes": notes}


if __name__ == "__main__":
    raise SystemExit(0 if run()["ok"] else 1)
