#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
if [[ -x "$PROJECT_DIR/.venv/bin/python" && -z "${PYTHON_BIN:-}" ]]; then
  PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
elif [[ -n "${PYTHON_BIN:-}" ]]; then
  : # Respect explicit PYTHON_BIN from the caller.
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.12)"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.11)"
elif command -v python3.10 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.10)"
else
  PYTHON_BIN="$(command -v python3)"
fi
LOG_DIR="$PROJECT_DIR/logs"
HOST="${HOST:-127.0.0.1}"

export PYTHONPATH="$PROJECT_DIR"
export MPLCONFIGDIR="$LOG_DIR/matplotlib"

# Bypass system proxy for local development and direct API gateway access.
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
export NO_PROXY="*"

mkdir -p "$LOG_DIR"
mkdir -p "$MPLCONFIGDIR"

UVICORN_RELOAD_ARGS=""
if [[ "${DASHBOARD_RELOAD:-0}" == "1" ]]; then
  UVICORN_RELOAD_ARGS="--reload"
fi

clear_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "  Clearing port $port: $pids"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local tries="${3:-30}"
  for _ in $(seq 1 "$tries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "  $name OK: $url"
      return 0
    fi
    sleep 1
  done
  echo "  $name may still be starting: $url"
}

echo "============================================="
echo " Fitness Dashboard Launcher for macOS"
echo "============================================="
echo "Python: $("$PYTHON_BIN" --version 2>&1) ($PYTHON_BIN)"
echo

echo "[0/3] Clearing ports..."
clear_port 8000
clear_port 8002

echo "[1/3] Starting PostgreSQL via Docker Compose..."
if command -v docker >/dev/null 2>&1; then
  docker compose -f "$PROJECT_DIR/docker-compose.dev.yml" up -d postgres
else
  echo "  Docker is not installed or not on PATH. Skipping PostgreSQL startup."
fi

echo "[2/3] Starting Dashboard API :8000 ..."
cd "$PROJECT_DIR"
nohup "$PYTHON_BIN" -m uvicorn agent_service.reports.api:app \
  --host "$HOST" \
  --port 8000 \
  $UVICORN_RELOAD_ARGS \
  > "$LOG_DIR/dashboard_api.log" 2>&1 &
echo $! > "$LOG_DIR/dashboard_api.pid"

echo "[3/3] Starting Gym Analyzer API :8002 ..."
nohup "$PYTHON_BIN" -m uvicorn gym_analyzer.api:app \
  --host "$HOST" \
  --port 8002 \
  $UVICORN_RELOAD_ARGS \
  > "$LOG_DIR/gym_analyzer_api.log" 2>&1 &
echo $! > "$LOG_DIR/gym_analyzer_api.pid"

echo
echo "Waiting for services..."
wait_for_url "Dashboard" "http://localhost:8000/docs" 20
wait_for_url "Analyzer" "http://localhost:8002/docs" 20

echo
echo "============================================="
echo " Relty App : http://localhost:8000/relty/"
echo " Dashboard : http://localhost:8000"
echo " Analyzer  : http://localhost:8002/analyzer"
echo " API docs  : http://localhost:8000/docs"
echo " Logs      : $LOG_DIR"
echo " Stop      : ./stop_dashboard_mac.sh"
echo "============================================="
