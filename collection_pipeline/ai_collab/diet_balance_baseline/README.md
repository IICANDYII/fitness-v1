# Diet Balance Baseline AI Collaboration

This folder is the shared workspace for Codex and Claude Code.

Use this folder instead of manually copying long outputs between agents.

## Files

- `STATUS.md`: current turn owner and completion state.
- `CODEX_OUT.md`: Codex writes repo-grounded facts, data availability, risks, and questions.
- `CLAUDE_OUT.md`: Claude Code writes product/scoring critique, baseline layer proposals, risks, and questions.
- `DECISIONS.md`: accepted decisions, rejected ideas, and open questions.
- `../../Diet Balance Baseline AI协作工作流.md`: full workflow and prompts.
- `../../Diet Balance Baseline 新版PRD.md`: current baseline PRD draft.

## Turn Protocol

1. Before writing, the agent reads `STATUS.md`, `DECISIONS.md`, and the other agent's latest output.
2. The active agent sets `STATUS.md` to `in_progress`.
3. The active agent writes only its own output file.
4. When finished, the active agent updates `STATUS.md` to `done_for_turn` and sets `next_owner`.
5. The next agent only starts after seeing `done_for_turn`.

## No-Hallucination Rule

Every claim must be tagged as one of:

- `local_file`
- `calculated_from_local_data`
- `external_source`
- `inference`
- `assumption`

Assumptions must never be written as facts.

## When A Watcher Is Needed

Manual turn-taking through `STATUS.md` is the safest baseline protocol, but it requires the user to tell each agent when the other side has updated files.

A watcher is useful once Codex and Claude Code are both working from this folder and the user wants automatic turn handoff.

Recommended watcher:

- Use a Codex App heartbeat automation every 1 minute for the Codex side.
- The heartbeat checks `STATUS.md`, `CODEX_OUT.md`, `CLAUDE_OUT.md`, and `DECISIONS.md`.
- If `status: done_for_turn` and `next_owner: codex`, Codex should read Claude's latest output and continue the next Codex turn.
- If it is not Codex's turn, Codex should stay idle and avoid writing files.
- A shell watcher such as `watch_handoff.sh codex` can detect the handoff, but it does not wake this Codex App thread unless it is paired with a Codex CLI or app automation bridge.

Optional local watcher:

- A PowerShell script can also watch file modification times and print notifications.
- This is useful for terminal visibility, but it does not by itself make Codex continue unless a Codex automation or active thread wakes up.
