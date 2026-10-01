"""Owner-side PC action coordinator (sprint-3 3.4): the ONLY core-side surface that may
send PC commands. Origin is checked first (untrusted content never mints intent), every
confirmed action gets ONE audit code shared by the Confirmations note, the tunnel command,
and the result message, and every event lands in the append-only audit ledger.
Remediation 2.4 (audit C-8): every prompt/outcome/confirm/reject exchange also enters
memory.remember — the brain never meets a confirmation turn it can't see."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import ClassVar, Final

from loguru import logger

from bridge.executor import CONFIRMATION_TTL, mint_audit_code, mint_confirmation_id
from common.consent import is_affirmative
from src.bridge_server import BridgeOffline
from src.vault import AUDIT_DIR, CONFIRMATIONS_DIR, VaultClient, write_frontmatter

# F-2: ONE TTL, defined on the side that ENFORCES it (the daemon refuses an
# expired id) and imported here, so the window the coordinator honours and the
# window the daemon applies can never drift apart.
PENDING_TTL = CONFIRMATION_TTL
LEDGER_PATH = f"{AUDIT_DIR}/pc-ledger.md"

UNKNOWN_APP_AR = "«{}» مش موجود بالقائمة المعتمدة — اسمه مش مسجّل عندي."

# F-6 (audit C-2): what the owner hears when he affirms a confirmation
# that already aged out. Measured, not invented: the expiry really does
# happen (`pending_active`, PENDING_TTL), and before this the refusal was
# SILENT — the turn fell through to the brain as ordinary chat, so a yes
# went to a conversation instead of to a decision, and the owner never
# learned the request had lapsed.
#
# Deliberately carries no app name, no vault path and no token: this line
# goes to Telegram, and the pending `target` is whatever
# `resolve_app_alias` returned — in legacy mode with no guard, that is any
# string the owner typed.
EXPIRED_CONFIRMATION_AR: Final[str] = (
    "انتهت مهلة التأكيد — ما نفّذت شي. إذا بدك أعمله، اطلبه من جديد."
)

# 2.4: fallback chat id when the notifier carries none (tests/plain coordinators) —
# in production the notifier's _chat_id IS the owner's real chat, so confirmation
# turns land in the SAME rolling buffer the brain reads.
OWNER_MEMORY_CHAT_ID = 111

# Remediation 2.2 (owner directive 2026-09-03, audit C-7): Arabic colloquial
# app aliases → whitelist keys. The owner says «الآلة الحاسبة», the bridge
# needs «calculator». Seeded from the 156-entry whitelist display names +
# common colloquial forms; resolved BEFORE any wire round-trip.
_APP_ALIASES: dict[str, str] = {
    # calculator
    "الآلة الحاسبة": "calculator",
    "اله الحاسبة": "calculator",
    "الحاسبة": "calculator",
    "الة حاسبة": "calculator",
    "كالكوليتر": "calculator",
    # notepad
    "المفكرة": "Notepad",
    "مفكرة": "Notepad",
    "المفكرة النصية": "Notepad",
    "نوتباد": "Notepad",
    # obsidian
    "أوبسيديان": "obsidian",
    "اوبسيديان": "obsidian",
    "اوبزديان": "obsidian",
    "أوبزديان": "obsidian",
    # chrome / edge / firefox
    "الكروم": "Google Chrome",
    "كروم": "Google Chrome",
    # live 2026-09-05 7:25am: short latin/exe names arrived from speech and
    # running-app reports — they must land on the same entry as the Arabic
    "chrome": "Google Chrome",
    "chrome.exe": "Google Chrome",
    "الإيدج": "Microsoft Edge",
    "ايدج": "Microsoft Edge",
    "الفيرفوكس": "Firefox",
    "فيرفوكس": "Firefox",
    # vs code
    "الفيسوال ستوديو كود": "Visual Studio Code",
    "الفي اس كود": "Visual Studio Code",
    "فيسوال كود": "Visual Studio Code",
    "الكود": "Visual Studio Code",
    # common colloquial singletons
    "الاكسبلورر": "File Explorer",
    "مدير الملفات": "File Explorer",
    "الملفات": "File Explorer",
    "السبوتيفاي": "Spotify",
    "سبوتيفاي": "Spotify",
    "التلغرام": "Telegram Desktop",
    "تلغرام": "Telegram Desktop",
    "الديسكورد": "Discord",
    "ديسكورد": "Discord",
    "الوثب": "WhatsApp",
    "واتساب": "WhatsApp",
    "الضغط": "7-Zip",
    # command-line tools (live 2026-09-04 3:22pm: «افتحي CMD» refused — the
    # terminal family was never in the alias table)
    "cmd": "Command Prompt",
    "سي ام دي": "Command Prompt",
    "الدوس": "Command Prompt",
    "دوس": "Command Prompt",
    "التيرمنال": "Windows Terminal",
    "تيرمنال": "Windows Terminal",
    "باورشيل": "PowerShell",
    "السيف مود": None,  # placeholder never matched — kept for table honesty
}

# case-insensitive lookup table (latin half) — built once at import
_APP_ALIASES_BY_FOLD: dict[str, str] = {
    key.casefold(): value for key, value in _APP_ALIASES.items() if value is not None
}


def resolve_app_alias(name: str) -> str:
    """Map a colloquial/short app name to its whitelist key (pass-through).
    Case-insensitive on the latin half — «Chrome.exe» and «chrome» reach the
    same entry as «كروم» (live 2026-09-05: case-mismatch fell through)."""
    clean = " ".join(name.split()).strip()
    hit = _APP_ALIASES.get(clean)
    if hit is not None:
        return hit
    folded = _APP_ALIASES_BY_FOLD.get(clean.casefold())
    return folded if folded is not None else clean


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
    def __init__(self, bridge, vault: VaultClient, notifier, guard=None, memory=None, now_fn=None):
        self._bridge = bridge
        self._vault = vault
        self._notifier = notifier
        self._guard = guard  # None = legacy pass-through (guard lives on the daemon)
        self._memory = memory  # 2.4: None = legacy, exchanges never enter memory
        # F-6: the repo's clock seam (same name and shape as
        # `bridge.executor.Executor` and `src.tools.ToolRegistry`). EVERY time
        # read in this class goes through it — half a seam is a second source
        # of truth, and a seam the caller cannot move is exactly why C-2 was
        # unverified: `pending_active` read `datetime.now(UTC)` directly, so no
        # test could cross the 10-minute TTL without sleeping for it.
        self._now = now_fn or (lambda: datetime.now(UTC))
        self._pending: _Pending | None = None
        # A prompt that aged out and has not been answered. Kept OUT of
        # `_pending` on purpose: `pending_active()` clears the expired prompt
        # (a test pins that), so the fact that it EXPIRED needs its own latch
        # or the honest line can never be worded.
        self._lapsed: bool = False

    def _remember(self, role: str, content: str) -> None:
        """2.4 (audit C-8): the confirmation conversation enters memory — the
        OWNER's chat id (Sara is owner-only, one chat), best-effort; a dead
        memory never breaks a launch."""
        if self._memory is None:
            return
        chat_id = getattr(self._notifier, "_chat_id", None) or OWNER_MEMORY_CHAT_ID
        try:
            self._memory.remember(chat_id, role, content)
        except Exception:  # noqa: BLE001 — memory is context, not a dependency
            logger.warning("coordinator memory write failed (best-effort skip)")

    def pending_active(self) -> bool:
        """True while a confirmation is still INSIDE its window.

        An aged-out prompt is dropped here exactly as before (state is
        cleared, the caller is told "no"), and the drop additionally
        latches `_lapsed` so the refusal can still be spoken.
        """
        if self._pending is None:
            return False
        if self._now() - self._pending.created_at > PENDING_TTL:
            self._pending = None
            self._lapsed = True
            return False
        return True

    def pending_open(self) -> bool:
        """True while a prompt is still AWAITING an answer, expired or not.
        This is the gate `src/bot.py` routes the owner's reply through.

        It is deliberately not `pending_active()`. F-6 measured that gating
        on the latter makes a lapsed confirmation invisible: the instant the
        TTL passes, «نعم» stops being a confirmation and becomes an ordinary
        chat message — the brain answers a yes to nothing, and the owner is
        never told it lapsed.
        """
        return self.pending_active() or self._lapsed

    async def request_close(self, name: str, *, origin: str) -> LaunchStatus:
        """Directive §2 (owner 2026-09-04): real app closing — «سكري X» routes
        HERE, never to launch. The daemon guards (same whitelist gate), runs
        taskkill, and VERIFIES termination via psutil before we confirm; an
        honest still-running line if the process survived."""
        self._require_owner_origin(origin)
        resolved = resolve_app_alias(name)
        if self._guard is not None:
            verdict = self._guard.check_app(resolved)
            if verdict.reason == "not whitelisted" and resolved == name:
                line = UNKNOWN_APP_AR.format(name)
                await self._notifier.notify(line)
                self._remember("assistant", line)
                return LaunchStatus.REFUSED
        try:
            result = await self._send("exec.close", {"name": resolved})
        except BridgeOffline:
            # the bridge-down launch honesty (round-2) applies to close too
            await self._notifier.notify("الجسر مو متصل هسا")
            self._remember("assistant", "الجسر مو متصل هسا")
            return LaunchStatus.REFUSED
        code = result["audit_code"]
        if result["status"] == "ok":
            # termination-verified confirmation only (live lesson 2026-09-04
            # 3:23pm: «اغلقها هي كمان؟» then «لم يتم اغلاق ولا واحدة»)
            killed = int(result.get("killed_processes", 0) or 0)
            await self._ledger(code, "close", "executed", resolved)
            if killed > 0:
                await self._notifier.notify(
                    f"✅ سكّرت {resolved} ({killed} نسخة). رمز التدقيق: {code}"
                )
                self._remember("assistant", f"سكّرت {resolved} ({killed} نسخة)")
            else:
                await self._notifier.notify(
                    f"✅ أرسلت أمر الإغلاق لـ{resolved} وما لقيت نسخة شغالة هسا. "
                    f"رمز التدقيق: {code}"
                )
                self._remember("assistant", f"أمر إغلاق {resolved}: ما في نسخة شغالة")
            return LaunchStatus.EXECUTED
        if "confirmation" in result["detail"] or "not whitelisted" in result["detail"]:
            prompt = (
                f"«{resolved}» مش بالقائمة المعتمدة — بتحب أسمح بإغلاقه هالمرة؟ "
                f"رد بـ«نعم» للتأكيد. رمز التدقيق: {code}"
            )
            self._pending = _Pending("close", resolved, self._now())
            self._lapsed = False
            await self._ledger(code, "close", "refused", result["detail"])
            await self._notifier.notify(prompt)
            self._remember("assistant", prompt)
            return LaunchStatus.CONFIRMATION_REQUIRED
        await self._ledger(code, "close", "error", result["detail"])
        await self._notifier.notify(f"⚠️ ما قدرت أسكّر {resolved}: {result['detail']}")
        self._remember("assistant", f"ما قدرت أسكّر {resolved}: {result['detail']}")
        return LaunchStatus.REFUSED

    async def request_launch(self, name: str, *, origin: str) -> LaunchStatus:
        self._require_owner_origin(origin)
        resolved = resolve_app_alias(name)
        if self._guard is not None:
            # 2.2: an unresolvable name gets the honest line NOW — no doomed
            # confirmation round-trip for a name that can never resolve.
            verdict = self._guard.check_app(resolved)
            if verdict.reason == "not whitelisted" and resolved == name:
                line = UNKNOWN_APP_AR.format(name)
                await self._notifier.notify(line)
                self._remember("assistant", line)
                return LaunchStatus.REFUSED
        result = await self._send("exec.launch", {"name": resolved})
        code = result["audit_code"]
        if result["status"] == "ok":
            await self._ledger(code, "launch", "executed", resolved)
            await self._notifier.notify(f"✅ شغّلت {resolved}. رمز التدقيق: {code}")
            self._remember("assistant", f"شغّلت {resolved} (رمز التدقيق: {code})")
            return LaunchStatus.EXECUTED
        if "confirmation" in result["detail"] or "not whitelisted" in result["detail"]:
            prompt = (
                f"«{resolved}» مش بالقائمة المعتمدة — بتحب أسمح فيه هالمرة؟ "
                f"رد بـ«نعم» للتأكيد. رمز التدقيق: {code}"
            )
            self._pending = _Pending("launch", resolved, self._now())
            self._lapsed = False
            await self._ledger(code, "launch", "refused", result["detail"])
            await self._notifier.notify(prompt)
            self._remember("assistant", prompt)
            return LaunchStatus.CONFIRMATION_REQUIRED
        await self._ledger(code, "launch", "error", result["detail"])
        await self._notifier.notify(f"⚠️ ما قدرت أشغّل {resolved}: {result['detail']}")
        self._remember("assistant", f"ما قدرت أشغّل {resolved}: {result['detail']}")
        return LaunchStatus.REFUSED

    async def request_power(self, action: str, *, origin: str) -> LaunchStatus:
        self._require_owner_origin(origin)
        prompt = f"أمر {action} على الجهاز بيتطلب تأكيد صريح — رد بـ«نعم» للمتابعة."
        self._pending = _Pending("power", action, self._now())
        self._lapsed = False
        await self._notifier.notify(prompt)
        self._remember("assistant", prompt)
        return LaunchStatus.CONFIRMATION_REQUIRED

    async def handle_owner_reply(self, text: str) -> str | None:
        if not self.pending_active():
            if not self._lapsed:
                return None  # nothing was ever pending: stay silent
            # F-6 (audit C-2): the prompt existed and it lapsed. Say so ONCE,
            # remember it (2.4/C-8: the brain must meet every confirmation
            # turn, including the dead one), and execute nothing. Without
            # this line the owner's «نعم» was swallowed in silence and the
            # request simply vanished.
            self._lapsed = False
            self._remember("user", text)
            await self._notifier.notify(EXPIRED_CONFIRMATION_AR)
            self._remember("assistant", EXPIRED_CONFIRMATION_AR)
            return None
        pending = self._pending
        self._remember("user", text)
        if not is_affirmative(text):
            self._pending = None
            await self._notifier.notify("تمام، ما نفذت شي.")
            self._remember("assistant", "تمام، ما نفذت شي.")
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
        now = self._now()
        # F-2: the id is a SIGNED, expiring token, not a bare uuid — the daemon
        # verifies it against the shared core<->daemon secret, which is the
        # only place it can be verified (it has no vault client to read this
        # note back through). No secret, no id: refuse rather than send one.
        confirmation_id = mint_confirmation_id(now=now)
        audit_code = mint_audit_code()
        if not confirmation_id:
            line = "ما قدرت أسجّل تأكيدك — مفتاح التأكيد مو مضبوط عندي. قل لي من جديد."
            await self._ledger(audit_code, kind, "refused", "confirmation signing key unreachable")
            await self._notifier.notify(line)
            self._remember("assistant", line)
            return None
        # The note is named by the token's NONCE, not by its first 8 characters:
        # a signed id starts with the fixed version prefix "cfm1.", so `[:8]`
        # would name every same-day note identically and `upsert` would
        # OVERWRITE the previous approval — weakening the audit trail this note
        # exists to be. The nonce is 8 random hex per mint.
        nonce = confirmation_id.split(".")[2]
        path = f"{CONFIRMATIONS_DIR}/{now:%Y-%m-%d}_{nonce}.md"
        meta = {
            "type": "pc-confirmation",
            "confirmation_id": confirmation_id,
            "audit_code": audit_code,
            "kind": kind,
            "target": target,
            "confirmed_at": now.isoformat(),
        }
        # the note lands BEFORE the command leaves: an approval without a persisted
        # audit trail is void
        await self._vault.upsert(
            path,
            write_frontmatter(meta, f"# {kind}: {target}\n\nسجل تأكيد مالك.\n"),
            message=f"sara: pc confirmation {nonce}",
        )
        if kind == "launch":
            result = await self._send(
                "exec.launch",
                {"name": target, "confirmation_id": confirmation_id, "audit_code": audit_code},
            )
        elif kind == "close":
            result = await self._send(
                "exec.close",
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
            self._remember("assistant", f"نفّذت {target} (رمز التدقيق: {audit_code})")
            return target
        await self._notifier.notify(f"⚠️ فشل تنفيذ {target}: {result['detail']}")
        self._remember("assistant", f"فشل تنفيذ {target}: {result['detail']}")
        return None

    async def _send(self, cmd: str, args: dict) -> dict:
        return await self._bridge.send_cmd(cmd, args)

    async def _ledger(self, audit_code: str, action: str, outcome: str, reason: str) -> None:
        ts = self._now().strftime("%Y-%m-%dT%H:%M:%SZ")
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
