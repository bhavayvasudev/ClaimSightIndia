"""Thin HTTP client for the ai-service (`ai-service/main.py`).

This is the only place `AI_SERVICE_URL`/timeout are read and the only
place `httpx` is imported for talking to it — nothing else should
hardcode the ai-service's address or reach for `httpx` directly.

`transport` is exposed purely for testing: pass an `httpx.MockTransport`
to exercise this client (and everything built on top of it) without a
real ai-service process, and without ever loading the YOLO models.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import httpx

from app.config import get_settings
from app.observability.context import get_request_id
from app.observability.timing import timed_block


class AIServiceError(Exception):
    """Base class for ai-service communication failures."""


class AIServiceUnavailable(AIServiceError):
    """The ai-service could not be reached, or returned a non-200 status."""


class AIServiceTimeout(AIServiceError):
    """The ai-service did not respond within the configured timeout."""


class AIServiceInvalidResponse(AIServiceError):
    """The ai-service responded, but the body wasn't valid JSON or didn't
    match the expected `/analyze-claim` response contract."""


class AIServiceValidationRejected(AIServiceError):
    """The ai-service understood the request and deliberately rejected it
    as a structured validation failure (e.g. one or more images don't
    contain a vehicle) — a request-content problem, never an outage. Must
    never be mapped to the same "AI service unavailable" response as a
    real transport failure."""

    def __init__(self, error_code: str, message: str, invalid_filenames: List[str]):
        super().__init__(message)
        self.error_code = error_code
        self.invalid_filenames = invalid_filenames


ImagePayload = Tuple[str, bytes, str]  # (filename, content, content_type)


class AIServiceClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        settings = get_settings()
        self._base_url = (base_url or settings.ai_service_url).rstrip("/")
        self._timeout = timeout if timeout is not None else settings.ai_service_timeout_seconds
        self._transport = transport
        self._shared_secret = settings.ai_service_shared_secret

    async def analyze_claim(self, images: List[ImagePayload]) -> dict:
        """POSTs the given images to `/analyze-claim` and returns the parsed
        JSON body. Raises an `AIServiceError` subclass on any failure —
        callers never need to know about `httpx` exceptions or raw status
        codes."""

        files = [
            ("images", (filename, content, content_type))
            for filename, content, content_type in images
        ]
        # Only set when configured (app.config.Settings.ai_service_shared_secret)
        # — an optional defense-in-depth layer on top of network isolation,
        # never required for local development.
        headers = {"X-Internal-Service-Token": self._shared_secret} if self._shared_secret else {}
        # Correlation id, not a secret: lets one ai-service log line be tied
        # to the exact backend request (and therefore claim) that caused it.
        request_id = get_request_id()
        if request_id:
            headers["X-Request-ID"] = request_id

        try:
            async with timed_block("ai_service_analyze_claim"):
                async with httpx.AsyncClient(
                    timeout=self._timeout, transport=self._transport
                ) as client:
                    response = await client.post(
                        f"{self._base_url}/analyze-claim", files=files, headers=headers
                    )
        except httpx.TimeoutException as exc:
            raise AIServiceTimeout("AI service did not respond in time") from exc
        except httpx.RequestError as exc:
            raise AIServiceUnavailable("AI service is unreachable") from exc

        if response.status_code == 422:
            detail = None
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None

            if isinstance(detail, dict) and detail.get("error_code"):
                raise AIServiceValidationRejected(
                    error_code=detail["error_code"],
                    message=detail.get("message", "One or more images were rejected."),
                    invalid_filenames=detail.get("invalid_filenames", []),
                )

        if response.status_code != 200:
            raise AIServiceUnavailable(
                f"AI service returned unexpected status {response.status_code}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise AIServiceInvalidResponse("AI service returned a non-JSON body") from exc

        if not isinstance(body, dict) or "claim_analysis" not in body:
            raise AIServiceInvalidResponse("AI service response is missing claim_analysis")

        return body
