import requests
from datetime import datetime
from database import init_db, save_startup
from ai_classifier import classify_candidates, get_devtools_category

def scrape_github_trending():
    url = "https://github.com/trending"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        print(f"Response status: {resp.status_code}")
        
        # Parse the trending page
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # Find trending repositories
        repos = soup.find_all('article', class_='Box-row')
        print(f"Found {len(repos)} trending repositories")
        
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
                print(f"  -> Skipped (not devtools related)")
                continue

            print(f"  -> SAVING (devtools related)")
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
        
        print(f"Total devtools items found: {devtools_count}")
        
    except requests.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"Error parsing response: {e}")

if __name__ == "__main__":
    init_db()
    scrape_github_trending()
    print("Scraping complete and saved to database.") 
