"""Owner-side PC action coordinator (sprint-3 3.4): the ONLY core-side surface that may
send PC commands. Origin is checked first (untrusted content never mints intent), every
confirmed action gets ONE audit code shared by the Confirmations note, the tunnel command,
and the result message, and every event lands in the append-only audit ledger."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import ClassVar

from loguru import logger

from bridge.executor import mint_audit_code
from common.consent import is_affirmative
from src.vault import AUDIT_DIR, CONFIRMATIONS_DIR, VaultClient, write_frontmatter

PENDING_TTL = timedelta(minutes=10)
LEDGER_PATH = f"{AUDIT_DIR}/pc-ledger.md"


class LaunchStatus(StrEnum):
    EXECUTED = "executed"
    CONFIRMATION_REQUIRED = "confirmation_required"
    REFUSED = "refused"


class RefusedOrigin(Exception):
    """PC intent from a non-owner origin — never executed, never queued."""


@dataclass
class _Pending:
    kind: str  # "launch" | "power"
    target: str
    created_at: datetime


class PCActionCoordinator:
    def __init__(self, bridge, vault: VaultClient, notifier):
        self._bridge = bridge
        self._vault = vault
        self._notifier = notifier
        self._pending: _Pending | None = None

    def pending_active(self) -> bool:
        if self._pending is None:
            return False
        if datetime.now(UTC) - self._pending.created_at > PENDING_TTL:
            self._pending = None
            return False
        return True

    async def request_launch(self, name: str, *, origin: str) -> LaunchStatus:
        self._require_owner_origin(origin)
        result = await self._send("exec.launch", {"name": name})
        code = result["audit_code"]
        if result["status"] == "ok":
            await self._ledger(code, "launch", "executed", name)
            await self._notifier.notify(f"✅ شغّلت {name}. رمز التدقيق: {code}")
            return LaunchStatus.EXECUTED
        if "confirmation" in result["detail"] or "not whitelisted" in result["detail"]:
            prompt = (
                f"«{name}» مش بالقائمة المعتمدة — بتحب أسمح فيه هالمرة؟ "
                f"رد بـ«نعم» للتأكيد. رمز التدقيق: {code}"
            )
            self._pending = _Pending("launch", name, datetime.now(UTC))
            await self._ledger(code, "launch", "refused", result["detail"])
            await self._notifier.notify(prompt)
            return LaunchStatus.CONFIRMATION_REQUIRED
        await self._ledger(code, "launch", "error", result["detail"])
        await self._notifier.notify(f"⚠️ ما قدرت أشغّل {name}: {result['detail']}")
        return LaunchStatus.REFUSED

    async def request_power(self, action: str, *, origin: str) -> LaunchStatus:
        self._require_owner_origin(origin)
        prompt = f"أمر {action} على الجهاز بيتطلب تأكيد صريح — رد بـ«نعم» للمتابعة."
        self._pending = _Pending("power", action, datetime.now(UTC))
        await self._notifier.notify(prompt)
        return LaunchStatus.CONFIRMATION_REQUIRED

    async def handle_owner_reply(self, text: str) -> str | None:
        if not self.pending_active():
            return None
        pending = self._pending
        if not is_affirmative(text):
            self._pending = None
            await self._notifier.notify("تمام، ما نفذت شي.")
            return None
        self._pending = None
        return await self._confirm_and_execute(pending.kind, pending.target)

    IDLE_CHOICES: ClassVar[dict[str, str]] = {"نوم": "sleep", "اطفاء": "shutdown"}

    async def handle_idle_choice(self, choice: str) -> str | None:
        action = next((v for k, v in self.IDLE_CHOICES.items() if k in choice), None)
        if action is None:
            return None
        return action if await self._confirm_and_execute("power", action) else None

    async def _confirm_and_execute(self, kind: str, target: str) -> str | None:
        confirmation_id = uuid.uuid4().hex[:12]
        audit_code = mint_audit_code()
        path = f"{CONFIRMATIONS_DIR}/{datetime.now(UTC):%Y-%m-%d}_{confirmation_id[:8]}.md"
        meta = {
            "type": "pc-confirmation",
            "confirmation_id": confirmation_id,
            "audit_code": audit_code,
            "kind": kind,
            "target": target,
            "confirmed_at": datetime.now(UTC).isoformat(),
        }
        # the note lands BEFORE the command leaves: an approval without a persisted
        # audit trail is void
        await self._vault.upsert(
            path,
            write_frontmatter(meta, f"# {kind}: {target}\n\nسجل تأكيد مالك.\n"),
            message=f"sara: pc confirmation {confirmation_id[:8]}",
        )
        if kind == "launch":
            result = await self._send(
                "exec.launch",
                {"name": target, "confirmation_id": confirmation_id, "audit_code": audit_code},
            )
        else:
            result = await self._send(
                "power",
                {"action": target, "confirmation_id": confirmation_id, "audit_code": audit_code},
            )
        ok = result["status"] == "ok"
        await self._ledger(audit_code, kind, "executed" if ok else "error", result["detail"])
        if ok:
            await self._notifier.notify(f"✅ نفّذت {target}. رمز التدقيق: {audit_code}")
            return target
        await self._notifier.notify(f"⚠️ فشل تنفيذ {target}: {result['detail']}")
        return None

    async def _send(self, cmd: str, args: dict) -> dict:
        return await self._bridge.send_cmd(cmd, args)

    async def _ledger(self, audit_code: str, action: str, outcome: str, reason: str) -> None:
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{ts} | {audit_code} | {action} | {outcome} | {reason.replace('|', '/')}"
        try:
            existing = await self._vault.read(LEDGER_PATH)
        except FileNotFoundError:
            existing = ""
        await self._vault.upsert(
            LEDGER_PATH, f"{existing}{line}\n", message=f"sara: pc audit {audit_code}"
        )

    @staticmethod
    def _require_owner_origin(origin: str) -> None:
        if origin != "owner_chat":
            logger.warning("PC intent from non-owner origin {origin!r} — refused", origin=origin)
            raise RefusedOrigin(origin)
