# Datadog Prompt Management: `LLMObs.get_prompt()` Missing from ddtrace 4.5.0rc1

## Environment

| Component | Value |
|-----------|-------|
| ddtrace version | `4.5.0rc1` (installed from S3 pre-release index) |
| S3 index URL | `https://dd-trace-py-builds.s3.amazonaws.com/96035140/index.html` |
| Wheel installed | `ddtrace-4.5.0rc1-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl` |
| Python version | 3.11 (python:3.11-slim Docker image) |
| Platform | Linux x86_64 (DigitalOcean droplet, Ubuntu) |
| LLMObs config | `DD_LLMOBS_ENABLED=1`, `DD_LLMOBS_ML_APP=devtoolscrape` |
| Tracer entry | `ddtrace-run gunicorn` via entrypoint.sh |

## Problem

The Prompt Management documentation describes `LLMObs.get_prompt()` as the primary API for fetching prompts at runtime:

```python
from ddtrace.llmobs import LLMObs

prompt = LLMObs.get_prompt("my-prompt-id", label="production", fallback="...")
messages = prompt.format(question="How do I reset my password?")
```

This method does not exist on `LLMObs` in ddtrace 4.5.0rc1 installed from the S3 index above. Calling it raises:

```
AttributeError: type object 'LLMObs' has no attribute 'get_prompt'
```

Additionally, the documentation references a `ManagedPrompt` class with `.format()` and `.to_annotation_dict()` methods, and `LLMObs.clear_prompt_cache()`. None of these exist in this build.

## Full Error from Production Logs

```
Traceback (most recent call last):
  File "/app/chatbot.py", line 161, in generate_chat_response
    prompt = _get_prompt()
             ^^^^^^^^^^^^^
  File "/app/chatbot.py", line 95, in _get_prompt
    return LLMObs.get_prompt(
           ^^^^^^^^^^^^^^^^^^
AttributeError: type object 'LLMObs' has no attribute 'get_prompt'
```

## What We Tried

### 1. Initial implementation following the documentation

Installed ddtrace 4.5.0rc1 from the S3 pre-release index as instructed:

**Dockerfile:**
```dockerfile
RUN pip install --no-cache-dir \
    --find-links=https://dd-trace-py-builds.s3.amazonaws.com/96035140/index.html \
    -r requirements.txt
```

**requirements.txt:**
```
ddtrace==4.5.0rc1
```

**chatbot.py (attempted implementation):**
```python
from ddtrace.llmobs import LLMObs

_PROMPT_ID = "devtools-assistant"
_PROMPT_LABEL = os.getenv("CHATBOT_PROMPT_LABEL", "production")
_FALLBACK_PROMPT = "You are a helpful assistant..."

def _get_prompt():
    return LLMObs.get_prompt(
        _PROMPT_ID,
        label=_PROMPT_LABEL,
        fallback=_FALLBACK_PROMPT,
    )

def generate_chat_response(user_message: str):
    prompt = _get_prompt()
    instructions = prompt.format()
    agent = Agent(name="DevToolsAssistant", instructions=instructions, ...)
    with LLMObs.annotation_context(prompt=prompt.to_annotation_dict()):
        result = Runner.run_sync(agent, input=user_message, ...)
```

This deployed successfully (CI tests pass because ddtrace is stubbed in tests), but crashed at runtime when the first chat request hit `LLMObs.get_prompt()`.

### 2. Investigated the actual API surface in the container

Connected to the running container and inspected what `LLMObs` actually exposes:

```python
>>> from ddtrace.llmobs import LLMObs
>>> [m for m in dir(LLMObs) if not m.startswith('_')]
['activate_distributed_headers', 'agent', 'annotate', 'annotation_context',
 'create_dataset', 'create_dataset_from_csv', 'disable', 'embedding',
 'enable', 'enabled', 'experiment', 'export_span', 'flush',
 'inject_distributed_headers', 'join', 'llm', 'pull_dataset',
 'register_processor', 'retrieval', 'start', 'stop', 'submit_evaluation',
 'task', 'tool', 'workflow']
```

**Missing from the documented Prompt Management API:**
- `LLMObs.get_prompt()` -- not present
- `LLMObs.clear_prompt_cache()` -- not present
- `ManagedPrompt` class -- not present anywhere in the package

**Present (Prompt Tracking API -- works):**
- `LLMObs.annotation_context(prompt=dict)` -- present and functional
- `ddtrace.llmobs.types.Prompt` -- a `dict` subclass (not the documented `ManagedPrompt`)

### 3. Searched the entire package for prompt-related APIs

```python
>>> from ddtrace.llmobs._llmobs import Prompt
>>> Prompt.__bases__
(<class 'dict'>,)
>>> # It's just a dict subclass, no format() or to_annotation_dict()

>>> # Prompt-related symbols in _llmobs module:
>>> ['INPUT_PROMPT', 'PROMPT_TRACKING_INSTRUMENTATION_METHOD', 'Prompt',
     'PromptOptimization', '_validate_prompt']
```

The `_prompt_optimization` submodule exists but contains `PromptOptimization` (an experimentation class), not the Prompt Management fetch API.

### 4. Verified the Prompt Tracking API does work

The `annotation_context(prompt=...)` method accepts a plain dict:

```python
_PROMPT_TRACKING = {
    "id": "devtools-assistant",
    "template": "You are a helpful assistant...",
    "version": "1.0",
}

with LLMObs.annotation_context(prompt=_PROMPT_TRACKING):
    result = Runner.run_sync(agent, input=user_message, ...)
```

This works and is our current workaround. It provides prompt tracking in LLM Observability traces but does not enable runtime prompt fetching or management from the Datadog UI.

## Hypothesis

**Update (2026-02-17):** We discovered that our Datadog account has not yet been enrolled in the Prompt Management beta -- the enabling PR on Datadog's side has not been merged. This is almost certainly the root cause. The S3 pre-release build was likely generated from a CI artifact that either:

1. Predates the Prompt Management feature branch being merged into the ddtrace codebase, or
2. Is a general-purpose pre-release build that does not include the Prompt Management code path, which may be gated behind beta enrollment

The documentation was written ahead of the feature being available in this build. The Prompt Tracking API (`annotation_context`) shipped earlier and works because it does not require any server-side beta gate -- it simply attaches metadata to LLM Observability spans locally.

The missing piece is specifically the Prompt Management runtime API:
- `LLMObs.get_prompt(prompt_id, label, fallback)` -- server-side prompt fetching
- `ManagedPrompt` class with `.format(**variables)` and `.to_annotation_dict(**variables)`
- `LLMObs.clear_prompt_cache()` -- cache invalidation
- The HTTP client that calls `api.datadoghq.com` to fetch prompt templates

## What We Need

1. Beta enrollment for our Datadog account so the Prompt Management feature is enabled
2. A build of ddtrace that actually includes `LLMObs.get_prompt()` and the `ManagedPrompt` class (this may require a new S3 build after the feature PR is merged)
3. Or confirmation that additional configuration flags or feature gates are needed beyond beta enrollment

## Workaround

We are currently using Prompt Tracking only (not Prompt Management). The system prompt is hardcoded in the application, and we pass it as a dict to `annotation_context` so it appears in LLM Observability traces:

```python
_PROMPT_TRACKING = {
    "id": "devtools-assistant",
    "template": _SYSTEM_PROMPT,
    "version": "1.0",
}

with LLMObs.annotation_context(prompt=_PROMPT_TRACKING):
    result = Runner.run_sync(agent, input=user_message, ...)
```

This does not allow runtime prompt updates from the Datadog UI, which was the intended goal.

## Reproduction Steps

1. Install ddtrace from the S3 index:
   ```bash
   pip install --find-links=https://dd-trace-py-builds.s3.amazonaws.com/96035140/index.html ddtrace==4.5.0rc1
   ```

2. Attempt to call `get_prompt`:
   ```python
   from ddtrace.llmobs import LLMObs
   LLMObs.enable(ml_app="test-app")
   prompt = LLMObs.get_prompt("my-prompt", label="production", fallback="hello")
   # => AttributeError: type object 'LLMObs' has no attribute 'get_prompt'
   ```

3. Verify the method is missing:
   ```python
   print(hasattr(LLMObs, 'get_prompt'))       # False
   print(hasattr(LLMObs, 'clear_prompt_cache')) # False
   ```
