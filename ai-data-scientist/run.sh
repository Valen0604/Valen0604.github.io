#!/usr/bin/env bash
# Start the app on macOS and Linux. Run ./setup.sh once first.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "The project is not set up yet. Run ./setup.sh first."
  exit 1
fi
exec .venv/bin/python -m app "$@"
