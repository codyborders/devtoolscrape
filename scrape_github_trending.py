import uuid
from datetime import datetime

import requests

from ai_classifier import classify_candidates, get_devtools_category
from database import init_db, save_startup
from logging_config import get_logger, logging_context

logger = get_logger("devtools.scraper.github_trending")

def scrape_github_trending():
    url = "https://github.com/trending"
    run_id = str(uuid.uuid4())
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    with logging_context(scraper="github_trending", scrape_run_id=run_id):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            logger.info(
                "scraper.response",
                extra={"event": "scraper.response", "status_code": resp.status_code},
            )
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            repos = soup.find_all('article', class_='Box-row')
            logger.info(
                "scraper.repos_found",
                extra={"event": "scraper.repos_found", "count": len(repos)},
            )
            
            candidates = []
            for repo in repos:
                name_elem = repo.find('h2', class_='h3')
                if not name_elem:
                    continue

                name = name_elem.get_text(strip=True).replace('\n', '').replace(' ', '')
                desc_elem = repo.find('p')
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                link_elem = name_elem.find('a')
                if not link_elem:
                    continue
                repo_url = f"https://github.com{link_elem['href']}"

                candidates.append({
                    "id": repo_url,
                    "name": name,
                    "text": description or name,
                    "description": description,
                    "url": repo_url,
                })

            results = classify_candidates(
                {
                    "id": candidate["id"],
                    "name": candidate["name"],
                    "text": candidate["text"],
                }
                for candidate in candidates
            )

            devtools_count = 0
            for candidate in candidates:
                if not results.get(candidate["id"]):
                    logger.debug(
                        "scraper.skip_non_devtool",
                        extra={
                            "event": "scraper.skip_non_devtool",
                            "repo_url": candidate["id"],
                        },
                    )
                    continue

                devtools_count += 1

                description = candidate["description"]
                category = get_devtools_category(description, candidate["name"])
                if category:
                    description = f"[{category}] {description}" if description else f"[{category}]"

                startup = {
                    "name": candidate["name"],
                    "url": candidate["url"],
                    "description": description,
                    "date_found": datetime.now(),
                    "source": "GitHub Trending"
                }

                save_startup(startup)
            
            logger.info(
                "scraper.complete",
                extra={
                    "event": "scraper.complete",
                    "devtools_count": devtools_count,
                    "total_repos": len(repos),
                },
            )
            
        except requests.RequestException:
            logger.exception("scraper.request_failed", extra={"event": "scraper.request_failed"})
        except Exception:
            logger.exception("scraper.parse_error", extra={"event": "scraper.parse_error"})

if __name__ == "__main__":
    init_db()
    scrape_github_trending()
    logger.info("scraper.script_complete", extra={"event": "scraper.script_complete"})
