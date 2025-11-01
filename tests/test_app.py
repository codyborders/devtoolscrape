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
    def _paginate(data, limit, offset):
        start = offset or 0
        end = start + limit if limit is not None else None
        return data[start:end]

    monkeypatch.setattr(
        module,
        "get_all_startups",
        lambda limit=None, offset=None: _paginate(_sample_startups(), limit, offset),
    )

    def fake_get_startups_by_source_key(key, limit=None, offset=None):
        data = _sample_startups()
        if key == "github":
            data = [s for s in data if s["source"] == "GitHub Trending"]
        elif key == "hackernews":
            data = [s for s in data if "Hacker News" in s["source"]]
        elif key == "producthunt":
            data = [s for s in data if s["source"] == "Product Hunt"]
        return _paginate(data, limit, offset)

    monkeypatch.setattr(module, "get_startups_by_source_key", fake_get_startups_by_source_key)
    monkeypatch.setattr(module, "count_all_startups", lambda: len(_sample_startups()))
    monkeypatch.setattr(module, "count_startups_by_source_key", lambda key: len(fake_get_startups_by_source_key(key)))
    monkeypatch.setattr(
        module,
        "get_source_counts",
        lambda: {
            "total": len(_sample_startups()),
            "github": 1,
            "hackernews": 1,
            "producthunt": 1,
            "other": 1,
        },
    )
    monkeypatch.setattr(module, "get_last_scrape_time", lambda: "2024-01-04T00:00:00")

    client = module.app.test_client()

    assert client.get("/").status_code == 200
    assert client.get("/?source=github").status_code == 200
    assert client.get("/?source=hackernews").status_code == 200
    assert client.get("/?source=producthunt").status_code == 200

    assert module.get_startups_by_source_key("other") == _sample_startups()


def test_filter_by_source_route_variants(app_module, monkeypatch):
    module = app_module
    monkeypatch.setattr(module, "get_all_startups", lambda limit=None, offset=None: _sample_startups())
    monkeypatch.setattr(module, "get_startups_by_source_key", lambda key, limit=None, offset=None: _sample_startups())
    monkeypatch.setattr(module, "count_all_startups", lambda: len(_sample_startups()))
    monkeypatch.setattr(module, "count_startups_by_source_key", lambda key: len(_sample_startups()))
    monkeypatch.setattr(
        module,
        "get_source_counts",
        lambda: {
            "total": len(_sample_startups()),
            "github": 1,
            "hackernews": 1,
            "producthunt": 1,
            "other": 1,
        },
    )
    monkeypatch.setattr(module, "get_last_scrape_time", lambda: "2024-01-04T00:00:00")

    client = module.app.test_client()
    assert client.get("/source/github").status_code == 200
    assert client.get("/source/hackernews").status_code == 200
    assert client.get("/source/producthunt").status_code == 200
    assert client.get("/source/other").status_code == 200


def test_search_route_with_and_without_query(app_module, monkeypatch):
    module = app_module
    monkeypatch.setattr(module, "search_startups", lambda q, limit=20, offset=0: _sample_startups()[offset:offset + limit] if q else [])
    monkeypatch.setattr(module, "count_search_results", lambda q: len(_sample_startups()) if q else 0)
    monkeypatch.setattr(module, "count_startups_by_source_key", lambda key: len(_sample_startups()))
    monkeypatch.setattr(module, "count_all_startups", lambda: len(_sample_startups()))
    monkeypatch.setattr(module, "get_last_scrape_time", lambda: None)

    client = module.app.test_client()
    assert client.get("/search?q=dev").status_code == 200
    assert client.get("/search?q=dev&page=2").status_code == 200
    assert client.get("/search").status_code == 200


def test_tool_detail_routes(app_module, monkeypatch):
    module = app_module
    sample = _sample_startups()

    def fake_get_startup_by_id(tool_id):
        return next((s for s in sample if s["id"] == tool_id), None)

    def fake_get_startups_by_source_key(key):
        if key == "github":
            return [s for s in sample if s["source"] == "GitHub Trending"]
        if key == "producthunt":
            return [s for s in sample if s["source"] == "Product Hunt"]
        if key == "hackernews":
            return [s for s in sample if "Hacker News" in s["source"]]
        return sample

    captured = {}

    def fake_get_startups_by_sources(clause, params):
        captured["clause"] = clause
        captured["params"] = params
        return [s for s in sample if s["source"] not in ("GitHub Trending", "Product Hunt") and "Hacker News" not in s["source"]]

    monkeypatch.setattr(module, "get_startup_by_id", fake_get_startup_by_id)
    monkeypatch.setattr(module, "get_startups_by_source_key", fake_get_startups_by_source_key)
    monkeypatch.setattr(module, "get_startups_by_sources", fake_get_startups_by_sources)
    monkeypatch.setattr(module, "get_last_scrape_time", lambda: None)

    client = module.app.test_client()
    assert client.get("/tool/1").status_code == 200
    assert client.get("/tool/3").status_code == 200
    assert client.get("/tool/2").status_code == 200
    assert client.get("/tool/4").status_code == 200
    assert client.get("/tool/999").status_code == 404
    assert captured["clause"] == 'source = ?'
    assert captured["params"] == ["Indie Hackers"]
    assert module.get_startups_by_source_key("other") == sample


def test_api_endpoints(app_module, monkeypatch):
    module = app_module
    monkeypatch.setattr(module, "get_all_startups", lambda limit=None, offset=None: _sample_startups()[offset or 0:(offset or 0) + limit] if limit is not None else _sample_startups())
    monkeypatch.setattr(module, "count_all_startups", lambda: len(_sample_startups()))
    monkeypatch.setattr(module, "search_startups", lambda q, limit=20, offset=0: _sample_startups()[offset:offset + limit] if q else [])
    monkeypatch.setattr(module, "count_search_results", lambda q: len(_sample_startups()) if q else 0)

    client = module.app.test_client()
    payload = client.get("/api/startups").get_json()
    assert payload["total"] == len(_sample_startups())
    assert len(payload["items"]) == len(_sample_startups())
    page2 = client.get("/api/startups?page=2&per_page=2").get_json()
    assert page2["page"] == 2
    assert len(page2["items"]) == 2

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
