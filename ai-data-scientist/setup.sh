#!/usr/bin/env bash
# One-time setup on macOS and Linux. Creates the project's own Python in .venv and
# installs everything into it. Nothing is installed into your system Python.
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for candidate in python3.12 python3.13 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10 or newer is required. Install it from https://www.python.org/downloads/"
  exit 1
fi

[ -x .venv/bin/python ] || { echo "Creating .venv with $PY ..."; "$PY" -m venv .venv; }

echo "Installing packages. This takes a few minutes the first time ..."
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -r requirements.txt -q

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env. Open it and paste your API key after ANTHROPIC_API_KEY="
fi
[ -f data/sample/customer_churn.csv ] || .venv/bin/python scripts/make_sample_data.py

echo
echo "Setup is complete. Start the app with:   bash run.sh"
