# Implementation Plan — TASK-382 / REQ-04: Add Limits to AI Quorum Diagnostic Tools

**Task:** TASK-382
**Requirement:** REQ-04
**Date:** 2026-03-08
**Status:** Ready for Execution
**Complexity:** Low
**Total Steps:** 1
**Steps Remaining:** 1
**Depends On:** None

---

## Overview

Verify and enforce limits on AI Quorum diagnostic tools. `list_quorum_sessions`
(default 20) and `get_quorum_logs` (default 50) already have limits applied at
the DB level. `get_quorum_model_performance` has no limit on its primary query
against `v_model_performance`. Add a limit to prevent unbounded output as usage
grows.

## Scope

### In Scope
- `tools/ai_quorum.py`: Add limit to `get_quorum_model_performance` view query
- Verify `list_quorum_sessions` and `get_quorum_logs` limits are properly applied

### Out of Scope
- Adding new filter parameters to AI Quorum tools
- Changing `get_quorum_turn_detail` or `get_quorum_turn_trace` (ID-based lookups, always bounded)
- `get_quorum_cost_summary` (aggregation query, always returns summary)

## Architecture Notes

- `list_quorum_sessions`: already has `.limit(limit)` with default 20 ✓
- `get_quorum_logs`: already has `.limit(limit)` with default 50 ✓
- `get_quorum_model_performance`: primary query against `v_model_performance`
  has NO limit. `run_metrics` fallback has `.limit(100)`.
  Add `.limit(50)` to the view query.
- Also add `limit` to the tool schema so callers can override.

## Sub-Agent Roles Involved

Solo — Solution Architect executes directly.

---

## Execution Steps

### Step 1: Add limit to get_quorum_model_performance

- **Agent:** Solution Architect
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/tools/ai_quorum.py`
- **Creates/Modifies:** `src/om_apex_mcp/tools/ai_quorum.py`
- **Task:**
  1. In the `get_quorum_model_performance` tool schema: add
     `"limit": {"type": "integer", "description": "Max results (default 50)"}` to properties
  2. In `_handle_model_performance()`:
     - Read `limit = min(arguments.get("limit", 50), 100)`
     - Add `.limit(limit)` to the `v_model_performance` query (line ~447, before `.execute()`)
     - Keep the existing `.limit(100)` on the `run_metrics` fallback, or use the same `limit`
  3. Verify `list_quorum_sessions` and `get_quorum_logs` both have their limits
     properly applied (they do — just confirm during execution)
- **Completion Check:** `v_model_performance` query has `.limit()`. Tool schema
  has `limit` property. `list_quorum_sessions` and `get_quorum_logs` confirmed bounded.
- **Depends On:** None

---

## Risks & Assumptions

- `v_model_performance` is a materialized view — row count depends on how many
  model/category combinations exist. Currently small but could grow.
- Adding limit to the view query does not affect aggregation — the view already
  pre-aggregates per model/category.

## Open Questions

None.
