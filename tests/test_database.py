from datetime import datetime, timedelta

import os
import sqlite3


def _fetch_all(connection, query):
    cur = connection.cursor()
    cur.execute(query)
    results = cur.fetchall()
    cur.close()
    return results


def test_init_db_creates_tables(fresh_db):
    fresh_db.init_db()
    # Run again to exercise the early exit path when schema already exists
    fresh_db.init_db()
    conn = sqlite3.connect(fresh_db.DB_NAME)
    tables = _fetch_all(conn, "SELECT name FROM sqlite_master WHERE type='table'")
    assert {"startups", "scrape_log"}.issubset({name for (name,) in tables})
    conn.close()


def test_save_and_retrieve_startups(fresh_db):
    now = datetime.now()
    startup = {
        "name": "AwesomeTool",
        "url": "https://example.com",
        "description": "A great developer helper",
        "source": "GitHub Trending",
        "date_found": now,
    }
    fresh_db.save_startup(startup)

    all_startups = fresh_db.get_all_startups()
    assert len(all_startups) == 1
    stored = all_startups[0]
    assert stored["name"] == "AwesomeTool"
    assert stored["url"] == "https://example.com"
    assert stored["source"] == "GitHub Trending"

    by_url = fresh_db.get_startup_by_url("https://example.com")
    assert by_url["id"] == stored["id"]


def test_is_duplicate_and_integrity_handling(fresh_db):
    now = datetime.now()
    base = {
        "name": "DupTool",
        "url": "https://duplicated.com",
        "description": "First",
        "source": "HN",
        "date_found": now,
    }
    fresh_db.save_startup(base)
    assert fresh_db.is_duplicate("DupTool", "https://duplicated.com")

    duplicate = dict(base, description="Second insertion")
    fresh_db.save_startup(duplicate)  # Should not raise despite unique constraint

    all_rows = fresh_db.get_all_startups()
    assert len(all_rows) == 1


def test_search_returns_matching_rows(fresh_db):
    now = datetime.now()
    second = now + timedelta(days=1)
    fresh_db.save_startup(
        {
            "name": "Searchable Tool",
            "url": "https://searchable.io",
            "description": "CLI for developers",
            "source": "Product Hunt",
            "date_found": second,
        }
    )
    fresh_db.save_startup(
        {
            "name": "Another App",
            "url": "https://another.app",
            "description": "Not devtools",
            "source": "Other",
            "date_found": now,
        }
    )

    results = fresh_db.search_startups("CLI")
    assert len(results) == 1
    assert results[0]["name"] == "Searchable Tool"


def test_record_scrape_completion_overwrites_history(fresh_db):
    # No rows yet -> ensure None path covered
    assert fresh_db.get_last_scrape_time() is None

    fresh_db.record_scrape_completion("GitHub Trending")
    first = fresh_db.get_last_scrape_time()
    assert first is not None

    fresh_db.record_scrape_completion("Product Hunt")
    second = fresh_db.get_last_scrape_time()
    assert second != first

    conn = sqlite3.connect(fresh_db.DB_NAME)
    rows = _fetch_all(conn, "SELECT scrapers_run FROM scrape_log")
    conn.close()
    # Only the most recent entry should remain
    assert len(rows) == 1
    assert rows[0][0] == "Product Hunt"


def test_init_db_recovers_from_partial_database(tmp_path, monkeypatch):
    import importlib
    import database

    importlib.reload(database)
    db_file = tmp_path / "partial.db"
    monkeypatch.setattr(database, "DB_NAME", str(db_file))

    # Create an existing SQLite file without the expected tables
    conn = sqlite3.connect(database.DB_NAME)
    conn.execute("CREATE TABLE temp_table(id INTEGER)")
    conn.commit()
    conn.close()

    database.init_db()
    conn = sqlite3.connect(database.DB_NAME)
    tables = _fetch_all(conn, "SELECT name FROM sqlite_master WHERE type='table'")
    conn.close()
    assert "startups" in {name for (name,) in tables}


def test_get_startup_by_url_missing(fresh_db):
    assert fresh_db.get_startup_by_url("https://missing.example.com") is None


def test_init_db_handles_initial_connect_failure(tmp_path, monkeypatch):
    import importlib
    import database

    importlib.reload(database)
    db_file = tmp_path / "retry.db"
    monkeypatch.setattr(database, "DB_NAME", str(db_file))

    # Pre-create file with content so init_db attempts the validation branch
    db_file.write_text("placeholder")

    original_connect = database.sqlite3.connect
    call_tracker = {"count": 0}

    def flaky_connect(path, *args, **kwargs):
        call_tracker["count"] += 1
        if call_tracker["count"] == 1:
            # Remove the invalid placeholder so the next attempt can create a real DB
            if os.path.exists(path):
                os.remove(path)
            raise database.sqlite3.OperationalError("first attempt fails")
        return original_connect(path, *args, **kwargs)

    monkeypatch.setattr(database.sqlite3, "connect", flaky_connect)

    database.init_db()
    assert call_tracker["count"] >= 2
