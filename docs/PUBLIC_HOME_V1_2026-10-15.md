# PUBLIC HOME V1 — non-demo guest surface (2026-10-15)

Status: Draft source candidate. Not deployed.

## Purpose

When `PROMOMED_SEED_DEMO=false`, requests for `/` and `/index.html` are routed to a dedicated public page instead of the legacy demo/investor application.

The page has exactly one application-data dependency: `GET /api/public-state/v1`.

## Data boundary

The public page does not request or store:
- `/api/state` legacy aggregate;
- `/api/discovery` legacy index;
- bearer/session credentials;
- participant/account records;
- booking, attendance, waitlist identities or notifications;
- partner CRM, leads, consent, commercial KPI, revenue or retention data.

Agenda/content can appear only after PUB-01 exact-hash publication admission. An empty admitted corpus is a valid safe state and renders explicit 'not published yet' messaging.

## Root behavior

- demo seed enabled: existing `public/index.html` remains the presentation/demo application;
- demo seed disabled: `/` and `/index.html` serve `public/public-home.html` before authentication;
- `/personal/` remains the separate authenticated participant surface.

This split is deliberate. The production-facing guest site must never become a thin skin over the demo/global-state authority.

## Browser qualification

A dedicated CI workflow starts a fresh non-demo SQLite authority, migrates it, inserts one synthetic content row and one synthetic event, creates exact `public_artifact_admissions` for their public payload hashes, then launches the real server.

At phone 390x844, tablet 820x1180 and desktop 1440x900 the browser must:
- render the admitted event and material;
- request `/api/public-state/v1`;
- never request `/api/state` or `/api/discovery`;
- keep localStorage/sessionStorage empty;
- have no page errors or horizontal overflow;
- expose `/personal/` as the account route.

CI screenshots are synthetic test evidence only. They do not depict an approved Promomed event or approved medical content.

## Release limitations

This slice does not provide a governance UI that grants publication admission, does not establish reviewer medical/legal credentials and does not make existing demo records public.

Production still requires actual Render/PostgreSQL admission (#64/#65), main protection (#94), public-content governance (#98), cross-tenant POST closure (#100) and independent review.
