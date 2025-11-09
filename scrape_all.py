#!/usr/bin/env python3
"""
Master scraper that runs all data sources
"""

import importlib.util
import sys
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from database import init_db, record_scrape_completion
from logging_config import get_logger, logging_context

logger = get_logger("devtools.scraper.runner")

def run_scraper(module_name, description):
    """Run a scraper module and handle any errors"""
    run_id = str(uuid.uuid4())
    with logging_context(scraper_runner_module=module_name, scrape_run_id=run_id):
        logger.info(
            "runner.start_scraper",
            extra={"event": "runner.start_scraper", "description": description},
        )
        try:
            spec = importlib.util.spec_from_file_location(module_name, f"{module_name}.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, 'scrape_github_trending'):
                module.scrape_github_trending()
            elif hasattr(module, 'scrape_hackernews'):
                module.scrape_hackernews()
                module.scrape_hackernews_show()
            elif hasattr(module, 'scrape_producthunt_api'):
                module.scrape_producthunt_api()
            else:
                logger.warning(
                    "runner.missing_entrypoint",
                    extra={"event": "runner.missing_entrypoint"},
                )
        except Exception:
            logger.exception(
                "runner.scraper_failed",
                extra={"event": "runner.scraper_failed"},
            )
            return False
        logger.info(
            "runner.scraper_complete",
            extra={"event": "runner.scraper_complete"},
        )
        return True

def main():
    """Run all scrapers"""
    logger.info("runner.start", extra={"event": "runner.start"})
    
    # Initialize database
    init_db()
    
    # Define scrapers to run
    scrapers = [
        ("scrape_github_trending", "GitHub Trending Repositories"),
        ("scrape_hackernews", "Hacker News & Show HN"),
        ("scrape_producthunt_api", "Product Hunt API"),
    ]
    
    successful_scrapers = 0
    total_scrapers = len(scrapers)
    
    for module_name, description in scrapers:
        if run_scraper(module_name, description):
            successful_scrapers += 1
    
    logger.info(
        "runner.summary",
        extra={
            "event": "runner.summary",
            "successful_scrapers": successful_scrapers,
            "total_scrapers": total_scrapers,
        },
    )
    
    # Record the scrape completion
    scrapers_run = [desc for _, desc in scrapers[:successful_scrapers]]
    record_scrape_completion(', '.join(scrapers_run))
    
    if successful_scrapers > 0:
        logger.info(
            "runner.success_notice",
            extra={"event": "runner.success_notice"},
        )

if __name__ == "__main__":
    main() 
