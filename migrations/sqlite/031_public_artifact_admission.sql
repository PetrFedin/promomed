-- Explicit, hash-bound public publication admission. No row is public by default.
CREATE TABLE IF NOT EXISTS public_artifact_admissions (
    artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('content','event')),
    artifact_ref TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256)=64),
    status TEXT NOT NULL CHECK (status IN ('admitted','withdrawn')),
    reviewer_ref TEXT NOT NULL CHECK (length(trim(reviewer_ref))>0),
    source_ref TEXT NOT NULL CHECK (length(trim(source_ref))>0),
    admitted_at BIGINT NOT NULL CHECK (admitted_at>0),
    withdrawn_at BIGINT,
    demo_only INTEGER NOT NULL DEFAULT 0 CHECK (demo_only IN (0,1)),
    PRIMARY KEY (artifact_kind,artifact_ref,payload_sha256),
    CHECK (
      (status='admitted' AND withdrawn_at IS NULL)
      OR (status='withdrawn' AND withdrawn_at IS NOT NULL AND withdrawn_at>=admitted_at)
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS public_artifact_admissions_one_active
ON public_artifact_admissions(artifact_kind,artifact_ref)
WHERE status='admitted';
