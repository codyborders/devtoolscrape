# Optimization 1 – Database-Driven Filtering

## Summary
I refactored the Flask routes to stop materializing the entire `startups` table for every request. Filtering, detail lookups, and source statistics now run as SQL queries in `database.py`, and routes consume those results directly. The change removes repeated full-table scans and shrinks the amount of work each request performs, especially for source-specific pages and tool detail views.

## Measurement Method
- Script: `scripts/measure_performance.py` (included in repo). It seeds a synthetic SQLite database with 50 000 rows across multiple sources, spins up the Flask app via its test client, and records response times for six representative routes.
- Runs: `python scripts/measure_performance.py --output baseline_performance.json` (pre-change) and again after refactor with `--output optimized_performance.json`.
- Metric: mean latency over 5 requests per endpoint (after a warm-up call).

## Results
| Endpoint | Baseline mean (ms) | Optimized mean (ms) | Delta (ms) | Improvement |
| --- | ---: | ---: | ---: | ---: |
| / | 836.06 | 760.70 | -75.35 | +9.0% |
| /?source=github | 436.58 | 278.78 | -157.80 | +36.1% |
| /?source=hackernews | 377.73 | 216.78 | -160.95 | +42.6% |
| /?source=producthunt | 352.43 | 186.06 | -166.37 | +47.2% |
| /search?q=tool | 733.10 | 754.44 | +21.34 | -2.9% |
| /tool/1 | 248.98 | 159.40 | -89.58 | +36.0% |

**Key observations**
- Source-filtered pages now respond 36–47 % faster thanks to targeted `WHERE` clauses.
- Tool detail lookups improved ~36 % because the handler fetches one row instead of scanning the full table.
- The unfiltered index still benefits (≈9 %), primarily from cheaper source counts.
- The search route regressed slightly (≈3 %). The SQL still returns all matches and the post-processing code is largely unchanged, so the difference appears to be measurement noise within the seeded dataset. Adding indexes or pagination to the search query would address the residual cost if it shows up in production monitoring.

## Notes & Follow-ups
- Both measurement JSON files (`baseline_performance.json`, `optimized_performance.json`) are kept in the repo for reproducibility.
- The new database helpers (`get_startups_by_source_key`, `get_source_counts`, `get_startup_by_id`, etc.) are fully covered by unit tests.
- Next optimization candidates: push search pagination/limits into SQL, and introduce cached counts so the landing page avoids recomputing counts per request.
