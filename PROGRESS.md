### 2025-11-08T21:14:30Z
- Patched the Docker entrypoint to bootstrap `/app/data/startups.db`, keep a backward-compatible symlink at `/app/startups.db`, and wrap Gunicorn with `ddtrace-run` so traces/profiles are emitted automatically.
- Extended `docker-compose.yaml` with Datadog service metadata plus runtime metrics, profiler, and dynamic instrumentation flags to mirror the agent configuration.
- Rebuilt the prod container, reattached the Datadog agent to the app network, confirmed HTTP 200s on port 8000, and validated via `agent status` that trace traffic from `service:devtoolscrape env:prod` is flowing.

### 2025-11-08T21:47:32Z
- Cloned the production `startups.db` to the dev droplet, replaced `/root/devtoolscrape/data/startups.db`, and restarted the systemd service so dev mirrors prod data.
- Enabled Datadog LLM Observability on the dev host by adding `DD_LLMOBS_ENABLED=1` and `DD_LLMOBS_ML_APP=devtoolscrape-dev` to `devtools-scraper.service`, per Datadog’s APM/LLM setup guide, then reloaded systemd and validated HTTP 200s + new env vars.

### 2025-11-08T22:01:56Z
- Re-applied the `DD_LLMOBS_ML_APP=devtoolscrape-dev` setting, confirmed it is live in the running Gunicorn process (`/proc/$PID/environ`), and restarted the systemd unit to pick up the corrected ML app name.
- Triggered `python scrape_all.py` on the dev droplet so fresh OpenAI-powered spans flow through LLM Observability and can be validated in Datadog.

### 2025-11-08T22:16:45Z
- Audited the dev droplet for stray `DD_LLMOBS_*` environment variables, confirmed only the desired `DD_LLMOBS_ENABLED`/`DD_LLMOBS_ML_APP` pair exists, and exported them explicitly for ad-hoc scrape runs.
- Reran `python scrape_all.py` with `DD_LLMOBS_ML_APP=devtoolscrape-dev` in the shell environment so every new LLM span in Datadog is tagged to the dev app name.

### 2025-11-08T22:27:55Z
- Updated `ai_classifier.py` to honor `DD_LLMOBS_ML_APP`, `DD_SERVICE`, and `DD_ENV` (with sensible fallbacks) when enabling `LLMObs`, ensuring LLM spans inherit the correct app/service/env metadata.
- Made `scrape_all.py` load the project `.env` before importing modules so manual scraper runs pick up `DD_*` settings; mirrored the `.env` additions on the dev droplet and reran the scraper to confirm logs now show `service=devtoolscrape-dev env=dev`.

### 2025-11-08T23:42:46Z
- Investigated the missing RUM data on the dev droplet by curling the gunicorn port (`146.190.133.225:8000`) and confirming the rendered HTML from `templates/base.html` lacks any Datadog snippet, so the browser never initializes `DD_RUM`.
- Compared that with traffic flowing through Nginx/TLS (port 443), which injects the RUM config defined in `/etc/nginx/nginx.conf`, and verified only those requests include the Datadog browser agent.
- Captured the nginx module errors showing it cannot reach `localhost:8126` for remote configuration and noted the Datadog agent actually listens on `127.0.0.1:8126`, which further explains the noisy logs while not affecting injection for 443 traffic. Documented that hitting port 8000 bypasses Nginx entirely, which is why no sessions land in Datadog when QA uses the bare gunicorn port.

### 2025-11-08T23:45:08Z
- Added server-side plumbing (`app_production.py`) that reads `DATADOG_RUM_*` secrets from `.env`, builds a normalized config (including the correct browser SDK URL per site), and exposes it to Jinja via a context processor.
- Updated `templates/base.html` to conditionally load the Datadog browser agent and initialize `DD_RUM` whenever the config is present, so traffic that hits Gunicorn directly (port 8000) now emits RUM telemetry without depending on nginx injection.
