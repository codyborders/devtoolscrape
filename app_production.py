from datetime import datetime
import os
import time
import uuid

from flask import Flask, render_template, request, jsonify, g
from dotenv import load_dotenv

from database import (
    get_all_startups,
    get_last_scrape_time,
    get_source_counts,
    get_startup_by_id,
    get_startups_by_source_key,
    get_startups_by_sources,
    get_related_startups,
    search_startups,
    count_search_results,
    count_all_startups,
    count_startups_by_source_key,
    init_db,
)

from logging_config import bind_context, get_logger, unbind_context




# Load environment variables
load_dotenv()

app = Flask(__name__)
logger = get_logger("devtools.app")

# Initialize database
init_db()

# Production configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['DEBUG'] = False


def _build_datadog_rum_config():
    application_id = os.getenv("DATADOG_RUM_APPLICATION_ID")
    client_token = os.getenv("DATADOG_RUM_CLIENT_TOKEN")
    if not application_id or not client_token:
        return None

    site = (
        os.getenv("DATADOG_RUM_SITE")
        or os.getenv("DATADOG_SITE")
        or os.getenv("DD_SITE")
        or "datadoghq.com"
    )
    region_map = {
        "datadoghq.com": "us1",
        "us3.datadoghq.com": "us3",
        "us5.datadoghq.com": "us5",
        "ap1.datadoghq.com": "ap1",
        "datadoghq.eu": "eu",
    }
    script_region = region_map.get(site, "us1")
    script_url = f"https://www.datadoghq-browser-agent.com/{script_region}/v5/datadog-rum.js"

    return {
        "applicationId": application_id,
        "clientToken": client_token,
        "site": site,
        "scriptUrl": script_url,
        "service": os.getenv("DATADOG_RUM_SERVICE", os.getenv("DD_SERVICE")),
        "env": os.getenv("DATADOG_RUM_ENV", os.getenv("DD_ENV")),
        "version": os.getenv("DATADOG_RUM_VERSION", os.getenv("DD_VERSION")),
        "sessionSampleRate": float(os.getenv("DATADOG_RUM_SESSION_SAMPLE_RATE", "100")),
        "sessionReplaySampleRate": float(os.getenv("DATADOG_RUM_SESSION_REPLAY_SAMPLE_RATE", "100")),
        "profilingSampleRate": float(os.getenv("DATADOG_RUM_PROFILING_SAMPLE_RATE", "100")),
        "trackResources": os.getenv("DATADOG_RUM_TRACK_RESOURCES", "true").lower() == "true",
        "trackLongTasks": os.getenv("DATADOG_RUM_TRACK_LONG_TASKS", "true").lower() == "true",
        "trackUserInteractions": os.getenv("DATADOG_RUM_TRACK_USER_INTERACTIONS", "true").lower() == "true",
    }


app.config["DATADOG_RUM_CONFIG"] = _build_datadog_rum_config()

@app.context_processor
def inject_datadog_rum_config():
    return {"datadog_rum_config": app.config.get("DATADOG_RUM_CONFIG")}

if not app.debug:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

@app.before_request
def _start_request_logging():
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    g.request_id = request_id
    g.request_start_time = time.perf_counter()
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    bind_context(
        request_id=request_id,
        http_method=request.method,
        http_path=request.path,
        client_ip=client_ip,
    )
    logger.debug(
        "request.start",
        extra={
            "event": "request.start",
            "http_method": request.method,
            "http_path": request.path,
            "client_ip": client_ip,
        },
    )


@app.after_request
def _complete_request_logging(response):
    duration_ms = None
    if hasattr(g, "request_start_time"):
        duration_ms = round((time.perf_counter() - g.request_start_time) * 1000, 2)
    logger.info(
        "request.complete",
        extra={
            "event": "request.complete",
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "content_length": response.calculate_content_length(),
        },
    )
    return response


@app.teardown_request
def _teardown_request_logging(exc):
    if exc is not None:
        logger.exception(
            "request.error",
            extra={
                "event": "request.error",
                "error_type": exc.__class__.__name__,
            },
        )
    unbind_context("request_id", "http_method", "http_path", "client_ip")

def summarize_sources(startups):
    logger.debug(
        "summarize.sources",
        extra={"event": "summarize.sources", "startup_count": len(startups)},
    )
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
    response = render_template(
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
    logger.info(
        "render.index",
        extra={
            "event": "render.index",
            "source_filter": source_filter or "all",
            "page": page,
            "per_page": per_page,
            "returned": len(startups),
            "total_results": total_results,
        },
    )
    return response

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
    response = render_template(
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
    logger.info(
        "render.source",
        extra={
            "event": "render.source",
            "source": source_name,
            "page": page,
            "per_page": per_page,
            "returned": len(filtered_startups),
            "total_results": total_results,
        },
    )
    return response

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
    response = render_template(
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
    logger.info(
        "render.search",
        extra={
            "event": "render.search",
            "query": query,
            "page": page,
            "per_page": per_page,
            "returned": len(startups),
            "total_results": total_results,
        },
    )
    return response

@app.route('/tool/<int:tool_id>')
def tool_detail(tool_id):
    """Show detailed view of a specific tool"""
    tool = get_startup_by_id(tool_id)
    if not tool:
        logger.warning(
            "render.tool_missing",
            extra={"event": "render.tool_missing", "tool_id": tool_id},
        )
        return "Tool not found", 404

    related = get_related_startups(tool['source'], tool['id'], limit=4)

    last_scrape_time = get_last_scrape_time()
    logger.info(
        "render.tool_detail",
        extra={
            "event": "render.tool_detail",
            "tool_id": tool_id,
            "source": tool.get("source"),
            "related_count": len(related),
        },
    )
    return render_template('tool_detail.html', tool=tool, startups=related, last_scrape_time=last_scrape_time)

@app.route('/api/startups')
def api_startups():
    """API endpoint for getting all startups"""
    per_page = min(max(int(request.args.get('per_page', 50)), 1), 200)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * per_page

    startups = get_all_startups(limit=per_page, offset=offset)
    total = count_all_startups()
    payload = {
        'items': startups,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': max((total + per_page - 1) // per_page, 1),
    }
    logger.info(
        "api.startups",
        extra={
            "event": "api.startups",
            "page": page,
            "per_page": per_page,
            "returned": len(startups),
            "total": total,
        },
    )
    return jsonify(payload)

@app.route('/api/search')
def api_search():
    """API endpoint for searching startups"""
    query = request.args.get('q', '')
    per_page = min(max(int(request.args.get('per_page', 20)), 1), 200)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * per_page

    if query:
        total = count_search_results(query)
        startups = search_startups(query, limit=per_page, offset=offset)
    else:
        total = 0
        startups = []

    payload = {
        'items': startups,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': max((total + per_page - 1) // per_page, 1) if total else 1,
    }
    logger.info(
        "api.search",
        extra={
            "event": "api.search",
            "query": query,
            "page": page,
            "per_page": per_page,
            "returned": len(startups),
            "total": total,
        },
    )
    return jsonify(payload)

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    logger.debug("health_check", extra={"event": "health_check"})
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
    logger.warning("http.404", extra={"event": "http.404"})
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.exception("http.500", extra={"event": "http.500"})
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Production settings
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')
    
    app.run(host=host, port=port, debug=False) 
