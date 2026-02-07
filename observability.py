"""
Lightweight helpers for Datadog tracing so we can consistently instrument
outbound calls even when ddtrace isn't available (e.g., in tests).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Iterator, Optional

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from ddtrace.span import Span  # type: ignore

try:  # pragma: no cover - ddtrace may not be installed in all environments
    from ddtrace import tracer  # type: ignore
except Exception:  # pragma: no cover - fallback to no-op tracing
    tracer = None  # type: ignore

DEFAULT_SERVICE = os.getenv("DD_SERVICE", "devtoolscrape")


@contextmanager
def trace_http_call(
    resource: str,
    method: str,
    url: str,
    *,
    service: Optional[str] = None,
    span_name: str = "external.http.request",
) -> Iterator[Optional["Span"]]:
    """
    Wrap an outbound HTTP call in a Datadog span if ddtrace is available.

    Returns the span so callers can attach additional tags (status code, etc.).
    When ddtrace isn't installed the context manager yields ``None``.
    """
    if tracer is None:
        yield None
        return

    effective_service = service or DEFAULT_SERVICE

    with tracer.trace(resource, service=effective_service, resource=url, span_type="http") as span:
        span.set_tag("http.method", method.upper())
        span.set_tag("http.url", url)
        yield span


@contextmanager
def trace_external_call(
    span_name: str,
    resource: str,
    *,
    service: Optional[str] = None,
    span_type: str = "custom",
    tags: Optional[Dict[str, Any]] = None,
) -> Iterator[Optional["Span"]]:
    """
    Generic tracing helper for non-HTTP calls (e.g., OpenAI SDK).
    """
    if tracer is None:
        yield None
        return

    effective_service = service or DEFAULT_SERVICE

    with tracer.trace(span_name, service=effective_service, resource=resource, span_type=span_type) as span:
        if tags:
            for key, value in tags.items():
                span.set_tag(key, value)
        yield span
