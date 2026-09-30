# Development and Release Protocol

1. All СОСТОЯНИЕ / Promomed product changes are made in `PetrFedin/promomed`.
2. `PetrFedin/Moscow` must not be used for new Promomed development.
3. Every meaningful change updates code and, when scope changes, `docs/IMPLEMENTED_SCOPE.md`.
4. Every deployment updates `docs/DEPLOYMENT_STATE.md` with exact Git SHA + Render deploy ID.
5. Every completed product wave adds an entry to `CHANGELOG.md`.
6. A release is considered complete only after live smoke verification.
7. Temporary cross-repository deployment branches are forbidden after the current Render migration is completed.
