"""Autonomous Coach Drill — hermetic end-to-end simulation (no gateway, no mic,
no live-vault writes; tmp vaults only).

Stage 1: 10-voice biometric matrix over synthetic fixed embeddings
         (1 owner + 9 guests) + diarizer attribution + Fish-only purity.
Stage 2: RAG self-grounding audit — every 04_Resources seed doc must
         top-1 retrieve itself (read-only), plus tmp-vault write-back.
Stage 3: 46-tool honest-degradation matrix + rich composition chain
         (gmail -> calendar -> telemetry -> vault note -> voice-policy gate).
Stage 4: cognitive trace — deduce() mapping, ReflectiveTrace friction math,
         failure -> retry self-correction, horizon adjacency.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import httpx
import pytest

from src.associative import VaultIndex
from src.cognition import ReflectiveTrace, deduce, expand_horizon
from src.fish_voice import FishFirstVoice, FishVoice, FishVoiceError
from src.gmail import EmailMessage
from src.google_suite import CalendarEvent
from src.skills.social_enrollment import CONTACT_MODE_AR, VoiceprintRegistry
from src.skills.speaker_diarization import OWNER_NAME, UNKNOWN_SPEAKER_AR, SpeakerDiarizer
from src.skills.voice_biometric_auth import GUEST_LOCKDOWN_AR, _cosine
from src.tools import TOOL_FAIL_AR, ToolRegistry
from src.voice_policy import assert_no_edge

REPO = Path(__file__).resolve().parent.parent
SEED = REPO / "04_Resources"
TZ = ZoneInfo("Asia/Amman")
NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
THRESHOLD = 0.60  # calibrated owner gate (live ECAPA finding 2026-09-03)

OWNER_V = [0.90, 0.70, 0.50, 0.30, 0.10, -0.20, -0.40, -0.60]


def _registry(tmp_path: Path) -> VoiceprintRegistry:
    bio = SimpleNamespace(owner_vector=list(OWNER_V))
    return VoiceprintRegistry(bio=bio, vault_root=tmp_path, enc_key="k", threshold=THRESHOLD)


# --- Stage 1: voice matrix ----------------------------------------------------


GUESTS: dict[str, list[float]] = {
    "silence": [0.0] * 8,  # empty capture
    "tts-impostor": [0.10, 0.05, -0.10, 0.05, 0.0, 0.10, -0.05, 0.0],
    "sibling-near": [0.50, 0.10, 0.40, -0.20, 0.40, 0.30, 0.20, -0.40],
    "friend-casual": [0.10, 0.55, -0.20, -0.10, 0.35, -0.25, -0.05, 0.30],
    "colleague-phone": [-0.10, -0.10, 0.45, -0.30, 0.30, 0.35, 0.10, 0.20],
    "child-high": [-0.10, 0.60, 0.20, 0.30, -0.20, 0.15, 0.10, -0.10],
    "elder-quiet": [0.25, 0.05, -0.15, 0.20, 0.30, -0.10, 0.25, -0.30],
    "stranger-far": [-0.50, 0.20, -0.30, 0.40, -0.10, 0.30, -0.20, 0.10],
    "noise-floor": [0.05, -0.05, 0.05, -0.05, 0.05, -0.05, 0.05, -0.05],
}


async def test_stage1_owner_unlocks_full_autonomy(tmp_path):
    reg = _registry(tmp_path)
    verdict = await reg.match_vector(list(OWNER_V))
    assert verdict.role == "owner"
    assert verdict.similarity == pytest.approx(1.0)


async def test_stage1_nine_guests_locked_out(tmp_path):
    """Every non-owner voice lands Guest Mode: role != owner, no private surfacing."""
    reg = _registry(tmp_path)
    assert len(GUESTS) == 9
    for label, vec in GUESTS.items():
        sim = _cosine(vec, OWNER_V)
        verdict = await reg.match_vector(list(vec))
        # The gate implements exactly the threshold rule — owner iff sim >= gate.
        assert (verdict.role == "owner") == (sim >= THRESHOLD), label
        assert verdict.role != "owner", f"guest leaked as owner: {label} sim={sim:.3f}"


async def test_stage1_guest_boundary_wording_arabic():
    assert GUEST_LOCKDOWN_AR and "عمر" in GUEST_LOCKDOWN_AR
    assert CONTACT_MODE_AR and "عمر" in CONTACT_MODE_AR


async def test_stage1_diarizer_attribution():
    dia = SpeakerDiarizer(embedder=None, transcriber=None, owner_vector=list(OWNER_V))
    assert await dia._identify(list(OWNER_V)) == OWNER_NAME
    assert await dia._identify([0.0] * 8) == UNKNOWN_SPEAKER_AR
    assert await dia._identify(GUESTS["stranger-far"]) == UNKNOWN_SPEAKER_AR


async def test_stage1_fish_only_purity():
    """Zero Edge-TTS footprint; Fish failure re-raises for honest text."""
    assert_no_edge()

    class _Rec(httpx.MockTransport):
        def __init__(self, status: int):
            self.status = status
            super().__init__(self._handle)

        def _handle(self, request: httpx.Request) -> httpx.Response:
            if self.status != 200:
                return httpx.Response(self.status, json={"error": {"message": "boom"}})
            return httpx.Response(200, content=b"ID3fake", headers={"Content-Type": "audio/mpeg"})

    pipe = FishFirstVoice(
        fish=FishVoice(model="m", voice_ref="r", api_key="k", transport=_Rec(429))
    )
    with pytest.raises(FishVoiceError):
        await pipe.synthesize("أهلاً عمر")
    with pytest.raises(FishVoiceError):
        await FishFirstVoice(fish=None).synthesize("أهلاً")


# --- Stage 2: RAG audit -------------------------------------------------------


def _query_terms(path: Path) -> str:
    """Deterministic self-grounding query: filename stem + longest body tokens."""
    stems = path.stem.replace("_", " ")
    tokens = sorted(
        {t.strip(".,:;!?()\"'").lower() for t in path.read_text(encoding="utf-8").split()},
        key=len,
        reverse=True,
    )
    long_tokens = [t for t in tokens if len(t) >= 6 and t.isalpha()][:4]
    return f"{stems} {' '.join(long_tokens)}"


def test_stage2_every_seed_doc_self_retrieves():
    """Each of the 16 knowledge seeds top-1 retrieves itself (read-only)."""
    files = sorted(SEED.rglob("*.md"))
    assert len(files) == 15, f"seed census drift: {len(files)}"
    index = VaultIndex(SEED)
    assert index.refresh_if_stale() is True
    misses = []
    for path in files:
        hits = index.query(_query_terms(path), top_k=1)
        if not hits or Path(hits[0].doc.path).name != path.name:
            got = hits[0].doc.path if hits else None
            misses.append(f"{path.name} -> {got}")
    assert not misses, f"retrieval misses: {misses}"


def test_stage2_drill_write_back_retrievable(tmp_path):
    """The Obsidian write leg: a drill note lands and cites back (tmp vault)."""
    token = "sara-drill-citation-زعفران"
    note = tmp_path / "Studies" / "drill-note.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(f"# Drill note\n\nGrounded finding: {token}\n", encoding="utf-8")
    index = VaultIndex(tmp_path)
    assert index.refresh_if_stale() is True
    hits = index.query(token, top_k=1)
    assert hits and hits[0].doc.path.endswith("drill-note.md")


# --- Stage 3: tools -----------------------------------------------------------


def _tool_names() -> list[str]:
    import re

    src = (REPO / "src" / "tools.py").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"async def _do_(\w+)", src)))


async def test_stage3_all_tools_degrade_honestly():
    """46/46 handlers answer with honest Arabic lines on zero backends: no crash,
    no silence, no raw exception surfacing."""
    names = _tool_names()
    assert len(names) == 46
    reg = ToolRegistry()
    failures = []
    for name in names:
        result = await reg.call(name, "test arg")
        if not isinstance(result, str) or not result or result == TOOL_FAIL_AR:
            failures.append(name)
    assert not failures, f"dishonest tools: {failures}"


class _Inbox:
    def __init__(self, messages):
        self.messages = messages

    async def peek_unread(self, max_n=25):
        return self.messages


class _Suite:
    def __init__(self, events):
        self.events = events

    async def list_events(self, start, end):
        return self.events

    async def list_tasks(self, tasklist="@default"):
        return []


class _Telemetry:
    async def report(self, **kwargs):
        return "المعالج 12% والرام 40% — الجهاز هادي"


async def test_stage3_composition_chain(tmp_path):
    """Email triage -> calendar check -> telemetry -> vault note -> voice gate:
    content tokens propagate end to end."""
    event_start = NOW + timedelta(hours=2)
    reg = ToolRegistry(
        inbox=_Inbox(
            [
                EmailMessage(
                    id="m1",
                    thread_id="t1",
                    from_email="laila@family.jo",
                    from_name="ليلى",
                    subject="عزومة عشا بكرا",
                    body_text="تعالي بكرا المسا",
                    received_at=NOW,
                )
            ]
        ),
        suite=_Suite(
            [
                CalendarEvent(
                    id="e1",
                    summary="عشا عائلي",
                    start=event_start,
                    end=event_start + timedelta(hours=2),
                )
            ]
        ),
        telemetry=_Telemetry(),
        tz=TZ,
        now_fn=lambda: NOW,
    )
    mail = await reg.call("gmail", "شو في ايميلات جديدة")
    assert "ليلى" in mail and "عزومة" in mail
    cal = await reg.call("calendar", "شو عندي مواعيد بكرا")
    assert "عشا عائلي" in cal
    tele = await reg.call("telemetry", "شو وضع الجهاز")
    assert "12%" in tele

    note = tmp_path / "Daily_Logs" / "2026-09-16.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        f"# Drill ledger\n\n- بريد: {mail.splitlines()[1]}\n- تقويم: {cal.splitlines()[1]}\n- جهاز: {tele}\n",
        encoding="utf-8",
    )
    hits = VaultIndex(tmp_path)
    assert hits.refresh_if_stale() is True
    found = hits.query("ليلى عزومة", top_k=1)
    assert found and "ليلى" in found[0].doc.body
    assert_no_edge()  # voice reply leg stays Fish-pure


# --- Stage 4: cognitive trace -------------------------------------------------


def test_stage4_natural_prompts_map_without_tool_names():
    assert deduce("شو في ايميلات جديدة").tool == "gmail"
    assert deduce("شو عندي مواعيد بكرا").tool == "calendar"
    assert deduce("شو وضع الجهاز").tool == "telemetry"
    assert deduce("افتحي المفكرة").tool == "launch"
    assert deduce("احكيلي نكتة").tool == "none"


def test_stage4_friction_math_matches_scale():
    trace = ReflectiveTrace()
    assert trace.penalty("gmail") == 0.0
    trace.record_outcome("gmail", False, "empty digest surfaced as fact")
    assert trace.penalty("gmail") == pytest.approx(0.30)
    trace.record_outcome("gmail", False, "repeated miss")
    assert trace.penalty("gmail") == pytest.approx(0.60)  # capped
    assert trace.friction_notes() == [
        "gmail: empty digest surfaced as fact",
        "gmail: repeated miss",
    ]


def test_stage4_failure_retry_self_corrects():
    """Hesitation/failure demotes the tool; a clean retry clears the ledger."""
    trace = ReflectiveTrace()
    first = deduce("شو في ايميلات جديدة", trace=trace)
    trace.record_outcome(first.tool, False, "wrong mailbox scope")
    assert trace.penalty(first.tool) > 0.0
    retry = deduce("شو في ايميلات جديدة", trace=trace)
    trace.record_outcome(retry.tool, True, "correct scope after correction")
    assert trace.penalty(retry.tool) == 0.0
    assert trace.friction_notes() == ["gmail: wrong mailbox scope"]


def test_stage4_horizon_adjacency():
    assert "brief" in expand_horizon("no_such_tool_xyz")
    assert isinstance(expand_horizon("gmail"), list)
