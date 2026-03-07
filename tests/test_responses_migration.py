"""Tests that ai_classifier uses the OpenAI Responses API.

These tests verify:
1. _call_openai uses client.responses.create (not chat.completions)
2. Parameters are translated: input, max_output_tokens, text.format
3. Response parsing uses output_text (not choices[0].message.content)
"""

import importlib
import json
import types

import pytest


def test_call_openai_uses_responses_create(reset_ai_classifier):
    """Verify _call_openai calls client.responses.create."""
    classifier = reset_ai_classifier
    captured = {}

    def fake_create(*args, **kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(output_text="yes")

    classifier.client.responses.create = fake_create

    response = classifier._call_openai(
        [{"role": "user", "content": "test"}],
        max_tokens=5,
    )

    assert response.output_text == "yes"
    assert "input" in captured, "Should pass 'input' param, not 'messages'"
    assert "max_output_tokens" in captured, "Should pass 'max_output_tokens', not 'max_tokens'"


def test_call_openai_translates_response_format_to_text(reset_ai_classifier):
    """Verify response_format is translated to text.format for Responses API."""
    classifier = reset_ai_classifier
    captured = {}

    def fake_create(*args, **kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(output_text='{"results": {}}')

    classifier.client.responses.create = fake_create

    classifier._call_openai(
        [{"role": "user", "content": "test"}],
        max_tokens=50,
        response_format={"type": "json_object"},
    )

    assert "text" in captured, "Should pass 'text' param for JSON format"
    assert captured["text"] == {"format": {"type": "json_object"}}
    assert "response_format" not in captured, "Should not pass legacy 'response_format'"


def test_call_openai_omits_text_when_no_format(reset_ai_classifier):
    """Verify text param is omitted when no response_format is requested."""
    classifier = reset_ai_classifier
    captured = {}

    def fake_create(*args, **kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(output_text="yes")

    classifier.client.responses.create = fake_create

    classifier._call_openai(
        [{"role": "user", "content": "test"}],
        max_tokens=5,
    )

    assert "text" not in captured, "Should not pass 'text' when no format requested"


def test_classify_single_parses_output_text(reset_ai_classifier, monkeypatch):
    """Verify _classify_single reads response.output_text."""
    classifier = reset_ai_classifier
    monkeypatch.setenv("OPENAI_API_KEY", "present")

    def fake_create(*args, **kwargs):
        return types.SimpleNamespace(output_text="yes")

    classifier.client.responses.create = fake_create
    assert classifier._classify_single("DevCLI", "developer CLI tool") is True


def test_get_devtools_category_parses_output_text(reset_ai_classifier, monkeypatch):
    """Verify get_devtools_category reads response.output_text."""
    classifier = reset_ai_classifier
    monkeypatch.setenv("OPENAI_API_KEY", "present")

    def fake_create(*args, **kwargs):
        return types.SimpleNamespace(output_text="CLI Tool")

    classifier.client.responses.create = fake_create
    assert classifier.get_devtools_category("CLI utilities", "Tooler") == "CLI Tool"


def test_batch_classify_parses_output_text(monkeypatch):
    """Verify classify_candidates batch path reads response.output_text."""
    monkeypatch.setenv("AI_CLASSIFIER_DISABLE_CACHE", "1")
    monkeypatch.setenv("AI_CLASSIFIER_DISABLE_BATCH", "0")
    monkeypatch.setenv("AI_CLASSIFIER_BATCH_SIZE", "8")
    monkeypatch.setenv("AI_CLASSIFIER_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "present")

    import ai_classifier

    importlib.reload(ai_classifier)

    def fake_create(*args, **kwargs):
        result = {"results": {"a": "yes", "b": "no"}}
        return types.SimpleNamespace(output_text=json.dumps(result))

    ai_classifier.client.responses.create = fake_create

    candidates = [
        {"id": "a", "name": "Tool A", "text": "developer CLI"},
        {"id": "b", "name": "Tool B", "text": "developer API"},
    ]

    results = ai_classifier.classify_candidates(candidates)
    assert results["a"] is True
    assert results["b"] is False
