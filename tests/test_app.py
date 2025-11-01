import importlib
import sys
from datetime import datetime

import pytest


@pytest.fixture
def app_module(monkeypatch):
    import database

    monkeypatch.setattr(database, "init_db", lambda: None)
    sys.modules.pop("app_production", None)
    module = importlib.import_module("app_production")
    return module


def _sample_startups():
    return [
        {"id": 1, "name": "GitHub Tool", "url": "https://github.com/tool", "description": "For devs", "source": "GitHub Trending", "date_found": "2024-01-01T00:00:00"},
        {"id": 2, "name": "HN Tool", "url": "https://hn.tool", "description": "For devs", "source": "Hacker News (score: 10)", "date_found": "2024-01-02T00:00:00"},
        {"id": 3, "name": "Product Hunt Tool", "url": "https://ph.tool", "description": "For devs", "source": "Product Hunt", "date_found": "2024-01-03T00:00:00"},
        {"id": 4, "name": "Other Tool", "url": "https://other.tool", "description": "Misc", "source": "Indie Hackers", "date_found": "2024-01-04T00:00:00"},
    ]


def test_index_route_filters_sources(app_module, monkeypatch):
    module = app_module
    monkeypatch.setattr(module, "get_all_startups", _sample_startups)
    monkeypatch.setattr(module, "get_last_scrape_time", lambda: "2024-01-04T00:00:00")

    client = module.app.test_client()

    assert client.get("/").status_code == 200
    assert client.get("/?source=github").status_code == 200
    assert client.get("/?source=hackernews").status_code == 200
    assert client.get("/?source=producthunt").status_code == 200


def test_filter_by_source_route_variants(app_module, monkeypatch):
    module = app_module
    monkeypatch.setattr(module, "get_all_startups", _sample_startups)
    monkeypatch.setattr(module, "get_last_scrape_time", lambda: "2024-01-04T00:00:00")

    client = module.app.test_client()
    assert client.get("/source/github").status_code == 200
    assert client.get("/source/hackernews").status_code == 200
    assert client.get("/source/producthunt").status_code == 200
    assert client.get("/source/other").status_code == 200


def test_search_route_with_and_without_query(app_module, monkeypatch):
    module = app_module
    monkeypatch.setattr(module, "search_startups", lambda q: _sample_startups() if q else [])
    monkeypatch.setattr(module, "get_last_scrape_time", lambda: None)

    client = module.app.test_client()
    assert client.get("/search?q=dev").status_code == 200
    assert client.get("/search").status_code == 200


def test_tool_detail_routes(app_module, monkeypatch):
    module = app_module
    monkeypatch.setattr(module, "get_all_startups", _sample_startups)
    monkeypatch.setattr(module, "get_last_scrape_time", lambda: None)

    client = module.app.test_client()
    assert client.get("/tool/1").status_code == 200
    assert client.get("/tool/999").status_code == 404


def test_api_endpoints(app_module, monkeypatch):
    module = app_module
    monkeypatch.setattr(module, "get_all_startups", _sample_startups)
    monkeypatch.setattr(module, "search_startups", lambda q: _sample_startups() if q else [])

    client = module.app.test_client()
    startups = client.get("/api/startups").get_json()
    assert isinstance(startups, list)

    assert client.get("/api/search?q=dev").status_code == 200
    assert client.get("/api/search").get_json() == []


def test_health_and_error_handlers(app_module, monkeypatch):
    module = app_module
    with module.app.app_context():
        response = module.health_check()
        assert response.get_json()["status"] == "healthy"

    client = module.app.test_client()
    assert client.get("/nonexistent").status_code == 404

    with module.app.app_context():
        rendered, status = module.internal_error(Exception("boom"))
        assert status == 500


def test_template_filters(app_module):
    module = app_module
    formatted = module.format_date("2024-01-05T00:00:00")
    assert "January" in formatted
    assert module.format_date("invalid-date") == "invalid-date"
    assert module.format_date(123) == 123

    dt_formatted = module.format_datetime("2024-01-05T12:30:00")
    assert "12:30 PM" in dt_formatted
    assert module.format_datetime("invalid-date") == "invalid-date"
    assert module.format_datetime(123) == 123


def test_app_main_guard(monkeypatch):
    import runpy

    monkeypatch.setattr("database.init_db", lambda: None)
    monkeypatch.setattr("flask.app.Flask.run", lambda self, *args, **kwargs: None, raising=False)

    runpy.run_module("app_production", run_name="__main__")
