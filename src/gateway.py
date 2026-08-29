"""OmniRoute brain adapter — the only module that speaks LLM wire format.

Free-pool survival: quota -> immediate fallback, transient -> capped-backoff retries,
fatal -> loud stop. Sprint 2+ consume this blindly.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Final, Literal, Self

import httpx
from loguru import logger

RETRY_ATTEMPTS: Final[int] = 3
BACKOFF_BASE_S: Final[float] = 0.5
BACKOFF_CAP_S: Final[float] = 8.0
REQUEST_TIMEOUT_S: Final[float] = 120.0

_sleep: Final = asyncio.sleep  # test seam; monkeypatched to instant in backoff tests


class GatewayError(RuntimeError):
    pass


class _QuotaExhausted(RuntimeError):
    pass


class _TransientFailure(RuntimeError):
    pass


def _classify(status_code: int, body_snippet: str) -> Literal["fatal", "quota", "transient"]:
    if status_code in (400, 401, 403, 404, 422):
        return "fatal"
    if status_code == 402:
        return "quota"
    if status_code == 429:
        markers = ("quota", "exhausted", "insufficient", "credit", "billing")
        return "quota" if any(m in body_snippet.lower() for m in markers) else "transient"
    if status_code in (408, 409, 425) or status_code >= 500:
        return "transient"
    return "fatal"


class OmniRouteClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        primary_model: str,
        fast_model: str,
        timeout_s: float = REQUEST_TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_s,
            transport=transport,
        )
        self._primary = primary_model
        self._fast = fast_model

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    def stream_chat(
        self, messages: list[dict[str, str]], *, temperature: float = 0.7, max_tokens: int = 2048
    ) -> AsyncIterator[str]:
        return self._stream(messages, temperature=temperature, max_tokens=max_tokens)

    async def chat(
        self, messages: list[dict[str, str]], *, temperature: float = 0.7, max_tokens: int = 2048
    ) -> str:
        parts: list[str] = []
        async for delta in self.stream_chat(
            messages, temperature=temperature, max_tokens=max_tokens
        ):
            parts.append(delta)
        return "".join(parts)

    async def _stream(
        self, messages: list[dict[str, str]], *, temperature: float, max_tokens: int
    ) -> AsyncIterator[str]:
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        last_cause = "unknown"
        for model in (self._primary, self._fast):
            delay = BACKOFF_BASE_S
            for attempt in range(1, RETRY_ATTEMPTS + 1):
                deltas = 0
                try:
                    async for content in self._attempt(model, payload):
                        deltas += 1
                        yield content
                    return
                except _QuotaExhausted as exc:
                    logger.info(
                        "gateway quota | model={} attempt={} -> immediate fallback", model, attempt
                    )
                    last_cause = str(exc)
                    break
                except _TransientFailure as exc:
                    last_cause = str(exc)
                    if attempt < RETRY_ATTEMPTS:
                        logger.warning(
                            "gateway transient | model={} attempt={} retry in {:.1f}s: {}",
                            model,
                            attempt,
                            delay,
                            exc,
                        )
                        await _sleep(delay)
                        delay = min(delay * 2, BACKOFF_CAP_S)
                    else:
                        logger.warning(
                            "gateway transient exhausted | model={} attempts={} :: {}",
                            model,
                            RETRY_ATTEMPTS,
                            exc,
                        )
                except httpx.HTTPError as exc:
                    if deltas > 0:
                        # Never restart a partially-yielded reply — owner would see duplicates.
                        logger.error(
                            "gateway mid-stream failure | model={} deltas={} :: {}",
                            model,
                            deltas,
                            exc,
                        )
                        raise GatewayError(
                            f"mid-stream failure on {model} after {deltas} deltas: {exc}"
                        ) from exc
                    last_cause = f"transport: {exc}"
                    if attempt < RETRY_ATTEMPTS:
                        logger.warning(
                            "gateway transport error | model={} attempt={} retry in {:.1f}s: {}",
                            model,
                            attempt,
                            delay,
                            exc,
                        )
                        await _sleep(delay)
                        delay = min(delay * 2, BACKOFF_CAP_S)
                    else:
                        logger.warning(
                            "gateway transport exhausted | model={} attempts={} :: {}",
                            model,
                            RETRY_ATTEMPTS,
                            exc,
                        )
        raise GatewayError(
            f"all models exhausted ({self._primary}, {self._fast}); last cause: {last_cause}"
        )

    async def _attempt(self, model: str, payload: dict) -> AsyncIterator[str]:
        request = self._client.build_request(
            "POST", "/chat/completions", json=dict(payload, model=model)
        )
        try:
            response = await self._client.send(request, stream=True)
        except httpx.HTTPError as exc:
            raise _TransientFailure(f"transport: {exc}") from exc
        if response.status_code != 200:
            try:
                await response.aread()  # stream=True leaves error bodies unread
            finally:
                await response.aclose()
            snippet = response.text[:500]
            kind = _classify(response.status_code, snippet)
            if kind == "quota":
                raise _QuotaExhausted(f"HTTP {response.status_code}: {snippet}")
            if kind == "transient":
                raise _TransientFailure(f"HTTP {response.status_code}: {snippet}")
            logger.error(
                "gateway fatal | model={} HTTP {} :: {}", model, response.status_code, snippet
            )
            raise GatewayError(f"fatal HTTP {response.status_code} on {model}: {snippet}")

        received = 0
        done_seen = False
        try:
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    logger.warning("gateway unexpected SSE line skipped: {!r}", line[:120])
                    continue
                received += len(line.encode())
                data = line[5:].strip()
                if data == "[DONE]":
                    done_seen = True
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("gateway malformed SSE line skipped: {!r}", data[:120])
                    continue
                choices = chunk.get("choices") or [{}]
                content = (choices[0].get("delta") or {}).get("content")
                if content:
                    yield content
        finally:
            await response.aclose()
        if not done_seen:
            logger.warning(
                "gateway stream ended without [DONE] | bytes={} (deltas still delivered)", received
            )
