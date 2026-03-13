# Implementation Plan — TASK-449 / REQ-01: Add project_code lookup helper

**Task:** TASK-449
**Requirement:** REQ-01
**Date:** 2026-03-12
**Status:** Ready for Execution
**Complexity:** Low
**Total Steps:** 2
**Steps Remaining:** 0
**Depends On:** None

---

## Overview

Create a shared helper function in `supabase_client.py` that resolves a human-friendly project code (e.g., `mcp-server`, `portal`, `root`) to the corresponding project UUID from the `projects` table. This helper will be called by both `add_task` and `update_task` handlers.

## Scope

### In Scope
- New function `resolve_project_code(project_code: str) -> str` in `supabase_client.py`
- Query `projects` table where `project_folder = project_code`
- Handle `root` -> `om-apex` mapping
- Return UUID string on success
- Raise `ValueError` with list of valid codes on failure
- Cache the project_folder->UUID mapping after first call (module-level dict)

### Out of Scope
- Changes to `tasks.py` tool definitions (REQ-02, REQ-03)
- Rule file updates (REQ-04)
- Any database schema changes

## Architecture Notes

- **Dynamic lookup vs hardcoded enum:** Use dynamic lookup from `projects` table, cached in a module-level dict after first call. This avoids hardcoding UUIDs and makes the system self-maintaining when new projects are added.
- **`root` special case:** Handle in the helper by mapping `root` -> `om-apex` before querying. This is a code-level mapping, not a DB change.
- **Error handling:** On invalid code, query all `project_folder` values and return them in the error message so the caller knows valid options.
- **Import in `tasks.py`:** The helper will be imported alongside existing supabase_client functions.

## Sub-Agent Roles Involved

- **Solution Architect** — solo execution, no team needed

---

## Execution Steps

### Step 1: Add resolve_project_code function to supabase_client.py
- **Agent:** Solution Architect
- **Status:** [x] Complete
- **Reads:** `tools/mcp-server/src/om_apex_mcp/supabase_client.py`
- **Creates/Modifies:** `tools/mcp-server/src/om_apex_mcp/supabase_client.py`
- **Task:** Add a new function `resolve_project_code(project_code: str) -> str` in the Task Operations section (after `get_next_task_id`, before `get_task_queue`). Implementation:
  1. Module-level cache: `_project_code_cache: dict[str, str] = {}` at top of file
  2. If cache is populated, look up `project_code` (with `root`->`om-apex` mapping applied)
  3. If not in cache or cache empty, query `projects` table: `select("id, project_folder").execute()`
  4. Build cache: `{row["project_folder"]: row["id"] for row in response.data}`
  5. Apply `root` mapping: if `project_code == "root"`, look up `"om-apex"` in cache
  6. If found, return UUID string
  7. If not found, raise `ValueError(f"Invalid project_code '{project_code}'. Valid codes: {sorted(cache.keys())} (use 'root' for om-apex)")`
  8. Wrap in try/except for Supabase errors, re-raise as `RuntimeError`
- **Completion Check:** Function exists, is importable, handles root mapping, raises ValueError on bad input
- **Depends On:** None

### Step 2: Add resolve_project_code to tasks.py imports
- **Agent:** Solution Architect
- **Status:** [x] Complete
- **Reads:** `tools/mcp-server/src/om_apex_mcp/tools/tasks.py` (line 18-26)
- **Creates/Modifies:** `tools/mcp-server/src/om_apex_mcp/tools/tasks.py`
- **Task:** Add `resolve_project_code` to the import block at line 18-26:
  ```python
  from ..supabase_client import (
      is_supabase_available,
      get_tasks as sb_get_tasks,
      get_task_by_id as sb_get_task_by_id,
      get_task_queue as sb_get_task_queue,
      add_task as sb_add_task,
      update_task as sb_update_task,
      get_next_task_id,
      resolve_project_code,
  )
  ```
- **Completion Check:** Import succeeds without error. `resolve_project_code` is available in tasks.py module scope.
- **Depends On:** Step 1

---

## Risks & Assumptions

- **Assumption:** The `projects` table is always available when the MCP server is running (same Supabase instance as tasks).
- **Risk:** If `projects` table is empty or missing, the cache will be empty and all project_code lookups will fail. Mitigated by the error message listing valid codes (which would be empty, signaling the issue).
- **Assumption:** `project_folder` values in the `projects` table are unique (no duplicates).

## Open Questions

None — all design decisions resolved in Architecture Notes.
