### 2025-12-06T17:07:33Z
- Enabled Datadog source code integration for the containerized Flask app by passing git metadata into the image build (Dockerfile build args -> ENV) and wiring compose/build scripts to supply `DD_GIT_REPOSITORY_URL`/`DD_GIT_COMMIT_SHA`.
- Rebuilt the `devtoolscrape` image with the current origin URL and commit SHA, recreated the container via `docker compose up -d`, and verified `/health` plus the in-container env show the git tags Datadog expects.

### 2025-12-06T17:20:31Z
- Enabled Datadog Code Origin by adding `DD_CODE_ORIGIN_FOR_SPANS_ENABLED=true` to all compose definitions and the cron runner env in `entrypoint.sh` so both the app and scheduled scrapes emit code-origin tags with spans.
- Rebuilt the image and recreated the container; verified `/health` is 200 and the running env exposes `DD_CODE_ORIGIN_FOR_SPANS_ENABLED=true`.

### 2025-12-06T17:30:15Z
- Added a Datadog Agent service to every compose variant (with hostname + API key from `.env`) so the app can actually deliver traces/code-origin data to an intake.
- Brought the agent up, confirmed `/info` is reachable from the app container, and reran `ddtrace-run python3 scrape_all.py`; spans now send without the prior `dd-agent` DNS failures, so APM should show code-origin tags on the latest scrape.

### 2025-12-06T16:52:12Z
- Verified the existing `.env` and used `docker-compose.yml` (the env_file-aware definition) to rebuild the `devtoolscrape` image and recreate the container with `docker compose -f docker-compose.yml up -d`.
- Waited for the container health check to go healthy on port 9000 (exposed as 8000) and confirmed `/health` returns HTTP 200 with `database=connected`.
- Could not locate `PRD.md` or `PYTHON.md` in the repo before the spin-up; proceeded with the compose defaults already committed.

### 2025-11-16T17:35:50Z
- Reverted the two revert commits on `main` so the cachetools-backed classifier cache and tenacity retry helper are reinstated without dragging the revert history into the default branch.
- Restored the dependency branch documentation entry that tracks how the cache/refactor work is coordinated across branches.
- Reactivated the project venv and re-ran `pytest tests/test_ai_classifier.py` (14 passing, 1 known warning) to ensure the classifier behavior matches the restored implementation.

### 2025-11-16T17:20:10Z
- Fast-forwarded `dependency-optimizations` with the `task-ai-classifier-cachetools-tenacity` branch so the cachetools/tenacity classifier refactor and its tests now ride with the dependency workstream.
- Recreated the venv run of `pytest tests/test_ai_classifier.py` after the merge (14 passing tests, 1 warning) to prove the shared branch keeps the retry/cache behavior sane.
- Captured the branch sync plus regression results in `BLOG.md` so teammates know the dependency fixes now live on the coordination branch.

### 2025-11-16T16:37:55Z
- Replaced the custom ai_classifier cache with `cachetools.TTLCache` guarded by a shared lock and refactored the retry helper around `tenacity.Retrying`, keeping the Datadog tracing metadata intact.
- Added regression coverage for cache TTL expiry and transient retry handling (plus sturdier ddtrace/openai stubs) and ran `pytest tests/test_ai_classifier.py` inside the project venv to confirm everything passes.
- Declared the new `cachetools`/`tenacity` dependencies in `requirements.txt` so deploys install the maintained primitives automatically.

### 2025-11-16T16:14:11Z
- Split the refactor plan into four actionable task briefs (`task-ai-classifier-cachetools-tenacity.md`, `task-database-orm-migration.md`, `task-flask-pagination-helper.md`, `task-logging-structlog-migration.md`) so incoming engineers have scoped instructions, references, and acceptance criteria for each dependency upgrade.
- No code behavior changed—this pass was documentation-only to unblock the next sprint’s refactor work.

### 2025-11-16T16:10:21Z
- Captured the high-impact dependency refactors (cachetools/tenacity for the classifier, ORM/pagination helpers for persistence + views, and structlog-based logging) in `2025-11-16-refactor.md` so another engineer can pick them up without re-reading the git history.
- Left the codebase untouched otherwise; this pass was purely documentation to guide the upcoming refactor, so no runtime changes needed verification.

### 2025-11-09T17:48:24Z
- Added `observability.py` helpers so we can consistently wrap outbound HTTP/LLM calls in Datadog spans even when ddtrace is missing in tests.
- Instrumented the GitHub Trending, Hacker News (top + Show HN), Product Hunt RSS/API scrapers, and all OpenAI classifier calls with the new tracing helpers to capture status codes, retry attempts, and model metadata.
- Triggered the production scraper manually to confirm the new spans appear alongside the existing runner trace, ensuring third-party APIs (GitHub/HN/Product Hunt/OpenAI) now show up in Datadog again.
- Marked the OpenAI spans with `span.kind=client`/`component=openai` so LLM Observability can ingest them without throwing warnings during batch runs.

### 2025-11-09T18:25:14Z
- Pointed the tracing helpers at `DD_SERVICE` (defaulting to `devtoolscrape`) so every child span—including OpenAI—stays under the single `devtoolscrape` service instead of spawning `devtoolscrape.scraper` / `devtoolscrape.ai` sub-services.
- Dropped the explicit service override in the OpenAI instrumentation to keep the span tree flat, matching the observability strategy.

### 2025-11-09T17:05:42Z
- Resolved the merge between `codex-review` and `main` by layering the RUM SDK v6 log entries ahead of the tracing/LLM diary so we preserve the full history without conflict markers.
- Bumped every `DD_VERSION` default (docker-compose + cron wrapper) to `1.1` while double-checking that the `DD_ENV`, `DD_SERVICE`, and LLM tags stayed untouched, so Datadog clearly shows the new build without forking tag cardinality.
- Prepped the no-blue/green deploy requested for today: once this commit lands on GitHub, I’ll push to production by SSH’ing to the droplet, running `git pull origin main`, restarting the systemd service, and verifying `/health`, cron logs, and Datadog telemetry all reflect version `1.1`.
- Updated both compose files so host port `8000` forwards to the container’s new Gunicorn listener on `9000`, so the container health check probes `http://localhost:9000/health`, and so `GUNICORN_BIND=0.0.0.0:9000` is exported inside the container—this keeps the droplet’s Nginx reverse proxy working without rewriting its config while still defaulting to loopback elsewhere.

### 2025-11-09T01:40:17Z
- Looked up the latest Datadog Browser SDK release (v6.23.0) via the GitHub API so we could pin the edge proxy to the newest build.
- Updated `/etc/nginx/nginx.conf` to use `datadog_rum_config "v6"`, ran `nginx -t`, and reloaded nginx so the module now serves the v6 script bundle.
- Confirmed `https://devtoolscrape.com` embeds `www.datadoghq-browser-agent.com/us1/v6/datadog-rum.js`, proving the upgrade is live.

### 2025-11-09T01:50:10Z
- Toggled the Datadog nginx module to add `allowedTracingUrls` (pointing at https://devtoolscrape.com) so browser sessions can correlate with backend traces per Datadog’s RUM+tracing guide.
- Validated the config with `nginx -t`, reloaded nginx, and confirmed the rendered HTML now includes `allowedTracingUrls` in the `DD_RUM.init` payload.

### 2025-11-09T02:09:42Z
- Backed out the experimental `allowedTracingUrls` config since the Datadog nginx module only emits strings and the browser SDK complained about the type mismatch.
- Removed the nginx stanza plus the temporary template shim, ran `nginx -t`, reloaded nginx, and confirmed the injected payload no longer includes the unsupported field.

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

### 2025-11-08T23:49:25Z
- Backed out the Flask/Jinja RUM injection so telemetry remains managed entirely by nginx per the architecture requirements.
- Added `nginx.conf.dev`, which loads the Datadog nginx module, reads the `DATADOG_RUM_*` values exported from `.env`, and configures the `datadog_rum_config` block (including regional script selection and sane defaults) before including `nginx-devtools-scraper.conf`.

### 2025-11-09T00:03:03Z
- Shifted Gunicorn to bind on `127.0.0.1:9000` (`gunicorn.conf.py`) and taught `nginx-devtools-scraper.conf` to listen on `:8000`, proxy to the new upstream, and serve `/static` so every request now traverses nginx (and picks up the Datadog RUM injection) even when QA hits `146.190.133.225:8000` directly.
- Rebuilt `nginx.conf.dev` as an envsubst template: it’s committed without secrets, but can be materialized on the host by sourcing `.env` (which now stores `DATADOG_RUM_*` tokens) and running `envsubst ... > /etc/nginx/nginx.conf`. Added a systemd drop-in so nginx inherits the `.env` content, then reloaded nginx + `devtools-scraper` to apply the new port layout.
- Verified the end-to-end fix by curling `http://146.190.133.225:8000` (now served via nginx) and confirming the injected `DD_RUM.init` block matches the Datadog credentials, ensuring RUM sessions land even without touching the TLS endpoints.

### 2025-11-09T00:52:40Z
- Loaded the `.env` secrets locally, SSH’d into `root@147.182.194.230`, and enumerated `/etc/nginx/nginx.conf` plus `sites-enabled/devtools-scraper` to check for Datadog RUM directives.
- Verified that neither file enables `datadog_rum` nor references the browser agent (no `datadogRum`/`datadog_rum_config` blocks), so the production nginx layer is not injecting the Datadog RUM snippet today.

### 2025-11-09T00:59:17Z
- Re-ran Datadog’s RUM auto-instrumentation installer on the prod droplet, pointing it at the Dockerized `dd-agent` (`http://172.17.0.2:8126`) so the module could register successfully and drop `ngx_http_datadog_module.so` plus the base config into `/etc/nginx/nginx.conf`.
- Replaced the generated `datadog_rum_config` stanza with the requested settings (app ID `5fcf523d-8cfe-417e-b822-bbc4dc2b3034`, service `devtoolscrape`, env `prod`, version `1.0`, all sampling switches at 100%, resource/interaction/long-task tracking enabled), validated the file via `nginx -t`, and reloaded nginx.
- Spot-checked `https://devtoolscrape.com` to confirm the injected HTML now includes the Datadog browser SDK plus a `DD_RUM.init` payload that matches the prod configuration.

### 2025-11-09T02:02:49Z
- Backed out the npm-based Datadog bundle entirely: removed `package.json`/`package-lock.json`, deleted `assets/rum/index.js`, nuked `static/js/datadog-rum.bundle.js`, and restored `.gitignore`, `app_production.py`, and `templates/base.html` to their pre-RUM state (no `/rum-config` endpoint, no client-side loader).
- Left the simplified `nginx.conf.dev`/`nginx-devtools-scraper.conf` in place but stripped any Datadog references so nginx simply proxies to Gunicorn without injecting telemetry; documented the rollback so the team knows RUM is disabled for now.

### 2025-11-09T02:52:20Z
- SSH’d into the prod droplet with the DIGITALOCEAN credentials, flipped `/etc/nginx/nginx.conf` back to `datadog_rum_config "v5"`, validated via `nginx -t`, and reloaded nginx so the browser agent downgrades immediately.
- Restarted the Dockerized app with `docker-compose restart devtoolscrape`, waited for the health check to return `healthy`, and verified `https://devtoolscrape.com` now references `www.datadoghq-browser-agent.com/us1/v5/datadog-rum.js`.

### 2025-11-09T03:30:27Z
- Inserted `DD_PROFILING_TIMELINE_ENABLED=true` into `devtoolscrape/docker-compose.yml` on the prod droplet so Gunicorn launches with Datadog’s profiling timeline feature enabled alongside the existing profiler flags.
- Recreated the `devtoolscrape_devtoolscrape_1` container via `docker-compose up -d devtoolscrape`, waited for the health check to report `healthy`, and confirmed the new env var is present with `docker inspect ... | grep DD_PROFILING_TIMELINE_ENABLED`.

### 2025-11-09T03:49:49Z
- Captured the scrape cron spec from the prod container (`docker exec devtoolscrape_devtoolscrape_1 cat /etc/cron.d/scrape_all`) so we can mirror the exact `0 */4 * * *` cadence elsewhere.
- Applied the same schedule on `DIGITALOCEAN_IP` by pushing `0 */4 * * * cd /root/devtoolscrape && /root/devtoolscrape/venv/bin/python3 scrape_all.py >> /var/log/devtoolscrape/scraper.log 2>&1` into root’s crontab and verified it with `crontab -l`, ensuring the dev box now runs `scrape_all.py` every four hours too.

### 2025-11-09T07:18:54Z
- Investigated the “missing scrapes” on prod and found cron spewing `/bin/sh: 1: python3: not found` because Debian’s cron PATH omits `/usr/local/bin`, so the containerized job never located Python after the last rebuild.
- Updated `entrypoint.sh` to resolve the absolute `python3` path (falling back if needed) before writing `/etc/cron.d/scrape_all`, copied the change to the droplet, and rebuilt the Docker image (`docker-compose up -d --build devtoolscrape`) so new containers bake in the fix.
- Cleared the stale container to dodge the compose `ContainerConfig` error, relaunched `devtoolscrape_devtoolscrape_1`, and verified `/etc/cron.d/scrape_all` now calls `/usr/local/bin/python3`.
- Manually ran `cd /app && /usr/local/bin/python3 scrape_all.py >> /var/log/cron.log 2>&1` inside the container; the log now shows a successful run finishing at `2025-11-09 07:18:35`, confirming cron will pick it up on the next 4‑hour tick.

### 2025-11-09T14:31:47Z
- Root-caused the missing Datadog scraper spans: cron executed `python3` directly, bypassing `ddtrace-run`, so no APM instrumentation wrapped the GitHub/HN/Product Hunt calls even though the app container itself was traced.
- Extended `entrypoint.sh` to resolve both `python3` and `ddtrace-run`, inject the Datadog env vars explicitly (`DD_ENV`, `DD_SERVICE`, etc.), and emit a cron line that runs `env ... ddtrace-run /usr/local/bin/python3 scrape_all.py`.
- Deployed the updated entrypoint to prod, rebuilt the image, recreated `devtoolscrape_devtoolscrape_1`, and verified `/etc/cron.d/scrape_all` now contains the traced command.
- Manually executed `env DD_ENV=prod ... /usr/local/bin/ddtrace-run /usr/local/bin/python3 scrape_all.py` in the container; the run completed at `2025-11-09 14:30:40` and should now emit spans for every outbound scraper call.

### 2025-12-06T18:17:13Z
- Added a request-scoped Datadog RUM context builder that reads tokens plus service/env/version from `.env`, defaults `allowedTracingUrls` to the current host when unset, and pins `tracePropagationMode` to `datadog` so browser requests inject trace headers that backend spans can consume.
- Injected a guarded RUM loader into `templates/base.html` that pulls the CDN script, initializes `DD_RUM` with the JSON-ified config, and optionally starts session replay when `DATADOG_RUM_SESSION_REPLAY` is true—keeping correlation wiring contained to one place.
- Rebuilt `devtoolscrape` via `docker compose up -d --build --no-deps devtoolscrape` so the running container now includes the correlation-ready template and config helpers while the Datadog agent sidecar stays healthy.
