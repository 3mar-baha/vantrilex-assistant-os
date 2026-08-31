"""Social graph — Contacts taxonomy + story extractor (sprint-3 §3.1b, ADR-21).

Owner narrates the day -> ONE FAST-tier extraction call -> entities filed as
dated sections into both the person's dossier and the day's Daily_Logs note.
LLM output is strictly DATA (validated through typed models, never instructions).
Ambiguous categories hold for owner confirmation; Ignored/ dossiers (tracking:
false) NEVER receive appends; Unknown/ carries security_flag: true.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from loguru import logger
from pydantic import BaseModel, ValidationError

from src.gateway import Tier
from src.vault import Note, VaultClient, WriteResult, redact_secret, split_frontmatter

CONTACT_CATEGORIES = ("Family", "Friends", "Colleagues")  # + Ignored/Unknown (system-managed)

_SYSTEM_PROMPT = (
    "You extract people mentioned in the owner's Arabic daily narration. "
    "Reply with ONLY a JSON array, no prose, no code fences. Each element: "
    '{"name": "<person name as spoken>", "action_summary": "<what happened, Arabic>", '
    '"category_inferred": "Family" | "Friends" | "Colleagues" | "Ignored" | null}. '
    "Use null when the relationship is unclear. Names stay verbatim Arabic."
)


class ContactDossier(BaseModel):
    name: str
    category: str
    relation_tags: list[str] = []
    voiceprint_ref: str | None = None  # State/voiceprints/<id>.enc
    created: date
    last_interaction: date | None = None


class EntityMention(BaseModel):
    name: str
    action_summary: str
    mentioned_at: datetime
    category_inferred: str | None = None  # None => ask owner before filing


def _json_array(reply: str) -> list | None:
    text = re.sub(r"```[a-z]*", "", reply).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match is None:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, list) else None


class SocialGraph:
    def __init__(
        self,
        vault: VaultClient,
        brain,  # OmniRouteClient — FAST-tier extraction (ADR-16)
        *,
        tz: ZoneInfo = ZoneInfo("Asia/Amman"),
    ) -> None:
        self._vault = vault
        self._brain = brain
        self._tz = tz

    async def dossier(self, category: str, name: str) -> ContactDossier | None:
        try:
            text = await self._vault.read(f"Contacts/{category}/{name}.md")
        except FileNotFoundError:
            return None
        meta, _ = split_frontmatter(text)
        return ContactDossier(**meta)

    async def create_dossier(self, d: ContactDossier, *, voiceprint: bytes | None) -> WriteResult:
        meta: dict = {
            "name": d.name,
            "category": d.category,
            "relation_tags": d.relation_tags,
            "voiceprint_ref": d.voiceprint_ref,
            "created": d.created,
            "last_interaction": d.last_interaction,
        }
        if d.category == "Ignored":
            meta["tracking"] = False
        if d.category == "Unknown":
            meta["security_flag"] = True
        if voiceprint is not None:
            await self._vault.upsert(
                f"State/voiceprints/{d.name}.enc",
                "",  # binary vector payloads ride the 2.3b Fernet registry; ref only here
                message=f"sara: voiceprint ref {d.name}",
            )
        return await self._vault.upsert_note(
            Note(
                path=f"Contacts/{d.category}/{d.name}.md",
                frontmatter=meta,
                body=f"# {d.name} — {d.category}\n\n## Interaction Log\n",
            ),
            message=f"sara: create dossier {d.name}",
        )

    async def extract_entities(
        self, narration: str, *, now: datetime | None = None
    ) -> list[EntityMention]:
        """One FAST-tier call; unparseable or invalid output -> [] (DATA, loudly)."""
        at = now or datetime.now(self._tz)
        reply = await self._brain.chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": narration},
            ],
            tier=Tier.FAST,
            temperature=0.0,
        )
        parsed = _json_array(reply)
        if parsed is None:
            logger.warning("story extractor: unparseable brain reply")
            return []
        mentions: list[EntityMention] = []
        for item in parsed:
            try:
                mentions.append(
                    EntityMention(
                        name=str(item["name"]).strip(),
                        action_summary=str(item["action_summary"]).strip(),
                        mentioned_at=at,
                        category_inferred=item.get("category_inferred") or None,
                    )
                )
            except (KeyError, ValidationError, TypeError) as error:
                logger.warning(
                    "story extractor: skipping malformed entity {e}", e=redact_secret(str(error))
                )
        return mentions

    async def file_action(self, m: EntityMention) -> list[WriteResult]:
        """File one mention: dated section in its dossier + the day's log.
        Ambiguous category holds for owner confirmation; Ignored/ never appends."""
        if m.category_inferred is None:
            logger.info("social graph: {name} held for owner confirmation", name=m.name)
            return []
        if m.category_inferred == "Ignored":  # tracking: false — never appends
            return []
        if m.category_inferred not in (*CONTACT_CATEGORIES, "Unknown"):
            logger.warning("social graph: unknown category {c} for {n}", c=m.category_inferred, n=m.name)
            return []
        heading = m.mentioned_at.strftime("%Y-%m-%d")
        results = [
            await self._vault.append_section(
                f"Contacts/{m.category_inferred}/{m.name}.md",
                heading,
                [f"- {m.action_summary}"],
                commit_prefix="sara: social",
            ),
            await self._vault.append_section(
                f"Daily_Logs/{m.mentioned_at.date().isoformat()}.md",
                heading,
                [f"- {m.name}: {m.action_summary}"],
                commit_prefix="sara: social",
            ),
        ]
        logger.info(
            "social graph: filed {name} under {category}",
            name=m.name,
            category=m.category_inferred,
        )
        return results
