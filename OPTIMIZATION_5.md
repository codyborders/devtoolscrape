# Optimization 5 – Paginated Search API

## Motivation & Change Set
- `/api/search` used to return the full result set, mirroring the heavy HTML search response. Large datasets meant large payloads and repeated reprocessing on clients.
- Introduced pagination for the API endpoint (`app_production.py:205-219`), reusing the existing `count_search_results` and paginated `search_startups(...)` helpers. Responses now include `{items, page, per_page, total, total_pages}`.
- Updated the measurement harness (`scripts/measure_performance.py`) to time the API endpoint, and expanded tests to assert the new JSON contract (`tests/test_app.py`).

## Benchmark Method
- Script: `scripts/measure_performance.py` with the seeded 50 000-row SQLite database (same approach as earlier optimizations).
- Baseline captured before the change: `op5_baseline_performance.json`
- After the change: `op5_optimized_performance.json`
- Metric: mean latency across 5 requests (after one warm-up).

## Results
| Endpoint | Baseline mean (ms) | Optimized mean (ms) | Delta (ms) | Improvement |
| --- | ---: | ---: | ---: | ---: |
| /api/search?q=tool | 77.66 | 79.75 | +2.09 | -2.7% |
| / | 10.10 | 9.53 | -0.57 | +5.6% |
| /?source=github | 7.45 | 7.05 | -0.40 | +5.3% |
| /?source=hackernews | 13.65 | 13.61 | -0.04 | +0.3% |
| /?source=producthunt | 5.41 | 5.66 | +0.24 | -4.5% |
| /search?q=tool | 80.26 | 79.84 | -0.42 | +0.5% |
| /tool/1 | 4.01 | 3.81 | -0.20 | +5.0% |

**Interpretation**
- Latency changes are within noise (API now does a count + limited fetch), but the payload size is dramatically smaller: clients now receive at most `per_page` rows instead of the full table and know how many remain.
- HTML endpoints remained essentially unchanged, confirming the optimization was scoped to the API.

## Validation
- Tests: `pytest --cov=.`
- Manual spot check confirmed `/api/search?q=dev&page=2&per_page=10` returns the expected envelope with paging metadata.

## Follow-ups
- Expose pagination metadata alongside search results in the HTML template if deep linking between pages is desired.
- Consider caching frequent `count_search_results` values if monitoring indicates it is a hot spot.
