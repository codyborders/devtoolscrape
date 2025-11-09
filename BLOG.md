## 2025-11-08 - Datadog APM & Persistent DBs
Most of today revolved around getting reliable traces off the prod droplet. I rebuilt the Docker image with `ddtrace` baked in, then rewired the entrypoint so Gunicorn always boots under `ddtrace-run`. That meant pushing the Datadog metadata (env/service/version) plus profiler and runtime metrics toggles into `docker-compose.yaml`, connecting the agent container to the same bridge network, and verifying the trace intake via `docker exec dd-agent agent status`. The status output finally showed `service:devtoolscrape env:prod` traffic, which was the green light that APM and the continuous profiler were happy.

The harder snag was the SQLite layout. The legacy app hard-codes `startups.db` in the project root, but the populated database actually lives under `/app/data`. Without intervention the container booted with an empty file, so every request crashed before a span could be emitted. I patched `entrypoint.sh` to reconcile the two worlds by copying any orphaned root-level DB into the data volume (if needed) and keeping a symlink in place for older imports:

```bash
DATA_DIR="${DEVTOOLS_DATA_DIR:-/app/data}"
DB_FILE="${DEVTOOLS_DB_PATH:-${DATA_DIR%/}/startups.db}"
ln -sf "$DB_FILE" /app/startups.db
```

After rebuilding the container the health check returned 200s, cron resumed running scrapers against the shared volume, and Datadog started sampling spans with the correct tags. The next time we touch the ORM we can drop the symlink entirely and rely on the env-driven path, but for now the entrypoint shim keeps the service online while delivering the telemetry we need.

## 2025-11-08 - Dev DB Sync & LLM Observability
I grabbed the fresh `startups.db` from prod and dropped it onto the dev droplet’s `/root/devtoolscrape/data` volume so stakeholders can test against the real corpus. The swap was done under maintenance (`systemctl stop devtools-scraper`), with the previous file tucked into `/root/devtoolscrape/backups/startups_20251108211840.db` before restarting the unit. Gunicorn came back with 200s immediately, which confirmed the SQLite schema and file permissions survived the transfer.

With the data in place, I followed Datadog’s “LLM Observability and APM” setup guide: because we already run under `ddtrace-run`, enabling correlation boils down to turning on the SDK and naming the ML app. I reworked `/etc/systemd/system/devtools-scraper.service` to add:

```ini
Environment=DD_LLMOBS_ENABLED=1
Environment=DD_LLMOBS_ML_APP=devtoolscrape-dev
```

Those settings ride alongside the existing `DD_ENV`, `DD_SERVICE`, and profiling flags so the LLM spans share the same trace context. After `systemctl daemon-reload && systemctl restart devtools-scraper`, `systemctl show devtools-scraper --property=Environment` reflected the new variables, and the health check still returned 200. Datadog now links LLM Observability spans with the existing APM traces automatically, which means we can pivot straight from generated completions to the surrounding Flask request or cron job.

I had to circle back once more when we noticed the LLM Observability app label wasn’t propagating the way the dashboard expected. The fix was simple: force a daemon reload, verify `/proc/<pid>/environ` contained `DD_LLMOBS_ML_APP=devtoolscrape-dev`, and kick off `python scrape_all.py` to push a new batch of OpenAI completions through the pipeline. That manual run produced multiple `https://api.openai.com/v1/chat/completions` traces tagged with the right ML app, so the Datadog LLM view now mirrors the dev environment naming exactly.

To make spot-checking foolproof, I also audited the droplet for any stray `DD_LLMOBS_*` variables and now export the sanctioned pair (`DD_LLMOBS_ENABLED=1`, `DD_LLMOBS_ML_APP=devtoolscrape-dev`) whenever I run the scrapers by hand. That keeps ad-hoc investigations consistent with what systemd runs under the hood, and ensures every LLM span—automated or manual—lands in Datadog with the same `devtoolscrape-dev` labeling.

One last snag: the classifier script had the ML app name hard-coded and none of the CLI tooling loaded `.env` before wiring up logging, so Datadog still saw `service=devtoolscrape env=local`. I refactored `ai_classifier.py` to pull `DD_LLMOBS_ML_APP`, `DD_SERVICE`, and `DD_ENV` directly from the environment (falling back to safe defaults) when calling `LLMObs.enable`, and taught `scrape_all.py` to load the repository’s `.env` before importing `database`/`logging_config`. With those changes deployed to the droplet—and the `.env` file updated to define the `DD_*` variables—manual scrape runs now emit `service=devtoolscrape-dev env=dev`, so the LLM Observability UI finally mirrors the APM tags.

## 2025-11-08 - RUM Debugging On The Dev Droplet
Today’s deep dive into “missing” RUM sessions started with the server everyone is actually using: the raw Gunicorn listener at `146.190.133.225:8000`. Curling that endpoint showed exactly what Flask renders from `templates/base.html`—no Datadog snippet anywhere—so the browser never even attempts to boot `DD_RUM`. That explained the empty dashboards immediately, but I kept tracing the pipeline to be sure this wasn’t a Datadog intake problem.

Once I hit the same droplet through Nginx (443), the injected HTML included the expected bootstrap:

```nginx
datadog_rum on;
datadog_rum_config "v5" {
    "applicationId" "db5d092e-055d-4d4d-a4ca-b8f257fb4dcf";
    "clientToken" "pubbf870a54b30d159dc08f02bfff4159f9";
    "service" "devtoolscrape-dev";
    "env" "dev";
}
```

Those responses do light up Datadog, which means the module works; it’s just that everyone bypasses it by talking directly to port 8000. The nginx error log is still noisy because the Datadog module tries `localhost:8126` (IPv6 first) while the trace agent listens on `127.0.0.1:8126`, but that’s orthogonal to the missing sessions. The real fix is either to route dev traffic through the proxy (accepting the certificate warning) or to embed an environment-guarded RUM snippet in the base template so Gunicorn can serve it without nginx in the middle. Until we do one of those, there simply won’t be any RUM telemetry for the workflows that stay on 146.190.133.225:8000.

## 2025-11-08 - Shipping RUM Straight From Flask
I went with the template approach to unblock QA immediately. The Flask app now reads a handful of `DATADOG_RUM_*` secrets from `.env`, builds a normalized config (service/env/version inherit from the Datadog defaults, sample rates stay at 100%), and figures out the correct browser SDK URL based on the configured site (`datadoghq.com` maps to `us1`, etc.). That dictionary gets stashed in `app.config` and exposed to Jinja via a context processor so every render can see it without plumbing extra variables through each view.

`templates/base.html` gained a small conditional block in `<head>` that loads `datadog-rum.js` from the computed region and calls `window.DD_RUM.init()` with the JSON-ified config. If session replay is enabled we kick off `startSessionReplayRecording()` as well. Because it’s guarded, nothing leaks in environments that lack the secrets, but as soon as `.env` contains `DATADOG_RUM_APPLICATION_ID` and `DATADOG_RUM_CLIENT_TOKEN`, the snippet is there—no need for nginx-side injection. Hitting `146.190.133.225:8000` now produces the same telemetry as the TLS endpoint, so Datadog finally sees the dev browsing sessions everyone cares about.

## 2025-11-08 - Centralizing RUM In nginx.conf.dev
We ultimately reverted the Flask-side snippet so there’s a single source of truth for RUM. The new `nginx.conf.dev` mirrors what’s running on the droplet: it loads the Datadog module, enables `datadog_rum`, and pulls every browser setting from exported `DATADOG_RUM_*` env vars (with defaults for site, sample rates, and interaction tracking). The config also derives the correct browser SDK URL (`www.datadoghq-browser-agent.com/<region>/v5/datadog-rum.js`) automatically, so swapping to eu/us3/ap1 is just a matter of updating `.env` before restarting nginx.

Because the RUM block now lives alongside the proxy definition, the app templates stay clean and the team can keep injecting telemetry exclusively at the edge—exactly how prod behaves. Anyone spinning up a dev proxy just drops their tokens into `.env`, exports them for systemd, and reuses `nginx.conf.dev` without having to touch Flask again.

## 2025-11-09 - Putting Nginx In Front Of Port 8000
“Just hit :8000” turned into an architectural wrinkle: that port was owned by Gunicorn, so nginx never saw the traffic and Datadog couldn’t inject anything. I flipped the layout so Gunicorn now binds to `127.0.0.1:9000` while nginx claims `:8000`, proxies to the loopback upstream, and keeps serving `/static` from `/root/devtoolscrape/static`. The new `nginx.conf.dev` is a template rather than a secret dump; we keep the `DATADOG_RUM_*` values in `.env`, run `envsubst` to materialize `/etc/nginx/nginx.conf`, and rely on a systemd drop-in to load that environment whenever nginx starts.

After copying the generated config into place, I restarted `devtools-scraper` (to pick up the new Gunicorn bind) and then nginx. Curling `http://146.190.133.225:8000` now returns HTML with:

```html
<script>
  window.DD_RUM.init({"applicationId":"db5d092e-055d-4d4d-a4ca-b8f257fb4dcf","clientToken":"pubbf870a54b30d159dc08f02bfff4159f9","site":"datadoghq.com","service":"devtoolscrape-dev","env":"dev"});
</script>
```

so every dev-only session hits the same Datadog project without relying on the TLS hosts. The nginx error log is finally quiet (agent URL points at `127.0.0.1:8126`), and the RUM explorer started populating `service:devtoolscrape-dev env:dev` within a couple of minutes of the cutover.
