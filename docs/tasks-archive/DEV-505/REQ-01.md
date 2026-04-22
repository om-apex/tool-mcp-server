# Implementation Plan — TASK-505 / REQ-01: Task ID Generation (DEV/ISSUE Prefixes)

**Task:** TASK-505
**Requirement:** REQ-01
**Date:** 2026-03-17
**Status:** Ready for Execution
**Complexity:** Medium
**Total Steps:** 3
**Steps Remaining:** 3
**Depends On:** None

---

## Overview

Rewrite `get_next_task_id()` to generate `DEV-nnn` or `ISSUE-nnn` prefixes based on task type, using a shared counter across all prefixes (TASK, DEV, ISSUE). Update `add_task` to pass task_type to the generator.

## Scope
### In Scope
- `get_next_task_id()` in `supabase_client.py` — rewrite with task_type param
- `add_task` handler in `tasks.py` — pass task_type
- Backward compat: existing TASK-nnn IDs remain queryable

### Out of Scope
- Handoff changes (REQ-02)
- Deployment (REQ-03)
- Any UI/portal changes

## Architecture Notes
- Shared counter: query ALL IDs (`TASK-%`, `DEV-%`, `ISSUE-%`), extract max numeric suffix, increment
- Prefix mapping: `enhancement`/`feature-request`/`dev`/`manual` → `DEV-`, `issue` → `ISSUE-`
- Fallback on error: `DEV-001` (not `TASK-001`)
- Zero-padding: `:03d` — continues existing convention

---

## Execution Steps

### Step 1: Rewrite `get_next_task_id()` in supabase_client.py
- **Agent:** Developer
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/supabase_client.py` (lines 314-347)
- **Creates/Modifies:** `src/om_apex_mcp/supabase_client.py`
- **Task:**
  1. Change signature: `get_next_task_id()` → `get_next_task_id(task_type: str = "enhancement")`
  2. Define prefix map: `{"enhancement": "DEV", "feature-request": "DEV", "dev": "DEV", "manual": "DEV", "issue": "ISSUE"}`
  3. Look up prefix from task_type, default to `"DEV"` for unknown types
  4. Query all task IDs with any known prefix: use three queries or an `or_` filter for `TASK-%`, `DEV-%`, `ISSUE-%`
  5. Extract numeric suffix from each, find the global max
  6. Return `f"{prefix}-{max_num + 1:03d}"`
  7. Fallback on error: return `f"{prefix}-001"`
  8. Update docstring
- **Completion Check:** Function accepts task_type, returns correct prefix. Manual test: calling with `"issue"` returns `ISSUE-nnn`, calling with `"enhancement"` returns `DEV-nnn`, number is globally max + 1
- **Depends On:** None

### Step 2: Update `add_task` handler in tasks.py
- **Agent:** Developer
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/tools/tasks.py` (lines 225-254)
- **Creates/Modifies:** `src/om_apex_mcp/tools/tasks.py`
- **Task:**
  1. Line 236: change `get_next_task_id()` → `get_next_task_id(arguments.get("task_type", "enhancement"))`
  2. Ensure the `task_type` argument is read before the ID generation call (it's currently read at line 251-252 — move up or pass directly)
- **Completion Check:** `add_task` with `task_type: "issue"` generates an `ISSUE-nnn` ID; with `task_type: "enhancement"` generates `DEV-nnn`
- **Depends On:** Step 1

### Step 3: Verify backward compatibility
- **Agent:** Developer
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/tools/tasks.py` (full file — check get_pending_tasks, update_task, complete_task)
- **Creates/Modifies:** None (verification only, unless issues found)
- **Task:**
  1. Check `get_pending_tasks` — the `task_id` filter uses `.eq("id", task_id)`. This is a direct equality match, so it works with any ID format (TASK-nnn, DEV-nnn, ISSUE-nnn). No change needed.
  2. Check `update_task`, `complete_task`, `update_task_status` — all use `.eq("id", task_id)`. Same — no changes needed.
  3. Check `get_pending_tasks` default filter — it currently has no `LIKE` filter on ID prefix. Tasks are filtered by status/category/etc. No change needed.
  4. Verify `get_next_task_id` import in tasks.py is correct
- **Completion Check:** All task tools accept TASK-nnn, DEV-nnn, and ISSUE-nnn IDs without error
- **Depends On:** Step 2

---

## Files Changed
<!-- Filled after execution -->

## Risks & Assumptions
- The shared counter approach requires querying 3 LIKE patterns. If performance is a concern, could use a single `or_` filter, but with <1000 tasks this is negligible.
- Race condition on concurrent `add_task` calls is pre-existing (client-side ID generation). Not in scope to fix.

## Open Questions
None.
