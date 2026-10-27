"""
Check that the API key in .env works, before starting the app.

    .venv/Scripts/python scripts/check_key.py        (Windows)
    .venv/bin/python scripts/check_key.py            (macOS, Linux)

Sends one very small request. Costs a fraction of a cent.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic  # noqa: E402

from app.agent.loop import explain  # noqa: E402
from app.config import ENV_FILE, SETTINGS  # noqa: E402


def main() -> int:
    if not SETTINGS.live:
        print(f"No key found.\nOpen {ENV_FILE}\nand add the line:  ANTHROPIC_API_KEY=sk-ant-...")
        return 1

    key = SETTINGS.api_key
    print(f"Key found: {key[:10]}...{key[-4:]}  ({len(key)} characters)")
    print(f"Model:     {SETTINGS.model}")

    client = anthropic.Anthropic(api_key=key)
    try:
        response = client.messages.create(
            model=SETTINGS.model,
            max_tokens=200,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        )
    except anthropic.APIError as e:
        print("\nThe request failed.")
        print(explain(e, SETTINGS))
        return 1

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    u = response.usage
    cost = (u.input_tokens * SETTINGS.price_input + u.output_tokens * SETTINGS.price_output) / 1e6
    print(f"Reply:     {text}")
    print(f"Tokens:    {u.input_tokens} in, {u.output_tokens} out  (about ${cost:.5f})")
    print("\nThe key works. Start the app with run.bat or ./run.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
