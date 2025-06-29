from bs4 import BeautifulSoup
from datetime import datetime
import requests
from database import init_db, save_startup
from dev_utils import is_devtools_related

def scrape_producthunt_rss():
    url = "https://www.producthunt.com/feed"
    
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()  # Raise exception for bad status codes
        print(f"Response status: {resp.status_code}")
        print(f"Response content length: {len(resp.content)}")
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return
    
    soup = BeautifulSoup(resp.content, features="xml")
    items = soup.findAll("item")
    print(f"Found {len(items)} items in RSS feed")

    devtools_count = 0
    for item in items:
        title = item.title.text
        description = item.description.text
        
        print(f"Checking: {title[:50]}...")
        
        if not is_devtools_related(title + " " + description):
            print(f"  -> Skipped (not devtools related)")
            continue

        print(f"  -> SAVING (devtools related)")
        devtools_count += 1
        
        startup = {
            "name": title,
            "url": item.link.text,
            "description": description,
            "date_found": datetime.strptime(item.pubDate.text, "%a, %d %b %Y %H:%M:%S %z"),
            "source": "Product Hunt"
        }

        save_startup(startup)
    
    print(f"Total devtools items found: {devtools_count}")

if __name__ == "__main__":
    init_db()
    scrape_producthunt_rss()
    print("Scraping complete and saved to database.")
