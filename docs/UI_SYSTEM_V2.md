# СОСТОЯНИЕ — Participant UI System v2

**Checkpoint:** 2026-10-07  
**Scope:** participant-facing MVP shell and shared interaction primitives.  
**Goal:** make the application comfortable for repeated daily use on phone, tablet and desktop without changing business authority or medical-governance semantics.

## 1. Responsive shell

### Phone — below 768 px

- thumb-first bottom navigation;
- navigation remains inside horizontal safe margins rather than spanning edge-to-edge;
- sticky translucent top bar for search, notifications and account access;
- single-column content is the default;
- modal sheets enter from the bottom and respect safe-area insets;
- horizontally scrollable editorial rails remain touch-native.

### Tablet — 768–1199 px

- compact fixed left navigation rail;
- content moves into a centered working canvas;
- navigation never consumes full content width;
- modal surfaces use centered sheets rather than phone-style full-width sheets;
- multi-column grids are used only where cards remain readable.

### Desktop / monitor — 1200 px and above

- expanded fixed left navigation rail with icon + label;
- working canvas is centered independently of the rail;
- denser card spacing and wider editorial / operational layouts;
- sticky header stays available without occupying a separate full-width toolbar;
- dialogs remain visually connected to the working canvas.

## 2. Core visual tokens

Use semantic tokens rather than ad-hoc colors: canvas, surfaces, text, secondary text, line, primary, success, warning, danger, elevation and radius.

## 3. Interaction quality

- minimum primary touch target: 44 × 44 px;
- primary actions must not become full-width on tablet/desktop unless task context requires it;
- hover is additive, never required for understanding;
- active state is visible in navigation and segmented controls;
- focus-visible state must remain obvious for keyboard users;
- disabled actions remain legible.

## 4. Typography and density

- supporting text must not render below 11 px in tested participant surfaces;
- tablet/desktop increase information density through grid structure, not by shrinking text;
- labels and status pills may be compact but must wrap safely where required;
- long governance / evidence text must never overflow cards.

## 5. Cards and surfaces

- everyday cards use restrained borders and low elevation;
- interactive cards gain stronger border/elevation only on hover-capable devices;
- premium/editorial surfaces may use gradients and large-format graphics;
- operational/governance surfaces remain calmer and more data-dense;
- status color never replaces status text.

## 6. Everyday-use hierarchy

1. Today / current state.
2. Media / knowledge.
3. Events / programme.
4. Community / relationships.
5. My / saved, progress, account and wallet.

Investor, corporate and governance surfaces remain role/presentation layers and must not dominate ordinary participant navigation.

## 7. Accessibility

Required: keyboard-visible focus, reduced-motion support, safe-area support, viewport-contained sheets, readable text contract, touch target contract, no horizontal page overflow, and responsive navigation placement.

## 8. Current repository implementation

Implemented in branch feat/mvp-ux-ui-v2:

- semantic visual token layer;
- phone bottom navigation refinement;
- tablet compact left rail;
- desktop expanded left rail;
- sticky translucent header;
- calmer card/elevation system;
- form focus state;
- hover/pressed interaction states;
- viewport-safe modal behavior;
- responsive QA updated to validate the new shell.

## 9. Truth boundary

This is a UI-system checkpoint, not a claim of a final Promomed brand identity.

The current CSS-generated gradients, abstract hero graphics and demo editorial art direction are MVP product-design assets. Final brand photography, illustration licensing, production iconography and official Promomed brand approval remain separate creative/brand admission work.

## 10. Polish layer

Additional daily-use refinements implemented in the polish branch:

- desktop navigation rail can collapse and expand without leaving the current screen;
- collapsed preference is stored locally and restored on desktop;
- tablet keeps the compact rail automatically and does not expose a redundant collapse control;
- landscape phones remain on the thumb-first bottom-navigation shell even when their CSS width exceeds 768 px;
- top actions and primary navigation use a coherent inline SVG icon language instead of prototype glyph characters;
- editorial cover cards and hubs use CSS-native abstract art surfaces with no external image/licensing dependency;
- reduced-motion users do not receive decorative hover motion.

These refinements remain presentation-only and do not modify application authority.

## 11. Visual evidence and account density

- on tablet/desktop the account ticket switches to a compact two-column composition;
- QR remains large enough for demo scanning but no longer dominates the whole working canvas;
- Passport stamps use compact rectangular surfaces on larger screens while phone retains the original stacked rhythm;
- browser evidence now captures the unobscured home after closing evidence sheets;
- desktop QA also captures a dedicated collapsed-rail screenshot for visual review.

## 12. Today experience v2

The Today surface shifts from duplicated topic navigation to action-first daily use:

- hero quick rail: Continue / Events / Studio / My;
- topic navigation remains in dedicated Topic Hubs below rather than duplicated in the hero;
- personal continuation and Relationship 365 form one compact working zone on tablet/desktop;
- desktop hero height is reduced to keep actionable content closer to the first viewport;
- medical-personalisation boundaries remain visible next to continuation logic.

## 13. Media experience v2

Media is treated as a daily knowledge workspace rather than a decorative feed:

- controls that look like filters must perform a real action; decorative category chips are not allowed;
- current MVP top actions are Search / Studio / Catalog;
- paired editorial/corporate/audio cards move to two-column grids on tablet/desktop;
- learning programmes use a three-column grid where viewport allows it;
- desktop density increases through layout, never by reducing readable text;
- long-form rails remain touch-native on phone.

## 14. Events experience v2

Events prioritizes operational use before conference storytelling:

- hero actions expose Programme / My schedule / Map;
- My schedule action switches the canonical programme renderer into mine mode;
- Venue Concierge now/next and Partner Appointments form one operational grid on tablet/desktop;
- phone keeps the same controls in a vertical sequence;
- conference narrative, ecosystem and curated moments remain below the operational layer.