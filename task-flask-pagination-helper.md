# Task: Introduce a Shared Pagination Helper for Flask Routes

## Goal
Adopt a pagination library (e.g., `Flask-Paginate`, `paginate`, or an in-house helper) so all list/search routes reuse the same paginator instead of manually computing offsets, total pages, and display ranges.

## Current State
- `app_production.py:124-349` (routes `/`, `/source/<source_name>`, `/search`, `/api/startups`, `/api/search`) each repeat:
  - Parsing `per_page`/`page` query params with min/max bounds.
  - Calculating `offset`, `first_item`, `last_item`, `total_pages`.
  - Formatting pagination metadata for templates/API responses.
- Manual arithmetic is error-prone and duplicated five times.
- Templates (`templates/index.html`, `templates/search.html`) expect fields like `page`, `per_page`, `total_pages`, `first_item`, `last_item`.

## Requirements / Acceptance Criteria
1. Choose a pagination helper (preferred: `Flask-Paginate` or `paginate` with Jinja support) and add it to `requirements.txt`.
2. Wrap all list/search routes with a shared helper that:
   - Validates query params.
   - Provides offset/limit for DB queries.
   - Exposes total pages, has_next/has_prev, and record range metadata for templates/API responses.
3. Update templates to rely on the helper’s attributes (e.g., `pagination.total`, `pagination.items`) instead of manual calculations when possible.
4. Ensure API endpoints still return the same JSON keys (`items`, `page`, `per_page`, `total`, `total_pages`).
5. Document the helper in code comments (brief) so future routes can plug in easily.
6. Add/adjust tests covering pagination behavior (see `tests/test_app.py`, `tests/test_scrape_all.py` if they assert counts).
7. Update documentation (PROGRESS/BLOG) after implementation.

## Suggested Approach
1. Create a utility (e.g., `from paginate import Pagination`) or your own `Paginator` class in a new module (e.g., `pagination.py`).
2. Centralize parameter parsing: `per_page = clamp(int(request.args.get("per_page", default)), min, max)`.
3. Return a dataclass/object with `items`, `page`, `per_page`, `total`, `pages`, `first_item`, `last_item`, `offset`, etc.
4. Use the helper in both HTML and API routes to keep behavior identical.
5. Update unit tests to instantiate the helper directly or assert route output using the new data structure.

## References
- `app_production.py:124-349` — repeated pagination logic.
- `templates/index.html`, `templates/search.html` — render pagination controls.
- `tests/test_app.py` — integration tests for list/search endpoints.
