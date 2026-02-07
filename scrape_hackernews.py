import time
import uuid
from datetime import datetime

import requests
from requests.exceptions import (
    ConnectionError,
    ConnectTimeout,
    HTTPError,
    ReadTimeout,
    SSLError,
    Timeout,
)

from ai_classifier import classify_candidates, get_devtools_category
from database import init_db, save_startup
from logging_config import get_logger, logging_context
from observability import trace_http_call

logger = get_logger("devtools.scraper.hackernews")


def _build_description(title: str, text: str, category: str | None) -> str:
    """Build a description string from title, text, and optional category prefix."""
    if category:
        description = f"[{category}] {title}"
    else:
        description = title
    if text:
        description += f"\n\n{text}"
    return description


# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1  # seconds
MAX_BACKOFF = 30  # seconds
BACKOFF_MULTIPLIER = 2

# Exceptions that should trigger a retry
RETRYABLE_EXCEPTIONS = (
    SSLError,
    ConnectionError,
    ConnectTimeout,
    ReadTimeout,
    Timeout,
)


def _is_retryable_status_code(status_code: int) -> bool:
    """Check if HTTP status code is retryable (5xx server errors)."""
    return status_code in (502, 503, 504)


def _request_with_retry(url: str, timeout: tuple, max_retries: int = MAX_RETRIES):
    """Make HTTP GET request with retry logic for transient failures.

    Retries on:
    - SSL errors (including SSL EOF)
    - Connection errors
    - Timeouts (connect and read)
    - 5xx server errors (502, 503, 504)

    Does NOT retry on:
    - 4xx client errors (400, 404, etc.)
    - JSON decode errors
    - Other non-transient failures

    Uses exponential backoff between retries.
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout)

            # Check for retryable status codes before raise_for_status
            if _is_retryable_status_code(response.status_code):
                if attempt < max_retries:
                    backoff = min(
                        INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt),
                        MAX_BACKOFF
                    )
                    logger.warning(
                        "scraper.retrying",
                        extra={
                            "event": "scraper.retrying",
                            "url": url,
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "backoff_seconds": backoff,
                        },
                    )
                    time.sleep(backoff)
                    continue
                else:
                    # Exhausted retries, raise the error
                    response.raise_for_status()

            return response

        except RETRYABLE_EXCEPTIONS as e:
            last_exception = e
            if attempt < max_retries:
                backoff = min(
                    INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt),
                    MAX_BACKOFF
                )
                logger.warning(
                    "scraper.retrying",
                    extra={
                        "event": "scraper.retrying",
                        "url": url,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "backoff_seconds": backoff,
                    },
                )
                time.sleep(backoff)
            else:
                # Exhausted retries
                raise

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected state in retry logic")

def scrape_hackernews():
    """Scrape Hacker News for devtools using their API"""
    run_id = str(uuid.uuid4())
    with logging_context(scraper="hackernews", scrape_run_id=run_id):
        try:
            top_stories_url = 'https://hacker-news.firebaseio.com/v0/topstories.json'
            with trace_http_call("hackernews.topstories", "GET", top_stories_url) as span:
                top_stories_resp = _request_with_retry(top_stories_url, timeout=(5, 10))
                if span:
                    span.set_tag("http.status_code", top_stories_resp.status_code)
            top_stories_resp.raise_for_status()
            top_story_ids = top_stories_resp.json()[:50]

            logger.info(
                "scraper.top_stories",
                extra={"event": "scraper.top_stories", "count": len(top_story_ids)},
            )

            story_cache = {}
            candidates = []
            for story_id in top_story_ids:
                try:
                    story_url = f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json'
                    with trace_http_call("hackernews.story", "GET", story_url) as span:
                        story_resp = _request_with_retry(story_url, timeout=(5, 10))
                        if span:
                            span.set_tag("http.status_code", story_resp.status_code)
                            span.set_tag("hackernews.story_id", story_id)
                    story_resp.raise_for_status()
                    story = story_resp.json()

                    if not story or story.get('type') != 'story':
                        continue

                    title = story.get('title', '')
                    url = story.get('url', '')
                    text = story.get('text', '')
                    score = story.get('score', 0)

                    if not url or score < 10:
                        continue

                    key = str(story_id)
                    full_text = f"{title} {text}"
                    story_cache[key] = (story, title, url, text, score, full_text)
                    candidates.append({"id": key, "name": title, "text": full_text})
                except Exception:
                    logger.warning(
                        "scraper.story_fetch_failed",
                        extra={"event": "scraper.story_fetch_failed", "story_id": story_id},
                    )
                    continue

            results = classify_candidates(candidates)

            devtools_count = 0
            for key, (story, title, url, text, score, full_text) in story_cache.items():
                if not results.get(key):
                    logger.debug(
                        "scraper.skip_non_devtool",
                        extra={"event": "scraper.skip_non_devtool", "story_id": key},
                    )
                    continue

                devtools_count += 1

                category = get_devtools_category(full_text, title)
                description = _build_description(title, text, category)

                startup = {
                    "name": title,
                    "url": url,
                    "description": description,
                    "date_found": datetime.fromtimestamp(story.get('time') or datetime.now().timestamp()),
                    "source": f"Hacker News (score: {score})"
                }

                save_startup(startup)

            logger.info(
                "scraper.complete",
                extra={"event": "scraper.complete", "devtools_count": devtools_count, "candidates": len(candidates)},
            )
            
        except requests.RequestException:
            logger.exception("scraper.request_failed", extra={"event": "scraper.request_failed"})
        except Exception:
            logger.exception("scraper.error", extra={"event": "scraper.error"})

def scrape_hackernews_show():
    """Scrape Hacker News Show HN posts (often devtools)"""
    run_id = str(uuid.uuid4())
    with logging_context(scraper="hackernews_show", scrape_run_id=run_id):
        try:
            show_hn_url = 'https://hacker-news.firebaseio.com/v0/showstories.json'
            with trace_http_call("hackernews.showstories", "GET", show_hn_url) as span:
                show_hn_resp = _request_with_retry(show_hn_url, timeout=(5, 10))
                if span:
                    span.set_tag("http.status_code", show_hn_resp.status_code)
            show_hn_resp.raise_for_status()
            show_story_ids = show_hn_resp.json()[:30]

            logger.info(
                "scraper.show_stories",
                extra={"event": "scraper.show_stories", "count": len(show_story_ids)},
            )

            story_cache = {}
            candidates = []
            for story_id in show_story_ids:
                try:
                    story_url = f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json'
                    with trace_http_call("hackernews.story", "GET", story_url) as span:
                        story_resp = _request_with_retry(story_url, timeout=(5, 10))
                        if span:
                            span.set_tag("http.status_code", story_resp.status_code)
                            span.set_tag("hackernews.story_id", story_id)
                    story_resp.raise_for_status()
                    story = story_resp.json()

                    if not story or story.get('type') != 'story':
                        continue

                    title = story.get('title', '')
                    url = story.get('url', '')
                    text = story.get('text', '')
                    score = story.get('score', 0)

                    if not url or score < 5:
                        continue

                    full_text = f"{title} {text}"
                    key = f"show-{story_id}"
                    story_cache[key] = (story, title, url, text, score, full_text)
                    candidates.append({"id": key, "name": title, "text": full_text})
                except Exception:
                    logger.warning(
                        "scraper.story_fetch_failed",
                        extra={"event": "scraper.story_fetch_failed", "story_id": story_id},
                    )
                    continue

            results = classify_candidates(candidates)

            devtools_count = 0
            for key, (story, title, url, text, score, full_text) in story_cache.items():
                if not results.get(key):
                    logger.debug(
                        "scraper.skip_non_devtool",
                        extra={"event": "scraper.skip_non_devtool", "story_id": key},
                    )
                    continue

                devtools_count += 1

                category = get_devtools_category(full_text, title)
                description = _build_description(title, text, category)

                startup = {
                    "name": title,
                    "url": url,
                    "description": description,
                    "date_found": datetime.fromtimestamp(story.get('time') or datetime.now().timestamp()),
                    "source": f"Show HN (score: {score})"
                }

                save_startup(startup)

            logger.info(
                "scraper.complete",
                extra={
                    "event": "scraper.complete",
                    "devtools_count": devtools_count,
                    "candidates": len(candidates),
                },
            )
            
        except requests.RequestException:
            logger.exception("scraper.request_failed", extra={"event": "scraper.request_failed"})
        except Exception:
            logger.exception("scraper.error", extra={"event": "scraper.error"})

if __name__ == "__main__":
    init_db()
    scrape_hackernews()
    scrape_hackernews_show()
    logger.info("scraper.script_complete", extra={"event": "scraper.script_complete"})
