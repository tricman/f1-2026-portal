"""
Context Tracing & Correlation Engine for F1 2026 Showrunner.
Provides zero-dependency distributed tracing primitives using Python contextvars.
"""
from __future__ import annotations

import functools
import inspect
import time
import uuid
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])

_current_trace_id: ContextVar[Optional[str]] = ContextVar("current_trace_id", default=None)
_current_span_id: ContextVar[Optional[str]] = ContextVar("current_span_id", default=None)
_current_parent_span_id: ContextVar[Optional[str]] = ContextVar("current_parent_span_id", default=None)
_current_trace_context: ContextVar[Dict[str, Any]] = ContextVar("current_trace_context", default={})


def generate_trace_id() -> str:
    """Generates a 16-character compact hexadecimal correlation trace_id."""
    return uuid.uuid4().hex[:16]


def generate_span_id() -> str:
    """Generates an 8-character span identifier."""
    return f"span_{uuid.uuid4().hex[:8]}"


def get_current_trace_id() -> Optional[str]:
    """Returns the active trace_id or None if uninitialized."""
    return _current_trace_id.get()


def get_current_span_id() -> Optional[str]:
    """Returns the active span_id or None."""
    return _current_span_id.get()


def get_current_parent_span_id() -> Optional[str]:
    """Returns the parent span_id or None."""
    return _current_parent_span_id.get()


def get_trace_context() -> Dict[str, Any]:
    """Returns a shallow copy of contextual metadata tags attached to the trace."""
    return dict(_current_trace_context.get())


def set_trace_context(
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    **tags: Any,
) -> None:
    """Sets or updates trace context values in the active contextvar scope."""
    if trace_id is not None:
        _current_trace_id.set(trace_id)
    if span_id is not None:
        _current_span_id.set(span_id)
    if parent_span_id is not None:
        _current_parent_span_id.set(parent_span_id)
    
    ctx = dict(_current_trace_context.get())
    ctx.update(tags)
    _current_trace_context.set(ctx)


def clear_trace_context() -> None:
    """Clears all trace context variables for the current context."""
    _current_trace_id.set(None)
    _current_span_id.set(None)
    _current_parent_span_id.set(None)
    _current_trace_context.set({})


def trace_span(
    name: Optional[str] = None,
    extract_args: bool = False,
    **default_tags: Any,
) -> Callable[[F], F]:
    """
    Decorator that instruments a function with an execution span:
      - Inherits active trace_id or generates a new one.
      - Nests span hierarchy (parent_span_id -> span_id).
      - Measures execution duration in milliseconds.
      - Emits structured TRACE logs on start and end.
    """
    def decorator(fn: F) -> F:
        span_name = name or fn.__name__

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            from src.logger import trace, is_trace_enabled

            token_trace = None
            existing_trace_id = _current_trace_id.get()
            effective_trace_id = existing_trace_id or generate_trace_id()
            if existing_trace_id is None:
                token_trace = _current_trace_id.set(effective_trace_id)

            parent_id = _current_span_id.get()
            new_span_id = generate_span_id()
            token_parent = _current_parent_span_id.set(parent_id)
            token_span = _current_span_id.set(new_span_id)

            ctx = dict(_current_trace_context.get())
            ctx.update(default_tags)
            token_ctx = _current_trace_context.set(ctx)

            start_perf = time.perf_counter()
            start_details: Dict[str, Any] = {
                "span_name": span_name,
                "span_id": new_span_id,
                "parent_span_id": parent_id,
            }
            if extract_args:
                clean_kwargs = {k: repr(v)[:150] for k, v in kwargs.items()}
                start_details["args_preview"] = [repr(a)[:100] for a in args[:3]]
                start_details["kwargs_preview"] = clean_kwargs

            if is_trace_enabled():
                trace(
                    f"▶ SPAN START [{span_name}]",
                    event="SPAN_START",
                    span_name=span_name,
                    span_id=new_span_id,
                    parent_span_id=parent_id,
                    details=start_details,
                )

            try:
                result = fn(*args, **kwargs)
                duration_ms = round((time.perf_counter() - start_perf) * 1000, 2)

                if is_trace_enabled():
                    end_details = {
                        "span_name": span_name,
                        "span_id": new_span_id,
                        "duration_ms": duration_ms,
                    }
                    trace(
                        f"✔ SPAN END [{span_name}] ({duration_ms}ms)",
                        event="SPAN_END",
                        span_name=span_name,
                        span_id=new_span_id,
                        duration_ms=duration_ms,
                        details=end_details,
                    )
                return result
            except Exception as exc:
                duration_ms = round((time.perf_counter() - start_perf) * 1000, 2)
                if is_trace_enabled():
                    trace(
                        f"✖ SPAN ERROR [{span_name}] ({duration_ms}ms): {exc}",
                        event="SPAN_ERROR",
                        span_name=span_name,
                        span_id=new_span_id,
                        duration_ms=duration_ms,
                        exc=exc,
                    )
                raise
            finally:
                _current_span_id.reset(token_span)
                _current_parent_span_id.reset(token_parent)
                _current_trace_context.reset(token_ctx)
                if token_trace is not None:
                    _current_trace_id.reset(token_trace)

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            from src.logger import trace, is_trace_enabled

            token_trace = None
            existing_trace_id = _current_trace_id.get()
            effective_trace_id = existing_trace_id or generate_trace_id()
            if existing_trace_id is None:
                token_trace = _current_trace_id.set(effective_trace_id)

            parent_id = _current_span_id.get()
            new_span_id = generate_span_id()
            token_parent = _current_parent_span_id.set(parent_id)
            token_span = _current_span_id.set(new_span_id)

            ctx = dict(_current_trace_context.get())
            ctx.update(default_tags)
            token_ctx = _current_trace_context.set(ctx)

            start_perf = time.perf_counter()
            if is_trace_enabled():
                trace(
                    f"▶ SPAN START (async) [{span_name}]",
                    event="SPAN_START",
                    span_name=span_name,
                    span_id=new_span_id,
                    parent_span_id=parent_id,
                )

            try:
                result = await fn(*args, **kwargs)
                duration_ms = round((time.perf_counter() - start_perf) * 1000, 2)
                if is_trace_enabled():
                    trace(
                        f"✔ SPAN END (async) [{span_name}] ({duration_ms}ms)",
                        event="SPAN_END",
                        span_name=span_name,
                        span_id=new_span_id,
                        duration_ms=duration_ms,
                    )
                return result
            except Exception as exc:
                duration_ms = round((time.perf_counter() - start_perf) * 1000, 2)
                if is_trace_enabled():
                    trace(
                        f"✖ SPAN ERROR (async) [{span_name}] ({duration_ms}ms): {exc}",
                        event="SPAN_ERROR",
                        span_name=span_name,
                        span_id=new_span_id,
                        duration_ms=duration_ms,
                        exc=exc,
                    )
                raise
            finally:
                _current_span_id.reset(token_span)
                _current_parent_span_id.reset(token_parent)
                _current_trace_context.reset(token_ctx)
                if token_trace is not None:
                    _current_trace_id.reset(token_trace)

        if inspect.iscoroutinefunction(fn):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator

