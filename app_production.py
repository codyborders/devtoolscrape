from datetime import datetime
import os

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

from database import (
    get_all_startups,
    get_last_scrape_time,
    get_source_counts,
    get_startup_by_id,
    get_startups_by_source_key,
    get_startups_by_sources,
    search_startups,
    count_search_results,
    count_all_startups,
    count_startups_by_source_key,
    init_db,
)




# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize database
init_db()

# Production configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['DEBUG'] = False

if not app.debug:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

def summarize_sources(startups):
    counts = {
        'total': len(startups),
        'github': 0,
        'hackernews': 0,
        'producthunt': 0,
        'other': 0
    }

    for startup in startups:
        source = startup['source']
        if 'GitHub' in source:
            counts['github'] += 1
        elif 'Hacker News' in source or 'Show HN' in source:
            counts['hackernews'] += 1
        elif 'Product Hunt' in source:
            counts['producthunt'] += 1
        else:
            counts['other'] += 1

    return counts

@app.route('/')
def index():
    """Main page showing all devtools"""
    source_filter = request.args.get('source', '')
    per_page = min(max(int(request.args.get('per_page', 20)), 1), 100)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * per_page

    if source_filter:
        total_results = count_startups_by_source_key(source_filter)
        startups = get_startups_by_source_key(source_filter, limit=per_page, offset=offset)
    else:
        total_results = count_all_startups()
        startups = get_all_startups(limit=per_page, offset=offset)

    source_counts = get_source_counts()
    last_scrape_time = get_last_scrape_time()
    total_pages = max((total_results + per_page - 1) // per_page, 1)
    first_item = offset + 1 if startups else 0
    last_item = offset + len(startups)
    return render_template(
        'index.html',
        startups=startups,
        source_counts=source_counts,
        current_filter=source_filter,
        last_scrape_time=last_scrape_time,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_results=total_results,
        first_item=first_item,
        last_item=last_item,
    )

@app.route('/source/<source_name>')
def filter_by_source(source_name):
    """Filter tools by source"""
    source_map = {
        'github': 'GitHub Trending',
        'hackernews': 'Hacker News',
        'producthunt': 'Product Hunt',
    }
    per_page = min(max(int(request.args.get('per_page', 20)), 1), 100)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * per_page

    filtered_startups = get_startups_by_source_key(source_name, limit=per_page, offset=offset)
    source_display = source_map.get(source_name, 'All Sources')

    source_counts = get_source_counts()
    total_results = count_startups_by_source_key(source_name)
    last_scrape_time = get_last_scrape_time()
    total_pages = max((total_results + per_page - 1) // per_page, 1)
    first_item = offset + 1 if filtered_startups else 0
    last_item = offset + len(filtered_startups)
    return render_template(
        'index.html',
        startups=filtered_startups,
        source_counts=source_counts,
        current_filter=source_name,
        source_display=source_display,
        last_scrape_time=last_scrape_time,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_results=total_results,
        first_item=first_item,
        last_item=last_item,
    )

@app.route('/search')
def search():
    """Search page"""
    query = request.args.get('q', '')
    per_page = min(max(int(request.args.get('per_page', 20)), 1), 100)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * per_page

    if query:
        total_results = count_search_results(query)
        startups = search_startups(query, limit=per_page, offset=offset)
    else:
        total_results = 0
        startups = []
    source_counts = summarize_sources(startups)
    last_scrape_time = get_last_scrape_time()
    total_pages = max((total_results + per_page - 1) // per_page, 1) if total_results else 1
    first_item = offset + 1 if startups else 0
    last_item = offset + len(startups)
    return render_template(
        'search.html',
        startups=startups,
        query=query,
        source_counts=source_counts,
        last_scrape_time=last_scrape_time,
        total_results=total_results,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        first_item=first_item,
        last_item=last_item,
    )

@app.route('/tool/<int:tool_id>')
def tool_detail(tool_id):
    """Show detailed view of a specific tool"""
    tool = get_startup_by_id(tool_id)
    if not tool:
        return "Tool not found", 404

    if tool['source'] == 'GitHub Trending':
        related = get_startups_by_source_key('github')
    elif tool['source'] == 'Product Hunt':
        related = get_startups_by_source_key('producthunt')
    elif 'Hacker News' in tool['source'] or 'Show HN' in tool['source']:
        related = get_startups_by_source_key('hackernews')
    else:
        related = get_startups_by_sources('source = ?', [tool['source']])

    last_scrape_time = get_last_scrape_time()
    return render_template('tool_detail.html', tool=tool, startups=related, last_scrape_time=last_scrape_time)

@app.route('/api/startups')
def api_startups():
    """API endpoint for getting all startups"""
    per_page = min(max(int(request.args.get('per_page', 50)), 1), 200)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * per_page

    startups = get_all_startups(limit=per_page, offset=offset)
    total = count_all_startups()
    return jsonify({
        'items': startups,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': max((total + per_page - 1) // per_page, 1),
    })

@app.route('/api/search')
def api_search():
    """API endpoint for searching startups"""
    query = request.args.get('q', '')
    if query:
        startups = search_startups(query)
    else:
        startups = []
    return jsonify(startups)

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected'
    })

@app.template_filter('format_date')
def format_date(date_str):
    """Format date for display"""
    if isinstance(date_str, str):
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%B %d, %Y')
        except:
            return date_str
    return date_str

@app.template_filter('format_datetime')
def format_datetime(date_str):
    """Format datetime for display"""
    if isinstance(date_str, str):
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%B %d, %Y at %I:%M %p')
        except:
            return date_str
    return date_str

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Production settings
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')
    
    app.run(host=host, port=port, debug=False) 
