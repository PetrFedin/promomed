-- Candidate document custody only. No verified revenue is created by this migration.
-- The financial authority is external; all records have candidate status.
CREATE TABLE IF NOT EXISTS commercial_contract_versions(
 id TEXT PRIMARY KEY,
 organization_id TEXT NOT NULL,
 external_ref TEXT NOT NULL,
 version INTEGER NOT NULL CHECK(version>0),
 previous_contract_id TEXT,
 currency_code TEXT NOT NULL CHECK(LENGTH(currency_code)=3),
 net_amount_minor BIGINT NOT NULL CHECK(net_amount_minor>0),
 source_ref TEXT NOT NULL,
 evidence_sha256 TEXT NOT NULL CHECK(LENGTH(evidence_sha256)=64),
 state TEXT NOT NULL DEFAULT 'candidate' CHECK(state='candidate'),
 recorded_by TEXT NOT NULL,
 recorded_at BIGINT NOT NULL,
 demo_only INTEGER NOT NULL CHECK(demo_only IN (0,1)),
 idempotency_key TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL CHECK(LENGTH(payload_sha256)=64),
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,external_ref,version),
 UNIQUE(organization_id,idempotency_key),
 FOREIGN KEY(organization_id) REFERENCES institutional_organizations(id),
 FOREIGN KEY(organization_id,previous_contract_id)
    REFERENCES commercial_contract_versions(organization_id,id)
);
CREATE INDEX IF NOT EXISTS idx_commercial_contract_org
 ON commercial_contract_versions(organization_id,external_ref,version);

CREATE TABLE IF NOT EXISTS commercial_evidence_events(
 id TEXT PRIMARY KEY,
 organization_id TEXT NOT NULL,
 contract_id TEXT NOT NULL,
 event_type TEXT NOT NULL CHECK(event_type IN (
   'obligation','delivery','invoice','credit_note','settlement',
   'allocation','refund','direct_cost','recognition','finance_review','renewal')),
 external_ref TEXT NOT NULL,
 version INTEGER NOT NULL CHECK(version>0),
 replaces_event_id TEXT,
 parent_event_id TEXT,
 related_event_id TEXT,
 amount_minor BIGINT NOT NULL DEFAULT 0 CHECK(amount_minor>=0),
 tax_minor BIGINT NOT NULL DEFAULT 0 CHECK(tax_minor>=0),
 currency_code TEXT NOT NULL CHECK(LENGTH(currency_code)=3),
 accounting_period TEXT,
 decision TEXT,
 CHECK (
   (event_type='finance_review' AND decision IN ('hold','request_changes','rejected'))
   OR (event_type<>'finance_review' AND decision IS NULL)
 ),
 source_ref TEXT NOT NULL,
 evidence_sha256 TEXT NOT NULL CHECK(LENGTH(evidence_sha256)=64),
 state TEXT NOT NULL DEFAULT 'candidate' CHECK(state='candidate'),
 recorded_by TEXT NOT NULL,
 recorded_at BIGINT NOT NULL,
 demo_only INTEGER NOT NULL CHECK(demo_only IN (0,1)),
 idempotency_key TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL CHECK(LENGTH(payload_sha256)=64),
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,event_type,external_ref,version),
 UNIQUE(organization_id,idempotency_key),
 FOREIGN KEY(organization_id,contract_id)
    REFERENCES commercial_contract_versions(organization_id,id),
 FOREIGN KEY(organization_id,parent_event_id)
    REFERENCES commercial_evidence_events(organization_id,id),
 FOREIGN KEY(organization_id,related_event_id)
    REFERENCES commercial_evidence_events(organization_id,id),
 FOREIGN KEY(organization_id,replaces_event_id)
    REFERENCES commercial_evidence_events(organization_id,id)
);
CREATE INDEX IF NOT EXISTS idx_commercial_events_scope
 ON commercial_evidence_events(organization_id,contract_id,event_type,recorded_at);
CREATE INDEX IF NOT EXISTS idx_commercial_events_parent
 ON commercial_evidence_events(organization_id,parent_event_id,event_type);
CREATE INDEX IF NOT EXISTS idx_commercial_events_related
 ON commercial_evidence_events(organization_id,related_event_id,event_type);

-- Hash chain is tamper-evident within a DB snapshot, not a third-party signature.
-- The application serializes writes per org for this *non-public* candidate API.
CREATE TABLE IF NOT EXISTS commercial_evidence_audit(
 id TEXT PRIMARY KEY,
 organization_id TEXT NOT NULL,
 entry_no BIGINT NOT NULL CHECK(entry_no>0),
 entity_kind TEXT NOT NULL CHECK(entity_kind IN ('contract','event')),
 entity_id TEXT NOT NULL,
 entry_sha256 TEXT NOT NULL UNIQUE CHECK(LENGTH(entry_sha256)=64),
 previous_sha256 TEXT,
 recorded_by TEXT NOT NULL,
 recorded_at BIGINT NOT NULL,
 UNIQUE(organization_id,entry_no)
);
CREATE INDEX IF NOT EXISTS idx_commercial_audit_scope
 ON commercial_evidence_audit(organization_id,entry_no);

CREATE TRIGGER IF NOT EXISTS commercial_contract_update_denied
 BEFORE UPDATE ON commercial_contract_versions
 BEGIN SELECT RAISE(ABORT,'immutable_commercial_contract'); END;
CREATE TRIGGER IF NOT EXISTS commercial_contract_delete_denied
 BEFORE DELETE ON commercial_contract_versions
 BEGIN SELECT RAISE(ABORT,'immutable_commercial_contract'); END;
CREATE TRIGGER IF NOT EXISTS commercial_event_update_denied
 BEFORE UPDATE ON commercial_evidence_events
 BEGIN SELECT RAISE(ABORT,'immutable_commercial_event'); END;
CREATE TRIGGER IF NOT EXISTS commercial_event_delete_denied
 BEFORE DELETE ON commercial_evidence_events
 BEGIN SELECT RAISE(ABORT,'immutable_commercial_event'); END;
CREATE TRIGGER IF NOT EXISTS commercial_audit_update_denied
 BEFORE UPDATE ON commercial_evidence_audit
 BEGIN SELECT RAISE(ABORT,'immutable_commercial_audit'); END;
CREATE TRIGGER IF NOT EXISTS commercial_audit_delete_denied
 BEFORE DELETE ON commercial_evidence_audit
 BEGIN SELECT RAISE(ABORT,'immutable_commercial_audit'); END;
