# Implementation Plan — TASK-382 / REQ-05: Update Skill Files and Rules

**Task:** TASK-382
**Requirement:** REQ-05
**Date:** 2026-03-08
**Status:** Ready for Execution
**Complexity:** Low
**Total Steps:** 1
**Steps Remaining:** 1
**Depends On:** REQ-01

---

## Overview

Audit all skill files and rules that reference `get_pending_tasks`. Update the
MCP tools reference table in `02-mcp-tools.md` to document the new `search`,
`task_id`, and `limit` parameters. Ensure no skill calls `get_pending_tasks`
without at least one filter.

## Scope

### In Scope
- `~/.claude/rules/02-mcp-tools.md` — update tool reference with new params
- `~/.claude/rules/04-work-protocols.md` — add filter guidance
- Audit all skills for unfiltered `get_pending_tasks` calls
- Both `~/.claude/` and `~/om-apex/dotfiles/` copies

### Out of Scope
- Changing skill logic or workflow
- Modifying how skills are triggered

## Architecture Notes

Audit results from investigation:
- `create-prd-for-enhancement/SKILL.md:29` — `get_pending_tasks(status: "approved-for-prd")` — already filtered ✓
- `next-up/SKILL.md:48-52` — multiple calls, each with status filter — already filtered ✓
- `look-for-work/SKILL.md` — does not reference `get_pending_tasks` ✓
- `find-priority-work/SKILL.md` — does not reference `get_pending_tasks` ✓
- `02-mcp-tools.md:15` — reference table says "List all tasks" — needs update
- `04-work-protocols.md:39` — "Check `get_pending_tasks` for related planned work" — needs filter hint

All existing skill calls already use filters. Only the rules files need updates.

## Sub-Agent Roles Involved

Solo — Solution Architect executes directly.

---

## Execution Steps

### Step 1: Update rules files

- **Agent:** Solution Architect
- **Status:** [ ] Incomplete
- **Reads:** `~/.claude/rules/02-mcp-tools.md`, `~/.claude/rules/04-work-protocols.md`,
  `~/om-apex/dotfiles/rules/02-mcp-tools.md`, `~/om-apex/dotfiles/rules/04-work-protocols.md`
- **Creates/Modifies:** Same 4 files
- **Task:**
  1. In `02-mcp-tools.md`: update the `get_pending_tasks` row in the MCP Tool table:
     - Change description from "List all tasks" to "List tasks (requires filter)"
     - Add a note below the table documenting new params:
       `get_pending_tasks` requires at least one filter: `status`, `company`,
       `owner`, `category`, `task_type`, `source`, `search`, or `task_id`.
       Default limit: 10. Max: 50. Excludes complete tasks unless status
       filter is specified.
  2. In `04-work-protocols.md`: update the "Check `get_pending_tasks` for related
     planned work" line to include a filter:
     "Check `get_pending_tasks(search=<keyword>)` or `get_pending_tasks(status=...)` for related planned work"
  3. Apply same changes to dotfiles source copies
- **Completion Check:** `grep "List all tasks" ~/.claude/rules/02-mcp-tools.md` returns
  no results. Filter guidance present in `04-work-protocols.md`. Dotfiles copies match.
- **Depends On:** None (can be executed any time, but logically follows REQ-01)

---

## Risks & Assumptions

- Existing skill calls are already filtered — this REQ only updates documentation
- Future skills should follow the documented pattern

## Open Questions

None.
