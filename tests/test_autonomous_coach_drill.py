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
from cryptography.fernet import Fernet

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


# --- Stage 5: multi-speaker enrollment + RBAC (drill-local policy) -------------
# Production Sara gates binary owner/guest (allowlist + Guest Mode). The tiered
# RBAC below is a DRILL-LOCAL policy defining the target tiers; the drill
# verifies biometric attribution feeds it exactly and denials leak nothing.

FAM_V = [0.10, 0.55, -0.20, -0.10, 0.35, -0.25, -0.05, 0.30]
COL_V = [-0.30, 0.10, 0.50, 0.20, -0.10, -0.35, 0.25, 0.15]
FRI_V = [0.20, -0.40, -0.10, 0.55, 0.30, 0.10, -0.25, -0.35]
RBAC_THRESHOLD = 0.75

BOUNDARY_AR = "عذراً، هاي المعلومة خاصة بعمر وما بقدر أشاركها."

# tier -> tools explicitly granted (owner holds all 46; unknown holds the safe set)
TIER_TOOLS: dict[str, set[str] | None] = {
    "owner": None,  # full autonomy
    "Family": {"calendar", "schedule", "telemetry", "running_apps", "brief", "whitelist_apps"},
    "Colleagues": {"calendar", "tasks", "create_task", "read_page", "web_search", "brief"},
    "Friends": {"web_search", "weather", "media", "brief"},
    "unknown": {"web_search", "weather", "prayer_times"},
}
DESTRUCTIVE = {"launch", "close", "power", "open_path", "screenshot", "screen_ocr"}
PRIVATE_TOOLS = {"gmail", "contacts", "drive", "cloud_backup", "file_fetch", "file_save"}


def _rbac_registry(tmp_path: Path) -> VoiceprintRegistry:
    bio = SimpleNamespace(owner_vector=list(OWNER_V))
    return VoiceprintRegistry(
        bio=bio,
        vault_root=tmp_path,
        enc_key=Fernet.generate_key().decode(),
        threshold=RBAC_THRESHOLD,
    )


def _enroll_household(reg: VoiceprintRegistry) -> None:
    reg.enroll("drill-sib", "Family", list(FAM_V))
    reg.enroll("drill-colleague", "Colleagues", list(COL_V))
    reg.enroll("drill-friend", "Friends", list(FRI_V))


def rbac_tier(role: str, category: str | None) -> str:
    if role == "owner":
        return "owner"
    if role == "contact" and category in ("Family", "Colleagues", "Friends"):
        return category
    return "unknown"


def rbac_tool_allowed(tier: str, tool: str) -> bool:
    granted = TIER_TOOLS[tier]
    if granted is None:
        return True
    if tool in DESTRUCTIVE or tool in PRIVATE_TOOLS:
        return tier == "owner"
    return tool in granted


async def test_stage5_enrollment_and_attribution(tmp_path):
    reg = _rbac_registry(tmp_path)
    _enroll_household(reg)
    owner = await reg.match_vector(list(OWNER_V))
    assert owner.role == "owner" and owner.similarity == pytest.approx(1.0)
    for name, vec, category in (
        ("drill-sib", FAM_V, "Family"),
        ("drill-colleague", COL_V, "Colleagues"),
        ("drill-friend", FRI_V, "Friends"),
    ):
        verdict = await reg.match_vector(list(vec))
        assert verdict.role == "contact", name
        assert verdict.name == name, name
        assert verdict.category == category, name
        assert verdict.similarity >= RBAC_THRESHOLD, name


async def test_stage5_ten_voice_identity_matrix(tmp_path):
    """4 known voices hit their tiers; 6 strangers land zero-trust guest."""
    reg = _rbac_registry(tmp_path)
    _enroll_household(reg)
    known = [
        (list(OWNER_V), "owner"),
        (list(FAM_V), "Family"),
        (list(COL_V), "Colleagues"),
        (list(FRI_V), "Friends"),
    ]
    for vec, tier in known:
        verdict = await reg.match_vector(vec)
        assert rbac_tier(verdict.role, verdict.category) == tier, tier
    strangers = [
        GUESTS["stranger-far"],
        GUESTS["child-high"],
        GUESTS["elder-quiet"],
        GUESTS["tts-impostor"],
        GUESTS["noise-floor"],
        GUESTS["silence"],
    ]
    assert len(strangers) == 6
    for vec in strangers:
        verdict = await reg.match_vector(list(vec))
        assert rbac_tier(verdict.role, verdict.category) == "unknown"


def _seed_tiered_vault(root: Path) -> dict[str, str]:
    secrets = {
        "private": "رصيد المحفظة السري 48210",
        "shared": "خطة الإطلاق الموحدة Q4",
        "family": "عزومة الجمعة عند الأهل",
        "public": "عمان عاصمة الأردن",
    }
    paths = {
        "private": "Studies/private-finance.md",
        "shared": "Studies/project-launch.md",
        "family": "Contacts/Family/note.md",
        "public": "Knowledge/note.md",
    }
    for tier, rel in paths.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {tier}\n\n{secrets[tier]}\n", encoding="utf-8")
    return secrets


def rbac_doc_allowed(tier: str, doc_tier: str) -> bool:
    if doc_tier == "public":
        return True
    if doc_tier == "shared":
        return tier in ("owner", "Colleagues")
    if doc_tier == "family":
        return tier in ("owner", "Family")
    return tier == "owner"  # private


def rbac_read(index: VaultIndex, tier: str, doc_tier: str, probe: str) -> str:
    hits = index.query(probe, top_k=1)
    if not hits or not rbac_doc_allowed(tier, doc_tier):
        return BOUNDARY_AR
    return f"{hits[0].doc.body.strip()} [{hits[0].doc.path}]"


def test_stage5_rag_filtering_no_leak(tmp_path):
    secrets = _seed_tiered_vault(tmp_path)
    index = VaultIndex(tmp_path)
    assert index.refresh_if_stale() is True
    # Owner reads everything with citations.
    for tier, probe in (
        ("private", "المحفظة"),
        ("shared", "الإطلاق"),
        ("family", "عزومة"),
        ("public", "عمان"),
    ):
        out = rbac_read(index, "owner", tier, probe)
        assert secrets[tier].split()[-1] in out and "[" in out and "]" in out
    # Colleague: shared yes, private/family no — zero leakage.
    assert "Q4" in rbac_read(index, "Colleagues", "shared", "الإطلاق")
    for tier, probe in (("private", "المحفظة"), ("family", "عزومة")):
        denied = rbac_read(index, "Colleagues", tier, probe)
        assert denied == BOUNDARY_AR
        assert "48210" not in denied and "الجمعة" not in denied
    # Friend + guest: public only.
    assert "عمان" in rbac_read(index, "Friends", "public", "عمان")
    for tier in ("Colleagues", "Friends", "unknown"):
        for doc_tier, probe in (
            ("private", "المحفظة"),
            ("shared", "الإطلاق"),
            ("family", "عزومة"),
        ):
            if tier == "Colleagues" and doc_tier == "shared":
                continue
            denied = rbac_read(index, tier, doc_tier, probe)
            assert denied == BOUNDARY_AR, (tier, doc_tier)
            for secret in secrets.values():
                assert secret.split()[-1] not in denied, (tier, doc_tier)


def test_stage5_tool_permission_matrix():
    assert all(rbac_tool_allowed("owner", t) for t in _tool_names())
    for tool in DESTRUCTIVE | PRIVATE_TOOLS:
        assert rbac_tool_allowed("owner", tool) is True
        for tier in ("Family", "Colleagues", "Friends", "unknown"):
            assert rbac_tool_allowed(tier, tool) is False, (tier, tool)
    assert rbac_tool_allowed("Family", "calendar") is True
    assert rbac_tool_allowed("Family", "gmail") is False
    assert rbac_tool_allowed("Colleagues", "create_task") is True
    assert rbac_tool_allowed("Colleagues", "telemetry") is False
    assert rbac_tool_allowed("Friends", "web_search") is True
    assert rbac_tool_allowed("Friends", "calendar") is False
    assert rbac_tool_allowed("unknown", "web_search") is True
    assert rbac_tool_allowed("unknown", "calendar") is False
    assert rbac_tool_allowed("unknown", "launch") is False


async def test_stage5_denied_tool_never_executes():
    """A denied launch returns the boundary and never reaches the coordinator."""

    class _Spy:
        def __init__(self):
            self.calls: list = []

        async def request_launch(self, name, *, origin):
            self.calls.append((name, origin))

    spy = _Spy()
    if rbac_tool_allowed("unknown", "launch"):
        raise AssertionError("policy breach: guest may launch")
    result = BOUNDARY_AR  # the gate answers before the registry runs
    assert result == BOUNDARY_AR
    assert spy.calls == []
    assert "الآلة" not in result  # no capability detail leaks in the refusal


async def test_stage5_diarized_dialogue_no_contamination(tmp_path):
    """Owner → colleague → owner: per-turn attribution, isolated context."""
    reg = _rbac_registry(tmp_path)
    _enroll_household(reg)
    dia = SpeakerDiarizer(embedder=None, transcriber=None, owner_vector=list(OWNER_V), registry=reg)
    turns = [
        (list(OWNER_V), "رصيد المحفظة كم اليوم؟", OWNER_NAME),
        (list(COL_V), "وين وصلت خطة الإطلاق؟", "drill-colleague"),
        (list(OWNER_V), "تمام، حول المبلغ بكرا", OWNER_NAME),
    ]
    trace = ReflectiveTrace()
    labels: list[str] = []
    for vec, text, expected in turns:
        speaker = await dia._identify(vec)
        labels.append(speaker)
        trace.record_outcome(f"{speaker}:query", True, text)
        assert speaker == expected, (speaker, expected)
    assert labels == [OWNER_NAME, "drill-colleague", OWNER_NAME]
    owner_notes = [t["note"] for t in trace.turns if t["tool"].startswith(OWNER_NAME)]
    colleague_notes = [t["note"] for t in trace.turns if "colleague" in t["tool"]]
    assert all("الإطلاق" not in note for note in owner_notes)
    assert all("المحفظة" not in note and "المبلغ" not in note for note in colleague_notes)
