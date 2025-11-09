# JSON Structured Logging Implementation Plan

## Objectives
- Adopt Datadog-aligned, JSON-structured logging for all services, scrapers, and scripts.
- Ensure logs include consistent metadata (service, env, request/tool identifiers, trace correlation) to support observability.
- Provide an ergonomic API so future code paths emit structured logs without boilerplate.
- Preserve backwards compatibility for local development while enabling easy expansion to additional sinks (stdout, files, Datadog agent).

## Guiding Principles (from Datadog best practices)
- Emit logs in JSON with explicit `timestamp`, `level`, `message`, and contextual fields (`logger`, `thread`, `service`, `env`).
- Use `logging.Logger` hierarchies and propagate context with `extra` data or `logging.LoggerAdapter`.
- Centralize configuration via `logging.config.dictConfig` and rely on environment variables for runtime tuning.
- Correlate logs with traces/metrics (include `dd.trace_id`, `dd.span_id` when `ddtrace` is active).
- Avoid noisy DEBUG logs in production; provide structured context that aids filtering (e.g., `source=producthunt`).

## High-Level Phases
1. **Foundation:** Install dependencies, define schema, centralize logging setup, and document usage.
2. **Instrumentation:** Hook logging into application entrypoints (Flask app, scrapers, CLI scripts, AI classifier).
3. **Context Propagation:** Ensure request IDs, scraper run IDs, and DB transaction metadata are attached automatically.
4. **Validation:** Add smoke tests and documentation; run scrapers/tests to verify structured output.

## Detailed Plan

### Phase 1 – Configuration & Schema
1. Add `python-json-logger` to `requirements.txt`; keep dependency optional for minimal environments via extras if needed.
2. Create `logging_config.py` to expose `setup_logging()` that:
   - Loads log level, destination, and sampling options from env vars (`LOG_LEVEL`, `LOG_FORMAT`, `LOG_JSON_INDENT`, etc.).
   - Configures a `dictConfig` with a JSON formatter (e.g., `pythonjsonlogger.jsonlogger.JsonFormatter`) and a fallback console formatter.
   - Sets defaults such as `service=devtoolscrape`, `env=local`, `ddtrace_enabled` detection, and attaches `dd.trace_id` / `dd.span_id` if available.
   - Establishes named loggers (`devtools.app`, `devtools.scraper`, `devtools.db`, `devtools.ai`, `devtools.scripts`).
3. Define a canonical schema (documented in `logging_config.py` docstring or `docs/logging.md`) including:
   - Core fields: `timestamp`, `level`, `message`, `logger`, `service`, `env`, `hostname`, `pid`, `dd.trace_id`, `dd.span_id`.
   - Domain metadata: `source`, `scraper`, `scrape_run_id`, `tool_id`, `http.method`, `http.path`, `status_code`, `duration_ms`.
4. Publish helper constants/enums for event categories (e.g., `LogEvent.TOOL_SAVED`, `LogEvent.SCRAPER_START`), to keep messages uniform.

### Phase 2 – Application Integration
5. Update `app_production.py` to call `setup_logging()` before creating the Flask app and ensure `app.logger` uses the configured handler.
6. Add Flask request middleware to:
   - Generate/propagate a `request_id` (use existing header `X-Request-ID` if present).
   - Log structured events for `request.start` and `request.completed`, including method, path, status, latency, client IP.
   - Capture unhandled exceptions via `app.logger.exception` with structured payloads (`error.type`, `error.message`, `stacktrace`).
7. Instrument key view functions (`index`, `search`, `tool_detail`) with INFO logs capturing pagination params, query, and result counts (avoid logging PII).
8. Extend `/api/*` endpoints to emit DEBUG/INFO logs for request parameters and counts, plus WARN for empty/slow responses.

### Phase 3 – Scrapers & Background Scripts
9. Introduce a shared scraper logger helper (e.g., `dev_utils.py` or new `logging_helpers.py`) that:
   - Accepts scraper name/source, returns a context-managed logger adapter injecting `scraper`, `scrape_run_id`, `target_url`.
   - Provides decorators for timing functions (log `duration_ms`, `item_count`, `status`).
10. Update each scraper (`scrape_producthunt.py`, `scrape_producthunt_api.py`, `scrape_github_trending.py`, `scrape_hackernews.py`, `scrape_all.py`) to:
    - Log lifecycle events: `scraper.start`, `scraper.fetch`, `scraper.parse`, `scraper.persist`, `scraper.complete`.
    - Log data quality warnings (e.g., skipped items, duplicates) with relevant identifiers.
    - Surface retries/backoff info (ties into existing retry logic, if any).
11. Instrument `ai_classifier.py`:
    - Log cache hits/misses, batch sizes, API call durations, and exceptions (masking sensitive prompt data if present).
    - Include OpenAI response metadata (model, completion tokens) when available.
12. Update CLI scripts (`scripts/measure_classifier.py`, `scripts/run_tests_ddtrace.sh` wrapper via Python entry, etc.) to initialize logging and emit structured summaries.

### Phase 4 – Database & Utilities
13. Wrap critical database operations in logging:
    - `init_db` logs schema migrations, rebuild attempts, and errors with `db.action`.
    - Query helpers log DEBUG-level statements with duration (use a timing decorator) and cardinality of results.
    - `save_startup` logs successes, duplicates, and validation issues.
14. Add context managers or decorators to log retries/backoff in network utilities (if any).

### Phase 5 – Context Propagation & Correlation
15. Implement a lightweight context propagation layer using `contextvars` or `structlog`-style threadlocal to share `request_id`, `scrape_run_id`, and `trace_id`.
16. Detect when `ddtrace` is installed (already set for tests) and hook into Datadog logging correlation via `ddtrace.contrib.logging.patch()` or manual `get_correlation_ids`.
17. Ensure logs from multiprocessing/async tasks preserve context (pass IDs explicitly or reinitialize loggers within workers).

### Phase 6 – Testing & Documentation
18. Add unit tests under `tests/` verifying `setup_logging()` produces JSON payloads with required fields (use `caplog` fixture).
19. Include integration tests for Flask request logging (simulate requests and assert on emitted JSON strings).
20. Update developer docs (`README.md` or create `docs/logging.md`) describing:
    - How to enable JSON logs locally (`LOG_FORMAT=json`).
    - Sample log entries for API requests, scraper runs, AI classification events.
    - Guidance on using `extra` dicts and log levels appropriately.
21. Provide Datadog dashboard/playbook pointers for new log fields; coordinate with infra configs if log shipping is already set up.

### Rollout & Validation
22. Roll out changes behind env toggles (default to human-readable logs locally, JSON in prod) to ease adoption.
23. Run full test suite and representative scraper jobs, capture sample logs, and validate JSON schema with `jq` or `log eval`.
24. After deployment, confirm logs appear in Datadog with desired facets (source, scraper, request_id) and adjust facets/indexes as needed.
25. Plan follow-up iteration to extend logging coverage to new features and monitor for PII leakage, log volume, and performance impact.
