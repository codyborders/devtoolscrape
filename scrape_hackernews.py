import uuid
from datetime import datetime

import requests

from ai_classifier import classify_candidates, get_devtools_category
from database import init_db, save_startup
from logging_config import get_logger, logging_context

logger = get_logger("devtools.scraper.hackernews")

def scrape_hackernews():
    """Scrape Hacker News for devtools using their API"""
    run_id = str(uuid.uuid4())
    with logging_context(scraper="hackernews", scrape_run_id=run_id):
        try:
            top_stories_resp = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=10)
            top_stories_resp.raise_for_status()
            top_story_ids = top_stories_resp.json()[:50]
            
            logger.info(
                "scraper.top_stories",
                extra={"event": "scraper.top_stories", "count": len(top_story_ids)},
            )
            
            story_cache = {}
            candidates = []
            for story_id in top_story_ids:
                story_resp = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json', timeout=10)
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
                if category:
                    description = f"[{category}] {title}"
                    if text:
                        description += f"\n\n{text}"
                else:
                    description = title
                    if text:
                        description += f"\n\n{text}"

                startup = {
                    "name": title,
                    "url": url,
                    "description": description,
                    "date_found": datetime.fromtimestamp(story.get('time', datetime.now().timestamp())),
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
            show_hn_resp = requests.get('https://hacker-news.firebaseio.com/v0/showstories.json', timeout=10)
            show_hn_resp.raise_for_status()
            show_story_ids = show_hn_resp.json()[:30]
            
            logger.info(
                "scraper.show_stories",
                extra={"event": "scraper.show_stories", "count": len(show_story_ids)},
            )
            
            story_cache = {}
            candidates = []
            for story_id in show_story_ids:
                story_resp = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json', timeout=10)
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
                if category:
                    description = f"[{category}] {title}"
                    if text:
                        description += f"\n\n{text}"
                else:
                    description = title
                    if text:
                        description += f"\n\n{text}"

                startup = {
                    "name": title,
                    "url": url,
                    "description": description,
                    "date_found": datetime.fromtimestamp(story.get('time', datetime.now().timestamp())),
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
