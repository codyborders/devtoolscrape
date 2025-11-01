import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_DATA_DIR = Path(os.getcwd()) / "data"
DATA_DIR = Path(os.getenv("DEVTOOLS_DATA_DIR", DEFAULT_DATA_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.getenv("DEVTOOLS_DB_PATH", DATA_DIR / "startups.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_NAME = str(DB_PATH)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)

def init_db():
        # Check if database already exists and has data
    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        # Test if the startups table exists
        try:
            conn = _connect()
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='startups'")
            if c.fetchone():
                conn.close()
                return  # Database already exists with proper schema
            conn.close()
        except Exception:
            pass

    conn = _connect()
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

    # Create table for tracking last scrape time
    c.execute('''
        CREATE TABLE IF NOT EXISTS scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_scrape TIMESTAMP NOT NULL,
            scrapers_run TEXT
        )
    ''')

    conn.commit()
    conn.close()

def is_duplicate(name: str, url: str) -> bool:
    """Check if item already exists in database"""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM startups WHERE name = ? OR url = ?", (name, url))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def save_startup(startup):
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
    except sqlite3.IntegrityError:
        # URL already exists
        pass
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
    return _row_to_dict(row) if row else None


def get_startups_by_sources(where_clause: str, params: Iterable) -> list[dict]:
    query = '''
        SELECT id, name, url, description, source, date_found
        FROM startups
        WHERE {} ORDER BY date_found DESC
    '''.format(where_clause)

    conn = _connect()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_dict(row) for row in rows]


def get_startups_by_source_key(source_key: str) -> list[dict]:
    if source_key == "github":
        return get_startups_by_sources("source = ?", ["GitHub Trending"])
    if source_key == "hackernews":
        return get_startups_by_sources(
            "source LIKE ? OR source LIKE ?",
            ["Hacker News%", "Show HN%"],
        )
    if source_key == "producthunt":
        return get_startups_by_sources("source = ?", ["Product Hunt"])
    return get_all_startups()


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

    return [_row_to_dict(row) for row in rows]

def search_startups(query):
    """Search startups by name or description"""
    conn = _connect()
    rows = conn.execute('''
        SELECT id, name, url, description, source, date_found
        FROM startups 
        WHERE name LIKE ? OR description LIKE ?
        ORDER BY date_found DESC
    ''', (f'%{query}%', f'%{query}%')).fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]

def get_startup_by_url(url):
    """Get startup by URL"""
    conn = _connect()
    row = conn.execute('''
        SELECT id, name, url, description, source, date_found
        FROM startups WHERE url = ?
    ''', (url,)).fetchone()
    conn.close()

    return _row_to_dict(row) if row else None

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

def get_last_scrape_time():
    """Get the timestamp of the last completed scrape"""
    conn = _connect()
    c = conn.cursor()
    c.execute('SELECT last_scrape FROM scrape_log ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    
    if row:
        return row[0]
    return None
