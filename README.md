# DevTools Scrape

A developer tools discovery platform that scrapes, classifies, and surfaces developer tools from multiple sources. Users can browse, search, and get AI-powered recommendations through a conversational chatbot.

## Disclaimer

This project is a **playground for experimenting with AI tooling, observability workflows, and deployment pipelines**. It is not intended for production use by others. The codebase prioritizes learning and experimentation over polish -- expect rough edges, evolving architecture, and occasional breakage as new integrations are tested.

## How It Works

### Data Pipeline

Scrapers collect developer tools from three sources:

- **GitHub Trending** -- trending repositories tagged as developer tools
- **Hacker News** -- Show HN posts and articles about developer tools
- **Product Hunt** -- new product launches in the developer tools category

`scrape_all.py` orchestrates the scrapers and stores results in a SQLite database with FTS5 full-text search indexing. An OpenAI-powered classifier (`ai_classifier.py`) categorizes each tool by type (DevOps, Testing, Build/Deploy, etc.).

### Web Application

A Flask app (`app_production.py`) serves:

- **Browse** -- paginated listing of all discovered tools, filterable by source
- **Search** -- full-text search powered by SQLite FTS5
- **Tool detail pages** -- individual tool pages with related tool recommendations
- **Chatbot** (`/api/chat`) -- an OpenAI Agents SDK chatbot that recommends tools based on natural language questions

### Infrastructure

- **Runtime**: gunicorn behind nginx on a DigitalOcean droplet
- **Container**: Docker image built with Depot, published to GHCR
- **CI/CD**: GitHub Actions (test -> Depot build -> SSH deploy)
- **Observability**: Datadog APM, profiling, ASM/IAST, LLM Observability, and load testing via Locust

### Observability Stack

The app is heavily instrumented with Datadog as a testbed for their observability products:

- **APM & Tracing** -- distributed traces across web requests, scraper jobs, and LLM calls
- **Profiling** -- continuous profiling with timeline, memory, heap, stack, and lock profilers
- **Application Security** -- AppSec and IAST vulnerability scanning
- **LLM Observability** -- agent workflow traces linking the chatbot's tool calls and LLM responses, with prompt tracking via `annotation_context`
- **Dynamic Instrumentation** -- live debugging and exception replay
- **Code Origin for Spans** -- source code links in traces
- **Test Optimization** -- CI test visibility with `ddtrace-run pytest`
- **Load Testing** -- Locust runs continuously against the production site

## Project Structure

```
app_production.py        Flask web app and API
chatbot.py               OpenAI Agents SDK chatbot with tool search
ai_classifier.py         OpenAI-powered tool categorization
database.py              SQLite + FTS5 persistence layer
scrape_all.py            Master scraper orchestrator
scrape_github_trending.py
scrape_hackernews.py
scrape_producthunt.py
scrape_producthunt_api.py
logging_config.py        Structured JSON logging
observability.py         Datadog tracing helpers
gunicorn.conf.py         Gunicorn configuration
entrypoint.sh            Container entrypoint (ddtrace-run)
Dockerfile               Container build
docker-compose.yml       Production stack (app + dd-agent + locust)
docker-compose.yaml      Development stack
tests/                   pytest suite (~140 tests)
loadtests/               Locust load test scenarios
templates/               Jinja2 HTML templates
static/                  Frontend assets
```

## Running Locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in the required API keys (`OPENAI_API_KEY`, `DATADOG_API_KEY`).

```bash
# Run scrapers
python scrape_all.py

# Start the dev server
flask --app app_production run --debug

# Run tests
pytest tests/
```

## Caveats

- **Experimental**: this project exists to test AI-assisted development workflows, Datadog integrations, and deployment automation. It is not designed or maintained as a reliable service.
- **API keys required**: the chatbot and classifier require an OpenAI API key. Datadog instrumentation requires a Datadog API key. Without these, only the browse/search features work.
- **Pre-release dependencies**: the project currently pins `ddtrace==4.5.0rc1` from a Datadog pre-release S3 bucket. This is intentional for testing unreleased features and may break without notice.
- **Single-server deployment**: the production stack runs on a single small droplet. Deploys cause brief downtime during container restarts.
- **No authentication**: the app has no user accounts or access control. It serves public, scraped data.
