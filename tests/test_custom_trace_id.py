"""Tests for custom W3C trace ID generation and root span replacement.

Verifies that:
- generate_trace_id_w3c() produces valid 128-bit hex trace IDs
- replace_root_span_trace_id() correctly swaps IDs and tags the original
- The Flask before_request hook respects the CUSTOM_TRACE_ID_ENABLED flag
"""

import importlib
import re
import sys

import pytest
from unittest.mock import MagicMock, patch

from observability import generate_trace_id_w3c, replace_root_span_trace_id


# ---------------------------------------------------------------------------
# Unit tests: generate_trace_id_w3c
# ---------------------------------------------------------------------------

_W3C_HEX_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def test_generate_trace_id_w3c_format():
    """Generated trace IDs must be exactly 32 lowercase hex characters, and
    each call must produce a unique value (statistical sanity check)."""
    sample_count = 10
    ids = set()

    for _ in range(sample_count):
        trace_id = generate_trace_id_w3c()
        assert _W3C_HEX_PATTERN.match(trace_id), (
            f"Trace ID '{trace_id}' is not 32 lowercase hex chars"
        )
        ids.add(trace_id)

    assert len(ids) == sample_count, (
        f"Expected {sample_count} unique IDs, got {len(ids)} -- possible RNG issue"
    )


def test_generate_trace_id_w3c_not_all_zeros():
    """W3C spec forbids all-zero trace IDs. Verify over many samples."""
    for _ in range(100):
        trace_id = generate_trace_id_w3c()
        assert trace_id != "0" * 32, "Generated all-zero trace ID"


# ---------------------------------------------------------------------------
# Unit tests: replace_root_span_trace_id
# ---------------------------------------------------------------------------

def _make_mock_span(trace_id: int = 99999):
    """Build a mock span with a mutable trace_id and recording set_tag."""
    span = MagicMock()
    span.trace_id = trace_id
    return span


def _make_mock_tracer(root_span=None):
    """Build a mock tracer whose current_root_span() returns the given span."""
    mock_tracer = MagicMock()
    mock_tracer.current_root_span.return_value = root_span
    return mock_tracer


def test_replace_root_span_succeeds():
    """When a root span exists, the trace ID should be replaced and the
    original stored as a tag."""
    original_id = 12345
    custom_hex = "aabbccdd" * 4  # 32 hex chars
    expected_new_id = int(custom_hex, 16)

    span = _make_mock_span(trace_id=original_id)
    mock_tracer = _make_mock_tracer(root_span=span)

    with patch("observability.tracer", mock_tracer):
        result = replace_root_span_trace_id(custom_hex)

    assert result == original_id
    span.set_tag.assert_called_once_with("original.trace_id", str(original_id))
    assert span.trace_id == expected_new_id


def test_replace_root_span_no_tracer():
    """When tracer is None (ddtrace not installed), return None gracefully."""
    with patch("observability.tracer", None):
        result = replace_root_span_trace_id("aa" * 16)

    assert result is None


def test_replace_root_span_no_root_span():
    """When current_root_span() returns None, return None gracefully."""
    mock_tracer = _make_mock_tracer(root_span=None)

    with patch("observability.tracer", mock_tracer):
        result = replace_root_span_trace_id("bb" * 16)

    assert result is None
    mock_tracer.current_root_span.assert_called_once()


def test_replace_root_span_validates_input():
    """Bad inputs must raise AssertionError, not silently corrupt spans."""
    # Wrong length (16 chars instead of 32).
    with pytest.raises(AssertionError, match="32 hex chars"):
        replace_root_span_trace_id("aabb" * 4)

    # Non-string input.
    with pytest.raises(AssertionError, match="must be str"):
        replace_root_span_trace_id(12345)


# ---------------------------------------------------------------------------
# Integration tests: Flask before_request hook
# ---------------------------------------------------------------------------

@pytest.fixture
def app_module(monkeypatch):
    """Import app_production with database init stubbed out."""
    import database

    monkeypatch.setattr(database, "init_db", lambda: None)
    sys.modules.pop("app_production", None)
    module = importlib.import_module("app_production")
    return module


def _stub_db(module, monkeypatch):
    """Wire minimal stubs so routes render without a real database."""
    sample = [
        {
            "id": 1,
            "name": "Test Tool",
            "url": "https://example.com",
            "description": "Test",
            "source": "GitHub Trending",
            "date_found": "2024-01-01T00:00:00",
        }
    ]
    monkeypatch.setattr(module, "get_all_startups", lambda limit=None, offset=None: sample)
    monkeypatch.setattr(module, "count_all_startups", lambda: 1)
    monkeypatch.setattr(
        module,
        "get_source_counts",
        lambda: {"total": 1, "github": 1, "hackernews": 0, "producthunt": 0, "other": 0},
    )
    monkeypatch.setattr(module, "get_last_scrape_time", lambda: "2024-01-01T00:00:00")


def test_before_request_applies_custom_trace_id_when_enabled(app_module, monkeypatch):
    """With the flag on and a root span available, the span's trace_id should
    be replaced and the original tagged."""
    module = app_module
    _stub_db(module, monkeypatch)

    monkeypatch.setattr(module, "_CUSTOM_TRACE_ID_ENABLED", True)

    original_id = 77777
    span = _make_mock_span(trace_id=original_id)
    mock_tracer = _make_mock_tracer(root_span=span)
    monkeypatch.setattr("observability.tracer", mock_tracer)

    client = module.app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    # The span's trace_id should have been changed from the original.
    assert span.trace_id != original_id
    span.set_tag.assert_called_once_with("original.trace_id", str(original_id))


def test_before_request_skips_when_disabled(app_module, monkeypatch):
    """With the flag off, replace_root_span_trace_id should never be called."""
    module = app_module
    _stub_db(module, monkeypatch)

    monkeypatch.setattr(module, "_CUSTOM_TRACE_ID_ENABLED", False)

    mock_tracer = _make_mock_tracer()
    monkeypatch.setattr("observability.tracer", mock_tracer)

    client = module.app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    # current_root_span should never be called when the flag is off.
    mock_tracer.current_root_span.assert_not_called()


def test_before_request_handles_missing_root_span(app_module, monkeypatch):
    """With the flag on but no root span, the request must still complete
    without errors."""
    module = app_module
    _stub_db(module, monkeypatch)

    monkeypatch.setattr(module, "_CUSTOM_TRACE_ID_ENABLED", True)

    mock_tracer = _make_mock_tracer(root_span=None)
    monkeypatch.setattr("observability.tracer", mock_tracer)

    client = module.app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    mock_tracer.current_root_span.assert_called_once()
