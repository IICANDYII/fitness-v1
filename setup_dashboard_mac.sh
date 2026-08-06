#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BOOTSTRAP="$(command -v python3.12)"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BOOTSTRAP="$(command -v python3.11)"
else
  echo "Python 3.11+ is required. Install it with Homebrew:"
  echo "  brew install python@3.12"
  exit 1
fi

cd "$PROJECT_DIR"

echo "Using Python: $("$PYTHON_BOOTSTRAP" --version 2>&1) ($PYTHON_BOOTSTRAP)"

if [[ ! -d ".venv" ]]; then
  "$PYTHON_BOOTSTRAP" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-mac.txt

echo
echo "Setup complete."
echo "Start services with:"
echo "  ./start_dashboard_mac.sh"
