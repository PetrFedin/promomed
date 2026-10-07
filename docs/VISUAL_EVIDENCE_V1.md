# СОСТОЯНИЕ — Visual Evidence v1

Checkpoint: 2026-10-07

Purpose: make participant UI review repeatable and inspectable across every interface change.

## Required surfaces

- Today
- Media
- Events
- Community
- My / account

## Required viewport families

- compact phone portrait
- modern phone portrait
- phone landscape
- tablet portrait
- tablet landscape
- desktop
- wide desktop

Desktop evidence additionally includes the collapsed left-navigation rail.

## Required machine checks

- no horizontal page overflow;
- navigation occupies the correct shell position for the viewport;
- visible primary navigation and top actions meet the 44 px touch-target contract;
- participant supporting text remains readable;
- sheets remain inside the viewport;
- base-screen screenshots are captured without an open overlay;
- every expected evidence image exists before QA can pass.

## Manifest

The browser evidence directory must include visual-evidence-manifest.json.

The manifest records:

- schema identifier;
- participant surfaces;
- device name;
- viewport width and height;
- touch/mobile flags;
- responsive shell mode;
- expected screenshot filenames;
- active geometry/accessibility rules.

## Review policy

Visual Evidence v1 is not a pixel-perfect screenshot-diff gate.

Reviewers should reject a change when evidence shows:

- navigation overlap;
- content clipped behind fixed controls;
- unintended full-width buttons on tablet/desktop;
- excessive dead space that harms task density;
- unreadable labels or status text;
- overlays obscuring the screenshot intended to represent a base surface;
- inconsistent responsive shell selection;
- broken hierarchy between primary action, supporting content and secondary storytelling.

Minor anti-aliasing, font-rasterization and sub-pixel differences are not regressions by themselves.

## Next maturity step

Only after the UI system stabilizes further should selected anchor surfaces receive image-diff thresholds. Those baselines should cover a small number of high-value states rather than every generated screen.