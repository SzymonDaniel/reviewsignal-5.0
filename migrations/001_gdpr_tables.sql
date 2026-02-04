-- GDPR Compliance Tables Migration
-- ReviewSignal 5.0 - GDPR Module
-- Created: 2026-02-04

-- ═══════════════════════════════════════════════════════════════════
-- 1. GDPR CONSENTS TABLE
-- Tracks consent status for each subject (Art. 7 GDPR)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS gdpr_consents (
    consent_id SERIAL PRIMARY KEY,
    subject_email VARCHAR(255) NOT NULL,
    consent_type VARCHAR(50) NOT NULL CHECK (consent_type IN ('marketing', 'data_processing', 'analytics', 'third_party_sharing')),
    status VARCHAR(20) NOT NULL DEFAULT 'granted' CHECK (status IN ('granted', 'withdrawn', 'expired')),
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    withdrawn_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    consent_version VARCHAR(20) DEFAULT '1.0',
    consent_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uq_consent_subject_type UNIQUE (subject_email, consent_type)
);

CREATE INDEX IF NOT EXISTS idx_gdpr_consents_email ON gdpr_consents(subject_email);
CREATE INDEX IF NOT EXISTS idx_gdpr_consents_status ON gdpr_consents(status);
CREATE INDEX IF NOT EXISTS idx_gdpr_consents_type ON gdpr_consents(consent_type);
CREATE INDEX IF NOT EXISTS idx_gdpr_consents_expires ON gdpr_consents(expires_at) WHERE expires_at IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════
-- 2. GDPR REQUESTS TABLE
-- Tracks data subject requests (Art. 15-22 GDPR)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS gdpr_requests (
    request_id SERIAL PRIMARY KEY,
    subject_email VARCHAR(255) NOT NULL,
    request_type VARCHAR(30) NOT NULL CHECK (request_type IN ('data_export', 'data_erasure', 'data_access', 'data_rectification', 'processing_restriction', 'data_portability')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'rejected', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deadline_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    processed_by VARCHAR(255),
    result_file_url VARCHAR(500),
    result_file_size INTEGER,
    rejection_reason TEXT,
    notes TEXT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    verification_token VARCHAR(255),
    verified_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_gdpr_requests_email ON gdpr_requests(subject_email);
CREATE INDEX IF NOT EXISTS idx_gdpr_requests_status ON gdpr_requests(status);
CREATE INDEX IF NOT EXISTS idx_gdpr_requests_type ON gdpr_requests(request_type);
CREATE INDEX IF NOT EXISTS idx_gdpr_requests_deadline ON gdpr_requests(deadline_at);
CREATE INDEX IF NOT EXISTS idx_gdpr_requests_pending ON gdpr_requests(status, deadline_at) WHERE status IN ('pending', 'in_progress');

-- ═══════════════════════════════════════════════════════════════════
-- 3. GDPR AUDIT LOG TABLE
-- Immutable audit trail for GDPR compliance (Art. 30 GDPR)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS gdpr_audit_log (
    audit_id SERIAL PRIMARY KEY,
    action VARCHAR(50) NOT NULL CHECK (action IN (
        'consent_granted', 'consent_withdrawn', 'consent_expired',
        'data_accessed', 'data_exported', 'data_deleted', 'data_anonymized',
        'request_created', 'request_processed', 'request_completed', 'request_rejected',
        'retention_cleanup', 'policy_updated',
        'verification_sent', 'verification_completed'
    )),
    subject_email VARCHAR(255),
    affected_tables TEXT[],
    affected_records_count INTEGER DEFAULT 0,
    performed_by VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    request_id INTEGER REFERENCES gdpr_requests(request_id),
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdpr_audit_email ON gdpr_audit_log(subject_email);
CREATE INDEX IF NOT EXISTS idx_gdpr_audit_action ON gdpr_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_gdpr_audit_created ON gdpr_audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_gdpr_audit_request ON gdpr_audit_log(request_id) WHERE request_id IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════
-- 4. DATA RETENTION POLICIES TABLE
-- Defines automatic data cleanup rules
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS data_retention_policies (
    policy_id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL UNIQUE,
    retention_days INTEGER NOT NULL CHECK (retention_days > 0),
    action VARCHAR(20) NOT NULL DEFAULT 'delete' CHECK (action IN ('delete', 'anonymize', 'archive')),
    condition_column VARCHAR(100),
    condition_value VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    last_run_at TIMESTAMP WITH TIME ZONE,
    last_run_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default retention policies
INSERT INTO data_retention_policies (table_name, retention_days, action, condition_column, condition_value) VALUES
    ('leads', 730, 'delete', 'status', 'lost'),
    ('outreach_log', 365, 'delete', NULL, NULL),
    ('user_sessions', 90, 'delete', NULL, NULL),
    ('gdpr_audit_log', 2555, 'archive', NULL, NULL)
ON CONFLICT (table_name) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════
-- 5. TRIGGERS FOR UPDATED_AT
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_gdpr_consents_updated_at ON gdpr_consents;
CREATE TRIGGER update_gdpr_consents_updated_at
    BEFORE UPDATE ON gdpr_consents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_gdpr_requests_updated_at ON gdpr_requests;
CREATE TRIGGER update_gdpr_requests_updated_at
    BEFORE UPDATE ON gdpr_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_data_retention_policies_updated_at ON data_retention_policies;
CREATE TRIGGER update_data_retention_policies_updated_at
    BEFORE UPDATE ON data_retention_policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ═══════════════════════════════════════════════════════════════════
-- 6. HELPER VIEWS
-- ═══════════════════════════════════════════════════════════════════

-- View: Pending GDPR requests (for admin dashboard)
CREATE OR REPLACE VIEW vw_gdpr_pending_requests AS
SELECT
    r.request_id,
    r.subject_email,
    r.request_type,
    r.status,
    r.created_at,
    r.deadline_at,
    r.deadline_at - NOW() AS time_remaining,
    CASE
        WHEN r.deadline_at < NOW() THEN true
        ELSE false
    END AS is_overdue
FROM gdpr_requests r
WHERE r.status IN ('pending', 'in_progress')
ORDER BY r.deadline_at ASC;

-- View: Active consents by subject
CREATE OR REPLACE VIEW vw_gdpr_active_consents AS
SELECT
    c.subject_email,
    array_agg(c.consent_type) AS consent_types,
    COUNT(*) AS consent_count,
    MIN(c.granted_at) AS first_consent,
    MAX(c.granted_at) AS last_consent
FROM gdpr_consents c
WHERE c.status = 'granted'
  AND (c.expires_at IS NULL OR c.expires_at > NOW())
GROUP BY c.subject_email;

-- View: GDPR compliance summary
CREATE OR REPLACE VIEW vw_gdpr_compliance_summary AS
SELECT
    (SELECT COUNT(*) FROM gdpr_consents WHERE status = 'granted') AS active_consents,
    (SELECT COUNT(*) FROM gdpr_requests WHERE status = 'pending') AS pending_requests,
    (SELECT COUNT(*) FROM gdpr_requests WHERE status = 'in_progress') AS in_progress_requests,
    (SELECT COUNT(*) FROM gdpr_requests WHERE deadline_at < NOW() AND status IN ('pending', 'in_progress')) AS overdue_requests,
    (SELECT COUNT(*) FROM gdpr_requests WHERE status = 'completed' AND completed_at > NOW() - INTERVAL '30 days') AS completed_last_30d,
    (SELECT COUNT(*) FROM gdpr_audit_log WHERE created_at > NOW() - INTERVAL '24 hours') AS audit_events_24h;

-- ═══════════════════════════════════════════════════════════════════
-- GRANTS (adjust user as needed)
-- ═══════════════════════════════════════════════════════════════════

-- Grant permissions to reviewsignal user (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'reviewsignal') THEN
        GRANT ALL PRIVILEGES ON TABLE gdpr_consents TO reviewsignal;
        GRANT ALL PRIVILEGES ON TABLE gdpr_requests TO reviewsignal;
        GRANT ALL PRIVILEGES ON TABLE gdpr_audit_log TO reviewsignal;
        GRANT ALL PRIVILEGES ON TABLE data_retention_policies TO reviewsignal;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO reviewsignal;
        GRANT SELECT ON vw_gdpr_pending_requests TO reviewsignal;
        GRANT SELECT ON vw_gdpr_active_consents TO reviewsignal;
        GRANT SELECT ON vw_gdpr_compliance_summary TO reviewsignal;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════
-- VERIFICATION QUERIES
-- ═══════════════════════════════════════════════════════════════════

-- Verify tables created
DO $$
BEGIN
    RAISE NOTICE 'GDPR Tables Migration Complete';
    RAISE NOTICE '================================';
    RAISE NOTICE 'Tables created: gdpr_consents, gdpr_requests, gdpr_audit_log, data_retention_policies';
    RAISE NOTICE 'Views created: vw_gdpr_pending_requests, vw_gdpr_active_consents, vw_gdpr_compliance_summary';
END $$;
