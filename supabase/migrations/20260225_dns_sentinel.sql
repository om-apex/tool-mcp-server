-- DNS Sentinel Schema Migration
-- Owner Portal Supabase (hympgocuivzxzxllgmcy)
-- Run via Supabase Dashboard > SQL Editor

-- ============================================================
-- 1. dns_services — reusable service record templates
-- ============================================================
CREATE TABLE IF NOT EXISTS dns_services (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    provider    TEXT,
    record_templates JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. dns_domain_config — per-domain source of truth
-- ============================================================
CREATE TABLE IF NOT EXISTS dns_domain_config (
    domain              TEXT PRIMARY KEY,
    tier                INTEGER,
    tier_label          TEXT,
    cloudflare_zone_id  TEXT,
    services            TEXT[] DEFAULT '{}',
    redirect_target     TEXT,
    custom_records      JSONB DEFAULT '[]',
    notes               TEXT,
    last_audit_at       TIMESTAMPTZ,
    last_audit_status   TEXT
);

-- ============================================================
-- 3. dns_policies — audit rules
-- ============================================================
CREATE TABLE IF NOT EXISTS dns_policies (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    scope       TEXT NOT NULL,
    rule_type   TEXT NOT NULL,
    rule        JSONB NOT NULL,
    severity    TEXT NOT NULL DEFAULT 'warning',
    auto_heal   BOOLEAN NOT NULL DEFAULT FALSE,
    heal_action JSONB,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 4. dns_audit_log — audit run results
-- ============================================================
CREATE TABLE IF NOT EXISTS dns_audit_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              TEXT NOT NULL,
    run_type            TEXT NOT NULL DEFAULT 'manual',
    domains_scanned     INTEGER DEFAULT 0,
    total_records_checked INTEGER DEFAULT 0,
    findings            JSONB DEFAULT '[]',
    summary             JSONB DEFAULT '{}',
    triggered_by        TEXT DEFAULT 'manual',
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

-- ============================================================
-- 5. dns_change_log — every DNS modification
-- ============================================================
CREATE TABLE IF NOT EXISTS dns_change_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain              TEXT NOT NULL,
    change_type         TEXT NOT NULL,
    record_type         TEXT,
    record_name         TEXT,
    action              TEXT NOT NULL,
    before_value        JSONB,
    after_value         JSONB,
    cloudflare_record_id TEXT,
    audit_run_id        TEXT,
    policy_id           TEXT,
    applied_by          TEXT DEFAULT 'sentinel',
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 6. dns_approval_queue — changes needing human approval
-- ============================================================
CREATE TABLE IF NOT EXISTS dns_approval_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain          TEXT NOT NULL,
    record_type     TEXT,
    record_name     TEXT,
    action          TEXT NOT NULL,
    current_value   JSONB,
    proposed_value  JSONB,
    reason          TEXT,
    risk_level      TEXT DEFAULT 'medium',
    status          TEXT NOT NULL DEFAULT 'pending',
    reviewed_by     TEXT,
    review_notes    TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '7 days'),
    audit_run_id    TEXT,
    policy_id       TEXT
);

-- ============================================================
-- 7. dns_snapshots — raw Cloudflare record snapshots
-- ============================================================
CREATE TABLE IF NOT EXISTS dns_snapshots (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain      TEXT NOT NULL,
    records     JSONB NOT NULL DEFAULT '[]',
    record_count INTEGER DEFAULT 0,
    taken_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dns_snapshots_domain_taken ON dns_snapshots(domain, taken_at DESC);
CREATE INDEX IF NOT EXISTS idx_dns_change_log_domain ON dns_change_log(domain, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dns_approval_queue_status ON dns_approval_queue(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_dns_audit_log_run_id ON dns_audit_log(run_id);

-- ============================================================
-- SEED: dns_services
-- ============================================================
INSERT INTO dns_services (id, name, description, provider, record_templates) VALUES

('google-workspace', 'Google Workspace Email', 'MX + SPF + DKIM + DMARC for Google Workspace email', 'Google', '[
  {"type": "MX", "name": "@", "content": "aspmx.l.google.com", "priority": 1, "ttl": 3600},
  {"type": "MX", "name": "@", "content": "alt1.aspmx.l.google.com", "priority": 5, "ttl": 3600},
  {"type": "MX", "name": "@", "content": "alt2.aspmx.l.google.com", "priority": 5, "ttl": 3600},
  {"type": "MX", "name": "@", "content": "alt3.aspmx.l.google.com", "priority": 10, "ttl": 3600},
  {"type": "MX", "name": "@", "content": "alt4.aspmx.l.google.com", "priority": 10, "ttl": 3600},
  {"type": "TXT", "name": "@", "content": "v=spf1 include:_spf.google.com ~all", "ttl": 3600},
  {"type": "CNAME", "name": "google._domainkey", "content": "google._domainkey.omapex.com.dkim.akamaidefaultssl.com", "ttl": 3600, "note": "Replace with actual DKIM value from Google Admin"},
  {"type": "TXT", "name": "_dmarc", "content": "v=DMARC1; p=quarantine; rua=mailto:dmarc@omapex.com; ruf=mailto:dmarc@omapex.com; fo=1", "ttl": 3600}
]'::jsonb),

('email-security-baseline', 'Email Security Baseline (Non-Email Domains)', 'SPF hard reject + DMARC reject for domains that do not send email', 'internal', '[
  {"type": "TXT", "name": "@", "content": "v=spf1 -all", "ttl": 3600},
  {"type": "TXT", "name": "_dmarc", "content": "v=DMARC1; p=reject; rua=mailto:dmarc@omapex.com", "ttl": 3600}
]'::jsonb),

('vercel-hosting', 'Vercel Hosting', 'A record for Vercel frontend deployments', 'Vercel', '[
  {"type": "A", "name": "@", "content": "76.76.21.21", "ttl": 1, "proxied": false},
  {"type": "CNAME", "name": "www", "content": "cname.vercel-dns.com", "ttl": 1, "proxied": false}
]'::jsonb),

('render-hosting', 'Render Hosting', 'CNAME for Render backend service deployments', 'Render', '[
  {"type": "CNAME", "name": "@", "content": "your-service.onrender.com", "ttl": 1, "proxied": false, "note": "Replace with actual Render service URL"}
]'::jsonb),

('cloudflare-redirect', 'Cloudflare Redirect (Proxy)', 'Dummy A record + www CNAME for Cloudflare-proxied domain redirects', 'Cloudflare', '[
  {"type": "A", "name": "@", "content": "192.0.2.1", "ttl": 1, "proxied": true},
  {"type": "CNAME", "name": "www", "content": "@", "ttl": 1, "proxied": true}
]'::jsonb)

ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    provider = EXCLUDED.provider,
    record_templates = EXCLUDED.record_templates;

-- ============================================================
-- SEED: dns_domain_config
-- ============================================================
INSERT INTO dns_domain_config (domain, tier, tier_label, services, redirect_target, notes) VALUES
-- Tier 1: Active
('omapex.com',            1, 'active',           ARRAY['google-workspace'],                                   NULL, 'Primary company domain. Google Workspace primary domain. nishad@omapex.com, sumedha@omapex.com'),
('omluxeproperties.com',  1, 'active',           ARRAY['google-workspace'],                                   NULL, 'Om Luxe Properties LLC. Google Workspace alternate domain. nishad@omluxeproperties.com'),
('omaisolutions.com',     1, 'active',           ARRAY['google-workspace'],                                   NULL, 'Om AI Solutions LLC. Google Workspace alternate domain. nishad@omaisolutions.com'),
('aiquorum.ai',           1, 'active',           ARRAY['email-security-baseline'],                            NULL, 'AI Quorum product domain. No email.'),
('omcortex.ai',           1, 'active',           ARRAY['email-security-baseline'],                            NULL, 'Om Cortex product domain. No email.'),
-- Tier 2: Near-term
('omwms.com',             2, 'near_term',        ARRAY['email-security-baseline'],                            NULL, 'Om WMS primary domain. No email yet.'),
('omwms.ai',              2, 'near_term',        ARRAY['email-security-baseline', 'cloudflare-redirect'],     'omwms.com', 'Redirects to omwms.com'),
('omvoice.ai',            2, 'near_term',        ARRAY['email-security-baseline'],                            NULL, 'Om Voice product domain. No email.'),
('omvoiceai.com',         2, 'near_term',        ARRAY['email-security-baseline', 'cloudflare-redirect'],     'omvoice.ai', 'Redirects to omvoice.ai'),
('omlms.com',             2, 'near_term',        ARRAY['email-security-baseline'],                            NULL, 'Om LMS domain. No email.'),
('omtms.com',             2, 'near_term',        ARRAY['email-security-baseline'],                            NULL, 'Om TMS domain. No email.'),
-- Tier 3: Future
('omintm.com',            3, 'future',           ARRAY['email-security-baseline'],                            NULL, 'Om ITM — intelligent transport management. Reserved.'),
('omintegrator.com',      3, 'future',           ARRAY['email-security-baseline'],                            NULL, 'Om Integrator. Reserved.'),
('omsfm.com',             3, 'future',           ARRAY['email-security-baseline'],                            NULL, 'Om SFM — store/shop floor management. Reserved.'),
('omstorefront.com',      3, 'future',           ARRAY['email-security-baseline'],                            NULL, 'Om Storefront. Reserved.'),
('omshopfloor.com',       3, 'future',           ARRAY['email-security-baseline'],                            NULL, 'Om Shop Floor. Reserved.'),
('omepos.com',            3, 'future',           ARRAY['email-security-baseline'],                            NULL, 'Om ePOS. Reserved.'),
-- Tier 4: Brand protection
('omsupplychain.com',     4, 'brand_protection', ARRAY['google-workspace'],                                   NULL, 'Om Supply Chain LLC. Google Workspace alternate domain despite Tier 4. nishad@omsupplychain.com'),
('omsupplychainsolutions.com', 4, 'brand_protection', ARRAY['email-security-baseline'],                       NULL, 'Brand protection. No email.'),
('omsupplychain.ai',      4, 'brand_protection', ARRAY['email-security-baseline'],                            NULL, 'Brand protection. No email.'),
('omquorum.com',          4, 'brand_protection', ARRAY['email-security-baseline', 'cloudflare-redirect'],     'aiquorum.ai', 'Redirects to aiquorum.ai'),
-- Tier 5: Discontinue
('theomgroup.ai',         5, 'discontinue',      ARRAY[]::TEXT[],                                             NULL, 'DO NOT RENEW. Audit only — no auto-heal.')
ON CONFLICT (domain) DO UPDATE SET
    tier = EXCLUDED.tier,
    tier_label = EXCLUDED.tier_label,
    services = EXCLUDED.services,
    redirect_target = EXCLUDED.redirect_target,
    notes = EXCLUDED.notes;

-- ============================================================
-- SEED: dns_policies
-- ============================================================
INSERT INTO dns_policies (id, name, scope, rule_type, rule, severity, auto_heal, heal_action, enabled) VALUES

-- Global policies
('global-spf-required', 'SPF Record Required', 'global', 'record_required',
 '{"type": "TXT", "name": "@", "content_startswith": "v=spf1"}'::jsonb,
 'critical', false, NULL, true),

('global-dmarc-required', 'DMARC Record Required', 'global', 'record_required',
 '{"type": "TXT", "name": "_dmarc", "content_startswith": "v=DMARC1"}'::jsonb,
 'critical', true,
 '{"action": "add", "record": {"type": "TXT", "name": "_dmarc", "content": "v=DMARC1; p=reject; rua=mailto:dmarc@omapex.com", "ttl": 3600}}'::jsonb,
 true),

('global-no-open-spf', 'No Open SPF (+all)', 'global', 'record_forbidden',
 '{"type": "TXT", "name": "@", "content_contains": "+all"}'::jsonb,
 'critical', true,
 '{"action": "description", "note": "Remove +all and replace with ~all or -all"}'::jsonb,
 true),

-- Email domain policies (4 sending domains)
('email-mx-google', 'Google MX Records Required', 'service:google-workspace', 'record_required',
 '{"type": "MX", "name": "@", "content": "aspmx.l.google.com"}'::jsonb,
 'critical', false, NULL, true),

('email-spf-google', 'SPF Must Include Google', 'service:google-workspace', 'record_value_match',
 '{"type": "TXT", "name": "@", "content_contains": "include:_spf.google.com"}'::jsonb,
 'critical', false, NULL, true),

('email-spf-softfail', 'SPF Must Use ~all (Not -all) for Email Domains', 'service:google-workspace', 'record_value_match',
 '{"type": "TXT", "name": "@", "content_contains": "~all"}'::jsonb,
 'warning', false, NULL, true),

('email-dkim-required', 'DKIM Record Required', 'service:google-workspace', 'record_required',
 '{"type": "CNAME", "name": "google._domainkey"}'::jsonb,
 'critical', false, NULL, true),

('email-dmarc-policy', 'DMARC Policy Must Be quarantine or reject', 'service:google-workspace', 'record_value_match',
 '{"type": "TXT", "name": "_dmarc", "content_contains_any": ["p=quarantine", "p=reject"]}'::jsonb,
 'critical', false, NULL, true),

('email-dmarc-rua', 'DMARC Must Include Reporting (rua)', 'service:google-workspace', 'record_value_match',
 '{"type": "TXT", "name": "_dmarc", "content_contains": "rua=mailto:"}'::jsonb,
 'warning', true,
 '{"action": "description", "note": "Add rua=mailto:dmarc@omapex.com to DMARC record"}'::jsonb,
 true),

-- Non-email domain policies (email-security-baseline)
('non-email-spf-reject', 'Non-Email Domains Must Use -all', 'service:email-security-baseline', 'record_value_match',
 '{"type": "TXT", "name": "@", "content": "v=spf1 -all"}'::jsonb,
 'critical', true,
 '{"action": "upsert", "record": {"type": "TXT", "name": "@", "content": "v=spf1 -all", "ttl": 3600}}'::jsonb,
 true),

('non-email-dmarc-reject', 'Non-Email Domains DMARC Must Reject', 'service:email-security-baseline', 'record_value_match',
 '{"type": "TXT", "name": "_dmarc", "content_contains": "p=reject"}'::jsonb,
 'critical', true,
 '{"action": "upsert", "record": {"type": "TXT", "name": "_dmarc", "content": "v=DMARC1; p=reject; rua=mailto:dmarc@omapex.com", "ttl": 3600}}'::jsonb,
 true),

('non-email-no-mx', 'Non-Email Domains Must Not Have MX Records', 'service:email-security-baseline', 'record_forbidden',
 '{"type": "MX"}'::jsonb,
 'warning', false, NULL, true),

-- Tier 1 additional
('tier1-caa-required', 'CAA Records Required on Tier 1 Domains', 'tier:1', 'record_required',
 '{"type": "CAA", "name": "@"}'::jsonb,
 'warning', true,
 '{"action": "add_if_missing", "records": [
   {"type": "CAA", "name": "@", "data": {"flags": 0, "tag": "issue", "value": "letsencrypt.org"}, "ttl": 3600},
   {"type": "CAA", "name": "@", "data": {"flags": 0, "tag": "issue", "value": "digicert.com"}, "ttl": 3600},
   {"type": "CAA", "name": "@", "data": {"flags": 0, "tag": "iodef", "value": "mailto:dns@omapex.com"}, "ttl": 3600}
 ]}'::jsonb,
 true),

-- Redirect domain policies
('redirect-has-a-record', 'Redirect Domains Must Have Proxied A Record', 'service:cloudflare-redirect', 'record_required',
 '{"type": "A", "name": "@", "proxied": true}'::jsonb,
 'warning', true,
 '{"action": "add", "record": {"type": "A", "name": "@", "content": "192.0.2.1", "ttl": 1, "proxied": true}}'::jsonb,
 true),

-- Tier 5 audit-only policy (no auto-heal)
('tier5-audit-only', 'Tier 5 Domains: Audit Only, No Auto-Heal', 'tier:5', 'record_required',
 '{"note": "Tier 5 domains are flagged for discontinuation. Report issues only."}'::jsonb,
 'info', false, NULL, true)

ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    scope = EXCLUDED.scope,
    rule_type = EXCLUDED.rule_type,
    rule = EXCLUDED.rule,
    severity = EXCLUDED.severity,
    auto_heal = EXCLUDED.auto_heal,
    heal_action = EXCLUDED.heal_action,
    enabled = EXCLUDED.enabled;
