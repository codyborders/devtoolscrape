# DevTools Scrape

DevTools Scrape collects developer-tool listings from GitHub Trending, Hacker News, and Product Hunt. It stores each entry in SQLite, classifies it with OpenAI, and exposes browse pages, search, detail pages, and a chatbot for tool recommendations.

## Disclaimer

This repository is a playground for AI tooling, Datadog observability, and deployment experiments. It is not packaged or maintained for outside production use. Expect rough edges, changing architecture, and occasional breakage while integrations are being tested.

## How It Works

### Data Pipeline

The scraper layer pulls from GitHub Trending developer-tool repositories, Show HN posts and developer-tool articles, and Product Hunt launches in the developer-tools category.

`scrape_all.py` runs each scraper and writes results to SQLite with FTS5 indexing. `ai_classifier.py` calls the OpenAI Responses API to assign categories. The category set includes DevOps and Testing, with Build/Deploy covering release tooling.

### Web Application

`app_production.py` is the Flask entry point. It provides paginated browsing with source filters, SQLite FTS5 search, detail pages with related-tool recommendations, and `/api/chat`, an OpenAI Agents SDK endpoint that answers natural language recommendation questions.

### Infrastructure

| Area | Setup |
| --- | --- |
| Runtime | `gunicorn` behind nginx on a DigitalOcean droplet |
| Container | Docker image built with Depot and published to GHCR |
| CI/CD | GitHub Actions runs tests, builds with Depot, and deploys over SSH |
| Observability | Datadog APM, profiling, ASM/IAST, and LLM Observability |

### Observability Stack

Datadog instrumentation makes the app a testbed for traces from Flask traffic, scraper jobs, and LLM calls. Coverage spans distributed tracing, continuous profiling, AppSec, IAST scanning, LLM Observability, prompt tracking through `annotation_context`, Dynamic Instrumentation for live debugging and exception replay, Code Origin for Spans, and CI test visibility through `ddtrace-run pytest`. The profilers capture timeline and memory data, plus heap snapshots, stack samples, and lock contention.

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
docker-compose.yml       Production stack (app + dd-agent)
docker-compose.yaml      Development stack
tests/                   pytest suite (~140 tests)
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

This project exists to test AI-assisted development workflows, Datadog integrations, and deployment automation. It is not designed or maintained as a reliable service.

The chatbot and classifier require an OpenAI API key. Datadog instrumentation requires a Datadog API key. Without those keys, only the browse and search features work.

The project currently pins `ddtrace==4.5.0rc1` from a Datadog pre-release S3 bucket. That pin is intentional for testing unreleased features and may break without notice.

The production stack runs on a single small droplet. Deploys cause brief downtime during container restarts.

The app has no user accounts or access control. It serves public, scraped data.
