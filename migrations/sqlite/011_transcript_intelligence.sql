CREATE TABLE IF NOT EXISTS transcript_segments(
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  studio_id TEXT,
  start_sec INTEGER NOT NULL,
  end_sec INTEGER NOT NULL,
  speaker_id TEXT,
  text TEXT NOT NULL,
  source_kind TEXT NOT NULL DEFAULT 'demo_transcript',
  review_status TEXT NOT NULL DEFAULT 'unreviewed',
  created_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS generated_takeaways(
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  studio_id TEXT,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  segment_start_sec INTEGER NOT NULL,
  segment_end_sec INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'generated',
  reviewer TEXT,
  reviewed_at BIGINT,
  created_at BIGINT NOT NULL,
  demo_only INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_transcript_segments_item_time
ON transcript_segments(item_id,start_sec,end_sec);

CREATE INDEX IF NOT EXISTS idx_generated_takeaways_item_status
ON generated_takeaways(item_id,status);
