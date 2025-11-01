import importlib
import pathlib
import sys
import types

import pytest

# Ensure project root is importable regardless of test runner cwd
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def stub_external_sdks():
    """Provide stub implementations for third-party SDKs used at import time."""
    # Stub ddtrace.llmobs.LLMObs.enable
    ddtrace_module = types.ModuleType("ddtrace")
    llmobs_module = types.ModuleType("ddtrace.llmobs")

    class _FakeLLMObs:
        calls = []

        @classmethod
        def enable(cls, *args, **kwargs):
            cls.calls.append((args, kwargs))

    llmobs_module.LLMObs = _FakeLLMObs
    ddtrace_module.llmobs = llmobs_module
    sys.modules["ddtrace"] = ddtrace_module
    sys.modules["ddtrace.llmobs"] = llmobs_module

    # Stub openai.OpenAI client
    openai_module = types.ModuleType("openai")

    class _FakeCompletions:
        def __init__(self):
            self._responses = []
            self._should_raise = False

        def queue_response(self, content):
            self._responses.append(content)

        def raise_on_create(self):
            self._should_raise = True

        def create(self, *_, **__):
            if self._should_raise:
                raise Exception("forced failure")
            content = self._responses.pop(0) if self._responses else "yes"
            message = types.SimpleNamespace(content=content)
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    openai_module.OpenAI = _FakeOpenAI
    sys.modules["openai"] = openai_module

    yield

    # Ensure stubs cleaned up for any downstream imports
    sys.modules.pop("ddtrace", None)
    sys.modules.pop("ddtrace.llmobs", None)
    sys.modules.pop("openai", None)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point the database module at an isolated SQLite file and initialize schema."""
    db_file = tmp_path / "startups.db"
    monkeypatch.setenv("DEVTOOLS_DB_PATH", str(db_file))
    monkeypatch.setenv("DEVTOOLS_DATA_DIR", str(tmp_path))

    import database

    importlib.reload(database)
    database.init_db()
    return database


@pytest.fixture
def reset_ai_classifier(monkeypatch):
    """Reload ai_classifier with stubbed dependencies and provide easy client control."""
    import ai_classifier

    importlib.reload(ai_classifier)
    yield ai_classifier
