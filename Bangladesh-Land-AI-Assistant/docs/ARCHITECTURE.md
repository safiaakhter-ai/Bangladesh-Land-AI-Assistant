# Architecture, provenance and trust boundaries

## Data flow

1. `frontend/` displays chat, records and Leaflet map. Calls use `/api/*`.
2. Next.js rewrites those requests to the Flask API identified by `BACKEND_URL`.
3. `app.py` validates request size, simple identifiers and pagination, and
   calls `chat_db.py` or `rag_engine.py`.
4. `rag_engine.py` extracts structured fields, queries a local SQLite khatian
   database if present, and synthesizes from found records and domain
   knowledge. With `GEMINI_API_KEY`, it can send selected context to Google's
   external language service. Without it, offline fallbacks remain available.
5. Optional map calls use `land_map_client.py`, whose upstream format/network
   conditions can change. No map feature should establish ownership by itself.

## Source provenance

- Runtime record DB is **not** included. Its origin, license, completeness and
  currency must be verified before use.
- Demonstration data is generated *only* by `scripts/create_demo_db.py` on an
  explicit command; it is clearly marked `DATA_SOURCE=DEMO`.
- Official-sounding past statistics and prototype reports are not presented as
  validated counts in the upgraded dashboard.
- The historical ingestion and mock-data scripts are quarantined in `legacy/`.

## Privacy and security

- Chat content is stored locally in `data/chat_history.db`; deleting a chat
  removes that chat from the active DB but does not revoke copies or backups.
- The optional Gemini provider receives query context if enabled. Obtain the
  necessary consent and data-processing approvals before sending owner data.
- Default API binds loopback. Docker binds Next to localhost, not the Python
  backend directly. Neither setup adds production authentication.
- `.env`, SQLite DBs, logs, exports and generated frontend files are ignored
  by Git to reduce accidental public disclosure.
- Scraper execution is explicitly disabled by default and requires verified
  HTTPS source configuration and an admin token.
- Do not rely on frontend filters for access-control boundaries.

## Limitations and backlog

The project is ready for local development and demonstration, not public-facing
production. Production readiness would require a licensed/verified official
record feed, database migrations/backup/retention, automated integration
checks, user authentication and authorization, request rate limiting,
permission-aware queries, accessible map behavior review, professional legal
review of knowledge-base claims and robust external provider monitoring.

External resource availability and model correctness are not guaranteed.
