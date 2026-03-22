# Implementation Plan — TASK-382 / REQ-01: Harden get_pending_tasks Tool

**Task:** TASK-382
**Requirement:** REQ-01
**Date:** 2026-03-08
**Status:** Ready for Execution
**Complexity:** Medium
**Total Steps:** 3
**Steps Remaining:** 3
**Depends On:** None

---

## Overview

Add `limit`, `search`, and `task_id` parameters to `get_pending_tasks`.
Enforce that at least one filter is provided. Default to excluding `complete`
status when no status filter is specified. This is the core fix that prevents
unbounded 350K+ character responses.

## Scope

### In Scope
- `supabase_client.py`: Add `limit`, `search`, `task_id` params to `get_tasks()`
- `tools/tasks.py`: Update tool schema + handler for `get_pending_tasks`
- Filter enforcement logic in handler
- Default status exclusion (exclude `complete`)

### Out of Scope
- `get_task_queue` (already has limits)
- Internal `sb_get_tasks()` calls in complete/force_complete (REQ-02)
- Other tool modules (REQ-03, REQ-04)
- Skill/rule updates (REQ-05)

## Architecture Notes

- `limit` default: 10, max: 50 (per Nishad's review)
- `search` uses Supabase `or` filter with `ilike` on description and notes
- `task_id` is an exact match that bypasses other filters and returns 1 result
- Filter enforcement: check if any of `company`, `category`, `status`, `owner`,
  `task_type`, `source`, `search`, or `task_id` is provided. If none, return error.
- Default status behavior: when no `status` filter is provided, exclude `complete`

## Sub-Agent Roles Involved

Solo — Solution Architect executes directly.

---

## Execution Steps

### Step 1: Update `get_tasks()` in supabase_client.py

- **Agent:** Solution Architect
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/supabase_client.py`
- **Creates/Modifies:** `src/om_apex_mcp/supabase_client.py`
- **Task:**
  1. Add `limit: int = 10`, `search: Optional[str] = None`, `task_id: Optional[str] = None`
     parameters to `get_tasks()` function signature
  2. If `task_id` is provided: query `client.table("tasks").select("*").eq("id", task_id).limit(1).execute()`
     and return immediately (bypass all other filters)
  3. If `search` is provided: add `.or_(f"description.ilike.%{search}%,notes.ilike.%{search}%")`
     to the query chain
  4. If no `status` filter: add `.neq("status", "complete")` (exclude complete by default)
  5. Cap `limit` to max 50: `limit = min(limit, 50)`
  6. Add `.limit(limit)` to the query chain before `.execute()`
- **Completion Check:** Function signature has all new params. `task_id` path returns single record. Query has `.limit()` applied. Default status exclusion present.
- **Depends On:** None

### Step 2: Update `get_pending_tasks` tool schema and handler in tasks.py

- **Agent:** Solution Architect
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/tools/tasks.py`
- **Creates/Modifies:** `src/om_apex_mcp/tools/tasks.py`
- **Task:**
  1. Add `limit`, `search`, and `task_id` to the `get_pending_tasks` tool inputSchema properties
  2. Update tool description to mention filter requirement and default behavior
  3. In handler: before calling `sb_get_tasks()`, check if at least one filter is
     provided (any of: company, category, status, owner, task_type, source, search, task_id).
     If none provided, return error:
     `"Error: get_pending_tasks requires at least one filter. Provide one or more of: status, company, owner, category, task_type, source, search, or task_id."`
  4. Pass new params through to `sb_get_tasks()`:
     `limit=arguments.get("limit", 10), search=arguments.get("search"), task_id=arguments.get("task_id")`
- **Completion Check:** Tool schema includes 3 new properties. Handler enforces filter requirement. New params passed to `sb_get_tasks()`.
- **Depends On:** Step 1

### Step 3: Test the hardened tool

- **Agent:** Solution Architect
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/tools/tasks.py`, `src/om_apex_mcp/supabase_client.py`
- **Creates/Modifies:** None
- **Task:**
  1. Start the MCP server locally and verify it starts without errors
  2. Verify `get_pending_tasks()` with no args returns the error message
  3. Verify `get_pending_tasks(status="coding-in-progress")` returns filtered results
  4. Verify `get_pending_tasks(task_id="TASK-382")` returns exactly one task
  5. Verify `get_pending_tasks(search="quorum")` returns matching tasks
  6. Verify result count does not exceed 10 (default limit)
- **Completion Check:** All 5 test scenarios pass. Server starts without errors.
- **Depends On:** Step 2

---

## Risks & Assumptions

- Supabase `.or_()` filter syntax needs verification — may need to use
  `.or("description.ilike.%term%,notes.ilike.%term%")` (string format, not method)
- `ilike` search is case-insensitive but not full-text — adequate for current needs

## Open Questions

None.
