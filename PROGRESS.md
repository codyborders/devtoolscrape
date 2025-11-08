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
