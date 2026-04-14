# Plan: Integrate Datadog LLM Observability and RUM

## Context

The Datadog LLM Observability + RUM integration correlates frontend user sessions (RUM) with backend AI agent processing (LLM Observability) by forwarding the RUM Session ID to the LLM Observability SDK.

**Current state:**
- RUM Browser SDK is already configured in `base.html` and `app_production.py`
- `chatbot.py` uses `LLMObs.annotation_context()` but does not pass a `session_id` tag
- `ai_classifier.py` uses `LLMObs` for tracing but lacks RUM correlation
- The chat widget POSTs to `/api/chat` without including the RUM `session_id`

**Changes needed (3 files + 1 template):**

---

### 1. `templates/base.html` — Include RUM `session_id` in chat requests

**Change:** In `window.sendMessage`, retrieve the RUM session ID via `window.DD_RUM.getInternalContext()` and include it in the request body.

```javascript
// In window.sendMessage, before fetch():
var rumContext = window.DD_RUM && window.DD_RUM.getInternalContext();
var body = { message: message };
if (rumContext && rumContext.session_id) {
    body.session_id = rumContext.session_id;
}
```

The existing `body = JSON.stringify({ message: message })` line becomes the snippet above.

---

### 2. `app_production.py` — Extract `session_id` and pass to `generate_chat_response`

**Change:** In `api_chat()`, read `session_id` from the JSON body and forward it as an argument.

In `generate_chat_response(user_message)`, add `session_id` parameter:
```python
def generate_chat_response(user_message: str, session_id: str | None = None) -> dict[str, Any]:
```

When calling, pass it through:
```python
result = generate_chat_response(user_message, session_id=data.get("session_id"))
```

---

### 3. `chatbot.py` — Tag LLM spans with `session_id`

**Change:** `generate_chat_response()` calls `LLMObs.annotation_context()`. After the agent run, use `LLMObs.annotate()` to attach the `session_id` tag.

```python
from ddtrace.llmobs import LLMObs

# Inside generate_chat_response, after result is obtained:
if session_id:
    try:
        LLMObs.annotate(
            span=None,
            tags={"session_id": session_id},
        )
    except Exception:
        pass
```

---

### 4. `ai_classifier.py` — (Optional) Add `session_id` param to classify functions

**Change:** Add `session_id: str | None = None` to `classify_candidates`, `_classify_single`, and `get_devtools_category`. When `_LLMObs` is available, wrap the OpenAI call with `LLMObs.annotate(span=None, tags={"session_id": session_id})` inside `_call_openai`.

This is lower priority since `ai_classifier.py` is called from scrape jobs rather than user-facing requests.

---

## Critical Files

| File | Role |
|------|------|
| `templates/base.html` | Frontend: include `session_id` in chat POST |
| `app_production.py` | Backend: extract `session_id`, pass to chatbot |
| `chatbot.py` | LLM Observability: tag spans with `session_id` |
| `ai_classifier.py` | LLM Observability: tag classifier spans with `session_id` (optional) |

---

## Verification

1. Run the Flask app and open the chat widget in a browser
2. Open browser DevTools → Network tab, filter for `/api/chat`
3. Send a message — request body should contain `"session_id": "<rum-session-id>"`
4. In Datadog LLM Observability, open the trace for that chat interaction
5. The span should have a `session_id` tag matching the RUM session ID
6. From the LLM trace, the "RUM Session" link should open the corresponding RUM session replay
