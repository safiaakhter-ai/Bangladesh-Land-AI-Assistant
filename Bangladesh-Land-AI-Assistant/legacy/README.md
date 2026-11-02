# Legacy research utilities — optional and unverified

These scripts are retained from the supplied prototype for traceability.
They are not used by the normal web application, CI, or demo-data generator.

**Do not use the historic sample/sync scripts to create evidence of legal
ownership.** Some historic code constructs synthetic holder names, sample URLs
or illustrative record counts. Those outputs are *not* government records and
must never be imported into a real title/ownership database.

Any API acquisition, automation, or scraping needs a separate source-review,
permission, rate-limit, privacy, and terms-of-service assessment. Official
external websites and their APIs can change or restrict access.

For an endorsed demonstration, use `python scripts/create_demo_db.py` from the
repository root instead. It produces only four synthetic records, with explicit
provenance labels in every record.

For older scripts with root imports, use `python -m legacy.<module>` from the
repository root rather than invoking a script from inside this directory.
