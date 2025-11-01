#!/usr/bin/env python3
"""Benchmark ai_classifier classification with stubbed OpenAI."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import threading
import types


class _StubChatCompletions:
    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.calls = 0
        self._lock = threading.Lock()

    def create(self, *_, **kwargs):
        time.sleep(self.delay)
        with self._lock:
            self.calls += 1
        if kwargs.get("response_format"):
            payload = kwargs.get("messages", [])
            if payload:
                try:
                    data = json.loads(payload[-1]["content"])
                    if isinstance(data, list):
                        results = {item.get("item_id", item.get("id", str(idx))): "yes" for idx, item in enumerate(data)}
                    else:
                        results = {}
                except Exception:
                    results = {}
            else:
                results = {}
            content = json.dumps({"results": results or {"single": "yes"}})
        else:
            content = "yes"

        message = types.SimpleNamespace(content=content)  # type: ignore[name-defined]
        choice = types.SimpleNamespace(message=message)  # type: ignore[name-defined]
        return types.SimpleNamespace(choices=[choice])  # type: ignore[name-defined]


class _StubOpenAI:
    def __init__(self, delay: float = 0.0):
        self.chat = types.SimpleNamespace(completions=_StubChatCompletions(delay=delay))  # type: ignore[name-defined]


def _prepare_environment(disable_cache: bool, disable_batch: bool, concurrency: int):
    os.environ["AI_CLASSIFIER_DISABLE_CACHE"] = "1" if disable_cache else "0"
    os.environ["AI_CLASSIFIER_DISABLE_BATCH"] = "1" if disable_batch else "0"
    os.environ["AI_CLASSIFIER_MAX_CONCURRENCY"] = str(concurrency)
    os.environ["OPENAI_API_KEY"] = "stub-key"


def run_scenario(name: str, disable_cache: bool, disable_batch: bool, concurrency: int, records: int, delay: float) -> dict:
    _prepare_environment(disable_cache, disable_batch, concurrency)
    import ai_classifier  # noqa
    importlib.reload(ai_classifier)
    ai_classifier.client = _StubOpenAI(delay=delay)

    dataset = []
    for idx in range(records):
        # Repeated descriptions to exercise caching
        suffix = idx % 20
        text = f"Developer CLI tool {suffix} with API integration"
        dataset.append({"id": f"item-{idx}", "name": f"Tool {idx}", "text": text})

    start = time.perf_counter()
    results = ai_classifier.classify_candidates(dataset)
    elapsed = time.perf_counter() - start

    return {
        "scenario": name,
        "records": records,
        "elapsed_ms": elapsed * 1000,
        "openai_calls": ai_classifier.client.chat.completions.calls,
        "classified": sum(1 for value in results.values() if value),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark ai_classifier with stubbed OpenAI.")
    parser.add_argument("--records", type=int, default=200, help="Number of mock records to classify")
    parser.add_argument("--delay", type=float, default=0.005, help="Artificial delay per OpenAI call in seconds")
    parser.add_argument("--output", type=Path, required=True, help="Path to write JSON results")
    parser.add_argument("--optimized", action="store_true", help="Run with caching/batching enabled")
    args = parser.parse_args()

    if args.optimized:
        metrics = run_scenario("optimized", disable_cache=False, disable_batch=False, concurrency=4, records=args.records, delay=args.delay)
    else:
        metrics = run_scenario("baseline", disable_cache=True, disable_batch=True, concurrency=1, records=args.records, delay=args.delay)

    args.output.write_text(json.dumps(metrics, indent=2))
    print(f"Wrote results to {args.output}")
