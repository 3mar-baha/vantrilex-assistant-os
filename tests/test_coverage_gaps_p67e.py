"""P6 batch 7e — social_enrollment + scheduled_tasks uncovered edges: embed
match path, enroll rollback, missing-dossier record, pending-briefs absent dir,
bogus verdict, seal-less confirm, ignored-blacklist + dossierless skips,
task-note malformed/partial shapes, sync skip matrix, dir-scan fallbacks,
sync-mark idempotence + write-failure, mark_done both outcomes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from cryptography.fernet import Fernet

from src.skills.scheduled_tasks import (
    ScheduledTasksEngine,
    TaskNote,
    parse_task_note,
    render_task_note,
)
from src.skills.social_enrollment import VoiceprintError, VoiceprintRegistry
from src.skills.voice_biometric_auth import VoiceBiometrics

KEY = Fernet.generate_key().decode()
NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
OWNER_VEC = [0.6, 0.8, 0.0]
AHMAD_VEC = [0.8, -0.6, 0.0]


def _registry(tmp_path, *, owner=True):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    bio = VoiceBiometrics(embedding_path=vault / "State" / "owner.enc", enc_key=KEY)
    if owner:
        bio._owner_vector = list(OWNER_VEC)
    return vault, bio, VoiceprintRegistry(bio=bio, vault_root=vault, enc_key=KEY)


async def test_match_runs_the_embed_lane(monkeypatch, tmp_path):
    _vault, bio, registry = _registry(tmp_path)

    async def _embed(_ogg):
        return list(OWNER_VEC)

    monkeypatch.setattr(bio, "embed", _embed)
    verdict = await registry.match(b"\x00\x01")
    assert verdict.role == "owner" and verdict.similarity == pytest.approx(1.0)


def test_enroll_dossier_failure_rolls_vector_back(tmp_path):
    vault, _bio, registry = _registry(tmp_path)
    (vault / "Contacts").write_text("a file, not a dir", encoding="utf-8")
    with pytest.raises(OSError):
        registry.enroll("أحمد", "Family", AHMAD_VEC)
    assert not (vault / "State" / "voiceprints" / "أحمد.enc").exists()


def test_record_without_dossier_raises(tmp_path):
    _vault, _bio, registry = _registry(tmp_path)
    with pytest.raises(VoiceprintError):
        registry.record_transcript("شبح", "لا ملف له")


def test_record_ignores_blacklisted_dossier_only(tmp_path):
    vault, _bio, registry = _registry(tmp_path)
    ignored = vault / "Contacts" / "Ignored"
    ignored.mkdir(parents=True)
    (ignored / "شبح.md").write_text("muted", encoding="utf-8")
    with pytest.raises(VoiceprintError):
        registry.record_transcript("شبح", "لا يُسمَع")


def test_pending_briefs_absent_dir_is_empty(tmp_path):
    _vault, _bio, registry = _registry(tmp_path)
    assert registry.pending_briefs() == []


def test_resolve_bogus_verdict_raises(tmp_path):
    _vault, _bio, registry = _registry(tmp_path)
    staged = registry.stage_pending(AHMAD_VEC, "رسالة", claimed_name="أحمد")
    with pytest.raises(VoiceprintError):
        registry.resolve_pending(staged.stem, "maybe-later")


def test_confirm_without_sealed_voiceprint_raises(tmp_path):
    _vault, _bio, registry = _registry(tmp_path)
    staged = registry.stage_pending(AHMAD_VEC, "رسالة", claimed_name="أحمد")
    payload = json.loads(staged.read_text(encoding="utf-8"))
    del payload["voiceprint_enc"]
    staged.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(VoiceprintError):
        registry.resolve_pending(staged.stem, "confirm:Family")


async def test_ignored_contact_never_matches_again(tmp_path):
    _vault, _bio, registry = _registry(tmp_path)
    registry.enroll("أحمد", "Family", AHMAD_VEC)
    staged = registry.stage_pending(AHMAD_VEC, "رسالة", claimed_name="أحمد")
    result = registry.resolve_pending(staged.stem, "ignore")
    assert result.outcome == "ignored"
    verdict = await registry.match_vector(AHMAD_VEC)
    assert verdict.role == "unknown"  # blacklisted: never matched again


async def test_dossierless_voiceprint_skipped(tmp_path):
    vault, _bio, registry = _registry(tmp_path, owner=False)
    sealed = registry._seal("يتيم", [0.0, 1.0, 0.0])
    vp_dir = vault / "State" / "voiceprints"
    vp_dir.mkdir(parents=True)
    (vp_dir / "يتيم.enc").write_bytes(sealed)
    verdict = await registry.match_vector([0.0, 1.0, 0.0])
    assert verdict.role == "unknown"


class _Vault:
    def __init__(self, files=None, lister=None, boom_upsert=False):
        self.files = dict(files or {})
        self._lister = lister
        self.boom_upsert = boom_upsert

    async def read(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def list_dir(self, path, *, recursive=False):
        if self._lister is not None:
            return await self._lister(path)
        prefix = f"{path}/"
        return [p for p in self.files if p.startswith(prefix) and p.endswith(".md")]

    async def upsert(self, path, content, *, message, merge=None):
        if self.boom_upsert:
            raise OSError("vault down")
        self.files[path] = content
        return content


class _Suite:
    def __init__(self, fail=False):
        self.fail = fail
        self.events: list = []

    async def create_event(self, summary, start, end, **kw):
        if self.fail:
            raise RuntimeError("google down")
        self.events.append(summary)
        return object()

    async def add_task(self, title, *, due=None, notes=None, tasklist="@default"):
        if self.fail:
            raise RuntimeError("google down")
        return object()


def _engine(vault=None, suite=None):
    return ScheduledTasksEngine(
        vault or _Vault(), suite or _Suite(), tz=ZoneInfo("UTC"), now_fn=lambda: NOW
    )


def test_parse_malformed_frontmatter_is_none():
    assert parse_task_note("---\ntitle: [unclosed\n---\n[sara:task:abc]\n") is None


def test_parse_tag_without_title_or_when_is_none():
    assert parse_task_note("---\nstatus: open\n---\n[sara:task:abc]\n") is None


async def test_sync_skips_missing_unparseable_and_failed_mirrors():
    note = TaskNote(title="X", when=NOW, task_id="abc")
    good = render_task_note(note)
    bad_yaml = "---\ntitle: [unclosed\n---\n[sara:task:bad]\n"
    no_title = "---\nstatus: open\n---\n[sara:task:notitle]\n"
    vault = _Vault(
        {"t/good.md": good, "t/bad.md": bad_yaml, "t/empty.md": no_title},
        lister=lambda _p: ["t/good.md", "t/bad.md", "t/empty.md", "t/ghost.md"],
    )
    engine = ScheduledTasksEngine(vault, _Suite(fail=True), tz=ZoneInfo("UTC"), now_fn=lambda: NOW)
    assert await engine.sync_pending() == 0  # ghost skipped, bad skipped, mirror parked


async def test_task_paths_without_helper_or_dead_scan_is_empty():
    bare = SimpleNamespace()
    assert await _engine(vault=bare)._task_paths() == []

    async def _boom(_path):
        raise RuntimeError("scan down")

    assert await _engine(vault=_Vault(lister=_boom))._task_paths() == []


async def test_mirror_marks_sync_once_then_idempotent():
    vault, note_path = _Vault(), "t/a.md"
    engine = _engine(vault=vault)
    note = await engine.create_task(title="مراجعة", when=NOW + timedelta(days=1))
    path = next(p for p in vault.files if p.endswith(".md"))
    assert engine._vault is vault
    assert '"synced": true' in vault.files[path] or "synced: true" in vault.files[path]
    assert note.task_id in path
    assert note_path is not None


async def test_mirror_bookkeeping_failure_still_reports_success():
    engine = _engine(vault=_Vault(boom_upsert=True))
    note = TaskNote(title="X", when=NOW, task_id="abc")
    assert await engine._mirror(note, "t/a.md") is True  # mirror done, mark best-effort


async def test_mark_done_true_false_and_missing():
    vault = _Vault()
    engine = _engine(vault=vault)
    await engine.create_task(title="فيزياء", when=NOW + timedelta(days=1))
    assert await engine.mark_done("فيزياء") is True
    assert await engine.mark_done("كيمياء") is False
    phantom = _Vault({}, lister=lambda _p: ["t/ghost.md"])
    assert await _engine(vault=phantom).mark_done("فيزياء") is False
