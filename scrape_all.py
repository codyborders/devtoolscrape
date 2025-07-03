#!/usr/bin/env python3
"""
Master scraper that runs all data sources
"""

from datetime import datetime
from database import init_db, record_scrape_completion
import importlib.util
import sys

def run_scraper(module_name, description):
    """Run a scraper module and handle any errors"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    
    try:
        # Import and run the scraper
        spec = importlib.util.spec_from_file_location(module_name, f"{module_name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Run the main function if it exists
        if hasattr(module, 'scrape_github_trending'):
            module.scrape_github_trending()
        elif hasattr(module, 'scrape_hackernews'):
            module.scrape_hackernews()
            module.scrape_hackernews_show()
        elif hasattr(module, 'scrape_producthunt_api'):
            module.scrape_producthunt_api()
        else:
            print(f"❌ No main scraping function found in {module_name}")
            
    except Exception as e:
        print(f"❌ Error running {module_name}: {e}")
        return False
    
    return True

def main():
    """Run all scrapers"""
    print("🚀 Starting DevTools Scraper")
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
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
    
    print(f"\n{'='*60}")
    print(f"✅ Scraping Complete!")
    print(f"📊 Results: {successful_scrapers}/{total_scrapers} scrapers successful")
    print(f"📅 Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # Record the scrape completion
    scrapers_run = [desc for _, desc in scrapers[:successful_scrapers]]
    record_scrape_completion(', '.join(scrapers_run))
    
    if successful_scrapers > 0:
        print("\n🌐 View your results at: http://localhost:8000")
        print("💡 Run 'python app.py' to start the web interface")

if __name__ == "__main__":
    main() 