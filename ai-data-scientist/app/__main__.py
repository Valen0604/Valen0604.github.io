"""
Start the app:   python -m app              (run.sh / run.bat do this for you)
Self-check:      python -m app --check      says what is wrong when it will not start
Options:         --no-browser               do not open a browser tab

The browser opens only once the server answers, so the tab never shows "page not found"
while the analysis libraries are still loading.

The `if __name__ == "__main__"` guard matters. The analysis worker is a child process, and
on Windows and macOS a child process re-imports this file. Without the guard every worker
would try to start its own web server.
"""
from __future__ import annotations

import sys
import threading
import time
import urllib.request
import webbrowser

READY_TIMEOUT_S = 180


def _wait_until_ready(url: str, open_browser: bool) -> None:
    """Poll the server; print when it answers, and open the browser then."""
    started = time.time()
    told_slow = False
    while True:
        try:
            with urllib.request.urlopen(url + "/api/config", timeout=2) as r:
                if r.status == 200:
                    break
        except Exception:
            pass
        waited = time.time() - started
        if waited > 20 and not told_slow:
            told_slow = True
            print("  Still loading. The first start on a new computer builds matplotlib's")
            print("  font cache, which can take a minute. If nothing happens after that,")
            print("  stop with Ctrl+C and run:   python -m app --check")
        if waited > READY_TIMEOUT_S:
            print(f"  The server has not answered after {READY_TIMEOUT_S} seconds.")
            print("  Stop with Ctrl+C and run:   python -m app --check")
            return
        time.sleep(0.5)
    print(f"  Ready ({time.time() - started:.0f}s). Open:   {url}")
    if open_browser:
        webbrowser.open(url)


def main() -> None:
    # Line-buffered output, so the Starting and Ready lines show at once even when the
    # output goes through a pipe or an IDE terminal.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    if "--check" in sys.argv:
        from .doctor import run
        raise SystemExit(0 if run()["ok"] else 1)

    from .config import ENV_FILE, SETTINGS
    from .doctor import port_free

    url = f"http://{SETTINGS.host}:{SETTINGS.port}"
    line = "-" * 66
    print(line)
    print("  AI Data Scientist")
    if SETTINGS.live:
        print(f"  Model:  {SETTINGS.model}   effort: {SETTINGS.effort}")
    else:
        print("  Mode:   OFFLINE DEMO. No API key found.")
        print(f"          Put your key in {ENV_FILE}")
        print("          as   ANTHROPIC_API_KEY=sk-ant-...   and restart.")
    print("  Stop:   Ctrl+C")
    print(line)

    if not port_free(SETTINGS.host, SETTINGS.port):
        print(f"  Port {SETTINGS.port} is already in use, probably by an earlier copy of this app.")
        print(f"  Open {url} in the browser, or stop the other copy, or set ADS_PORT=8001 in .env.")
        raise SystemExit(1)

    print("  Starting. Loading the analysis libraries takes a few seconds ...")
    threading.Thread(target=_wait_until_ready, args=(url, "--no-browser" not in sys.argv),
                     daemon=True).start()

    import uvicorn
    uvicorn.run("app.main:app", host=SETTINGS.host, port=SETTINGS.port, log_level="warning")


if __name__ == "__main__":
    main()
