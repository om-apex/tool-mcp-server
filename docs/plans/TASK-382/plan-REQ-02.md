# Implementation Plan — TASK-382 / REQ-02: Fix Internal Unbounded sb_get_tasks() Calls

**Task:** TASK-382
**Requirement:** REQ-02
**Date:** 2026-03-08
**Status:** Ready for Execution
**Complexity:** Low
**Total Steps:** 1
**Steps Remaining:** 1
**Depends On:** None

---

## Overview

`complete_task` and `force_complete` handlers both call `sb_get_tasks()` with
no filters to fetch the entire tasks table just to find one task by ID. Replace
these with a direct `get_task_by_id()` helper that queries by exact ID with
`.limit(1)`. Internal optimization only — no tool interface change.

## Scope

### In Scope
- Add `get_task_by_id()` function to `supabase_client.py`
- Replace `sb_get_tasks()` calls in `complete_task` and `force_complete` handlers
- Update import in `tasks.py`

### Out of Scope
- Changing tool interfaces
- Modifying `get_tasks()` function (REQ-01)

## Architecture Notes

`get_task_by_id()` does a single-row query:
`client.table("tasks").select("*").eq("id", task_id).limit(1).execute()`
Returns `Optional[dict]` — the task record or None.

## Sub-Agent Roles Involved

Solo — Solution Architect executes directly.

---

## Execution Steps

### Step 1: Add get_task_by_id() and replace unbounded calls

- **Agent:** Solution Architect
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/supabase_client.py`, `src/om_apex_mcp/tools/tasks.py`
- **Creates/Modifies:** `src/om_apex_mcp/supabase_client.py`, `src/om_apex_mcp/tools/tasks.py`
- **Task:**
  1. In `supabase_client.py`, add `get_task_by_id(task_id: str) -> Optional[dict]`:
     ```python
     def get_task_by_id(task_id: str) -> Optional[dict]:
         client = get_supabase_client()
         if not client:
             return None
         response = client.table("tasks").select("*").eq("id", task_id).limit(1).execute()
         return response.data[0] if response.data else None
     ```
  2. In `tasks.py`, add `get_task_by_id as sb_get_task_by_id` to imports
  3. In `complete_task` handler: replace
     `existing_tasks = sb_get_tasks()` +
     `existing_task = next((t for t in existing_tasks if t.get("id") == task_id), None)`
     with `existing_task = sb_get_task_by_id(task_id)`
  4. In `force_complete` handler: same replacement
- **Completion Check:** `grep -n "sb_get_tasks()" tasks.py` returns zero hits for
  `complete_task` and `force_complete` blocks. `get_task_by_id` is imported and used.
- **Depends On:** None

---

## Risks & Assumptions

- `get_task_by_id` may still be called with invalid IDs — returns None, handlers
  already check for this case
- No error handling changes needed — existing None checks remain valid

## Open Questions

None.
