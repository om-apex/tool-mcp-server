# Database Schema Quick Reference

> Last updated: 2026-02-25

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

### leads
Contact form submissions from all websites. Dual-write target (Supabase + HubSpot).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| email | TEXT NOT NULL | Submitter email |
| firstname | TEXT | First name |
| lastname | TEXT | Last name |
| company | TEXT | Company name |
| phone | TEXT | Phone number |
| brand | TEXT NOT NULL | `om_apex_holdings`, `om_ai_solutions`, `om_supply_chain` |
| form_type | TEXT NOT NULL | `general`, `demo_request`, `consultation_request` (default: general) |
| message | TEXT | Form message |
| metadata | JSONB | Additional data (default: {}) |
| hubspot_contact_id | TEXT | HubSpot contact ID after sync |
| hubspot_synced | BOOLEAN | Whether HubSpot sync succeeded (default: false) |
| created_at | TIMESTAMPTZ | Auto |

**RLS:** Service role full access only. Indexes on `brand` and `email`.

### dns_services
Reusable DNS record templates (e.g., "google-workspace" = 5 MX + SPF + DKIM + DMARC).

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | Slug: `google-workspace`, `email-security-baseline`, `vercel-hosting`, `render-hosting`, `cloudflare-redirect` |
| name | TEXT | Human-readable name |
| description | TEXT | What this service provides |
| provider | TEXT | Google, Vercel, Render, Cloudflare, internal |
| record_templates | JSONB | Array of record objects with type/name/content/priority/ttl/proxied |
| created_at | TIMESTAMPTZ | Auto |

### dns_domain_config
Per-domain source of truth. Links each domain to its tier, Cloudflare zone ID, and assigned services.

| Column | Type | Notes |
|--------|------|-------|
| domain | TEXT PK | e.g., `omapex.com` |
| tier | INTEGER | 1–5 matching domain inventory tiers |
| tier_label | TEXT | `active`, `near_term`, `future`, `brand_protection`, `discontinue` |
| cloudflare_zone_id | TEXT | CF zone ID (populated by `dns_snapshot`) |
| services | TEXT[] | Array of `dns_services.id` assigned to this domain |
| redirect_target | TEXT | Target domain if redirect (e.g., `aiquorum.ai`) |
| custom_records | JSONB | Domain-specific records not from a service template |
| notes | TEXT | Human notes (includes email user info for email domains) |
| last_audit_at | TIMESTAMPTZ | Last audit timestamp |
| last_audit_status | TEXT | `pass`, `drift`, `error` |

**21 domains seeded.** 4 email domains use `google-workspace`; 16 non-email use `email-security-baseline`; 2 redirects also use `cloudflare-redirect`; theomgroup.ai has no services (Tier 5, audit-only).

### dns_policies
Audit rules checked on every `dns_audit` run.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | e.g., `global-spf-required`, `email-dkim-required` |
| name | TEXT | Human-readable name |
| scope | TEXT | `global`, `tier:1`, `service:google-workspace`, `domain:omapex.com` |
| rule_type | TEXT | `record_required`, `record_forbidden`, `record_value_match` |
| rule | JSONB | Check spec: `{type, name, content_startswith, content_contains, content_contains_any}` |
| severity | TEXT | `critical`, `warning`, `info` |
| auto_heal | BOOLEAN | Can Sentinel fix without approval? |
| heal_action | JSONB | `{action: "add"/"upsert"/"add_if_missing", record: {...}}` |
| enabled | BOOLEAN | Active or disabled |

**15 policies seeded:** 3 global, 5 email-domain, 3 non-email, 1 Tier 1 CAA, 1 redirect, 1 Tier 5 audit-only.

### dns_audit_log
Full record of every audit run with findings and summary.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| run_id | TEXT | e.g., `AUDIT-20260225-143022` |
| run_type | TEXT | `scheduled`, `manual`, `snapshot` |
| domains_scanned | INTEGER | Count |
| total_records_checked | INTEGER | Count |
| findings | JSONB | Array of finding objects: `{domain, severity, policy_id, description, healed, queued_for_approval}` |
| summary | JSONB | `{pass, drift, auto_healed, pending_approval}` |
| triggered_by | TEXT | `manual`, `cron`, `claude` |
| started_at / completed_at | TIMESTAMPTZ | Run timing |

### dns_change_log
Full audit trail of every DNS record modification.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| domain | TEXT | Which domain |
| change_type | TEXT | `auto_heal`, `approved`, `manual`, `drift_detected` |
| record_type | TEXT | A, CNAME, MX, TXT, CAA, etc. |
| record_name | TEXT | `@`, `_dmarc`, `www`, etc. |
| action | TEXT | `create`, `update`, `delete` |
| before_value | JSONB | Full record before change (null for create) |
| after_value | JSONB | Full record after change (null for delete) |
| cloudflare_record_id | TEXT | CF record ID |
| audit_run_id | TEXT | Links to dns_audit_log.run_id |
| policy_id | TEXT | Which policy triggered this |
| applied_by | TEXT | `sentinel`, `manual`, `claude` |
| notes | TEXT | Context notes |
| created_at | TIMESTAMPTZ | Auto |

Index: `idx_dns_change_log_domain` on `(domain, created_at DESC)`

### dns_approval_queue
Changes that require human approval before applying to Cloudflare.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| domain | TEXT | Which domain |
| record_type | TEXT | A, CNAME, MX, TXT, etc. |
| record_name | TEXT | `@`, `_dmarc`, etc. |
| action | TEXT | `create`, `update`, `delete` |
| current_value | JSONB | Current record (null for create) |
| proposed_value | JSONB | Proposed new record |
| reason | TEXT | Why change is proposed |
| risk_level | TEXT | `high`, `medium`, `low` |
| status | TEXT | `pending`, `approved`, `rejected`, `expired` |
| reviewed_by | TEXT | Who acted on it |
| review_notes | TEXT | Notes from reviewer |
| created_at | TIMESTAMPTZ | Auto |
| expires_at | TIMESTAMPTZ | Auto-expires 7 days after creation |
| audit_run_id | TEXT | Links to dns_audit_log.run_id |
| policy_id | TEXT | Which policy triggered this |

**Note:** Tier 5 domains (`theomgroup.ai`) are never queued — audit-only.

Index: `idx_dns_approval_queue_status` on `(status, expires_at)`

### dns_snapshots
Raw Cloudflare DNS record snapshots per domain per run.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| domain | TEXT | Which domain |
| records | JSONB | Full array of CF DNS records (as returned by Cloudflare API) |
| record_count | INTEGER | Count of records |
| taken_at | TIMESTAMPTZ | When snapshot was taken |

Index: `idx_dns_snapshots_domain_taken` on `(domain, taken_at DESC)`

**Usage:** `dns_view_snapshot` shows the latest snapshot per domain. Multiple snapshots per domain are retained for history.

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

### marketing_channels
Marketing channel master table for coupon attribution.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| name | TEXT UNIQUE | Display name (e.g., "LinkedIn") |
| slug | TEXT UNIQUE | URL-safe slug (e.g., "linkedin") |
| description | TEXT | Channel description |
| is_active | BOOLEAN | Default true |
| created_at | TIMESTAMPTZ | Auto |

Seeded with: LinkedIn, X/Twitter, Facebook, AI Blog, SCM Blog, Refer a Friend.

### coupons
Campaign, referral, and weekly coupons with full lifecycle management.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| code | TEXT UNIQUE | Coupon code (uppercased) |
| channel_id | UUID FK | References marketing_channels(id) |
| source | TEXT | `campaign`, `referral`, `weekly` |
| source_campaign | TEXT | Campaign identifier (optional) |
| credits_amount | INT | Credits awarded (default 500) |
| status | TEXT | `draft`, `published`, `expired`, `exhausted`, `deactivated` |
| valid_from | TIMESTAMPTZ | Default now() |
| valid_until | TIMESTAMPTZ | Expiry date (nullable) |
| max_uses | INT | Usage limit (nullable = unlimited) |
| current_uses | INT | Current redemption count (default 0) |
| referrer_user_id | UUID FK | References auth.users (for referral coupons) |
| referrer_bonus_credits | INT | Bonus for referrer (default 0) |
| notes | TEXT | Admin notes |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |
| published_at | TIMESTAMPTZ | When admin published |
| published_by | TEXT | Who published |

**RLS:** Users can read published coupons. Service role has full access.
**Seed:** WELCOME2026 (published, ai-blog channel, 500 credits, no expiry).

### coupon_redemptions
Per-user coupon usage history for analytics.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| coupon_id | UUID FK | References coupons(id) |
| user_id | UUID FK | References auth.users(id) |
| credits_awarded | INT | Credits given |
| redeemed_at | TIMESTAMPTZ | Default now() |

**Constraint:** UNIQUE(coupon_id, user_id) — one redemption per user per coupon.

### referral_conversions
Tracks referral bonus conversions (deferred — for Stripe integration).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| referral_coupon_id | UUID FK | References coupons(id) |
| referred_user_id | UUID FK | References auth.users(id) |
| referrer_user_id | UUID FK | References auth.users(id) |
| conversion_type | TEXT | Default `signup` |
| bonus_credits_awarded | INT | Default 0 |
| converted_at | TIMESTAMPTZ | Default now() |

### v_coupon_attribution (View)
Joins coupons + marketing_channels + aggregated redemption counts. Used by admin coupon management UI.

Columns: All coupons columns + `channel_name`, `channel_slug`, `redemption_count`, `total_credits_awarded`.

### RPC Functions (Coupon System)

**redeem_coupon(p_code TEXT, p_user_id UUID)**
Validates coupon status (published), checks expiry/max_uses/already-redeemed, updates `profiles.credits_remaining`, inserts redemption record, increments `current_uses`. Returns JSON `{success, credits_awarded, new_balance}` or `{success: false, error: "ERROR_CODE"}`.

**generate_referral_coupon(p_user_id UUID)**
Creates or retrieves a referral coupon for the user. Source='referral', channel='refer-a-friend', auto-published (bypasses admin). Code pattern: `REFER-{8chars}`. Returns JSON with coupon details.

**generate_weekly_coupons()**
For each active marketing channel, creates a draft coupon with source='weekly', valid_until = 7 days. Code pattern: `WEEKLY-{SLUG}-{YYYYWW}`. Returns array of created coupon objects.

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

### cortex_publish_log (Phase 5)
Tracks every outbound publish attempt (Post This feature).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| turn_id | TEXT | AI Quorum turn ID being published |
| user_id | TEXT | User who triggered publish |
| channel | TEXT | `linkedin`, `x`, `whatsapp`, `telegram`, `email`, `slack`, `teams` |
| status | TEXT | `queued`, `sent`, `failed` (CHECK constraint) |
| content_type | TEXT | `verdict`, `insights`, `report` |
| formatted_content | TEXT | Channel-formatted text |
| verdict_card_url | TEXT | PNG URL in Supabase Storage |
| error_message | TEXT | Error if failed (nullable) |
| created_at | TIMESTAMPTZ | Auto |
| sent_at | TIMESTAMPTZ | Null until sent |

Indexes: `idx_publish_log_user` on `(user_id)`, `idx_publish_log_turn` on `(turn_id)`

### cortex_oauth_tokens (Phase 5)
Encrypted OAuth credentials per user/channel. Tokens stored with AES-256-GCM encryption.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| user_id | TEXT | User identifier |
| channel | TEXT | `linkedin`, `x`, `slack` (OAuth channels) |
| access_token | TEXT | AES-256-GCM encrypted |
| refresh_token | TEXT | AES-256-GCM encrypted (nullable) |
| expires_at | TIMESTAMPTZ | Token expiry (nullable) |
| scopes | TEXT[] | Granted OAuth scopes |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

Unique constraint: `(user_id, channel)`. Index: `idx_oauth_tokens_user_channel`.

### cortex_channel_configs (Phase 5)
Channel configuration and enable/disable state per user. Used for non-OAuth channels (WhatsApp, Telegram, Email, Teams) that use API keys/webhooks.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | Auto-generated |
| user_id | TEXT | User identifier |
| channel | TEXT | Channel name |
| config | JSONB | Channel-specific config (apiKey, webhookUrl, phoneNumberId, etc.) |
| enabled | BOOL | Default true |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

Unique constraint: `(user_id, channel)`. Index: `idx_channel_configs_user`.
