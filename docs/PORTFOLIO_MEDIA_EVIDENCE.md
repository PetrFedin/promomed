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
- `screenshots/` — iPhone (390 × 844), iPad (820 × 1180) and desktop (1440 × 900);
- `videos/desktop-journey-25s.mp4` and `videos/iphone-journey-25s.mp4`,
  browser recordings converted to shareable H.264 MP4, muted, 25 seconds;
- CI-preview-only `videos/iphone-personal-demo-25s.mp4` showing actual sign-in,
  personal registrations, partner requests and notes in a seeded dummy account.
  **This recording must never be labeled as a live participant session.**
- `index.html` — standalone responsive media gallery to curate for the personal website.

The video route is Home → Media → Events → Community → My Space.
All captures are actual automated browser navigation, not image mockups.
A separate `iphone-personal-demo.png` illustrates the demo account in the isolated preview.
Never publish it as a real participant or real end-user experience.

## Verification and no-fabrication rules
- Manifest `completed=true` and all assets present are required before release.
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
As of 2026-10-18 public `/` and `/personal/` returned HTTP 503 during
independent URL checks. This is not a proof of a working production release.
Render workspace/service/deploy verification, robust public health and PostgreSQL
production admission remain separate release requirements. A passing CI preview
cannot close them.
