# Render Deployment State

> This file is the deployment ledger for СОСТОЯНИЕ / Promomed. Update it after every production/demo deployment. GitHub `PetrFedin/promomed` is the product source-of-truth.

## Current live state — 2026-09-30

### Operational web service

- Render service: `sostoyanie-promomed-v06`
- Service ID: `srv-datcnn893c1s73a3irng`
- URL: https://sostoyanie-promomed-v06.onrender.com
- Region: Frankfurt
- Plan: free
- Runtime: Python
- Build: `python -m py_compile server.py`
- Start: `python server.py`
- Auto deploy: yes
- Live deploy: `dep-daudqeflot8c73aomq30`
- Live source commit: `32ad35e4cc3f1ad70d627e239fdb44faa23bd088`
- Live release: v1.3 Pilot Command System
- Status at capture: LIVE

### Static sales/demo surface

- Render service: `sostoyanie-promomed-preview`
- Service ID: `srv-dat45kgjo6nc73e6aofg`
- URL: https://sostoyanie-promomed-preview.onrender.com
- Auto deploy: yes
- Live deploy: `dep-daudqgek1f9s73beucu0`
- Live source commit: `667fe54e2e26aca34e30f88476bbe3620d1ae055`
- Live release: v1.3 Pilot Command System
- Status at capture: LIVE

## Repository migration state

The two existing live services were originally created from temporary branches in `PetrFedin/Moscow`:

- `deploy/promomed-v06-interactive`
- `deploy/promomed-sostoyanie-preview`

The complete current source has now been migrated to `PetrFedin/promomed/main`.

**Migration blocker:** Render's GitHub integration currently cannot fetch the private `PetrFedin/promomed` repository. An attempted direct service creation on 2026-09-30 returned `repository URL is invalid or unfetchable`. Until GitHub access is granted to Render for this private repository, the legacy Render services must remain attached to the old branches to keep the existing URLs live.

After access is granted, the required cutover is:

1. deploy `PetrFedin/promomed/main` as the authoritative Render service;
2. verify `/health`, role flows and `/api/command`;
3. record new service/deploy IDs and exact Git SHA here;
4. retire the two legacy Render services or repoint traffic;
5. remove the two Promomed branches from `PetrFedin/Moscow`.

## Release completion rule

A change is **not complete** merely because it is committed. Every completed release must record:

- Git SHA in `PetrFedin/promomed`;
- release/version;
- Render service ID;
- Render deploy ID;
- deployment status;
- public URL;
- smoke-test result;
- known blockers/deferred boundaries.

The newest verified entry in this file is the operational answer to “where did we finish?”.
