# Security guidance

This repository is an **unsecured local-development example**. Do not expose it
to untrusted networks, real land-owner data, or sensitive client conversations
without an authentication/authorization layer, HTTPS, logging/privacy controls,
rate limiting and operational review.

Do not commit `.env`, database files, data extracts, logs, cache folders or
scraped credentials. Limit access to `data/` by operating system permissions.
Review provider privacy terms before enabling `GEMINI_API_KEY`. Review and
obtain authorization for any ingestion target before enabling scraper routes.
An admin token does **not** secure ordinary chats or searches; those routes
remain intended only for trusted local use.

If you find a security issue, report it privately to the repository owner
rather than posting credentials or private ownership information publicly.
