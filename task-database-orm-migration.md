# Task: Replace Raw SQLite Layer with an ORM / Query Builder

## Goal
Adopt a lightweight ORM or query-builder (SQLAlchemy, SQLModel, or peewee) so `database.py` no longer handcrafts SQL strings, manual row-to-dict conversions, and pagination logic.

## Current State
- `database.py:36-486` defines schema creation, inserts, counts, FTS triggers, and multiple query helpers via raw SQL strings.
- Every function opens a new sqlite3 connection, executes SQL, and converts rows via `_row_to_dict`.
- Pagination math (LIMIT/OFFSET) is repeated across `get_all_startups`, `get_startups_by_sources`, `search_startups`, etc.
- App routes (`app_production.py:124-349`) depend on these helpers for listing, filtering, and search.
- Tests (`tests/test_database.py`, others) assume direct sqlite3 usage and environment-variable overrides (`DEVTOOLS_DB_PATH`, `DEVTOOLS_DATA_DIR`).

## Requirements / Acceptance Criteria
1. Introduce your chosen ORM dependency in `requirements.txt` and document configuration (respecting `.env` for DB path).
2. Model the schema (startups table, scrape_log, FTS virtual table) using ORM constructs:
   - Preserve indexes on `name` + `source`.
   - Ensure FTS updates stay in sync (via ORM events or raw SQL triggers/migrations).
3. Replace CRUD helpers (`init_db`, `save_startup`, `get_startup_by_id`, search helpers, counts, etc.) with ORM queries that return plain dicts or model objects convertible for existing templates/api.
4. Centralize connection/session handling (context manager or Session factory) to avoid opening a new sqlite connection for each call.
5. Maintain backward compatibility with environment-driven DB paths (`DEVTOOLS_DB_PATH`, `DEVTOOLS_DATA_DIR`).
6. Update any dependent modules (`scrape_*.py`, `app_production.py`, tests) to use the new ORM APIs.
7. Ensure migrations/initialization still happen via `init_db()` (or equivalent) and that `scrape_all.py` continues to call it before running scrapers.
8. Update tests to validate ORM behavior and adjust fixtures (e.g., tweak `tests/conftest.py:fresh_db`).
9. Document the migration (PROGRESS/BLOG) and provide upgrade notes if manual DB changes are required.

## Suggested Approach
1. Pick `SQLModel` (built on SQLAlchemy) or `peewee` for minimal boilerplate with SQLite.
2. Define models for `Startup` and `ScrapeLog`; consider using SQLAlchemy events or `sqlite3` triggers to maintain `startups_fts`.
3. Provide helper functions returning query results in dict form to minimize template churn.
4. Implement pagination via ORM constructs (limit/offset) and expose counts for the Flask routes.
5. Update tests incrementally, ensuring `fresh_db` fixture initializes ORM metadata when pointing to temp files.

## References
- `database.py` — all existing SQL helpers to replace.
- `app_production.py` & scraper modules — consumers of database helpers.
- `tests/test_database.py` & related fixtures — validation suite.
