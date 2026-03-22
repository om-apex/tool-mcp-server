# Implementation Plan — TASK-382 / REQ-03: Add Limit to get_decisions_history

**Task:** TASK-382
**Requirement:** REQ-03
**Date:** 2026-03-08
**Status:** Ready for Execution
**Complexity:** Low
**Total Steps:** 1
**Steps Remaining:** 1
**Depends On:** None

---

## Overview

Add `limit` parameter (default 10, max 50) to `get_decisions_history` tool
schema and `get_decisions()` in `supabase_client.py`. The decisions table is
growing and will eventually hit the same unbounded output issue as tasks.

## Scope

### In Scope
- `supabase_client.py`: Add `limit` param to `get_decisions()` function
- `tools/context.py`: Add `limit` to `get_decisions_history` tool schema and handler

### Out of Scope
- Adding search or required filters to decisions (decisions table is smaller)
- Other context tools

## Architecture Notes

Simple limit addition — matches the pattern being established in REQ-01.
Default 10, max 50. No filter enforcement for decisions since the table is
much smaller than tasks.

## Sub-Agent Roles Involved

Solo — Solution Architect executes directly.

---

## Execution Steps

### Step 1: Add limit to get_decisions() and get_decisions_history tool

- **Agent:** Solution Architect
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/supabase_client.py`, `src/om_apex_mcp/tools/context.py`
- **Creates/Modifies:** `src/om_apex_mcp/supabase_client.py`, `src/om_apex_mcp/tools/context.py`
- **Task:**
  1. In `supabase_client.py` `get_decisions()`: add `limit: int = 10` parameter.
     Cap to max 50: `limit = min(limit, 50)`. Add `.limit(limit)` to query.
  2. In `tools/context.py`: find the `get_decisions_history` tool schema and add
     `"limit": {"type": "integer", "description": "Max results to return (default 10, max 50)"}` to properties
  3. In handler: pass `limit=arguments.get("limit", 10)` to `get_decisions()`
- **Completion Check:** `get_decisions()` has `limit` param with `.limit()` on query.
  Tool schema includes `limit` property. Handler passes limit through.
- **Depends On:** None

---

## Risks & Assumptions

- Decisions table currently ~200 records — limit is preventive, not urgent
- Existing callers that don't pass limit will get default 10 (acceptable for
  most use cases; callers needing more can pass explicit limit)

## Open Questions

None.
