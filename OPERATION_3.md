# Operation 3 – Paginated Listings

## Changes & Motivation
- **Database pagination**: Added `count_all_startups`, `count_startups_by_source_key`, and enhanced `get_startups_by_source_key` / `get_startups_by_sources` to accept `limit`/`offset` (database.py). This lets upstream callers fetch a single page instead of the full table.
- **Resilient initialization**: `init_db` now retries `_connect()` once and ignores FTS rebuild failures, ensuring the migrations run even if the first attempt hiccups.
- **Flask routes**: `/` and `/source/<source>` accept `page`/`per_page` params, request only the necessary slice, and compute pagination metadata (`app_production.py:62-121`). `/api/startups` mirrors the behavior by returning `{items, page, per_page, total, total_pages}`.
- **Templates**: `templates/index.html` now shows “Showing X–Y of Z tools” and renders Next/Previous controls keyed by the current filter.

## Benchmark Method
- Reused `scripts/measure_performance.py` with a synthetic 50 000-row SQLite database.
- Baseline captured before the change: `python scripts/measure_performance.py --output op3_baseline_performance.json`
- Post-change run: `python scripts/measure_performance.py --output op3_optimized_performance.json`
- Metric: mean latency across 5 requests per endpoint (after warm-up).

## Results
| Endpoint | Baseline mean (ms) | Optimized mean (ms) | Delta (ms) | Improvement |
| --- | ---: | ---: | ---: | ---: |
| / | 753.09 | 9.27 | -743.82 | +98.8% |
| /?source=github | 276.56 | 6.72 | -269.85 | +97.6% |
| /?source=hackernews | 214.73 | 13.14 | -201.59 | +93.9% |
| /?source=producthunt | 178.07 | 5.64 | -172.43 | +96.8% |
| /search?q=tool | 80.65 | 79.18 | -1.47 | +1.8% |
| /tool/1 | 158.54 | 158.46 | -0.08 | +0.0% |

**Interpretation**
- Index loads now only fetch 20 rows per page, slashing latency by ~99 % across the landing and source-specific pages in the synthetic dataset.
- Search and tool detail remain flat (search already benefited from FTS in Operation 2; tool detail still loads a single record).
- JSON payloads shrink drastically (`/api/startups` returns a paginated envelope), which will further reduce bandwidth and client render cost.

## Validation
- Tests: `pytest --cov=.`
- Manual check: verified pagination UI and API responses with page/size variations via Flask test client.

## Follow-ups
- Consider exposing pagination parameters on `/api/search` for parity.
- Add caching on aggregate counts if `/` traffic becomes high, though current SQL is cheap with indexes in place.
