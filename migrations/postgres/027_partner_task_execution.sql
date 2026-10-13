-- Partner task execution: internal two-party review only, not a contract/delivery payment.
-- Separate execution status preserves the immutable 026 task table schema and checksum.
CREATE TABLE IF NOT EXISTS partner_collab_task_execution (
 task_id TEXT PRIMARY KEY REFERENCES partner_collab_tasks(id),
 status TEXT NOT NULL CHECK(status IN ('todo','in_progress','submitted','changes_requested','accepted')),
 version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
 submitted_by TEXT,
 submitted_role TEXT CHECK(submitted_role IN ('partner','organizer')),
 evidence_ref TEXT,
 evidence_ref_sha256 TEXT,
 reviewed_by TEXT,
 reviewed_role TEXT CHECK(reviewed_role IN ('partner','organizer')),
 decision_note TEXT,
 updated_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_partner_collab_execution_status
 ON partner_collab_task_execution(status,updated_at);

CREATE TABLE IF NOT EXISTS partner_collab_task_receipts (
 id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL REFERENCES partner_collab_tasks(id),
 project_id TEXT NOT NULL REFERENCES partner_collab_projects(id),
 operation_id TEXT NOT NULL,
 actor_email TEXT NOT NULL,
 actor_role TEXT NOT NULL CHECK(actor_role IN ('partner','organizer')),
 action TEXT NOT NULL CHECK(action IN ('start','submit','accept','request_changes')),
 previous_status TEXT NOT NULL,
 next_status TEXT NOT NULL,
 task_version INTEGER NOT NULL CHECK(task_version>0),
 evidence_ref TEXT,
 evidence_ref_sha256 TEXT,
 decision_note TEXT,
 created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_partner_collab_receipts_task
 ON partner_collab_task_receipts(task_id,created_at,id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_partner_collab_task_receipt_op
 ON partner_collab_task_receipts(actor_email,operation_id);

DROP TRIGGER IF EXISTS partner_task_receipts_immutable ON partner_collab_task_receipts;
CREATE TRIGGER partner_task_receipts_immutable
 BEFORE UPDATE OR DELETE ON partner_collab_task_receipts
 FOR EACH ROW EXECUTE FUNCTION promomed_block_partner_collab_ledger_mutation();
