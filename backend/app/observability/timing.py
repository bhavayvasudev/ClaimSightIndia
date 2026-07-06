"""Timing helpers for workflow node / external-call duration logging
(Task 13). Every graph node and every AI-service/RAG call this project
makes is wrapped with one of these so latency is visible per-stage in
logs — never swallowed silently."""

from __future__ import annotations

import functools
import logging
import time
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger("app.observability.timing")

T = TypeVar("T")


def timed_node(node_name: str) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for LangGraph node coroutines — logs how long the node
    took, regardless of whether it did real work or short-circuited
    (skip-because-already-done is itself useful signal: a node that
    always takes ~0ms is a sign the idempotency check is working)."""

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs) -> T:
            start = time.perf_counter()
            try:
                return await fn(*args, **kwargs)
            finally:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                logger.info("workflow_node node=%s duration_ms=%d", node_name, elapsed_ms)

        return wrapper

    return decorator


class timed_block:
    """Context manager for timing a non-node operation (an AI-service
    call, a RAG retrieval pass). Usage:

        async with timed_block("ai_service_call"):
            await ai_client.analyze_claim(images)
    """

    def __init__(self, operation_name: str):
        self._name = operation_name
        self._start = 0.0

    def __enter__(self) -> "timed_block":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        elapsed_ms = int((time.perf_counter() - self._start) * 1000)
        status = "failed" if exc_type is not None else "ok"
        logger.info("timed_operation op=%s duration_ms=%d status=%s", self._name, elapsed_ms, status)

    async def __aenter__(self) -> "timed_block":
        return self.__enter__()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.__exit__(exc_type, exc, tb)
