from flask import Flask, render_template, request, jsonify
from database import get_all_startups, search_startups, get_startup_by_url, get_last_scrape_time
from datetime import datetime
import sqlite3
import os
from dotenv import load_dotenv




# Load environment variables
load_dotenv()

app = Flask(__name__)

# Production configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['DEBUG'] = False

if not app.debug:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

def get_source_counts(startups):
    """Calculate counts for each source"""
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
    startups = get_all_startups()
    
    # Filter by source if specified
    if source_filter:
        if source_filter == 'github':
            startups = [s for s in startups if s['source'] == 'GitHub Trending']
        elif source_filter == 'hackernews':
            startups = [s for s in startups if 'Hacker News' in s['source']]
        elif source_filter == 'producthunt':
            startups = [s for s in startups if s['source'] == 'Product Hunt']
    
    source_counts = get_source_counts(get_all_startups())  # Always show total counts
    last_scrape_time = get_last_scrape_time()
    return render_template('index.html', startups=startups, source_counts=source_counts, current_filter=source_filter, last_scrape_time=last_scrape_time)

@app.route('/source/<source_name>')
def filter_by_source(source_name):
    """Filter tools by source"""
    startups = get_all_startups()
    
    # Filter by source
    if source_name == 'github':
        filtered_startups = [s for s in startups if s['source'] == 'GitHub Trending']
        source_display = 'GitHub Trending'
    elif source_name == 'hackernews':
        filtered_startups = [s for s in startups if 'Hacker News' in s['source']]
        source_display = 'Hacker News'
    elif source_name == 'producthunt':
        filtered_startups = [s for s in startups if s['source'] == 'Product Hunt']
        source_display = 'Product Hunt'
    else:
        filtered_startups = startups
        source_display = 'All Sources'
    
    source_counts = get_source_counts(get_all_startups())
    last_scrape_time = get_last_scrape_time()
    return render_template('index.html', startups=filtered_startups, source_counts=source_counts, 
                         current_filter=source_name, source_display=source_display, last_scrape_time=last_scrape_time)

@app.route('/search')
def search():
    """Search page"""
    query = request.args.get('q', '')
    if query:
        startups = search_startups(query)
    else:
        startups = []
    source_counts = get_source_counts(startups)
    last_scrape_time = get_last_scrape_time()
    return render_template('search.html', startups=startups, query=query, source_counts=source_counts, last_scrape_time=last_scrape_time)

@app.route('/tool/<int:tool_id>')
def tool_detail(tool_id):
    """Show detailed view of a specific tool"""
    # Get all startups and find the one with matching ID
    startups = get_all_startups()
    tool = None
    for startup in startups:
        if startup['id'] == tool_id:
            tool = startup
            break
    
    if not tool:
        return "Tool not found", 404
    
    last_scrape_time = get_last_scrape_time()
    return render_template('tool_detail.html', tool=tool, startups=startups, last_scrape_time=last_scrape_time)

@app.route('/api/startups')
def api_startups():
    """API endpoint for getting all startups"""
    startups = get_all_startups()
    return jsonify(startups)

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
