# Session Operations Reference

> Last updated: 2026-02-25

This document captures the operational mechanics of starting/ending Claude Code sessions, the `.zshrc` configuration, and known quirks. Keep this updated when anything changes.

---

## Session Start Flow

Session start runs **two parallel batches** (see CLAUDE.md for the full protocol):

### Batch 1 (parallel)
```
echo $CLAUDE_INSTANCE          → identity (e.g. "Nishad-1")
get_session_handoff             → current global handoff state
```

### Batch 2 (parallel, depends on identity from Batch 1)
```
get_handoff_history(created_by=<instance>, limit=2)   → this instance's last 1–2 sessions
get_task_queue(limit=50)                              → cross-reference to verify tasks still open
```

### Greeting output format
```
Handoff loaded.

**Last Session (<instance>):** [1-line summary — from history if global handoff was written by other instance]

**Blockers:** [brief note — omit if none]

**Next Up:** N tasks
1. TASK-XXX: Description (High) @Owner
...

Instance: Nishad-1
```

---

## Known Quirks

### Multi-instance handoff mismatch
When two instances are running, only one writes the final `save_session_handoff` at session end. The other writes a checkpoint. This means:

- The **global handoff** may have been written by the other instance (e.g., Nishad-2)
- The **"Last Session" line** in the greeting should use the global handoff only if `created_by` matches the current instance — otherwise pull it from history
- In practice: if you're Nishad-1 and the global handoff says `By: Nishad-2`, your "Last Session" comes from `get_handoff_history`, not from the global handoff

The greeting should label clearly which instance the last session belongs to, e.g. `**Last Session (Nishad-2):**` vs `**Last Session (Nishad-1):**`.

### Task queue size
`get_task_queue(limit=50)` returns tasks for all owners (@Claude, @Cursor, @Sumedha, etc.). This is noisy but necessary to verify that "Next Up" tasks from the handoff are still open. The handoff itself pre-filters by instance, so the task queue is only used for cross-reference — not as the primary source of "what's next."

---

## How to Launch

Instance numbering is **fully automatic**. Just run `claude` in each terminal — no exports or prompts needed.

```bash
# Terminal 1 → auto-assigned Nishad-1 (or Sumedha-1 on her machine)
claude

# Terminal 2 → auto-assigned Nishad-2 (next free slot)
claude
```

The `claude()` shell function in `~/.zshrc`:
1. Sweeps stale lockfiles (catches kill -9 exits)
2. Finds the lowest unused number for `$TERMINAL_NAME`
3. Writes `/tmp/claude-instance-Nishad-N.lock` with the shell PID
4. Launches with `CLAUDE_INSTANCE=Nishad-N`
5. Removes the lockfile on clean exit

If you need to check what's running:
```bash
ls /tmp/claude-instance-*.lock
```

---

## `.zshrc` Reference

**Location:** `~/.zshrc`
**Machine:** Nishad's Mac (Darwin)

### Current contents (as of 2026-02-25)

```zsh
# Python version manager
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"

# Minimal prompt: shows current dir only
export PS1="%1d %% "

# Identity for Claude Code multi-instance coordination
# Set this per machine — Nishad on Mac, Sumedha on her laptop
export TERMINAL_NAME="Nishad"

# Pipx / user-local bins
export PATH="$HOME/.local/bin:$PATH"

# AI Quorum backend scripts on PATH
export PATH="$PATH:/Users/nishad/om-apex/products/ai-quorum/backend/scripts"

# Project shortcuts
alias startquorum="/Users/nishad/om-apex/products/ai-quorum/scripts/startquorum.sh"
alias stopquorum="/Users/nishad/om-apex/products/ai-quorum/scripts/stopquorum.sh"
alias startapex="/Users/nishad/om-apex/websites/apex/scripts/startapex.sh"
alias stopapex="/Users/nishad/om-apex/websites/apex/scripts/stopapex.sh"

# Claude Code instance selector — auto-detects instance number via lockfiles
# Uses TERMINAL_NAME as the base; appends -1, -2, etc.
# Bypasses auto-detection for non-interactive commands (/login, auth, --version)
claude() {
  if [[ "$1" == "/login" || "$1" == "auth" || "$1" == "--version" || "$1" == "-v" ]]; then
    command claude "$@"
    return
  fi

  local base="${TERMINAL_NAME:-Nishad}"

  # Clean up stale locks (process exited without cleanup, e.g. kill -9)
  for lockfile in /tmp/claude-instance-${base}-*.lock(N); do
    local pid=$(cat "$lockfile" 2>/dev/null)
    if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$lockfile"
    fi
  done

  # Find lowest available instance number (fills gaps left by exited instances)
  local instance_num=1
  while [[ -f "/tmp/claude-instance-${base}-${instance_num}.lock" ]]; do
    ((instance_num++))
  done

  local instance="${base}-${instance_num}"
  local lockfile="/tmp/claude-instance-${base}-${instance_num}.lock"

  echo $$ > "$lockfile"
  echo "Starting $instance"

  CLAUDE_INSTANCE="$instance" command claude "$@"
  local status=$?

  rm -f "$lockfile"
  return $status
}

# Claude Code settings
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export ENABLE_TOOL_SEARCH=auto:5  # Load tools incrementally to conserve context
```

### Commented-out options (not active, kept for reference)
```zsh
# export CLAUDE_CODE_MAX_OUTPUT_TOKENS=16384  # Raise for large file writes
# export BASH_DEFAULT_TIMEOUT_MS=30000        # Raise if MCP/build scripts time out
```

---

## What Was Removed and Why

These were in `.zshrc` and removed during the 2026-02-25 session cleanup:

| Removed | Reason |
|---------|--------|
| `cl()` function | Too slow — added latency on every session start, not worth it |
| `ANTHROPIC_MODEL=opusplan` | Typo — caused Claude Code to fail auth (not a real env var) |
| `ANTHROPIC_DEFAULT_*` vars | Not real Claude Code env vars — were completely inert |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` | Not needed — using Claude Code's default compaction threshold |

---

## Session End Protocol

When the user says "end session", "wrap up", or similar → invoke `/end-session` skill.

Mid-session checkpoint (after significant milestones): invoke `/session-hand-off`.

See CLAUDE.md for full details.

---

## Reference

- Full session protocol: `~/CLAUDE.md` (Session Start Protocol section)
- Multi-agent coordination: `tools/mcp-server/docs/TEAM-PROTOCOL.md`
- CLI access & project refs: `tools/mcp-server/docs/CLI-ACCESS-REFERENCE.md`
