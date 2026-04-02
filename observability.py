"""
Lightweight helpers for Datadog tracing so we can consistently instrument
outbound calls even when ddtrace isn't available (e.g., in tests).
"""
from __future__ import annotations

import os
import secrets
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

    try:
        ctx = tracer.trace(span_name, service=effective_service, resource=resource, span_type="http")
    except Exception:
        yield None
        return

    with ctx as span:
        try:
            span.set_tag("http.method", method.upper())
            span.set_tag("http.url", url)
        except Exception:
            span = None
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

    try:
        ctx = tracer.trace(span_name, service=effective_service, resource=resource, span_type=span_type)
    except Exception:
        yield None
        return

    with ctx as span:
        try:
            if tags:
                for key, value in tags.items():
                    span.set_tag(key, value)
        except Exception:
            span = None
        yield span


_TRACE_ID_HEX_LENGTH = 32  # 128 bits = 16 bytes = 32 hex characters


def generate_trace_id_w3c() -> str:
    """Generate a 128-bit W3C-compatible trace ID as a 32-character hex string.

    Uses secrets.token_hex for cryptographic randomness, which is the stdlib
    recommendation for security-sensitive random values.
    """
    trace_id_hex = secrets.token_hex(16)
    assert len(trace_id_hex) == _TRACE_ID_HEX_LENGTH, (
        f"Expected {_TRACE_ID_HEX_LENGTH} hex chars, got {len(trace_id_hex)}"
    )
    # W3C Trace Context spec forbids all-zero trace IDs.
    assert trace_id_hex != "0" * _TRACE_ID_HEX_LENGTH, (
        "Generated all-zero trace ID, which is invalid per W3C spec"
    )
    return trace_id_hex


def replace_root_span_trace_id(trace_id_hex: str) -> Optional[int]:
    """Replace the trace ID on the current root span with a custom W3C trace ID.

    Stores the original ddtrace-assigned trace ID as a span tag so it can be
    cross-referenced in Datadog.

    Returns the original trace ID (as int) if replacement succeeded, None otherwise.
    """
    assert isinstance(trace_id_hex, str), (
        f"trace_id_hex must be str, got {type(trace_id_hex)}"
    )
    assert len(trace_id_hex) == _TRACE_ID_HEX_LENGTH, (
        f"W3C trace ID must be {_TRACE_ID_HEX_LENGTH} hex chars, got {len(trace_id_hex)}"
    )

    if tracer is None:
        return None

    try:
        root_span = tracer.current_root_span()
    except AttributeError:
        # Tracer stub or incompatible ddtrace version lacks current_root_span.
        return None

    if root_span is None:
        return None

    original_trace_id = root_span.trace_id
    original_trace_id_hex = format(original_trace_id, "032x")
    root_span.set_tag("custom.trace_id", trace_id_hex)
    root_span.set_tag("original.trace_id", original_trace_id_hex)
    root_span.trace_id = int(trace_id_hex, 16)

    return original_trace_id
