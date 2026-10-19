# СОСТОЯНИЕ — portfolio media evidence / revision protocol

## Purpose
Deliver inspectable images and genuine 25-second browser recordings for the founder's
portfolio site without misrepresenting CI previews as the public deployed application.

## Capture channels
1. **CI preview** — isolated GitHub-hosted browser + seeded **demo-only** SQLite,
   never a patient/participant production database. The `preview` artifacts visibly
   label that provenance. `RENDER_GIT_COMMIT` is set to the exact checked-out commit.
2. **Published public site** — unauthenticated `https://sostoyanie-promomed-live.onrender.com`.
   Requires `/health` HTTP 200 + `ok=true` and the real landing/navigation. It does
   not sign in, scrape credentials or substitute the preview when the service is 503.
   `live_sha_verified` is only true if the deployed health commit equals the
   requested SHA; mismatches mean *different published revision*, not a failed image.

## Outputs
Each GitHub Actions capture produces a versioned archive with:
- `manifest.json` — capture time, source URL, screenshot/video SHA-256, source code SHA,
  `/health` metadata and precise verification status;
- `screenshots/` — presentation-ready visible viewport frames: iPhone (390 × 844), iPad (820 × 1180) and desktop (1440 × 900), avoiding fixed bottom-navigation overlays halfway through long iPhone images; original full-page screenshots remain in the separate responsive QA workflow;
- `videos/desktop-journey-25s.mp4` and `videos/iphone-journey-25s.mp4`,
  browser recordings converted to shareable H.264 MP4, muted, 25 seconds;
- CI-preview-only `videos/iphone-personal-demo-25s.mp4` showing actual sign-in,
  a test participant registration (confirmed by SQLite `participant_event_registrations_v1` and `event_registration_transitions_v1`), partner requests and notes in a seeded dummy account;
  **This recording must never be labeled as a live participant session.**
- Preview includes `screenshots/iphone-personal-demo.png` (full-page before the action) and `screenshots/iphone-personal-confirmed-demo.png` (full-page evidence after a real successful demo registration).
- `index.html` — standalone responsive media gallery to curate for the personal website.

The video route is Home → Media → Events → Community → My Space.
All captures are actual automated browser navigation, not image mockups.
A separate `iphone-personal-demo.png` illustrates the demo account in the isolated preview.
Never publish it as a real participant or real end-user experience.

## Verification and no-fabrication rules
- Manifest `completed=true` and all assets present are required before release.
- `ops/verify_portfolio_media.py` independently validates SHA-256, expected 13 public and 15 preview PNG screenshots, 2/3 H.264 MP4 videos, video duration, non-static frames, viewport geometry, demo action evidence and gallery coverage; any mismatch fails CI.
- Never label local CI preview content **LIVE**, even if it looks identical.
- On unavailable public service, record the failed health call and preserve the failed
  `manifest.json`; **no** synthetic screenshot/video is produced.
- Live capture is a snapshot of the currently served deployment, potentially *behind*
  the GitHub SHA. Inspect `health.git_commit` and `live_sha_verified` before using
  a frame to represent the latest features. A missing/unmatched commit is explicitly unverified.
- No production authentication, personal data, medical diagnoses, patient details,
  contractual evidence or sensitive partner information in externally published media.
- Review rights/licences for photos, logos, text, music and third-party materials before
  publishing a marketing reel. Source and embedded assets may have their own licences.
- Screen recording has no audio; narration and brand voiceover should be added only
  after legal/editorial review.

## Repeatability
- Workflow: `.github/workflows/portfolio-media-evidence.yml`.
- Push capture: trigger on media-capture source/workflow/site change (in the candidate branch).
- Manual capture: GitHub → Actions → **SOSTOYANIE portfolio media evidence** → Run workflow.
- Weekly schedule: Monday 07:37 UTC **only after workflow exists in default `main`**.
- GitHub Actions artifacts currently expire after **30 days**. Download and curate
  approved portfolio media into the final persistent storage of the personal landing
  page (object storage or repository-managed asset system), with SHA/time metadata.
  CI artifacts are *not* a permanent media archive. Never silently delete the older
  approved version until a new version is QA verified.

## Release bar for personal brand portfolio
1. Source SHA, Render deploy ID and /health commit reconciled.
2. Desktop/phone clip lasts 24.2–25.1 seconds, contains actual route changes and
   runs without JavaScript page errors.
3. Screenshots have no cropped essential interface, credentials, demo disclosures
   removed or misleading health/medical benefit statements.
4. Screenshot/video approved by editorial and privacy review.
5. Published portfolio links to the exact revision and capture date. A new release
   creates a new version; historical versions remain labelled rather than overwritten.

## Known current infrastructure gate
As of 2026-10-18 external probes intermittently returned HTTP 503, but GitHub-hosted public browser recordings subsequently succeeded. The public `/health` reported SQLite with `durable=false`, `demo_seed=true` and deployed SHA `ae5303b3d4f28d558cf4cf35b9927da88653b4ed`. This is an observed demo service, **not** proof of a stable production-ready release.
Render workspace/service/deploy verification, robust public health and PostgreSQL
production admission remain separate release requirements. A passing CI preview
cannot close them.


## Integrity hardening — proposed branch, 2026-10-19

The archive gate now rejects symlinks at *every path component* (including
directory aliases), and rejects symlinked manifest/gallery files. Screenshots
must carry a complete PNG chunk stream with valid CRCs **and** decode as actual
pixels using ffmpeg; an IHDR-only file is not proof of a valid screenshot.
Video must have an MP4 container and an exact 390×844 or 1440×900 viewport,
in addition to the existing H.264, duration and non-static-frame checks.
Adversarial regression tests run before both media capture channels are
considered releasable.

This is proposed GitHub-only hardening, not a claim of improved live Render
configuration, durable portfolio-hosting, or production PostgreSQL readiness.
Published media still require rights/privacy/editorial review and permanent
approved storage; CI artifacts still expire.
