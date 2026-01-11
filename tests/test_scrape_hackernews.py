from datetime import datetime
from typing import Any, Dict, List, Tuple, Union
from unittest.mock import MagicMock, call

import pytest


# Expected timeout tuple: (connection_timeout, read_timeout)
EXPECTED_TIMEOUT = (5, 10)


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

    def fake_classify(candidates):
        mapping = {}
        for item in candidates:
            mapping[item["id"]] = item["name"] in {"Devtool Launch", "Categoryless Tool"}
        return mapping

    monkeypatch.setattr("scrape_hackernews.classify_candidates", fake_classify)
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

    def fake_classify(candidates):
        mapping = {}
        for item in candidates:
            mapping[item["id"]] = item["name"] in {"Show HN: Dev CLI", "Show HN: Dev Notes"}
        return mapping

    monkeypatch.setattr("scrape_hackernews.classify_candidates", fake_classify)

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


class TestRequestTimeouts:
    """Test suite for verifying correct timeout configuration on HTTP requests.

    The scraper should use a tuple timeout (connection_timeout, read_timeout)
    to prevent SSL handshake hangs while allowing adequate time for data transfer.
    """

    @pytest.fixture
    def mock_requests_get(self, monkeypatch) -> MagicMock:
        """Create a mock for requests.get that tracks all calls."""
        mock = MagicMock()
        mock.return_value = FakeJSONResponse([])
        mock.return_value.raise_for_status = MagicMock()
        monkeypatch.setattr("scrape_hackernews.requests.get", mock)
        return mock

    @pytest.fixture
    def stub_dependencies(self, monkeypatch) -> None:
        """Stub out classifier and database dependencies."""
        monkeypatch.setattr("scrape_hackernews.classify_candidates", lambda c: {})
        monkeypatch.setattr("scrape_hackernews.get_devtools_category", lambda t, n: None)
        monkeypatch.setattr("scrape_hackernews.save_startup", lambda r: None)

    def test_topstories_request_uses_tuple_timeout(
        self, monkeypatch, mock_requests_get, stub_dependencies
    ) -> None:
        """Verify topstories endpoint uses (connection, read) timeout tuple."""
        import scrape_hackernews

        scrape_hackernews.scrape_hackernews()

        # Find the call to topstories.json
        topstories_calls = [
            c for c in mock_requests_get.call_args_list
            if "topstories.json" in str(c)
        ]
        assert len(topstories_calls) == 1, "Expected exactly one topstories request"

        _, kwargs = topstories_calls[0]
        assert kwargs.get("timeout") == EXPECTED_TIMEOUT, (
            f"topstories request should use timeout={EXPECTED_TIMEOUT}, "
            f"got timeout={kwargs.get('timeout')}"
        )

    def test_story_requests_use_tuple_timeout(
        self, monkeypatch, mock_requests_get, stub_dependencies
    ) -> None:
        """Verify individual story requests use (connection, read) timeout tuple."""
        import scrape_hackernews

        # Return some story IDs so we make story requests
        story_ids = [101, 102, 103]
        story_data = {
            "type": "story",
            "title": "Test Story",
            "url": "https://example.com",
            "text": "",
            "score": 100,
            "time": datetime.now().timestamp(),
        }

        def mock_get(url: str, timeout: Tuple[int, int]) -> FakeJSONResponse:
            if "topstories.json" in url:
                return FakeJSONResponse(story_ids)
            return FakeJSONResponse(story_data)

        mock_requests_get.side_effect = mock_get

        scrape_hackernews.scrape_hackernews()

        # Check all story item requests
        story_calls = [
            c for c in mock_requests_get.call_args_list
            if "/item/" in str(c)
        ]
        assert len(story_calls) == len(story_ids), (
            f"Expected {len(story_ids)} story requests, got {len(story_calls)}"
        )

        for story_call in story_calls:
            _, kwargs = story_call
            assert kwargs.get("timeout") == EXPECTED_TIMEOUT, (
                f"Story request should use timeout={EXPECTED_TIMEOUT}, "
                f"got timeout={kwargs.get('timeout')}"
            )

    def test_showstories_request_uses_tuple_timeout(
        self, monkeypatch, mock_requests_get, stub_dependencies
    ) -> None:
        """Verify showstories endpoint uses (connection, read) timeout tuple."""
        import scrape_hackernews

        scrape_hackernews.scrape_hackernews_show()

        # Find the call to showstories.json
        showstories_calls = [
            c for c in mock_requests_get.call_args_list
            if "showstories.json" in str(c)
        ]
        assert len(showstories_calls) == 1, "Expected exactly one showstories request"

        _, kwargs = showstories_calls[0]
        assert kwargs.get("timeout") == EXPECTED_TIMEOUT, (
            f"showstories request should use timeout={EXPECTED_TIMEOUT}, "
            f"got timeout={kwargs.get('timeout')}"
        )

    def test_show_hn_story_requests_use_tuple_timeout(
        self, monkeypatch, mock_requests_get, stub_dependencies
    ) -> None:
        """Verify Show HN story requests use (connection, read) timeout tuple."""
        import scrape_hackernews

        # Return some story IDs so we make story requests
        story_ids = [201, 202]
        story_data = {
            "type": "story",
            "title": "Show HN: Test",
            "url": "https://show.example.com",
            "text": "Description",
            "score": 50,
            "time": datetime.now().timestamp(),
        }

        def mock_get(url: str, timeout: Tuple[int, int]) -> FakeJSONResponse:
            if "showstories.json" in url:
                return FakeJSONResponse(story_ids)
            return FakeJSONResponse(story_data)

        mock_requests_get.side_effect = mock_get

        scrape_hackernews.scrape_hackernews_show()

        # Check all story item requests
        story_calls = [
            c for c in mock_requests_get.call_args_list
            if "/item/" in str(c)
        ]
        assert len(story_calls) == len(story_ids), (
            f"Expected {len(story_ids)} story requests, got {len(story_calls)}"
        )

        for story_call in story_calls:
            _, kwargs = story_call
            assert kwargs.get("timeout") == EXPECTED_TIMEOUT, (
                f"Show HN story request should use timeout={EXPECTED_TIMEOUT}, "
                f"got timeout={kwargs.get('timeout')}"
            )

    def test_timeout_is_tuple_not_single_value(
        self, monkeypatch, mock_requests_get, stub_dependencies
    ) -> None:
        """Verify timeout is a tuple, not a single integer value.

        A tuple timeout separates connection timeout from read timeout,
        which helps prevent SSL handshake hangs while allowing adequate
        time for data transfer.
        """
        import scrape_hackernews

        scrape_hackernews.scrape_hackernews()

        for call_args in mock_requests_get.call_args_list:
            _, kwargs = call_args
            timeout = kwargs.get("timeout")
            assert isinstance(timeout, tuple), (
                f"Timeout should be a tuple (connection, read), got {type(timeout).__name__}: {timeout}"
            )
            assert len(timeout) == 2, (
                f"Timeout tuple should have 2 elements (connection, read), got {len(timeout)}"
            )

    def test_connection_timeout_less_than_read_timeout(
        self, monkeypatch, mock_requests_get, stub_dependencies
    ) -> None:
        """Verify connection timeout is shorter than read timeout.

        Connection timeout should be shorter since establishing a connection
        should be fast. Read timeout can be longer to allow for slow responses.
        """
        import scrape_hackernews

        scrape_hackernews.scrape_hackernews()

        for call_args in mock_requests_get.call_args_list:
            _, kwargs = call_args
            timeout = kwargs.get("timeout")
            connection_timeout, read_timeout = timeout
            assert connection_timeout < read_timeout, (
                f"Connection timeout ({connection_timeout}s) should be less than "
                f"read timeout ({read_timeout}s)"
            )
