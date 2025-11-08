## 2025-11-08 - Datadog APM & Persistent DBs
Most of today revolved around getting reliable traces off the prod droplet. I rebuilt the Docker image with `ddtrace` baked in, then rewired the entrypoint so Gunicorn always boots under `ddtrace-run`. That meant pushing the Datadog metadata (env/service/version) plus profiler and runtime metrics toggles into `docker-compose.yaml`, connecting the agent container to the same bridge network, and verifying the trace intake via `docker exec dd-agent agent status`. The status output finally showed `service:devtoolscrape env:prod` traffic, which was the green light that APM and the continuous profiler were happy.

The harder snag was the SQLite layout. The legacy app hard-codes `startups.db` in the project root, but the populated database actually lives under `/app/data`. Without intervention the container booted with an empty file, so every request crashed before a span could be emitted. I patched `entrypoint.sh` to reconcile the two worlds by copying any orphaned root-level DB into the data volume (if needed) and keeping a symlink in place for older imports:

```bash
DATA_DIR="${DEVTOOLS_DATA_DIR:-/app/data}"
DB_FILE="${DEVTOOLS_DB_PATH:-${DATA_DIR%/}/startups.db}"
ln -sf "$DB_FILE" /app/startups.db
```

After rebuilding the container the health check returned 200s, cron resumed running scrapers against the shared volume, and Datadog started sampling spans with the correct tags. The next time we touch the ORM we can drop the symlink entirely and rely on the env-driven path, but for now the entrypoint shim keeps the service online while delivering the telemetry we need.
