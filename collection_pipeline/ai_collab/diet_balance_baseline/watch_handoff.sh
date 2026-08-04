#!/usr/bin/env bash
# Event-driven turn watcher for the Diet Balance Baseline collaboration.
#
# Usage:
#   ./watch_handoff.sh <wait_for_owner>
#   e.g. ./watch_handoff.sh claude   # wakes when it's Claude's turn
#        ./watch_handoff.sh codex    # wakes when it's Codex's turn
#
# It polls STATUS.md at the shell level (no model cost) and exits 0 only when
#   status: done_for_turn   AND   next_owner: <wait_for_owner>
# Exiting re-invokes the agent that launched it in background.

set -u

WAIT_FOR="${1:-claude}"
DIR="$(cd "$(dirname "$0")" && pwd)"
STATUS="$DIR/STATUS.md"

POLL_SECONDS=20
MAX_ITERS=360            # 360 * 20s = 2h, then exit as a heartbeat

if [[ ! -f "$STATUS" ]]; then
  echo "ERROR: STATUS.md not found at $STATUS"
  exit 2
fi

field() { grep -iE "^$1:" "$STATUS" | head -1 | sed -E "s/^$1:[[:space:]]*//I"; }

echo "watcher armed: waiting for status=done_for_turn next_owner=$WAIT_FOR"

for ((i=0; i<MAX_ITERS; i++)); do
  status="$(field status)"
  owner="$(field next_owner)"
  round="$(field round)"
  if echo "$status" | grep -qi 'done_for_turn' && echo "$owner" | grep -qi "$WAIT_FOR"; then
    echo "TRIGGER: round=$round status=$status next_owner=$owner"
    echo "----- STATUS.md -----"
    cat "$STATUS"
    exit 0
  fi
  sleep "$POLL_SECONDS"
done

echo "HEARTBEAT: no handoff to '$WAIT_FOR' after 2h; relaunch the watcher to keep waiting."
exit 0
