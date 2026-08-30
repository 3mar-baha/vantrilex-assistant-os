"""Multi-speaker voiceprint registry — social graph + voice enrollment (§2.3b, ADR-17).

Extends the sealed owner voiceprint (voice_biometric_auth) to enrolled contacts: known
speakers get a warm message-taking reply and their transcripts append to a dossier;
unknown speakers stage into Pending_Speakers and route through an owner verdict
(confirm / ignore / unknown). Every non-owner verdict keeps guest containment —
zero gateway calls carrying personal context, zero whitelist, zero PC actions.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from cryptography.fernet import Fernet
from loguru import logger
from pydantic import BaseModel

from src.skills.voice_biometric_auth import DEFAULT_MODEL_ID, VoiceBiometrics, _cosine, _fernet

CONTACT_MODE_AR: Final[str] = "هلا ونور! عمر مش موجود هسا، بس أنا سمسعتك — سيبلي رسالة وببلّغه فوراً."

_CONTACTS = "Contacts"


class Verdict(BaseModel):
    role: Literal["owner", "contact", "unknown"]
    name: str | None = None
    category: str | None = None
    similarity: float = 0.0


class PendingSpeaker(BaseModel):
    pending_id: str
    claimed_name: str | None = None
    transcript_hint: str = ""
    received_at: str = ""


class WriteResult(BaseModel):
    pending_id: str
    outcome: Literal["enrolled", "ignored", "flagged"]
    path: Path


class VoiceprintError(RuntimeError):
    pass


class VoiceprintRegistry:
    """Fernet-sealed per-contact voiceprints under {vault}/State/voiceprints/ with
    dossiers under Contacts/{Category}/{Name}.md (ADR-15: the vault is the only
    durable home). Owner is always matched first."""

    def __init__(
        self,
        *,
        bio: VoiceBiometrics,
        vault_root: Path,
        enc_key: str,
        threshold: float = 0.75,
    ) -> None:
        self._bio = bio
        self._vault = Path(vault_root)
        self._enc_key = enc_key
        self._threshold = threshold

    async def match(self, ogg_opus: bytes) -> Verdict:
        vector = await self._bio.embed(ogg_opus)
        return self.match_vector(vector)

    async def match_vector(self, vector: list[float]) -> Verdict:
        owner_vector = self._bio.owner_vector
        if owner_vector is not None:
            similarity = _cosine(vector, owner_vector)
            if similarity >= self._threshold:
                return Verdict(role="owner", similarity=similarity)
        best: Verdict | None = None
        for name, category, stored in self._load_contacts():
            similarity = _cosine(vector, stored)
            if similarity >= self._threshold and (best is None or similarity > best.similarity):
                best = Verdict(role="contact", name=name, category=category, similarity=similarity)
        return best or Verdict(role="unknown")

    def enroll(self, name: str, category: str, embedding: bytes | list[float]) -> Path:
        """Create the dossier + encrypted vector as one unit: a failed dossier write
        rolls the vector file back — no half-created identity."""
        vector_path = self._vault / "State" / "voiceprints" / f"{name}.enc"
        vector_path.parent.mkdir(parents=True, exist_ok=True)
        vector_path.write_bytes(self._seal(name, embedding))
        dossier = self._dossier_path(name, category)
        try:
            dossier.parent.mkdir(parents=True, exist_ok=True)
            dossier.write_text(self._dossier_text(name, category), encoding="utf-8")
        except Exception:
            vector_path.unlink(missing_ok=True)
            raise
        return dossier

    def update_stability(self, name: str, embedding: bytes | list[float]) -> None:
        """Running centroid: fold the new sample into the stored vector (count+1)."""
        path = self._vault / "State" / "voiceprints" / f"{name}.enc"
        payload = json.loads(Fernet(self._enc_key.encode()).decrypt(path.read_bytes()))
        count = int(payload.get("count", 1))
        old = payload["vector"]
        centroid = [(o * count + n) / (count + 1) for o, n in zip(old, embedding)]
        payload.update(vector=centroid, count=count + 1)
        path.write_bytes(self._fernet().encrypt(json.dumps(payload).encode()))

    def record_transcript(self, name: str, transcript: str) -> Path:
        dossier = self._dossier_path(name, None)
        if not dossier.exists():
            raise VoiceprintError(f"no dossier for {name!r} — enroll first")
        with dossier.open("a", encoding="utf-8") as handle:
            handle.write(
                f"\n## {datetime.now(UTC).isoformat(timespec='seconds')}\n\n{transcript}\n"
            )
        return dossier

    def stage_pending(
        self, embedding: bytes | list[float], transcript_hint: str, claimed_name: str | None = None
    ) -> Path:
        from src.skills.voice_biometric_auth import stage_guest_note

        vector = embedding if isinstance(embedding, list) else json.loads(embedding)
        return stage_guest_note(
            self._vault,
            vector,
            enc_key=self._enc_key,
            transcript=transcript_hint,
            claimed_name=claimed_name,
        )

    def pending_briefs(self) -> list[PendingSpeaker]:
        directory = self._vault / "Voice_Memos" / "Pending_Speakers"
        if not directory.exists():
            return []
        briefs: list[PendingSpeaker] = []
        for note in sorted(directory.glob("*.json")):
            payload = json.loads(note.read_text(encoding="utf-8"))
            briefs.append(
                PendingSpeaker(
                    pending_id=note.stem,
                    claimed_name=payload.get("claimed_name"),
                    transcript_hint=payload.get("transcript", ""),
                    received_at=payload.get("received_at", ""),
                )
            )
        return briefs

    def resolve_pending(self, pending_id: str, verdict: str) -> WriteResult:
        note = self._vault / "Voice_Memos" / "Pending_Speakers" / f"{pending_id}.json"
        payload = json.loads(note.read_text(encoding="utf-8"))
        name = payload.get("claimed_name") or pending_id
        if verdict == "ignore":
            dossier = self._dossier_path(name, "Ignored")
            dossier.parent.mkdir(parents=True, exist_ok=True)
            dossier.write_text(
                self._dossier_text(name, "Ignored", extra={"ignored": True}), encoding="utf-8"
            )
            result = WriteResult(pending_id=pending_id, outcome="ignored", path=dossier)
        elif verdict.startswith("confirm:"):
            dossier = self.enroll(name, verdict.split(":", 1)[1], self._unseal(payload))
            result = WriteResult(pending_id=pending_id, outcome="enrolled", path=dossier)
        elif verdict == "unknown":
            dossier = self._dossier_path(name, "Unknown")
            dossier.parent.mkdir(parents=True, exist_ok=True)
            dossier.write_text(
                self._dossier_text(name, "Unknown", extra={"security_flag": True}),
                encoding="utf-8",
            )
            self._store_vector(name, self._unseal(payload))
            result = WriteResult(pending_id=pending_id, outcome="flagged", path=dossier)
        else:
            raise VoiceprintError(f"unknown verdict {verdict!r} for pending {pending_id!r}")
        note.unlink()
        return result

    # --- internals ---

    def _fernet(self):
        return _fernet(self._enc_key)

    def _seal(self, name: str, embedding: bytes | list[float]) -> bytes:
        vector = embedding if isinstance(embedding, list) else json.loads(embedding)
        payload = {"model": DEFAULT_MODEL_ID, "vector": vector, "count": 1}
        return self._fernet().encrypt(json.dumps(payload).encode())

    def _unseal(self, payload: dict) -> list[float]:
        raw = payload.get("voiceprint_enc")
        if not raw:
            raise VoiceprintError("pending note carries no voiceprint")
        decoded = json.loads(self._fernet().decrypt(raw.encode()).decode())
        return decoded["vector"] if isinstance(decoded, dict) else decoded

    def _store_vector(self, name: str, vector: list[float]) -> None:
        directory = self._vault / "State" / "voiceprints"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{name}.enc").write_bytes(
            self._fernet().encrypt(
                json.dumps({"model": DEFAULT_MODEL_ID, "vector": vector, "count": 1}).encode()
            )
        )

    def _dossier_path(self, name: str, category: str | None) -> Path:
        if category is not None:
            return self._vault / "Contacts" / category / f"{name}.md"
        for candidate in sorted((self._vault / "Contacts").glob(f"*/{name}.md")):
            if candidate.parent.name != "Ignored":
                return candidate
        raise VoiceprintError(f"no dossier found for {name!r}")

    def _dossier_text(self, name: str, category: str, extra: dict[str, bool] | None = None) -> str:
        frontmatter = [
            "name: " + name,
            "category: " + category,
            f"voiceprint_ref: State/voiceprints/{name}.enc",
            "enrolled_at: " + datetime.now(UTC).isoformat(timespec="seconds"),
        ]
        if extra:
            frontmatter.extend(f"{key}: true" for key in extra)
        return "\n".join(["---", *frontmatter, "---", "", f"# {name} — {category}", ""])

    def _load_contacts(self) -> list[tuple[str, str, list[float]]]:
        directory = self._vault / "State" / "voiceprints"
        if not directory.exists():
            return []
        contacts: list[tuple[str, str, list[float]]] = []
        for stored in sorted(directory.glob("*.enc")):
            name = stored.stem
            if (self._vault / "Contacts" / "Ignored" / f"{name}.md").exists():
                continue  # blacklisted: never matched, never tracked again
            try:
                payload = json.loads(self._fernet().decrypt(stored.read_bytes()).decode())
            except Exception:  # noqa: BLE001 — one corrupt entry must not break the registry
                logger.warning("unreadable voiceprint for {name}; skipping", name=name)
                continue
            try:
                dossier = self._dossier_path(name, None)
            except VoiceprintError:
                logger.warning("voiceprint without dossier for {name}; skipping", name=name)
                continue
            category = dossier.parent.name
            contacts.append((name, category, payload["vector"]))
        return contacts
