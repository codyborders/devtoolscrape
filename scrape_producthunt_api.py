import requests
import os
from datetime import datetime
from database import init_db, save_startup
from ai_classifier import is_devtools_related_ai, get_devtools_category
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_producthunt_token():
    """Get Product Hunt access token using API key and secret"""
    client_id = os.getenv('PRODUCTHUNT_CLIENT_ID')
    client_secret = os.getenv('PRODUCTHUNT_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("❌ PRODUCTHUNT_CLIENT_ID and PRODUCTHUNT_CLIENT_SECRET environment variables not set")
        print("Get them from: https://api.producthunt.com/v2/oauth/applications")
        return None
    
    # Get access token
    token_url = "https://api.producthunt.com/v2/oauth/token"
    token_data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    
    try:
        token_resp = requests.post(token_url, data=token_data, timeout=10)
        token_resp.raise_for_status()
        token_info = token_resp.json()
        return token_info.get('access_token')
    except Exception as e:
        print(f"❌ Failed to get access token: {e}")
        return None

def scrape_producthunt_api():
    """Scrape Product Hunt using their official API"""
    
    # Get access token
    access_token = get_producthunt_token()
    if not access_token:
        print("❌ Cannot proceed without Product Hunt API credentials")
        return
    
    # Product Hunt API endpoint
    url = "https://api.producthunt.com/v2/api/graphql"
    
    # GraphQL query to get today's products
    query = """
    query {
        posts(first: 50, order: NEWEST) {
            edges {
                node {
                    id
                    name
                    tagline
                    description
                    url
                    createdAt
                    topics {
                        edges {
                            node {
                                name
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}',
        'User-Agent': 'DevTools Scraper/1.0'
    }
    
    try:
        resp = requests.post(url, json={'query': query}, headers=headers, timeout=10)
        resp.raise_for_status()
        print(f"✅ Product Hunt API response: {resp.status_code}")
        
        data = resp.json()
        posts = data.get('data', {}).get('posts', {}).get('edges', [])
        print(f"Found {len(posts)} products")
        
        devtools_count = 0
        for post_edge in posts:
            post = post_edge['node']
            name = post['name']
            tagline = post.get('tagline', '')
            description = post.get('description', '')
            
            # Check if it's devtools related using AI
            full_text = f"{name} {tagline} {description}"
            print(f"Checking: {name[:50]}...")
            
            if not is_devtools_related_ai(full_text, name):
                print(f"  -> Skipped (not devtools related)")
                continue
            
            print(f"  -> SAVING (devtools related)")
            devtools_count += 1
            
            # Get category if possible
            category = get_devtools_category(full_text, name)
            if category:
                description = f"[{category}] {tagline}\n\n{description}"
            else:
                description = f"{tagline}\n\n{description}"
            
            startup = {
                "name": name,
                "url": post.get('url', ''),
                "description": description,
                "date_found": datetime.fromisoformat(post['createdAt'].replace('Z', '+00:00')),
                "source": "Product Hunt"
            }
            
            save_startup(startup)
        
        print(f"Total devtools items found: {devtools_count}")
        
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Error parsing response: {e}")

if __name__ == "__main__":
    init_db()
    scrape_producthunt_api()
    print("Product Hunt scraping complete and saved to database.") 