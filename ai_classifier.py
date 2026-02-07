import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from cachetools import TTLCache
from dotenv import load_dotenv
import openai
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

# Load environment variables from .env file before importing modules that depend on them
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from logging_config import get_logger, logging_context
from observability import trace_external_call

# Initialize LLM Observability before creating OpenAI client
from ddtrace.llmobs import LLMObs

def _strtobool(val: Optional[str]) -> bool:
    return str(val).lower() not in {"0", "false", "none", "", "null"}

_llmobs_enabled = _strtobool(os.getenv("DD_LLMOBS_ENABLED", "1"))
_llmobs_ml_app = (
    os.getenv("DD_LLMOBS_ML_APP")
    or os.getenv("LLMOBS_ML_APP")
    or os.getenv("DD_SERVICE")
    or "devtoolscrape"
)

if _llmobs_enabled:
    LLMObs.enable(
        ml_app=_llmobs_ml_app,
        api_key=os.getenv("DATADOG_API_KEY"),
        site=os.getenv("DD_SITE", "datadoghq.com"),
        agentless_enabled=False,
        env=os.getenv("DD_ENV"),
        service=os.getenv("DD_SERVICE"),
    )

# Set up OpenAI client
client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

logger = get_logger("devtools.ai")

# Feature flags and tuning knobs
_CACHE_ENABLED = os.getenv("AI_CLASSIFIER_DISABLE_CACHE", "0") != "1"
_CACHE_TTL = float(os.getenv("AI_CLASSIFIER_CACHE_TTL", "3600"))
_CACHE_SIZE = int(os.getenv("AI_CLASSIFIER_CACHE_SIZE", "2048"))
_USE_BATCH = os.getenv("AI_CLASSIFIER_DISABLE_BATCH", "0") != "1"
_BATCH_SIZE = max(1, int(os.getenv("AI_CLASSIFIER_BATCH_SIZE", "8")))
_MAX_CONCURRENCY = max(1, int(os.getenv("AI_CLASSIFIER_MAX_CONCURRENCY", "4")))
_MAX_RETRIES = max(1, int(os.getenv("AI_CLASSIFIER_MAX_RETRIES", "3")))


def _has_openai_key() -> bool:
    return bool(os.getenv('OPENAI_API_KEY'))


_classification_cache = TTLCache(_CACHE_SIZE, _CACHE_TTL)
_category_cache = TTLCache(_CACHE_SIZE, _CACHE_TTL)
_cache_lock = threading.RLock()


def _cache_get(cache: TTLCache, key: str):
    if not _CACHE_ENABLED:
        return None
    with _cache_lock:
        return cache.get(key)


def _cache_set(cache: TTLCache, key: str, value) -> None:
    if not _CACHE_ENABLED:
        return
    with _cache_lock:
        cache[key] = value

DEVTOOLS_KEYWORDS = [
    "developer", "devtool", "CLI", "SDK", "API", "code", "coding", "debug", "git",
    "CI", "CD", "DevOps", "terminal", "IDE", "framework", "testing", "monitoring",
    "observability", "build", "deploy", "infra", "cloud-native", "backend", "log",
    "linter", "formatter", "package manager", "dependency", "compiler", "interpreter",
    "container", "kubernetes", "docker", "microservice", "serverless", "database",
    "query", "schema", "migration", "deployment", "orchestration", "automation",
]

_DEVTOOLS_KEYWORDS_LOWER = [kw.lower() for kw in DEVTOOLS_KEYWORDS]


def has_devtools_keywords(text: str, name: str = "") -> bool:
    """Quick keyword pre-filter to avoid unnecessary API calls."""
    combined_text = f"{name} {text}".lower()
    return any(keyword in combined_text for keyword in _DEVTOOLS_KEYWORDS_LOWER)

def _cache_key(name: str, text: str) -> str:
    return f"{name.strip().lower()}|{text.strip().lower()}"


def _is_retryable_error(exc: Exception) -> bool:
    if exc is None:
        return False
    message = str(exc).lower()
    return any(keyword in message for keyword in ("rate limit", "timeout", "429"))


def _build_openai_retry() -> Retrying:
    return Retrying(
        stop=stop_after_attempt(_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )


def _call_openai(messages: List[Dict[str, str]], max_tokens: int, temperature: float = 0.0, response_format=None):
    retrying = _build_openai_retry()
    for attempt in retrying:
        with attempt:
            attempt_number = attempt.retry_state.attempt_number
            logger.debug(
                "openai.request",
                extra={
                    "event": "openai.request",
                    "attempt": attempt_number,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "response_format": bool(response_format),
                },
            )
            try:
                with trace_external_call(
                    "openai.chat.completion",
                    resource="classifier.batch",
                    span_type="llm",
                    tags={
                        "openai.model": _OPENAI_MODEL,
                        "openai.attempt": attempt_number,
                        "openai.max_tokens": max_tokens,
                        "openai.temperature": temperature,
                        "openai.response_format": bool(response_format),
                        "openai.message_count": len(messages),
                    },
                ) as span:
                    if span:
                        span.set_tag("span.kind", "client")
                        span.set_tag("component", "openai")
                    response = client.chat.completions.create(
                        model=_OPENAI_MODEL,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        response_format=response_format,
                    )
                    if span and getattr(response, "usage", None):
                        usage = response.usage
                        span.set_tag("openai.prompt_tokens", getattr(usage, "prompt_tokens", 0))
                        span.set_tag("openai.completion_tokens", getattr(usage, "completion_tokens", 0))
                        span.set_tag("openai.total_tokens", getattr(usage, "total_tokens", 0))
                    return response
            except Exception as exc:  # pragma: no cover - relies on API behaviour
                logger.warning(
                    "openai.error",
                    extra={
                        "event": "openai.error",
                        "attempt": attempt_number,
                        "error": str(exc),
                    },
                )
                raise


def classify_candidates(candidates: Iterable[Dict[str, str]]) -> Dict[str, bool]:
    """
    Batch classify multiple candidates. Each candidate must contain keys:
    - id: unique identifier
    - name: tool name
    - text: description
    """
    candidates = list(candidates)
    results: Dict[str, bool] = {}
    pending: List[Dict[str, str]] = []

    for candidate in candidates:
        cid = candidate["id"]
        name = candidate.get("name", "")
        text = candidate.get("text", "")
        with logging_context(candidate_id=cid, candidate_name=name):
            if not has_devtools_keywords(text, name):
                logger.debug(
                    "classifier.keyword_filter",
                    extra={
                        "event": "classifier.keyword_filter",
                    },
                )
                results[cid] = False
                continue
            key = _cache_key(name, text)
            cached = _cache_get(_classification_cache, key)
            if cached is not None:
                logger.debug(
                    "classifier.cache_hit",
                    extra={
                        "event": "classifier.cache_hit",
                        "outcome": cached,
                    },
                )
                results[cid] = cached
            else:
                candidate["_cache_key"] = key
                pending.append(candidate)

    if not pending:
        return results

    if not _has_openai_key() or not _USE_BATCH or len(pending) == 1:
        for candidate in pending:
            outcome = _classify_single(candidate.get("name", ""), candidate.get("text", ""))
            _cache_set(_classification_cache, candidate["_cache_key"], outcome)
            results[candidate["id"]] = outcome
        return results

    chunks = [pending[i:i + _BATCH_SIZE] for i in range(0, len(pending), _BATCH_SIZE)]

    def worker(chunk):
        payload = [
            {
                "item_id": candidate["id"],
                "name": candidate.get("name", ""),
                "description": candidate.get("text", ""),
            }
            for candidate in chunk
        ]
        try:
            response = _call_openai(
                [
                    {
                        "role": "system",
                        "content": (
                            "Classify each item as devtools-related. "
                            "Respond with JSON object {\"results\": {\"<item_id>\": \"yes\"|\"no\", ...}}. "
                            "If unsure, respond with \"no\"."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload)},
                ],
                max_tokens=len(payload) * 20 + 50,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            result_map = data.get("results", {})
        except Exception as exc:
            logger.exception(
                "classifier.batch_failure",
                extra={"event": "classifier.batch_failure", "error": str(exc)},
            )
            result_map = {}

        if not result_map:
            for candidate in chunk:
                with logging_context(candidate_id=candidate["id"], candidate_name=candidate.get("name")):
                    outcome = _classify_single(candidate.get("name", ""), candidate.get("text", ""))
                    _cache_set(_classification_cache, candidate["_cache_key"], outcome)
                    results[candidate["id"]] = outcome
        else:
            for candidate in chunk:
                with logging_context(candidate_id=candidate["id"], candidate_name=candidate.get("name")):
                    answer = result_map.get(candidate["id"])
                    if answer is None:
                        logger.warning(
                            "classifier.batch_missing_id",
                            extra={
                                "event": "classifier.batch_missing_id",
                                "candidate_id": candidate["id"],
                            },
                        )
                        outcome = _classify_single(candidate.get("name", ""), candidate.get("text", ""))
                    else:
                        outcome = str(answer).strip().lower() == "yes"
                    logger.debug(
                        "classifier.batch_result",
                        extra={
                            "event": "classifier.batch_result",
                            "outcome": outcome,
                        },
                    )
                    _cache_set(_classification_cache, candidate["_cache_key"], outcome)
                    results[candidate["id"]] = outcome

    with ThreadPoolExecutor(max_workers=min(_MAX_CONCURRENCY, len(chunks))) as executor:
        futures = [executor.submit(worker, chunk) for chunk in chunks]
        for future in as_completed(futures):
            future.result()

    return results


def _classify_single(name: str, text: str) -> bool:
    if not has_devtools_keywords(text, name):
        return False
    if not _has_openai_key():
        logger.warning(
            "classifier.no_api_key",
            extra={"event": "classifier.no_api_key"},
        )
        return is_devtools_related_fallback(text)

    prompt = f"""
    You are a classifier that determines if software/tools are developer tools (devtools).

    Devtools include:
    - Development tools (IDEs, text editors, debuggers)
    - Build tools, package managers, CI/CD tools
    - Testing frameworks, monitoring tools
    - API tools, SDKs, libraries
    - DevOps tools, infrastructure tools
    - Code analysis, linting, formatting tools
    - Database tools, deployment tools
    - Terminal tools, CLI applications
    - Developer productivity tools

    NOT devtools:
    - End-user applications (games, social media, productivity apps)
    - Business software, marketing tools
    - Consumer apps, entertainment apps
    - E-commerce, finance apps (unless specifically for developers)

    Content to classify:
    Name: {name}
    Description: {text}

    Answer with ONLY "yes" or "no".
    """
    try:
        response = _call_openai(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a binary classifier for developer tools. "
                        "Respond with EXACTLY 'yes' or 'no'. If uncertain, respond 'no'."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=5,
            temperature=0.0,
        )
        answer = response.choices[0].message.content.strip().lower()
        if answer not in {"yes", "no"}:
            logger.warning(
                "classifier.unexpected_answer",
                extra={
                    "event": "classifier.unexpected_answer",
                    "answer": answer,
                    "tool_name": name,
                },
            )
            return is_devtools_related_fallback(text)
        return answer == "yes"
    except Exception as exc:
        logger.exception(
            "classifier.single_error",
            extra={"event": "classifier.single_error", "tool_name": name},
        )
        return is_devtools_related_fallback(text)


def is_devtools_related_ai(text: str, name: str = "") -> bool:
    """
    Use OpenAI to classify if content is devtools-related.
    Returns True if it's devtools, False otherwise.
    """
    key = _cache_key(name, text)
    cached = _cache_get(_classification_cache, key)
    if cached is not None:
        return cached
    result = classify_candidates([{"id": "_single", "name": name, "text": text}]).get("_single", False)
    _cache_set(_classification_cache, key, result)
    return result

def is_devtools_related_fallback(text: str) -> bool:
    """Fallback keyword-based classifier when AI is unavailable."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in _DEVTOOLS_KEYWORDS_LOWER)


def get_devtools_category(text: str, name: str = "") -> Optional[str]:
    """
    Get a more specific category for the devtool.
    Returns category like 'IDE', 'CLI Tool', 'Testing', etc.
    """
    if not _has_openai_key():
        return None

    key = _cache_key(name, text)
    cached = _cache_get(_category_cache, key)
    if cached is not None:
        return cached
    
    prompt = f"""
    Classify this devtool into one of these categories:
    - IDE/Editor: Integrated development environments, code editors
    - CLI Tool: Command line tools, terminal applications
    - Testing: Testing frameworks, test runners, mocking tools
    - Build/Deploy: Build tools, deployment tools, CI/CD
    - Monitoring/Observability: Logging, metrics, tracing, alerting
    - Database: Database tools, ORMs, query builders
    - API/SDK: API tools, SDKs, client libraries
    - DevOps: Infrastructure, containerization, orchestration
    - Code Quality: Linters, formatters, static analysis
    - Package Manager: Dependency management, package managers
    - Other: Anything else

    Examples:
    Name: VSCode
    Description: A code editor for developers.
    Category: IDE/Editor

    Name: GitHub Actions
    Description: A CI/CD automation tool for code repositories.
    Category: Build/Deploy

    Name: Postman
    Description: API development and testing tool.
    Category: API/SDK

    Name: Datadog
    Description: Cloud monitoring and observability platform.
    Category: Monitoring/Observability

    Name: Slack
    Description: A team chat and collaboration app.
    Category: Other

    Name: QuickBooks
    Description: Accounting software for small businesses.
    Category: Other

    Name: {name}
    Description: {text}

    Respond with ONLY the category name.
    """

    try:
        response = _call_openai(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a devtool categorizer. Respond with EXACTLY one of the specified category names. "
                        "If the tool doesn't fit, respond with 'Other'."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=15,
            temperature=0.0,
        )

        category = response.choices[0].message.content.strip()
        _cache_set(_category_cache, key, category)
        logger.debug(
            "classifier.category",
            extra={
                "event": "classifier.category",
                "tool_name": name,
                "category": category,
            },
        )
        return category

    except Exception as e:
        logger.exception(
            "classifier.category_error",
            extra={"event": "classifier.category_error", "tool_name": name},
        )
        return None
