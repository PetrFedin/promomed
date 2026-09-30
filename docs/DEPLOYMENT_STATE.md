# Render Deployment State

> Operational ledger for СОСТОЯНИЕ / Promomed. Product source-of-truth: `PetrFedin/promomed/main`.

## Current authoritative live — 2026-09-30

- Release: **v1.4 Health Media & Conference**
- Repository: `PetrFedin/promomed`
- Branch: `main`
- Verified application Git SHA: `7315c8036050a85254d91d9504c063f09edeedb6`
- Render service: `sostoyanie-promomed-live`
- Service ID: `srv-daug7pnlot8c73b1aja0`
- Deploy ID: `dep-daug9m1srm7s73c59dk0`
- URL: https://sostoyanie-promomed-live.onrender.com
- Region: Frankfurt
- Plan: free
- Runtime: Python 3.12.8
- Build: `python -m py_compile server.py`
- Start: `python server.py`
- Auto deploy: yes
- Render status: **LIVE**
- Runtime evidence: `SOSTOYANIE v1.4 health media conference listening 10000`
- HTTP evidence: Render observed `HEAD / 200` and `GET / 200`
- Build evidence: **Build successful**
- Error logs at verification: no deployment/runtime error reported.

## v1.4 product state

- homepage rebuilt as a year-round health media/product/conference hub;
- Promomed editorial/company/product context;
- products presented inside an educational and regulatory-aware journey, not as disguised independent recommendation;
- richer Media: explainers, R&D/company stories, healthy launches, FM/podcast, lectorium and СОСТОЯНИЕ Box concept;
- conference expanded from 18 to **42 events**;
- **7 parallel venues**, 09:00–20:00;
- keynote, lecture, debate, panel, roundtable, workshop, practice, appointments, community, networking and B2B formats;
- existing v1.3 Pilot Command System remains part of the release.

## Legacy Render services

Historical services `sostoyanie-promomed-v06` and `sostoyanie-promomed-preview` were created from temporary Moscow branches. They are no longer the source-of-truth. The authoritative service above is built directly from `PetrFedin/promomed/main`.

## Release completion rule

Every completed wave records: application Git SHA, release version, Render service ID, deploy ID, URL, build/runtime verification and known production boundaries.

## Known production boundary

Persistent production datastore is still not admitted: current free service uses SQLite under `/tmp`. Production pilot requires durable PostgreSQL/migrations/session-consent-audit authority.
