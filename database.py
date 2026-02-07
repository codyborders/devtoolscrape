import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from logging_config import get_logger

logger = get_logger("devtools.db")

DEFAULT_DATA_DIR = Path(os.getcwd()) / "data"
DATA_DIR = Path(os.getenv("DEVTOOLS_DATA_DIR", DEFAULT_DATA_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.getenv("DEVTOOLS_DB_PATH", DATA_DIR / "startups.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_NAME = str(DB_PATH)


def _connect() -> sqlite3.Connection:
    start = time.perf_counter()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    duration = round((time.perf_counter() - start) * 1000, 2)
    logger.debug(
        "db.connect",
        extra={"event": "db.connect", "duration_ms": duration, "db_path": str(DB_PATH)},
    )
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)

def init_db():
    logger.info("db.init.start", extra={"event": "db.init.start", "db_path": str(DB_PATH)})
    conn = None
    for attempt in range(2):
        try:
            conn = _connect()
            break
        except sqlite3.OperationalError:
            if attempt == 1:
                raise
            continue

    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS startups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT UNIQUE,
            description TEXT,
            source TEXT,
            date_found TIMESTAMP
        )
    ''')

    # Add index on name for faster duplicate checking
    c.execute('CREATE INDEX IF NOT EXISTS idx_startups_name ON startups(name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_startups_source ON startups(source)')

    # Create table for tracking last scrape time
    c.execute('''
        CREATE TABLE IF NOT EXISTS scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_scrape TIMESTAMP NOT NULL,
            scrapers_run TEXT
        )
    ''')

    # Create FTS index for fast search
    c.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS startups_fts
        USING fts5(name, description, content='startups', content_rowid='id')
    ''')
    c.executescript('''
        CREATE TRIGGER IF NOT EXISTS startups_ai AFTER INSERT ON startups BEGIN
            INSERT INTO startups_fts(rowid, name, description) VALUES (new.id, new.name, new.description);
        END;
        CREATE TRIGGER IF NOT EXISTS startups_ad AFTER DELETE ON startups BEGIN
            INSERT INTO startups_fts(startups_fts, rowid, name, description) VALUES('delete', old.id, old.name, old.description);
        END;
        CREATE TRIGGER IF NOT EXISTS startups_au AFTER UPDATE ON startups BEGIN
            INSERT INTO startups_fts(startups_fts, rowid, name, description) VALUES('delete', old.id, old.name, old.description);
            INSERT INTO startups_fts(rowid, name, description) VALUES (new.id, new.name, new.description);
        END;
    ''')
    try:
        c.execute("INSERT INTO startups_fts(startups_fts) VALUES('rebuild')")
    except sqlite3.OperationalError:
        # Rebuild may fail if table is empty or FTS not initialised yet; safe to ignore
        pass

    conn.commit()
    conn.close()
    logger.info("db.init.complete", extra={"event": "db.init.complete"})


def is_duplicate(name: str, url: str) -> bool:
    """Check if item already exists in database"""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM startups WHERE name = ? OR url = ?", (name, url))
    count = cursor.fetchone()[0]
    conn.close()
    logger.debug(
        "db.is_duplicate",
        extra={
            "event": "db.is_duplicate",
            "startup_name": name,
            "url": url,
            "is_duplicate": count > 0,
        },
    )
    return count > 0


def save_startup(startup):
    if is_duplicate(startup['name'], startup['url']):
        logger.warning(
            "db.startup_duplicate",
            extra={
                "event": "db.startup_duplicate",
                "startup_name": startup.get('name'),
                "url": startup.get('url'),
                "reason": "name_or_url_match",
            },
        )
        return

    conn = _connect()
    c = conn.cursor()

    try:
        c.execute('''
            INSERT INTO startups (name, url, description, source, date_found)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            startup['name'],
            startup['url'],
            startup['description'],
            startup['source'],
            startup['date_found']
        ))
        conn.commit()
        logger.info(
            "db.startup_saved",
            extra={
                "event": "db.startup_saved",
                "startup_name": startup.get('name'),
                "url": startup.get('url'),
                "source": startup.get('source'),
            },
        )
    except sqlite3.IntegrityError:
        # URL already exists (race condition fallback)
        logger.warning(
            "db.startup_duplicate",
            extra={
                "event": "db.startup_duplicate",
                "startup_name": startup.get('name'),
                "url": startup.get('url'),
            },
        )
    finally:
        conn.close()

def get_startup_by_id(startup_id: int) -> Optional[dict]:
    conn = _connect()
    row = conn.execute(
        '''
        SELECT id, name, url, description, source, date_found
        FROM startups WHERE id = ?
        ''',
        (startup_id,),
    ).fetchone()
    conn.close()
    result = _row_to_dict(row) if row else None
    logger.debug(
        "db.get_startup_by_id",
        extra={
            "event": "db.get_startup_by_id",
            "startup_id": startup_id,
            "found": bool(result),
        },
    )
    return result


def get_related_startups(source: str, exclude_id: int, limit: int = 4) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        '''
        SELECT id, name, url, description, source, date_found
        FROM startups
        WHERE source = ? AND id != ?
        ORDER BY date_found DESC
        LIMIT ?
        ''',
        (source, exclude_id, limit),
    ).fetchall()
    conn.close()
    results = [_row_to_dict(row) for row in rows]
    logger.debug(
        "db.get_related_startups",
        extra={
            "event": "db.get_related_startups",
            "source": source,
            "exclude_id": exclude_id,
            "limit": limit,
            "returned": len(results),
        },
    )
    return results


def get_startups_by_sources(where_clause: str, params: Iterable, limit: Optional[int] = None, offset: Optional[int] = None) -> list[dict]:
    query = '''
        SELECT id, name, url, description, source, date_found
        FROM startups
        WHERE {} ORDER BY date_found DESC
    '''.format(where_clause)

    args = list(params)
    if limit is not None:
        query += " LIMIT ?"
        args.append(limit)
    if offset is not None:
        if limit is None:
            query += " LIMIT -1"
        query += " OFFSET ?"
        args.append(offset)

    conn = _connect()
    rows = conn.execute(query, args).fetchall()
    conn.close()
    results = [_row_to_dict(row) for row in rows]
    logger.debug(
        "db.get_startups_by_sources",
        extra={
            "event": "db.get_startups_by_sources",
            "where": where_clause,
            "limit": limit,
            "offset": offset,
            "returned": len(results),
        },
    )
    return results


def count_startups_by_sources(where_clause: str, params: Iterable) -> int:
    query = 'SELECT COUNT(*) FROM startups WHERE {}'.format(where_clause)
    conn = _connect()
    (count,) = conn.execute(query, params).fetchone()
    conn.close()
    logger.debug(
        "db.count_startups_by_sources",
        extra={
            "event": "db.count_startups_by_sources",
            "where": where_clause,
            "count": count,
        },
    )
    return count


def get_startups_by_source_key(source_key: str, limit: Optional[int] = None, offset: Optional[int] = None) -> list[dict]:
    if source_key == "github":
        results = get_startups_by_sources("source = ?", ["GitHub Trending"], limit, offset)
    elif source_key == "hackernews":
        results = get_startups_by_sources(
            "source LIKE ? OR source LIKE ?",
            ["Hacker News%", "Show HN%"],
            limit,
            offset,
        )
    elif source_key == "producthunt":
        results = get_startups_by_sources("source = ?", ["Product Hunt"], limit, offset)
    else:
        results = get_all_startups(limit, offset)
    logger.debug(
        "db.get_startups_by_source_key",
        extra={
            "event": "db.get_startups_by_source_key",
            "source_key": source_key,
            "limit": limit,
            "offset": offset,
            "returned": len(results),
        },
    )
    return results


def count_startups_by_source_key(source_key: str) -> int:
    if source_key == "github":
        count = count_startups_by_sources("source = ?", ["GitHub Trending"])
    elif source_key == "hackernews":
        count = count_startups_by_sources(
            "source LIKE ? OR source LIKE ?",
            ["Hacker News%", "Show HN%"],
        )
    elif source_key == "producthunt":
        count = count_startups_by_sources("source = ?", ["Product Hunt"])
    else:
        count = count_all_startups()
    logger.debug(
        "db.count_startups_by_source_key",
        extra={
            "event": "db.count_startups_by_source_key",
            "source_key": source_key,
            "count": count,
        },
    )
    return count


def get_source_counts() -> dict:
    conn = _connect()
    rows = conn.execute("SELECT source, COUNT(*) as count FROM startups GROUP BY source").fetchall()
    conn.close()

    summary = {
        "total": 0,
        "github": 0,
        "hackernews": 0,
        "producthunt": 0,
        "other": 0,
    }

    for row in rows:
        source = row["source"]
        count = row["count"]
        summary["total"] += count
        if source == "GitHub Trending":
            summary["github"] += count
        elif source.startswith("Hacker News") or source.startswith("Show HN"):
            summary["hackernews"] += count
        elif source == "Product Hunt":
            summary["producthunt"] += count
        else:
            summary["other"] += count
    logger.debug(
        "db.get_source_counts",
        extra={"event": "db.get_source_counts", "summary": summary},
    )
    return summary


def get_all_startups(limit: Optional[int] = None, offset: Optional[int] = None):
    """Get all startups"""
    query = '''
        SELECT id, name, url, description, source, date_found
        FROM startups ORDER BY date_found DESC
    '''
    params: list = []
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    if offset is not None:
        if limit is None:
            query += " LIMIT -1"
        query += " OFFSET ?"
        params.append(offset)

    conn = _connect()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    results = [_row_to_dict(row) for row in rows]
    logger.debug(
        "db.get_all_startups",
        extra={
            "event": "db.get_all_startups",
            "limit": limit,
            "offset": offset,
            "returned": len(results),
        },
    )
    return results


def get_existing_startup_keys() -> list[dict]:
    """Return existing startup name/url pairs for fast duplicate checks."""
    conn = _connect()
    rows = conn.execute('SELECT name, url FROM startups').fetchall()
    conn.close()

    results = [{"name": row["name"], "url": row["url"]} for row in rows]
    logger.debug(
        "db.get_existing_startup_keys",
        extra={"event": "db.get_existing_startup_keys", "returned": len(results)},
    )
    return results


def count_all_startups() -> int:
    conn = _connect()
    (count,) = conn.execute('SELECT COUNT(*) FROM startups').fetchone()
    conn.close()
    logger.debug(
        "db.count_all_startups",
        extra={"event": "db.count_all_startups", "count": count},
    )
    return count


def search_startups(query: str, limit: int = 20, offset: int = 0):
    """Search startups using FTS."""
    if not query:
        return []

    conn = _connect()
    rows = conn.execute(
        '''
        SELECT s.id, s.name, s.url, s.description, s.source, s.date_found
        FROM startups s
        JOIN startups_fts fts ON s.id = fts.rowid
        WHERE startups_fts MATCH ?
        ORDER BY rank
        LIMIT ? OFFSET ?
        ''',
        (query, limit, offset),
    ).fetchall()
    conn.close()

    results = [_row_to_dict(row) for row in rows]
    logger.debug(
        "db.search_startups",
        extra={
            "event": "db.search_startups",
            "query": query,
            "limit": limit,
            "offset": offset,
            "returned": len(results),
        },
    )
    return results


def count_search_results(query: str) -> int:
    if not query:
        return 0
    conn = _connect()
    (count,) = conn.execute(
        '''
        SELECT COUNT(*) FROM startups_fts
        WHERE startups_fts MATCH ?
        ''',
        (query,),
    ).fetchone()
    conn.close()
    logger.debug(
        "db.count_search_results",
        extra={"event": "db.count_search_results", "query": query, "count": count},
    )
    return count


def get_startup_by_url(url):
    """Get startup by URL"""
    conn = _connect()
    row = conn.execute('''
        SELECT id, name, url, description, source, date_found
        FROM startups WHERE url = ?
    ''', (url,)).fetchone()
    conn.close()

    result = _row_to_dict(row) if row else None
    logger.debug(
        "db.get_startup_by_url",
        extra={"event": "db.get_startup_by_url", "url": url, "found": bool(result)},
    )
    return result


def record_scrape_completion(scrapers_run=None):
    """Record that a scrape has completed"""
    conn = _connect()
    c = conn.cursor()

    # Clear old entries and insert new one
    c.execute('DELETE FROM scrape_log')
    c.execute('''
        INSERT INTO scrape_log (last_scrape, scrapers_run)
        VALUES (?, ?)
    ''', (datetime.now().isoformat(), scrapers_run))

    conn.commit()
    conn.close()
    logger.info(
        "db.scrape_log_updated",
        extra={
            "event": "db.scrape_log_updated",
            "scrapers_run": scrapers_run,
        },
    )

def get_last_scrape_time():
    """Get the timestamp of the last completed scrape"""
    conn = _connect()
    c = conn.cursor()
    c.execute('SELECT last_scrape FROM scrape_log ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()

    result = row[0] if row else None
    logger.debug(
        "db.get_last_scrape_time",
        extra={"event": "db.get_last_scrape_time", "last_scrape": result},
    )
    return result
