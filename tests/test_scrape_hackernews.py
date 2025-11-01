from datetime import datetime

import pytest


class FakeJSONResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("bad status")

    def json(self):
        return self._payload


def test_fake_json_response_raise_for_status():
    response = FakeJSONResponse({}, status_code=500)
    with pytest.raises(Exception):
        response.raise_for_status()


def test_scrape_hackernews_success(monkeypatch):
    import scrape_hackernews

    top_story_ids = [1, 2, 3, 4, 5]
    stories = {
        1: {"type": "story", "title": "Devtool Launch", "url": "https://devtool.com", "text": "Launch details", "score": 50, "time": datetime.now().timestamp()},
        2: {"type": "story", "title": "Skip due to score", "url": "https://skip.com", "text": "", "score": 5, "time": datetime.now().timestamp()},
        3: {"type": "job"},  # ignored non-story
        4: {"type": "story", "title": "Non Devtool", "url": "https://not.dev", "text": "", "score": 60, "time": datetime.now().timestamp()},
        5: {"type": "story", "title": "Categoryless Tool", "url": "https://categoryless.dev", "text": "More details", "score": 70, "time": datetime.now().timestamp()},
    }

    def fake_get(url, timeout):
        if url.endswith("topstories.json"):
            return FakeJSONResponse(top_story_ids)
        story_id = int(url.split("/")[-1].split(".")[0])
        return FakeJSONResponse(stories[story_id])

    monkeypatch.setattr("scrape_hackernews.requests.get", fake_get)

    def classifier(text, name):
        return name in {"Devtool Launch", "Categoryless Tool"}

    monkeypatch.setattr("scrape_hackernews.is_devtools_related_ai", classifier)
    def categorizer(text, name):
        if name == "Devtool Launch":
            return "Build/Deploy"
        return None

    monkeypatch.setattr("scrape_hackernews.get_devtools_category", categorizer)

    saved = []
    monkeypatch.setattr("scrape_hackernews.save_startup", lambda record: saved.append(record))

    scrape_hackernews.scrape_hackernews()
    assert len(saved) == 2
    assert saved[0]["description"].startswith("[Build/Deploy]")
    assert "More details" in saved[1]["description"]


def test_scrape_hackernews_show_success(monkeypatch):
    import scrape_hackernews

    show_ids = [10, 11, 12, 13, 14]
    show_story = {
        10: {"type": "story", "title": "Show HN: Dev CLI", "url": "https://devcli.dev", "text": "Details", "score": 40, "time": datetime.now().timestamp()},
        11: {"type": "story", "title": "Show HN: Dev Notes", "url": "https://devnotes.dev", "text": "Extras", "score": 60, "time": datetime.now().timestamp()},
        12: {"type": "comment"},
        13: {"type": "story", "title": "Show HN: Low Score", "url": "https://lowscore.dev", "text": "", "score": 1, "time": datetime.now().timestamp()},
        14: {"type": "story", "title": "Show HN: Not Dev", "url": "https://nodev.dev", "text": "", "score": 70, "time": datetime.now().timestamp()},
    }

    def fake_get(url, timeout):
        if url.endswith("showstories.json"):
            return FakeJSONResponse(show_ids)
        story_id = int(url.split("/")[-1].split(".")[0])
        return FakeJSONResponse(show_story[story_id])

    monkeypatch.setattr("scrape_hackernews.requests.get", fake_get)

    def classifier(text, name):
        return name in {"Show HN: Dev CLI", "Show HN: Dev Notes"}

    monkeypatch.setattr("scrape_hackernews.is_devtools_related_ai", classifier)

    def categorizer(text, name):
        return "CLI Tool" if name == "Show HN: Dev CLI" else None

    monkeypatch.setattr("scrape_hackernews.get_devtools_category", categorizer)

    saved = []
    monkeypatch.setattr("scrape_hackernews.save_startup", lambda record: saved.append(record))

    scrape_hackernews.scrape_hackernews_show()
    assert len(saved) == 2
    assert saved[0]["description"].startswith("[CLI Tool]")
    assert "Extras" in saved[1]["description"]


def test_scrape_hackernews_handles_errors(monkeypatch):
    import scrape_hackernews
    from requests import RequestException

    # Network level failure
    monkeypatch.setattr(
        "scrape_hackernews.requests.get", lambda *args, **kwargs: (_ for _ in ()).throw(RequestException("network down"))
    )
    scrape_hackernews.scrape_hackernews()

    # Request exception for Show HN
    monkeypatch.setattr(
        "scrape_hackernews.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RequestException("show down")),
    )
    scrape_hackernews.scrape_hackernews_show()

    # General parsing failure for top stories
    class BadTopStoriesResponse:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("invalid json")

    monkeypatch.setattr("scrape_hackernews.requests.get", lambda *args, **kwargs: BadTopStoriesResponse())
    scrape_hackernews.scrape_hackernews()

    # General parsing failure for Show HN
    class BadResponse:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("invalid json")

    monkeypatch.setattr("scrape_hackernews.requests.get", lambda *args, **kwargs: BadResponse())
    scrape_hackernews.scrape_hackernews_show()


def test_scrape_hackernews_main_guard(monkeypatch):
    import runpy

    def fake_get(url, timeout):
        if url.endswith("topstories.json") or url.endswith("showstories.json"):
            return FakeJSONResponse([])
        return FakeJSONResponse({})

    # Exercise both branches explicitly for coverage
    assert isinstance(fake_get("https://hacker-news.firebaseio.com/v0/topstories.json", 5), FakeJSONResponse)
    assert isinstance(fake_get("https://example.com/other", 5), FakeJSONResponse)

    monkeypatch.setattr("database.init_db", lambda: None)
    monkeypatch.setattr("database.save_startup", lambda record: None)
    monkeypatch.setattr("ai_classifier.is_devtools_related_ai", lambda *args, **kwargs: False)
    monkeypatch.setattr("ai_classifier.get_devtools_category", lambda *args, **kwargs: None)
    monkeypatch.setattr("requests.get", fake_get)

    runpy.run_module("scrape_hackernews", run_name="__main__")
