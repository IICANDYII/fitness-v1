#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

stop_pid_file() {
  local name="$1"
  local pid_file="$2"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping $name: $pid"
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
}

clear_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "Clearing port $port: $pids"
    kill $pids 2>/dev/null || true
  fi
}

stop_pid_file "Dashboard API" "$LOG_DIR/dashboard_api.pid"
stop_pid_file "Gym Analyzer API" "$LOG_DIR/gym_analyzer_api.pid"
clear_port 8000
clear_port 8002

echo "Stopped local dashboard services."
