# Blue/Green Deployment Notes

This branch introduces structured logging, a configurable sqlite location, and a local blue/green docker topology. To run the new "green" stack alongside the current production stack, ensure both tiers point to the same sqlite database file and verify the green-only schema additions are backward compatible.

## Summary of Database Differences vs `origin/main`

- The database path is now driven by `DEVTOOLS_DB_PATH` / `DEVTOOLS_DATA_DIR`. The production branch hardcodes `startups.db` in the repo root.
- `init_db()` now creates a virtual FTS table (`startups_fts`) plus insert/update/delete triggers, and adds an index on `startups.source`. No columns were added or removed.
- Connection helpers wrap sqlite connections (`row_factory`, logging) but do not mutate the schema.

## Production Checklist

1. Confirm the real path to the live database file (e.g. `/root/devtoolscrape/startups.db`).
2. For the green deployment, export `DEVTOOLS_DB_PATH` to that same file path before starting the service/container. Without this, green will create a new database under `./data/`.
3. Bring the green stack online and hit `/health` (or another read-only endpoint) to confirm sqlite opens successfully.
4. Inspect the sqlite file once (e.g. `sqlite3 /root/devtoolscrape/startups.db ".tables"`). You should see `startups`, `scrape_log`, and the new `startups_fts` table after green runs `init_db()`.
5. Keep background jobs/scrapers running on only one stack to avoid duplicate work.
6. When satisfied with the green version, flip traffic (Nginx / load balancer) and retire the old stack or upgrade it to honor `DEVTOOLS_DB_PATH`.

### Compatibility Notes
- The legacy blue stack ignores `startups_fts` and continues working even after green creates it.
- `fts5` is part of modern sqlite builds; if the droplet’s Python lacks it, `init_db()` would fail. You can sanity-check by running:
  ```bash
  python - <<'PY'
  import sqlite3
  conn = sqlite3.connect('/root/devtoolscrape/startups.db')
  options = ','.join(conn.execute('pragma compile_options').fetchone() or [])
  print('fts5' in options)
  PY
  ```
- If you plan to move the production database under `./data/`, update the blue stack to honor `DEVTOOLS_DB_PATH` first to avoid breaking older deployments.

