# Operation 4 – Lean Related Items

## What Changed & Why
- Introduced `get_related_startups(source, exclude_id, limit)` in `database.py` so the tool-detail view can request only a handful of siblings instead of pulling every row from that source.
- Updated `/tool/<id>` in `app_production.py` to call the new helper with a limit of 4, eliminating large per-request lists for popular sources.
- Extended database tests to cover the helper, and simplified the app tests to assert the route uses the limited result set.

## Benchmark Method
- Script: `scripts/measure_performance.py` with the 50k-row synthetic SQLite DB (same as prior operations).
- Runs:
  1. `python scripts/measure_performance.py --output op4_baseline_performance.json`
  2. `python scripts/measure_performance.py --output op4_optimized_performance.json`
- Metric: mean latency across 5 requests.

## Results
| Endpoint | Baseline mean (ms) | Optimized mean (ms) | Delta (ms) | Improvement |
| --- | ---: | ---: | ---: | ---: |
| /tool/1 | 158.04 | 3.83 | -154.21 | +97.6% |
| / | 9.93 | 9.77 | -0.15 | +1.6% |
| /?source=github | 7.11 | 6.99 | -0.12 | +1.7% |
| /?source=hackernews | 13.30 | 13.72 | +0.42 | -3.2% |
| /?source=producthunt | 5.55 | 5.68 | +0.14 | -2.4% |
| /search?q=tool | 79.85 | 80.16 | +0.32 | -0.4% |

**Interpretation**
- Tool detail requests are now ~98 % faster because the route fetches only four related entries instead of the full source set.
- Other endpoints are unchanged (minor variance from measurement noise), confirming the optimization is scoped tightly to tool details.

## Validation
- Tests: `pytest --cov=.`
- Quick manual spot-check of `/tool/<id>` confirmed only the limited list renders.
