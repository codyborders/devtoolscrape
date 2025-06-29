import requests
from datetime import datetime
from database import init_db, save_startup
from ai_classifier import is_devtools_related_ai, get_devtools_category

def scrape_hackernews():
    """Scrape Hacker News for devtools using their API"""
    
    # Get top stories
    try:
        top_stories_resp = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=10)
        top_stories_resp.raise_for_status()
        top_story_ids = top_stories_resp.json()[:50]  # Get top 50 stories
        
        print(f"Found {len(top_story_ids)} top stories")
        
        devtools_count = 0
        for story_id in top_story_ids:
            # Get story details
            story_resp = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json', timeout=10)
            story_resp.raise_for_status()
            story = story_resp.json()
            
            if not story or story.get('type') != 'story':
                continue
                
            title = story.get('title', '')
            url = story.get('url', '')
            text = story.get('text', '')  # Self-post text
            score = story.get('score', 0)
            
            # Skip if no URL (self-posts) or low score
            if not url or score < 10:
                continue
            
            # Combine title and text for classification
            full_text = f"{title} {text}"
            print(f"Checking: {title[:50]}... (score: {score})")
            
            # Check if it's devtools related using AI
            if not is_devtools_related_ai(full_text, title):
                print(f"  -> Skipped (not devtools related)")
                continue
            
            print(f"  -> SAVING (devtools related)")
            devtools_count += 1
            
            # Get category if possible
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
        
        print(f"Total devtools items found: {devtools_count}")
        
    except requests.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"Error: {e}")

def scrape_hackernews_show():
    """Scrape Hacker News Show HN posts (often devtools)"""
    
    try:
        show_hn_resp = requests.get('https://hacker-news.firebaseio.com/v0/showstories.json', timeout=10)
        show_hn_resp.raise_for_status()
        show_story_ids = show_hn_resp.json()[:30]  # Get top 30 Show HN stories
        
        print(f"Found {len(show_story_ids)} Show HN stories")
        
        devtools_count = 0
        for story_id in show_story_ids:
            # Get story details
            story_resp = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json', timeout=10)
            story_resp.raise_for_status()
            story = story_resp.json()
            
            if not story or story.get('type') != 'story':
                continue
                
            title = story.get('title', '')
            url = story.get('url', '')
            text = story.get('text', '')
            score = story.get('score', 0)
            
            # Skip if no URL or low score
            if not url or score < 5:
                continue
            
            # Show HN posts are often devtools, so be more lenient
            full_text = f"{title} {text}"
            print(f"Checking Show HN: {title[:50]}... (score: {score})")
            
            # For Show HN, we can be more lenient with classification
            if not is_devtools_related_ai(full_text, title):
                print(f"  -> Skipped (not devtools related)")
                continue
            
            print(f"  -> SAVING (devtools related)")
            devtools_count += 1
            
            # Get category if possible
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
        
        print(f"Total Show HN devtools found: {devtools_count}")
        
    except requests.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    init_db()
    print("Scraping Hacker News top stories...")
    scrape_hackernews()
    print("\nScraping Show HN posts...")
    scrape_hackernews_show()
    print("Hacker News scraping complete and saved to database.") 