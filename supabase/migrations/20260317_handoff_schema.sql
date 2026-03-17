-- TASK-505: Handoff schema refactor
-- Drop singleton session_handoff table (replaced by local handoff.md files)
DROP TABLE IF EXISTS session_handoff;

-- Add project_code to history for per-project filtering
ALTER TABLE session_handoff_history
  ADD COLUMN IF NOT EXISTS project_code TEXT;
