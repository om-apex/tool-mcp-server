-- Document templates table for storing markdown templates
CREATE TABLE IF NOT EXISTS document_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    filename TEXT NOT NULL,
    content TEXT NOT NULL,
    description TEXT,
    variables TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Company configs table for storing branding and legal info
CREATE TABLE IF NOT EXISTS company_configs (
    id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    short_name TEXT,
    config JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE document_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_configs ENABLE ROW LEVEL SECURITY;

-- Allow service role and authenticated users full access
CREATE POLICY "Allow all access" ON document_templates FOR ALL USING (true);
CREATE POLICY "Allow all access" ON company_configs FOR ALL USING (true);

-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_document_templates_name ON document_templates(name);
CREATE INDEX IF NOT EXISTS idx_company_configs_company_name ON company_configs(company_name);
CREATE INDEX IF NOT EXISTS idx_company_configs_short_name ON company_configs(short_name);
