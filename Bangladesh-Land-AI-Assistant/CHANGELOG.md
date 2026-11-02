# Changelog

## 1.0.0 — Professional source-code refresh (2026-11-02)

- Preserved and reorganized the existing Next.js, Flask, SQLite, Bengali RAG,
  record viewer and digital map application.
- Added environment samples, Windows/Linux startup scripts and Docker Compose.
- Replaced hard-coded localhost browser API calls with same-origin Next rewrites.
- Removed fictional national record progress and counts from live UI telemetry.
- Added accurate missing-database states, health endpoint, input bounds, SQL
  whitelist, response headers and disabled/admin-gated ingestion controls.
- Prevented a record's dag number from being matched to spatial geometry in
  an unrelated mouza without an explicit matching mouza code.
- Added an intentionally synthetic, labeled, four-record demo generator,
  SQLite structure validator, offline unit tests, Flask API contract tests,
  GitHub Actions workflow and VS Code launch/task configuration.
- Separated historic experimental scripts from runtime code under `legacy/`.
- Added architecture, API, privacy, security and legal-reliance documentation.
- Replaced unverified fixed mutation fees in the active knowledge base with
  a direction to verify current official service terms.

### Verification recorded in preparation environment

- Python compilation: passed.
- Six offline RAG/data unit tests: passed.
- Frontend ESLint: passed.
- Flask integration tests: source provided, not run here (Flask dependency
  unavailable in the isolated packaging environment).
- Next.js production build: not validated here (supplied node_modules contained
  a Windows-only SWC native binary and the Linux binary could not be downloaded).
  GitHub Actions is configured to validate the production build online.
- Live map/government APIs and Gemini service: not tested; require network,
  stable provider compatibility and, for Gemini, a user key.
