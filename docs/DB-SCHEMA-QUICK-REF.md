# Database Schema Quick Reference

> Last updated: 2026-02-21

## Owner Portal (hympgocuivzxzxllgmcy)

### tasks
Central task tracker for all Om Apex companies.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | Format: `TASK-001` (auto-generated) |
| description | TEXT | Task description |
| category | TEXT | Technical, Marketing, Legal, Operations, Administrative, Content |
| company | TEXT | Om Apex Holdings, Om Luxe Properties, Om AI Solutions, Om Supply Chain |
| priority | TEXT | High, Medium, Low |
| status | TEXT | pending, in_progress, completed |
| owner | TEXT | Person name (Nishad, Sumedha, Claude, etc.) |
| notes | TEXT | Additional notes |
| project_code | TEXT | Optional project code |
| duration_days | INTEGER | Estimated duration |
| due | DATE | Due date |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |
| completed_at | TIMESTAMPTZ | Set on completion |
| completion_notes | TEXT | What was done |
| task_type | TEXT | `issue`, `dev`, `manual` (default: manual) |
| commit_refs | TEXT[] | Git commit SHAs associated with task |
| issue_ref | TEXT | GitHub issue reference (e.g., `om-apex/repo#123`) |

### decisions
Technology and business decisions with rationale.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | Format: `TECH-001` or `BIZ-001` |
| area | TEXT | e.g., "Frontend Framework", "Authentication" |
| decision | TEXT | The decision made |
| rationale | TEXT | Why this decision was made |
| company | TEXT | Which company it applies to |
| confidence | TEXT | High, Medium, Low |
| alternatives_considered | TEXT | Other options considered |
| date_decided | DATE | When decided |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

### companies
Company registry with legal and banking info.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | **Slugs** like `"om-apex-holdings"` (NOT BIGSERIAL) |
| legal_name | TEXT | Full legal name |
| ein | TEXT | EIN number |
| state_control_number | TEXT | State registration |
| state_of_formation | TEXT | e.g., "Georgia" |
| bank_name | TEXT | Bank name |
| bank_account_type | TEXT | Checking, Savings |
| domain | TEXT | Primary domain |
| status | TEXT | active, inactive |
| parent_company_id | TEXT FK | References companies(id) |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

### document_templates
Templates for generating branded documents.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | Slug format |
| name | TEXT | Display name |
| filename | TEXT | Output filename |
| content | TEXT | Markdown template with `{{variables}}` |
| content_plain | TEXT | Plain text version |
| content_body_html | TEXT | HTML body content |
| content_snapshot_html | TEXT | Full HTML snapshot |
| description | TEXT | What this template is for |
| variables | JSONB | Variable definitions |
| document_variables | JSONB | Document-level variables |
| document_variable_defaults | JSONB | Default values |
| companies | TEXT[] | Which companies can use it |
| page_size | TEXT | e.g., "letter" |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

### session_handoff
Single-row table for cross-laptop context sync (upserted each session end).

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Always 1, enforced by CHECK constraint |
| content | TEXT | Full markdown handoff content |
| created_by | TEXT | "Nishad" or "Sumedha" |
| interface | TEXT | "code", "code-app", "chat", "cowork" |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Last upsert time |

### session_handoff_history
Archived previous handoffs for audit/review.

| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | Auto-generated identity |
| content | TEXT | Archived handoff content |
| created_by | TEXT | Who wrote it |
| interface | TEXT | Which interface |
| session_date | DATE | Date of the archived session |
| created_at | TIMESTAMPTZ | When archived |

---

## AI Quorum (ixncscosicyjzlopbfiz)

### sessions
User query sessions.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| user_id | UUID FK | References auth.users |
| title | TEXT | Session title |
| initial_query | TEXT | Original user query |
| optimized_query | TEXT | AI-optimized query |
| category | TEXT | Topic category |
| state | TEXT | Session state (active, completed, etc.) |
| turn_count | INTEGER | Number of turns |
| total_cost | NUMERIC | Total cost in dollars |
| total_cost_cents | INTEGER | Total cost in cents |
| total_tokens | INTEGER | Total tokens used |
| total_file_tokens | INTEGER | Tokens from file attachments |
| attachments_meta | JSONB | File attachment metadata |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

### session_turns
Individual turns within a session (one per query/response cycle).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| session_id | UUID FK | References sessions(id) |
| turn_number | INTEGER | Turn sequence |
| query | TEXT | User query for this turn |
| optimized_query | TEXT | Optimized version |
| category | TEXT | Topic category |
| stage0_output | JSONB | Stage 0: Query analysis |
| stage1_responses | JSONB | Stage 1: Individual LLM responses |
| stage2_diff | JSONB | Stage 2: Difference analysis |
| stage3_challenges | JSONB | Stage 3: Challenge responses |
| stage3_perplexity | JSONB | Stage 3: Perplexity fact-check |
| stage4_convictions | JSONB | Stage 4: Final convictions |
| stage5_synthesis | JSONB | Stage 5: Consensus synthesis |
| report | TEXT | Final rendered report |
| dissent_triggered | BOOLEAN | Whether dissent round triggered |
| dissenting_model | TEXT | Which model dissented |
| cost | NUMERIC | Cost for this turn |
| tokens_used | INTEGER | Tokens for this turn |
| time_seconds | NUMERIC | Processing time |
| created_at | TIMESTAMPTZ | Auto |

### llm_master
Master list of available LLM models.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| model_code | VARCHAR(20) | Short code (e.g., "gpt4o") |
| model_id | TEXT | Provider model ID |
| model_name | TEXT | Display name |
| model_type | TEXT | Type (chat, reasoning, etc.) |
| provider | TEXT | Provider name |
| provider_code | TEXT | Provider short code |
| api_identifier | TEXT | Full API model identifier |
| tier | TEXT | Model tier |
| context_length | INTEGER | Max context tokens |
| input_cost_per_mtok | NUMERIC | Input cost per million tokens |
| output_cost_per_mtok | NUMERIC | Output cost per million tokens |
| is_available | BOOLEAN | Whether model is currently available |
| brand_terms | TEXT | Brand/marketing terms |
| s0_test_count, s0_last_tested_at | — | Stage 0 test stats |
| s1_rank, s1_accuracy_pct, s1_avg_latency_ms | — | Stage 1 benchmarks |
| s1_is_recommended, s1_test_count, s1_last_tested_at | — | Stage 1 recommendation |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

### orch_config_versions
Orchestration configuration versions.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| version_number | INTEGER | Unique version number |
| version_name | VARCHAR(100) | Version label |
| description | TEXT | What this config does |
| status | VARCHAR(20) | draft, active, deprecated, archived |
| created_at | TIMESTAMPTZ | Auto |
| activated_at | TIMESTAMPTZ | When activated |
| deprecated_at | TIMESTAMPTZ | When deprecated |

### user_preferences
Per-user settings.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| user_id | UUID FK | References auth.users |
| default_mode | TEXT | Preferred query mode |
| preferred_models | JSONB | Preferred model list |
| report_format | TEXT | Preferred report format |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

### Additional Config Tables (orch_*)
The orchestration engine has several config tables for stages, model slots, prompt templates, and taxonomy. These are seeded via migrations and rarely queried directly. See migration files in `products/ai-quorum/supabase/migrations/` for full schema.

---

## Om Cortex (sgcfettixymowtokytwk)

### cortex_sessions
One row per conversation session.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| user_id | TEXT | Default `'owner'` |
| channel | TEXT | `web`, `api`, etc. |
| session_key | TEXT | Unique, client-provided |
| metadata | JSONB | Extensible metadata |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

### cortex_turns
Append-only conversation log.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| session_id | UUID FK | References cortex_sessions(id) |
| role | TEXT | `user`, `assistant`, `tool_call`, `tool_result` |
| content | TEXT | Message content (nullable) |
| metadata | JSONB | Tool params, etc. |
| tokens_in | INT | Input tokens |
| tokens_out | INT | Output tokens |
| cost_usd | NUMERIC(10,6) | Estimated cost |
| created_at | TIMESTAMPTZ | Auto |

Index: `idx_turns_session` on `(session_id, created_at)`

### cortex_audit_log
Every action logged.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| session_id | UUID | Nullable |
| action | TEXT | `chat.message`, `tool.executed`, `tool.denied`, etc. |
| tool | TEXT | Tool name (nullable) |
| params | JSONB | Tool parameters |
| result | JSONB | Tool result or error |
| channel | TEXT | Source channel |
| triggered_by | TEXT | `user`, `cron`, or `agent` |
| created_at | TIMESTAMPTZ | Auto |

Index: `idx_audit_created` on `(created_at desc)`

### cortex_conversations (Phase 1)
Vector-searchable conversation archive. Auto-populated after each agent run.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| session_id | UUID FK | References cortex_sessions(id), unique index |
| user_id | TEXT | Default `'owner'` |
| channel | TEXT | Source channel |
| title | TEXT | First sentence of Haiku summary |
| summary | TEXT | Full Haiku-generated summary |
| embedding | VECTOR(1536) | OpenAI text-embedding-3-small |
| tags | TEXT[] | Haiku-generated tags |
| turn_count | INT | Number of turns |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

Unique index: `idx_conversations_session` on `(session_id)`

### cortex_knowledge (Phase 1)
User-saved notes and documents with vector embeddings.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| user_id | TEXT | Default `'owner'` |
| type | TEXT | `note`, `document`, etc. |
| title | TEXT | Note title |
| content | TEXT | Full content |
| embedding | VECTOR(1536) | OpenAI text-embedding-3-small |
| source | TEXT | Origin of content |
| metadata | JSONB | Tags and other metadata |
| created_at | TIMESTAMPTZ | Auto |

### cortex_memory (Phase 1)
Key-value working memory. Facts auto-extracted from conversations.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| user_id | TEXT | Default `'owner'` |
| key | TEXT | Unique key |
| value | TEXT | Stored value |
| confidence | FLOAT | Default 0.8 |
| source_conversation_id | UUID FK | References cortex_conversations(id) |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

Unique constraint on `key`.

### RPC Functions (Phase 1)

**match_conversations(query_embedding, match_threshold, match_count)**
Returns: `(id UUID, title TEXT, summary TEXT, similarity FLOAT)`
Uses `1 - (embedding <=> query_embedding)` for cosine similarity.

**match_knowledge(query_embedding, match_threshold, match_count)**
Returns: `(id UUID, title TEXT, content TEXT, type TEXT, similarity FLOAT)`
Uses `1 - (embedding <=> query_embedding)` for cosine similarity.
