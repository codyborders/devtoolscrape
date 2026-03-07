# Code Review

## Overview
The project reliably gathers and serves devtool listings, but core services lean heavily on ad-hoc scripts, repeated DB calls, and synchronous third-party requests. Tightening data-access patterns, consolidating scraper logic, and adding guardrails around external integrations would improve maintainability, performance, and operational safety.

## Key Findings
- **Database path mismatch (`database.py:6-26`)**: `DATA_DIR` is created under the current working directory, yet every connection targets the hard-coded `/app/data/startups.db`. On non-container runs this path rarely exists, so reads/writes fail silently. Align the directory creation and connection path or make the location configurable.
- **Repeated full-table scans in the web tier (`app_production.py:54-120`)**: Each request pulls the entire `startups` table multiple times, does in-memory filtering, and loops to locate a single row. This couples route logic to storage layout and scales poorly as data grows.
- **`scrape_all` result logging bug (`scrape_all.py:58-70`)**: Successful modules are tracked in a counter, then `scrapers[:successful_scrapers]` is sliced by position. If a middle scraper fails but a later one succeeds, the report lists the wrong modules.
- **Aggressive exception swallowing (`database.py:80-82`, `scrape_producthunt_api.py:126-130`)**: Broad `except` blocks hide DB and parsing failures, making data issues hard to diagnose.
- **Service instrumentation requires missing credentials (`ai_classifier.py:9-20`)**: `LLMObs.enable` and the OpenAI client are initialized at import time without checking for required API keys, so local usage fails before fallbacks trigger.
- **No pagination or throttling on public APIs (`app_production.py:122-136`)**: `/api/startups` and `/api/search` return unbounded datasets, exposing the server to large payloads and expensive SQLite scans.
- **Duplicated keyword heuristics (`ai_classifier.py:24-30`, `ai_classifier.py:139-146`, `dev_utils.py:1-9`)**: Maintaining multiple overlapping keyword lists increases drift risk between scrapers and fallback logic.
- **Lack of persistence safeguards**: Scrapers insert raw HTML/text into SQLite without normalization, and `record_scrape_completion` (`database.py:156-168`) deletes history on each run, complicating diagnostics.
- **Security defaults**: The Flask app ships with `SECRET_KEY='dev-secret-key-change-in-production'` (`app_production.py:20`) and a `/health` endpoint that always reports "database: connected" without verifying connectivity (`app_production.py:138-145`).

## Improvement Opportunities
- Extract a lightweight data-access layer (context-managed connections, row factories, query helpers) and push filtering into SQL (`WHERE source = ?`, `LIMIT/OFFSET`, `get_startup_by_id`) to avoid repeated full-table scans.
- Make the database location configurable (env var or app config) and ensure both scrapers and the web app reuse the same resolver.
- Harden scraper orchestration: reuse a shared HTTP client with sensible retries/backoff, surface per-source failures, and fix success tracking so later successes are not dropped.
- Wrap expensive third-party calls (OpenAI, Product Hunt, HN) behind feature flags/circuit breakers, and defer imports/client initialization until credentials are confirmed.
- Normalize and truncate stored descriptions (strip HTML, enforce max length) and add defensive logging when inserts fail so bad records do not silently disappear.
- Add pagination and caching to API/List views, and derive counts via SQL `COUNT` queries to reduce per-request load and mitigate amplification attacks.
- Unify keyword heuristics in one module, feed them into both scrapers and fallbacks, and add tests around classification to catch regression when keywords change.
- Replace the hard-coded Flask `SECRET_KEY`, validate `/health` by running a lightweight DB query, and consider adding basic auth or tokens to `/api/*` if exposed publicly.
