# Task: Replace Custom Logging Stack with Structlog/Loguru

## Goal
Retire `logging_config.py`’s bespoke JSON formatter/context filter setup in favor of a maintained structured-logging library (structlog or loguru) that integrates with Datadog correlation IDs.

## Current State
- `logging_config.py:1-210` implements:
  - Custom `DatadogJSONFormatter` (timestamp injection, dd.trace/span IDs).
  - Context variable management via `ContextVar`, `bind_context`, `logging_context` utilities.
  - Manual handler setup for rotating file + stdout, plus ddtrace correlation glue.
- `app_production.py`, scrapers, and other modules import `get_logger`, `bind_context`, `logging_context` from this module.
- Datadog correlation uses `ddtrace.helpers.get_correlation_ids` when available.

## Requirements / Acceptance Criteria
1. Pick a structured logging library (`structlog` recommended for ContextVar support) and add it to `requirements.txt`.
2. Reimplement logging initialization so:
   - JSON output remains Datadog-friendly (keys: `timestamp`, `level`, `logger`, `dd.trace_id`, etc.).
   - Context binding (`logging_context`, `bind_context`, `unbind_context`) still works.
   - Rotating file handler + stdout remain configurable via env vars (`LOG_DIR`, `LOG_LEVEL`, etc.).
3. Ensure ddtrace correlation IDs are still attached when ddtrace is installed (structlog processors or custom processor).
4. Update all modules to use the new logger factory (ideally keep `get_logger` API for minimal churn).
5. Keep backwards compatibility for absence of `.env` or ddtrace (tests rely on optional availability).
6. Refresh or add tests covering logging context (see `tests/test_app.py` or create new ones).
7. Document the migration (PROGRESS/BLOG) and note any new env vars.

## Suggested Approach
1. Install `structlog` and configure processors: `structlog.processors.TimeStamper`, custom ddtrace processor, JSON renderer.
2. Use `structlog.contextvars.bind_contextvars` and `structlog.contextvars.clear_contextvars` to mimic existing `bind_context`/`logging_context` semantics.
3. Provide a compatibility layer so existing code importing `get_logger` receives a structlog logger (or adapter exposing `.info`, `.debug`, etc.).
4. Ensure log configuration still honors `LOG_FORMAT=json|console`, `LOG_STDOUT`, `LOG_FILENAME`, etc.
5. Update docs/tests accordingly.

## References
- `logging_config.py` — code to replace.
- Modules using logging helpers (`ai_classifier.py`, `scrape_*.py`, `app_production.py`, etc.).
- Project requirements around Datadog logging (see `static-analysis.datadog.yml`, `JSON_LOGGING_PLAN.md`).
