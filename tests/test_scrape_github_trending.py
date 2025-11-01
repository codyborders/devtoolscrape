import types

import pytest


class FakeResponse:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP error")


def test_scrape_github_trending_success(monkeypatch):
    import scrape_github_trending

    html = """
    <article class="Box-row">
        <h2 class="h3"><a href="/owner/devtool">Dev Tool</a></h2>
        <p>Developer CLI</p>
    </article>
    <article class="Box-row">
        <h2 class="h3"><a href="/owner/skiptool">Skip Tool</a></h2>
        <p>Fun social app</p>
    </article>
    """
    response = FakeResponse(content=html.encode("utf-8"))
    monkeypatch.setattr("scrape_github_trending.requests.get", lambda *args, **kwargs: response)

    saved = []
    monkeypatch.setattr(
        "scrape_github_trending.save_startup",
        lambda record: saved.append(record),
    )
    call_sequence = iter([True, False])
    monkeypatch.setattr(
        "scrape_github_trending.is_devtools_related_ai",
        lambda description, name: next(call_sequence),
    )
    monkeypatch.setattr(
        "scrape_github_trending.get_devtools_category",
        lambda description, name: "CLI Tool",
    )

    scrape_github_trending.scrape_github_trending()
    assert saved and saved[0]["description"].startswith("[CLI Tool]")


def test_scrape_github_trending_handles_request_error(monkeypatch):
    import scrape_github_trending
    from requests import RequestException

    monkeypatch.setattr(
        "scrape_github_trending.requests.get", lambda *args, **kwargs: (_ for _ in ()).throw(RequestException("fail"))
    )
    # No exception should bubble up
    scrape_github_trending.scrape_github_trending()


def test_scrape_github_trending_handles_parse_error(monkeypatch):
    import scrape_github_trending

    response = FakeResponse(content=b"<html></html>")
    monkeypatch.setattr("scrape_github_trending.requests.get", lambda *args, **kwargs: response)
    monkeypatch.setattr("bs4.BeautifulSoup", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("boom")))

    scrape_github_trending.scrape_github_trending()


def test_scrape_github_trending_main_guard(monkeypatch):
    import runpy

    monkeypatch.setattr("database.init_db", lambda: None)
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: FakeResponse(content=b"<article class='Box-row'></article>"))
    monkeypatch.setattr("ai_classifier.is_devtools_related_ai", lambda *args, **kwargs: False)
    monkeypatch.setattr("ai_classifier.get_devtools_category", lambda *args, **kwargs: None)
    monkeypatch.setattr("database.save_startup", lambda record: None)

    runpy.run_module("scrape_github_trending", run_name="__main__")


def test_scrape_github_trending_skips_missing_link(monkeypatch):
    import scrape_github_trending

    html = """
    <article class='Box-row'>
        <h2 class='h3'>Missing Link</h2>
    </article>
    """
    response = FakeResponse(content=html.encode("utf-8"))
    monkeypatch.setattr("scrape_github_trending.requests.get", lambda *args, **kwargs: response)

    monkeypatch.setattr("scrape_github_trending.is_devtools_related_ai", lambda *args, **kwargs: True)
    monkeypatch.setattr("scrape_github_trending.get_devtools_category", lambda *args, **kwargs: None)

    saved = []
    monkeypatch.setattr("scrape_github_trending.save_startup", lambda record: saved.append(record))

    scrape_github_trending.scrape_github_trending()
    assert saved == []


def test_fake_response_raises_on_error():
    response = FakeResponse(status_code=500)
    with pytest.raises(Exception):
        response.raise_for_status()
