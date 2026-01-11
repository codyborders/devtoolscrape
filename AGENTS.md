# Agent Instructions for devtoolscrape

This is a Flask-based web application that scrapes and aggregates startup/developer tool data from GitHub Trending, Hacker News, and Product Hunt. It uses AI classification via OpenAI to categorize entries.

## Quick Setup

```bash
# Install dependencies (creates .venv and installs packages)
bash setup.sh

# Activate the virtual environment
source .venv/bin/activate
```

## Running the Application

### Development Server

```bash
.venv/bin/flask --app app_production run --host 0.0.0.0 --port 8000
```

### Production Server (Gunicorn)

```bash
.venv/bin/gunicorn -c gunicorn.conf.py app_production:app
```

## Running Tests

```bash
bash run-tests.sh
```

With coverage:

```bash
bash run-tests.sh --cov=. --cov-report=term-missing
```

## Building Docker Image

Use `depot` instead of `docker` for builds:

```bash
depot build -t devtoolscrape .
```

Run with docker-compose:

```bash
docker compose up -d
```

## Project Structure

| File | Purpose |
|------|---------|
| `app_production.py` | Main Flask application with API routes |
| `database.py` | SQLite database operations |
| `scrape_all.py` | Orchestrates all scrapers |
| `scrape_hackernews.py` | Hacker News scraper |
| `scrape_producthunt.py` | Product Hunt scraper |
| `scrape_producthunt_api.py` | Product Hunt API client |
| `ai_classifier.py` | OpenAI-based classification |
| `logging_config.py` | Structured JSON logging |
| `gunicorn.conf.py` | Gunicorn server configuration |
| `tests/` | pytest test suite |

## Environment Variables

Create a `.env` file with these variables:

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | AI classification of entries |
| `PRODUCTHUNT_CLIENT_ID` | No | Product Hunt API access |
| `PRODUCTHUNT_CLIENT_SECRET` | No | Product Hunt API access |
| `DATADOG_API_KEY` | No | Observability/monitoring |
| `SECRET_KEY` | No | Flask session secret (has default) |

## Code Style

Follow the practices in `PYTHON.md`:
- Type hints on all function signatures
- Google-style docstrings
- pytest for testing
- black/flake8/mypy for linting

## Database

SQLite database at `startups.db`. Initialize with:

```python
from database import init_db
init_db()
```

## Key Endpoints

- `GET /` - Main page with startup listings
- `GET /health` - Health check endpoint
- `GET /api/startups` - JSON API for startups
- `GET /startup/<id>` - Individual startup detail
