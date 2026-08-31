"""Sprint-3 §3.1b AC12: story extractor — daily narration files to contact
dossiers AND the daily log; ambiguous category holds for owner confirmation;
Ignored/ mentions never receive writes. LLM output is DATA (fast-tier, JSON)."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from helpers_vault import FakeGitHub

from src.gateway import Tier
from src.skills.social_graph import SocialGraph
from src.vault import VaultClient

AMMAN = ZoneInfo("Asia/Amman")
MENTIONED_AT = datetime(2026, 8, 31, 20, 15, tzinfo=AMMAN)
NARRATION = "اليوم اجتمعت مع أحمد ورتبنا خطة الربع، وكلمت محمد بالتلفون."
ENTITIES_JSON = json.dumps(
    [
        {
            "name": "أحمد",
            "action_summary": "اجتماع وترتيب خطة الربع",
            "category_inferred": "Colleagues",
        },
        {"name": "محمد", "action_summary": "مكالمة هاتفية", "category_inferred": None},
        {"name": "زيزي", "action_summary": "ثلاث مكالمات", "category_inferred": "Ignored"},
    ],
    ensure_ascii=False,
)

DOSSIER_AHMAD = (
    "---\nname: أحمد\ncategory: Colleagues\ncreated: 2026-01-10\n---\n\n"
    "# أحمد — Colleagues\n\n## Interaction Log\n"
)


class FakeBrain:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[list[dict]] = []
        self.kwargs: list[dict] = []

    async def chat(self, messages, **kwargs):
        self.calls.append(messages)
        self.kwargs.append(kwargs)
        return self.reply


def _graph(gh: FakeGitHub, reply: str = ENTITIES_JSON) -> tuple[FakeBrain, SocialGraph]:
    session = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
    vault = VaultClient(
        "owner/vault-repo", "your-github-test-pat-abcdef0123456789", session=session
    )
    brain = FakeBrain(reply)
    return brain, SocialGraph(vault=vault, brain=brain, tz=AMMAN)


async def test_daily_narration_files_actions_to_contacts_and_log():
    """AC12: fixture narration -> entities filed as dated sections in BOTH the
    correct dossier and Daily_Logs/YYYY-MM-DD.md; ambiguous mention holds for
    owner confirmation (no write); Ignored/ mention produces NO dossier write."""
    gh = FakeGitHub()
    gh.seed("Contacts/Colleagues/أحمد.md", DOSSIER_AHMAD)
    brain, graph = _graph(gh)

    mentions = await graph.extract_entities(NARRATION, now=MENTIONED_AT)
    assert [m.name for m in mentions] == ["أحمد", "محمد", "زيزي"]
    assert mentions[0].mentioned_at == MENTIONED_AT
    assert mentions[1].category_inferred is None  # ambiguous => owner confirms first
    assert brain.kwargs and brain.kwargs[0].get("tier") == Tier.FAST  # one FAST-tier call

    results = await graph.file_action(mentions[0])
    assert [r.path for r in results] == [
        "Contacts/Colleagues/أحمد.md",
        "Daily_Logs/2026-08-31.md",
    ]
    dossier = gh.objects["Contacts/Colleagues/أحمد.md"][1]
    assert "## 2026-08-31" in dossier and "اجتماع وترتيب خطة الربع" in dossier
    log = gh.objects["Daily_Logs/2026-08-31.md"][1]
    assert "أحمد" in log and "اجتماع وترتيب خطة الربع" in log

    puts_after_filing = len(gh.puts)
    assert await graph.file_action(mentions[1]) == []  # ambiguous: held, zero writes
    assert all("محمد" not in path for path in gh.objects)
    assert await graph.file_action(mentions[2]) == []  # Ignored/: tracking false
    assert len(gh.puts) == puts_after_filing


async def test_extractor_garbage_output_returns_empty():
    """Error mode: LLM output is DATA — unparseable reply yields [], loudly."""
    gh = FakeGitHub()
    _brain, graph = _graph(gh, reply="س 史 <<<not json>>>")
    assert await graph.extract_entities("نص عشوائي", now=MENTIONED_AT) == []
