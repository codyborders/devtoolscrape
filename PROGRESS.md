### 2025-11-08T21:14:30Z
- Patched the Docker entrypoint to bootstrap `/app/data/startups.db`, keep a backward-compatible symlink at `/app/startups.db`, and wrap Gunicorn with `ddtrace-run` so traces/profiles are emitted automatically.
- Extended `docker-compose.yaml` with Datadog service metadata plus runtime metrics, profiler, and dynamic instrumentation flags to mirror the agent configuration.
- Rebuilt the prod container, reattached the Datadog agent to the app network, confirmed HTTP 200s on port 8000, and validated via `agent status` that trace traffic from `service:devtoolscrape env:prod` is flowing.
