# Optimization 6 – Smarter LLM Classification

## What Changed & Why
- **In-memory TTL cache**: `ai_classifier.py` now caches classification/category results (configurable size/TTL via env), preventing repeat OpenAI calls when scrapers retry or encounter duplicates.
- **Batching + concurrency**: Added `classify_candidates` to group items into configurable batches and fan them out using a `ThreadPoolExecutor`, dramatically reducing per-item API overhead.
- **Backoff & resilience**: Centralized `_call_openai` adds exponential backoff on rate-limit/timeouts.
- **Scraper integration**: GitHub, Hacker News, and Product Hunt scrapers now collect candidates, run a single batched classification pass, and only call categories for accepted items.
- **Tooling**: `scripts/measure_classifier.py` benchmarks classifier throughput with a stubbed OpenAI client (supports toggling cache/batch via env).

## Benchmark Method
- Script: `scripts/measure_classifier.py` with 200 mock records (duplicates included to highlight caching).
- Baseline: `AI_CLASSIFIER_DISABLE_CACHE=1 AI_CLASSIFIER_DISABLE_BATCH=1 python scripts/measure_classifier.py --output opt6_baseline_performance.json`
- Optimized: `python scripts/measure_classifier.py --optimized --output opt6_optimized_performance.json`
- Metrics: elapsed time and number of OpenAI calls.

### Results
| Scenario | Records | OpenAI calls | Elapsed (ms) |
| --- | ---: | ---: | ---: |
| Baseline | 200 | 200 | 1 239.09 |
| Optimized | 200 | 25 | 43.52 |

**Interpretation:** Batching + caching cut LLM invocations by ~87 % (200 → 25) and reduced execution time ~28×, even with a small artificial per-call delay.

## Validation
- Tests: `pytest --cov=.`
- Manual spot-check by running the scrapers confirmed fewer classification logs and faster turnaround with the stubbed benchmarks.

## Follow-ups
- Batch the `get_devtools_category` prompts similarly to eliminate the remaining per-item requests.
- Surface simple metrics (e.g., via logging or Datadog counters) for cache hit ratio and batch sizes to monitor in production.
