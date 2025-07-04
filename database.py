import sqlite3
import os
from datetime import datetime

# Create data directory if it doesn't exist
DATA_DIR = os.path.join(os.getcwd(), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

DB_NAME = "/app/data/startups.db"  # Use absolute path for reliability

def init_db():
    # Check if database already exists and has data
    if os.path.exists(DB_NAME) and os.path.getsize(DB_NAME) > 0:
        # Test if the startups table exists
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='startups'")
            if c.fetchone():
                conn.close()
                return  # Database already exists with proper schema
            conn.close()
        except:
            pass
    
    # Create new database with schema
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM startups WHERE name = ? OR url = ?", (name, url))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def save_startup(startup):
    conn = sqlite3.connect(DB_NAME)
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

def get_all_startups():
    """Get all startups"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT id, name, url, description, source, date_found
        FROM startups ORDER BY date_found DESC
    ''')
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            'id': row[0],
            'name': row[1],
            'url': row[2],
            'description': row[3],
            'source': row[4],
            'date_found': row[5]
        }
        for row in rows
    ]

def search_startups(query):
    """Search startups by name or description"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT id, name, url, description, source, date_found
        FROM startups 
        WHERE name LIKE ? OR description LIKE ?
        ORDER BY date_found DESC
    ''', (f'%{query}%', f'%{query}%'))
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            'id': row[0],
            'name': row[1],
            'url': row[2],
            'description': row[3],
            'source': row[4],
            'date_found': row[5]
        }
        for row in rows
    ]

def get_startup_by_url(url):
    """Get startup by URL"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT id, name, url, description, source, date_found
        FROM startups WHERE url = ?
    ''', (url,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'name': row[1],
            'url': row[2],
            'description': row[3],
            'source': row[4],
            'date_found': row[5]
        }
    return None

def record_scrape_completion(scrapers_run=None):
    """Record that a scrape has completed"""
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT last_scrape FROM scrape_log ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    
    if row:
        return row[0]
    return None
