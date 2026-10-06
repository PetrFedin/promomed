CREATE TABLE IF NOT EXISTS evidence_monitor_jobs(
 target_id TEXT PRIMARY KEY,
 status TEXT NOT NULL DEFAULT 'queued',
 next_run_at BIGINT NOT NULL,
 attempt_count INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL DEFAULT 5,
 interval_seconds INTEGER NOT NULL DEFAULT 21600,
 last_error TEXT NOT NULL DEFAULT '',
 last_started_at BIGINT,
 last_finished_at BIGINT,
 updated_at BIGINT NOT NULL,
 demo_only INTEGER NOT NULL DEFAULT 0,
 FOREIGN KEY(target_id) REFERENCES evidence_watch_targets(id)
);
CREATE INDEX IF NOT EXISTS idx_evidence_monitor_jobs_due ON evidence_monitor_jobs(status,next_run_at);
