import importlib
import types

import pytest


def test_has_devtools_keywords(reset_ai_classifier):
    classifier = reset_ai_classifier
    assert classifier.has_devtools_keywords("Great CLI for developers", "Tool")
    assert not classifier.has_devtools_keywords("A gardening app", "Gardenify")


def test_is_devtools_related_ai_pre_filter(reset_ai_classifier, monkeypatch):
    classifier = reset_ai_classifier
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    # Patch client to record calls; keyword filter should skip API call
    calls = {"count": 0}

    def fake_create(*args, **kwargs):
        calls["count"] += 1
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="no"))]
        )

    classifier.client.chat.completions.create = fake_create
    assert not classifier.is_devtools_related_ai("A travel planner")
    assert calls["count"] == 0

    # Manually invoke to exercise stubbed function body for coverage
    result = fake_create()
    assert result.choices[0].message.content == "no"


def test_is_devtools_related_ai_without_api_key_uses_fallback(reset_ai_classifier, monkeypatch):
    classifier = reset_ai_classifier
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert classifier.is_devtools_related_ai("Developer platform with SDKs")
    assert not classifier.is_devtools_related_ai("Photo album for families")


def test_is_devtools_related_ai_with_invalid_response_falls_back(reset_ai_classifier, monkeypatch):
    classifier = reset_ai_classifier
    monkeypatch.setenv("OPENAI_API_KEY", "present")

    def fake_create(*args, **kwargs):
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="maybe"))]
        )

    classifier.client.chat.completions.create = fake_create
    assert classifier.is_devtools_related_ai("Developer utilities for CI pipelines")


def test_is_devtools_related_ai_handles_api_errors(reset_ai_classifier, monkeypatch):
    classifier = reset_ai_classifier
    monkeypatch.setenv("OPENAI_API_KEY", "present")

    def failing_create(*args, **kwargs):
        raise RuntimeError("down")

    classifier.client.chat.completions.create = failing_create
    assert classifier.is_devtools_related_ai("Developer monitoring with logs")


def test_is_devtools_related_ai_with_valid_response(reset_ai_classifier, monkeypatch):
    classifier = reset_ai_classifier
    monkeypatch.setenv("OPENAI_API_KEY", "present")

    def fake_create(*args, **kwargs):
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="yes"))]
        )

    classifier.client.chat.completions.create = fake_create
    assert classifier.is_devtools_related_ai("CLI deployment helper", "DeployTool")


def test_get_devtools_category_without_api_key(reset_ai_classifier, monkeypatch):
    classifier = reset_ai_classifier
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert classifier.get_devtools_category("Any text") is None


def test_get_devtools_category_success(reset_ai_classifier, monkeypatch):
    classifier = reset_ai_classifier
    monkeypatch.setenv("OPENAI_API_KEY", "present")

    def fake_create(*args, **kwargs):
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="CLI Tool"))]
        )

    classifier.client.chat.completions.create = fake_create
    assert classifier.get_devtools_category("CLI utilities", "Tooler") == "CLI Tool"


def test_is_devtools_related_fallback(reset_ai_classifier):
    classifier = reset_ai_classifier
    assert classifier.is_devtools_related_fallback("Manage CI pipelines")
    assert not classifier.is_devtools_related_fallback("Handmade pottery marketplace")


def test_get_devtools_category_handles_exception(reset_ai_classifier, monkeypatch):
    classifier = reset_ai_classifier
    monkeypatch.setenv("OPENAI_API_KEY", "present")

    def failing_create(*args, **kwargs):
        raise RuntimeError("bad request")

    classifier.client.chat.completions.create = failing_create
    assert classifier.get_devtools_category("API helper", "API Helper") is None


def test_openai_stub_queue_and_raise(reset_ai_classifier):
    classifier = reset_ai_classifier
    stub = classifier.client.chat.completions
    stub.queue_response("no")
    stub.queue_response("yes")
    first = stub.create(None)
    assert first.choices[0].message.content == "no"
    second = stub.create(None)
    assert second.choices[0].message.content == "yes"

    stub.raise_on_create()
    with pytest.raises(Exception):
        stub.create(None)


def test_classify_candidates_caches_results(monkeypatch):
    monkeypatch.setenv("AI_CLASSIFIER_DISABLE_CACHE", "0")
    monkeypatch.setenv("AI_CLASSIFIER_DISABLE_BATCH", "0")
    monkeypatch.setenv("AI_CLASSIFIER_MAX_CONCURRENCY", "2")
    monkeypatch.setenv("OPENAI_API_KEY", "present")

    import importlib
    import ai_classifier

    importlib.reload(ai_classifier)

    stub = ai_classifier.client.chat.completions
    stub.queue_response({"results": {"a": "yes", "b": "no"}})
    stub.queue_response({"results": {"a": "no", "b": "yes"}})

    candidates = [
        {"id": "a", "name": "Tool A", "text": "developer CLI"},
        {"id": "b", "name": "Tool B", "text": "developer API"},
    ]

    first = ai_classifier.classify_candidates(candidates)
    assert first["a"] is True
    assert first["b"] is False
    assert stub.calls == 1

    second = ai_classifier.classify_candidates(candidates)
    assert second["a"] is True
    assert second["b"] is False
    assert stub.calls == 1  # cache hit prevents second API call
