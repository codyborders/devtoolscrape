#!/usr/bin/env python3
"""
Measure response times for key Flask routes using a synthetic SQLite database.
Intended to be run before and after performance optimizations to quantify impact.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from datetime import datetime, timedelta

import sqlite3


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


RECORD_COUNT = 50000
SOURCES = (
    ("GitHub Trending", 0.4),
    ("Hacker News (score: 100)", 0.3),
    ("Product Hunt", 0.25),
    ("Indie Hackers", 0.05),
)


def seed_database(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE startups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT UNIQUE,
            description TEXT,
            source TEXT,
            date_found TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_scrape TIMESTAMP NOT NULL,
            scrapers_run TEXT
        )
        """
    )

    insert_sql = """
        INSERT INTO startups (name, url, description, source, date_found)
        VALUES (?, ?, ?, ?, ?)
    """

    rows: List[Tuple[str, str, str, str, str]] = []
    index = 0
    for source, ratio in SOURCES:
        count = int(RECORD_COUNT * ratio)
        for i in range(count):
            index += 1
            days = index % 365
            date_found = (datetime.utcnow() - timedelta(days=days)).isoformat()
            rows.append(
                (
                    f"{source} Tool {index}",
                    f"https://example.com/{source.replace(' ', '-').replace('(', '').replace(')', '').lower()}/{index}",
                    f"{source} productivity booster #{index}",
                    source,
                    date_found,
                )
            )
    # Ensure total count exactly RECORD_COUNT
    while len(rows) < RECORD_COUNT:
        index += 1
        date_found = (datetime.utcnow() - timedelta(days=index % 365)).isoformat()
        rows.append(
            (
                f"Extra Tool {index}",
                f"https://example.com/extra/{index}",
                f"Extra devtool #{index}",
                "Misc",
                date_found,
            )
        )

    conn.executemany(insert_sql, rows)
    conn.commit()
    conn.close()


@contextmanager
def configured_app(tmp_dir: Path):
    db_path = tmp_dir / "startups.db"
    seed_database(db_path)
    os.environ["DEVTOOLS_DB_PATH"] = str(db_path)
    # Import after setting env so init_db uses seeded DB
    import importlib
    import sys

    if "database" in sys.modules:
        database = importlib.reload(sys.modules["database"])
    else:
        import database  # type: ignore  # noqa: F401
        database = sys.modules["database"]
    if "app_production" in sys.modules:
        app_production = importlib.reload(sys.modules["app_production"])
    else:
        import app_production  # type: ignore  # noqa: F401
        app_production = sys.modules["app_production"]

    app = app_production.app
    with app.test_client() as client:
        yield client


def time_call(client, path: str, iterations: int = 5) -> List[float]:
    durations: List[float] = []

    # warm up
    client.get(path)

    for _ in range(iterations):
        start = time.perf_counter()
        resp = client.get(path)
        resp.get_data()
        durations.append(time.perf_counter() - start)
    return durations


def measure(client) -> Dict[str, Dict[str, float]]:
    metrics: Dict[str, Dict[str, float]] = {}
    endpoints = [
        ("/", 5),
        ("/?source=github", 5),
        ("/?source=hackernews", 5),
        ("/?source=producthunt", 5),
        ("/search?q=tool", 5),
        ("/tool/1", 5),
        ("/api/search?q=tool", 5),
    ]
    for path, iterations in endpoints:
        durations = time_call(client, path, iterations)
        metrics[path] = {
            "median_ms": statistics.median(durations) * 1000,
            "mean_ms": statistics.mean(durations) * 1000,
            "stdev_ms": statistics.pstdev(durations) * 1000,
        }
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Measure Flask route performance.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("performance_results.json"),
        help="Where to write the measurement results (JSON).",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with configured_app(tmp_dir) as client:
            results = measure(client)

    args.output.write_text(json.dumps(results, indent=2))
    print(f"Wrote results to {args.output}")


if __name__ == "__main__":
    main()
