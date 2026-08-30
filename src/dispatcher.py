"""Fast Front-Door Dispatcher (ADR-18): Tier-1 ack first, then tiered execution.

One Tier-1 router call classifies the request (tiny JSON verdict) and supplies the
instant Jordanian acknowledgment; simple chat is answered fully at Tier 1,
single/dual-tool work streams at Tier 2, multi-step DAGs at Tier 3 (ADR-16).
Router failure degrades safely to Tier 2 with a loud log — Sara always speaks
immediately, never hangs.
"""

import json
import re
from collections.abc import AsyncIterator
from typing import Final

from loguru import logger

from src.config import Settings
from src.gateway import GatewayError, OmniRouteClient, Tier

DEFAULT_ACK_AR: Final[str] = "من عيوني هسا ببدأ..."

_ROUTER_PROMPT_AR: Final[str] = (
    "أنت بوابة سارة الأمامية. صنّف طلب المالك وأجب بسطر JSON واحد فقط:\n"
    '{"route": "direct"|"tier2"|"tier3", "ack": "..."}\n'
    '- direct: دردشة أو سؤال بسيط — ضع ردّك الكامل بالعامية الأردنية الدافئة في "ack".\n'
    "- tier2: مهمة بأداة أو أداتين (تقويم، مهام، بريد، ملفات، تشغيل برنامج) — "
    'ضع إقرارًا فوريًا قصيرًا في "ack".\n'
    '- tier3: تخطيط متعدد الخطوات، تعليم عميق، تحليل ملفات — إقرار فوري في "ack".\n'
    "لا تكتب أي شيء خارج الـ JSON."
)

_ROUTES: Final[dict[str, Tier]] = {"tier2": Tier.MEDIUM, "tier3": Tier.HEAVY}
_VALID_ROUTES: Final = ("direct", *_ROUTES)
_JSON_RE: Final = re.compile(r"\{.*\}", re.DOTALL)


def _parse_router(reply: str) -> tuple[str, str] | None:
    """Extract the {route, ack} verdict; None when the reply is not a valid routing."""
    match = _JSON_RE.search(reply)
    if not match:
        return None
    try:
        verdict = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    route = verdict.get("route")
    ack = str(verdict.get("ack") or "").strip()
    if route not in _VALID_ROUTES or (route == "direct" and not ack):
        return None
    return route, ack or DEFAULT_ACK_AR


class FrontDoorDispatcher:
    def __init__(self, gateway: OmniRouteClient, settings: Settings) -> None:
        self._gateway = gateway
        self._settings = settings

    async def handle(self, user_text: str, *, system: str | None = None) -> AsyncIterator[str]:
        route, ack = "tier2", DEFAULT_ACK_AR  # safe default: degraded routing, never a hang
        try:
            reply = await self._gateway.chat(
                [
                    {"role": "system", "content": _ROUTER_PROMPT_AR},
                    {"role": "user", "content": user_text},
                ],
                tier=Tier.FAST,
                temperature=0.0,
                max_tokens=1024,
            )
            parsed = _parse_router(reply)
        except GatewayError as exc:
            logger.warning("dispatcher router failed -> default tier2: {}", exc)
        else:
            if parsed is None:
                logger.warning(
                    "dispatcher unparsable router reply -> default tier2: {!r}", reply[:200]
                )
            else:
                route, ack = parsed
        yield ack
        if route == "direct":
            return
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": user_text}
        ]
        async for delta in self._gateway.stream_chat(messages, tier=_ROUTES[route]):
            yield delta
