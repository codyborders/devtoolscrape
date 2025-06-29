import requests
from datetime import datetime
from database import init_db, save_startup
from ai_classifier import is_devtools_related_ai, get_devtools_category

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
        
        devtools_count = 0
        for repo in repos:
            # Extract repo name
            name_elem = repo.find('h2', class_='h3')
            if not name_elem:
                continue
                
            name = name_elem.get_text(strip=True).replace('\n', '').replace(' ', '')
            
            # Extract description
            desc_elem = repo.find('p')
            description = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Extract URL
            link_elem = name_elem.find('a')
            if not link_elem:
                continue
            repo_url = f"https://github.com{link_elem['href']}"
            
            # Check if it's devtools related using AI
            print(f"Checking: {name[:50]}...")
            
            if not is_devtools_related_ai(description, name):
                print(f"  -> Skipped (not devtools related)")
                continue
            
            print(f"  -> SAVING (devtools related)")
            devtools_count += 1
            
            # Get category if possible
            category = get_devtools_category(description, name)
            if category:
                description = f"[{category}] {description}"
            
            startup = {
                "name": name,
                "url": repo_url,
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