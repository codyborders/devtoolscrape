# Task: Swap TTLCache/Retry Logic for Well-Maintained Libraries

## Goal
Replace the handwritten caching + retry primitives in `ai_classifier.py` with off-the-shelf libraries (e.g., `cachetools.TTLCache` for memoization and `tenacity` or `backoff` for retry policy) so the classifier module is shorter and easier to reason about.

## Current State
- `ai_classifier.py` lines ~63-118 define a custom `TTLCache` plus manual locking/expiry management.
- `_call_openai` (lines ~121-181) implements ad-hoc exponential backoff, logging, and retry logic around `client.chat.completions.create`.
- Threading + manual chunk workers (`ThreadPoolExecutor`, `_classification_cache`, `_category_cache`) rely on that cache implementation.
- Tests (`tests/test_ai_classifier.py`) rely on cache disabling env vars (`AI_CLASSIFIER_DISABLE_CACHE`, `AI_CLASSIFIER_DISABLE_BATCH`) and stubbed OpenAI client provided by `tests/conftest.py`.

## Requirements / Acceptance Criteria
1. Introduce dependency/dependencies (e.g., add `cachetools>=X`, `tenacity>=Y`) to `requirements.txt` if not already present.
2. Replace the custom `TTLCache` class with `cachetools.TTLCache` (or equivalent) while preserving:
   - Config knobs `_CACHE_TTL`, `_CACHE_SIZE`, `_CACHE_ENABLED`.
   - Thread-safe access inside classify/category helpers.
   - `.clear()` behavior for tests (adjust tests or expose helper as needed).
3. Replace `_call_openai`’s manual retry loop with a decorated helper using `tenacity`/`backoff` so retry policy (max attempts, exponential delay, retry-on errors) is declarative yet still allows logging/tracing tags.
4. Keep the Datadog tracing instrumentation inside `_call_openai` or its wrapper (span tags for attempts/tokens etc.).
5. Ensure batch + single classification paths (`classify_candidates`, `_classify_single`, `get_devtools_category`) still populate caches and respect `_CACHE_ENABLED`/`_USE_BATCH` flags.
6. Update or add tests covering:
   - Cache hit/miss behavior with the new cache.
   - Retry policy triggered on transient errors (leverage stubbed client in tests).
   - Any helper functions whose signature changes.
7. Document new dependencies / behavioral notes if needed (README/PROGRESS/BLOG per project rules after implementation).

## Suggested Approach
1. Add the new library imports near the top of `ai_classifier.py` (after `.env` load, before logger setup).
2. Instantiate `cachetools.TTLCache` objects with `maxsize=_CACHE_SIZE` and `ttl=_CACHE_TTL`, wrapping them with `cachetools.cachedmethod` or manual get/set based on `_CACHE_ENABLED` flag.
3. Use `tenacity.retry` (or similar) with `stop_after_attempt(_MAX_RETRIES)` and `wait_exponential(multiplier=1, min=1)` to replicate current semantics; log attempts via retry callbacks so structured logs stay informative.
4. Ensure thread-safety: `cachetools.TTLCache` isn’t thread-safe by default, so either wrap in `cachetools.Cache` + `cachetools.func.lockedmethod` or guard with existing `_cache_lock`.
5. Run the AI classifier tests (`pytest tests/test_ai_classifier.py`) to confirm behavior.

## References
- `ai_classifier.py:63-210` — current custom cache + retry logic.
- `tests/test_ai_classifier.py` — existing unit tests for caching and classifier behavior.
- `tests/conftest.py` — OpenAI + ddtrace stubs used during testing.
