-- GDPR Extended Tables Migration
-- ReviewSignal 5.0
-- Adds: Processing Restrictions (Art. 18), Webhooks, Audit Enhancements

-- ═══════════════════════════════════════════════════════════════════════════════
-- PROCESSING RESTRICTIONS TABLE (Art. 18)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS gdpr_processing_restrictions (
    restriction_id SERIAL PRIMARY KEY,
    subject_email VARCHAR(255) NOT NULL,
    reason VARCHAR(50) NOT NULL,
    reason_details TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    restricted_operations JSONB DEFAULT '["all"]',
    restricted_tables JSONB DEFAULT '["all"]',
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    lifted_at TIMESTAMPTZ,
    lifted_by VARCHAR(255),
    lift_reason TEXT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    request_id INTEGER REFERENCES gdpr_requests(request_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdpr_restrictions_email ON gdpr_processing_restrictions(subject_email);
CREATE INDEX IF NOT EXISTS idx_gdpr_restrictions_active ON gdpr_processing_restrictions(is_active);
CREATE INDEX IF NOT EXISTS idx_gdpr_restrictions_reason ON gdpr_processing_restrictions(reason);


-- ═══════════════════════════════════════════════════════════════════════════════
-- WEBHOOK SUBSCRIPTIONS TABLE
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS gdpr_webhook_subscriptions (
    subscription_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    url VARCHAR(500) NOT NULL,
    secret VARCHAR(255) NOT NULL,
    events TEXT[] NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    headers JSONB DEFAULT '{}',
    retry_count INTEGER DEFAULT 3,
    timeout_seconds INTEGER DEFAULT 30,
    last_triggered_at TIMESTAMPTZ,
    last_status_code INTEGER,
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdpr_webhooks_active ON gdpr_webhook_subscriptions(is_active);


-- ═══════════════════════════════════════════════════════════════════════════════
-- WEBHOOK LOGS TABLE
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS gdpr_webhook_logs (
    log_id SERIAL PRIMARY KEY,
    subscription_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    response_status INTEGER,
    response_body TEXT,
    attempt_number INTEGER DEFAULT 1,
    success BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdpr_webhook_logs_subscription ON gdpr_webhook_logs(subscription_id);
CREATE INDEX IF NOT EXISTS idx_gdpr_webhook_logs_event ON gdpr_webhook_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_gdpr_webhook_logs_created ON gdpr_webhook_logs(created_at);


-- ═══════════════════════════════════════════════════════════════════════════════
-- ADD NEW AUDIT ACTION TYPES (if using enum)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Add new audit action types if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'audit_action_enum') THEN
        CREATE TYPE audit_action_enum AS ENUM (
            'consent_granted',
            'consent_withdrawn',
            'consent_expired',
            'data_accessed',
            'data_exported',
            'data_deleted',
            'data_anonymized',
            'data_rectified',
            'processing_restricted',
            'processing_restriction_lifted',
            'request_created',
            'request_processed',
            'request_completed',
            'request_rejected',
            'retention_cleanup',
            'policy_updated',
            'verification_sent',
            'verification_completed',
            'webhook_subscribed',
            'webhook_unsubscribed'
        );
    END IF;
END
$$;


-- ═══════════════════════════════════════════════════════════════════════════════
-- COMMENTS
-- ═══════════════════════════════════════════════════════════════════════════════

COMMENT ON TABLE gdpr_processing_restrictions IS 'Tracks processing restrictions per GDPR Art. 18';
COMMENT ON TABLE gdpr_webhook_subscriptions IS 'Webhook subscriptions for GDPR event notifications';
COMMENT ON TABLE gdpr_webhook_logs IS 'Delivery logs for GDPR webhooks';

COMMENT ON COLUMN gdpr_processing_restrictions.reason IS 'accuracy_contested, unlawful_processing, no_longer_needed, objection_pending';
COMMENT ON COLUMN gdpr_processing_restrictions.restricted_operations IS 'JSON array of restricted operations: read, update, delete, export, share, process, marketing';
COMMENT ON COLUMN gdpr_processing_restrictions.restricted_tables IS 'JSON array of restricted tables or ["all"]';


-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION METADATA
-- ═══════════════════════════════════════════════════════════════════════════════

-- Record migration
INSERT INTO gdpr_audit_log (action, subject_email, performed_by, details)
VALUES ('policy_updated', NULL, 'migration', '{"migration": "002_gdpr_extended", "tables_created": ["gdpr_processing_restrictions", "gdpr_webhook_subscriptions", "gdpr_webhook_logs"]}')
ON CONFLICT DO NOTHING;
