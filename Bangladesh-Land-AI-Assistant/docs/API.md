# Backend API Reference

Default local API: `http://127.0.0.1:5000`. Frontend requests `/api/*` through
the Next.js server so browser code does not need a hard-coded API host.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | API readiness, AI provider mode, local database availability |
| GET | `/api/telemetry` | Real local SQLite totals (zero/no DB, never invented counts) |
| GET | `/api/status` | Optional scraper status and counts |
| GET | `/api/khatians/search?q=...&page=1&per_page=12` | Bounded khatian lookup; `total_is_estimate` indicates a capped count |
| GET | `/api/chats` | List local conversation sessions |
| POST | `/api/chats` | Create conversation: `{"title":"New search"}` |
| GET | `/api/chats/{session_id}` | Messages of the selected session |
| DELETE | `/api/chats/{session_id}` | Delete selected session and its messages |
| POST | `/api/chats/{session_id}/message` | Ask: `{"message":"CS ও RS এর পার্থক্য কী?"}` |
| GET | `/api/map-admin?level=forDist&division_code=20` | Optional remote administrative levels |
| GET | `/api/plot-geometry?mauza_code=...&plot=...` | Optional local/external GeoJSON features |
| POST | `/api/reverse-geocode-plot` | Analyze map click; requires lat/lon/session_id |
| GET | `/api/data/{survey_records|namjari_records|mouza_maps}` | Paginated legacy local scraper data |

`POST /api/start`, `POST /api/stop` and `POST /api/reset` are disabled by
default. After an independent source review, these additionally require
`ENABLE_SCRAPER=true`, `DLRMS_SOURCE_URL=https://...` and a secret
`X-Admin-Token` header matching `ADMIN_API_TOKEN`. `GET /api/logs` also
requires the admin token.

## Sample requests

Create a chat session:

```sh
curl -X POST http://127.0.0.1:5000/api/chats \
  -H "Content-Type: application/json" \
  -d '{"title":"Land records research"}'
```

Use the resulting `session_id` to submit a question:

```sh
curl -X POST http://127.0.0.1:5000/api/chats/SESSION_ID/message \
  -H "Content-Type: application/json" \
  -d '{"message":"What is a khatian?"}'
```

Error responses are JSON, usually `{"error":"..."}` with an appropriate
HTTP status code. Chat messages are stored locally in SQLite; protect the
directory and do not publish an unsecured instance. The app intentionally has
no official record verifiability guarantee, user authentication, or service
level agreement.
