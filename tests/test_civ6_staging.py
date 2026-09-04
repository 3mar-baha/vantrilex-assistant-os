"""Pass-4 Civ6 module (v2.0 §3-ح): the fair-play LAN bridge + Discord voice
binding, STAGED per §7 (the game socket and the Discord bot token arrive with
the owner). What exists NOW is the contract core:

1. The TurnState wire schema (cities/units/production/science/diplomacy) —
   the JSON the in-game Lua script will export over localhost:9871.
2. The FAIR-PLAY ENFORCER (the module's soul): any field covered by Fog of
   War is structurally stripped from Sara's view — she CANNOT see it, ever;
   a decision request referencing hidden tiles is refused before it forms.
3. The Voice-to-Player binding: each friend's ECAPA voiceprint maps to their
   civilization (voice of X = Rome), persisted, with the Telegram secret
   lane kept SEPARATE from the public Discord lane.
4. Opponent dossiers path convention: Studies/Gaming/Civ6/Opponent_Dossiers/
   {Friend}.md + Tactical_Lessons.md (vault learning loop).

No game runs yet: every surface is staged + tested; the Lua script content
ships as a constant so the owner can drop it into a Civ6 mod folder day one."""

from __future__ import annotations

from src.skills.civ6 import (
    CIV6_STUDIES_DIR,
    LUA_BRIDGE_SCRIPT,
    TurnState,
    VisibleTurnView,
    bind_voice_to_civ,
    civ_of_speaker,
    strip_fogged,
)


def _full_state() -> TurnState:
    return TurnState(
        turn=42,
        acting_player="Sara",
        cities=[
            {
                "name": "بابل",
                "x": 30,
                "y": 22,
                "pop": 8,
                "fogged": False,
                "producing": "فرسان",
                "production_progress": 0.6,
            },
            {
                "name": "مدينة عدو",
                "x": 55,
                "y": 60,
                "pop": 12,
                "fogged": True,
                "producing": "?",
                "production_progress": None,
            },
        ],
        units=[
            {"id": 1, "type": "فارس", "x": 31, "y": 23, "fogged": False, "hp": 100},
            {"id": 2, "type": "؟", "x": 70, "y": 70, "fogged": True, "hp": None},
        ],
        science=120.5,
        diplomacy=[{"with_player": "خالد", "attitude": "war", "fogged": False}],
    )


def test_fog_strips_hidden_tiles_structurally():
    """The FAIR-PLAY ENFORCER: fogged cities/units/diplomacy never reach Sara."""
    view = strip_fogged(_full_state())
    assert isinstance(view, VisibleTurnView)
    names = [c["name"] for c in view.cities]
    assert "مدينة عدو" not in names  # fogged enemy city INVISIBLE
    assert "بابل" in names
    assert all(not u.get("fogged", True) for u in view.units) or len(view.units) == 1


def test_visible_view_carries_her_own_numbers():
    view = strip_fogged(_full_state())
    assert view.science == 120.5
    assert view.turn == 42


def test_voice_binding_persists_and_resolves():
    """صوت خالد = روما (the directive's example)."""
    bind_voice_to_civ("خالد", "روما")
    assert civ_of_speaker("خالد") == "روما"
    bind_voice_to_civ("أحمد", "مصر")
    assert civ_of_speaker("أحمد") == "مصر"
    assert civ_of_speaker("عمر") == "بابل"


def test_unbound_speaker_is_none_never_guessed():
    assert civ_of_speaker("شخص غريب") is None


def test_lua_script_exports_turn_state_and_calls_only_legal_api():
    """The staged in-game script: reads game state through LEGAL visibility
    APIs only (no fog peeking), JSON over localhost:9871."""
    assert "9871" in LUA_BRIDGE_SCRIPT
    assert "GetPlot" in LUA_BRIDGE_SCRIPT  # legal API surface
    for forbidden in ("RevealPlot", "SetVisible", "CHEAT", "debug"):
        assert forbidden not in LUA_BRIDGE_SCRIPT


def test_studies_paths_follow_the_directive():
    assert CIV6_STUDIES_DIR.startswith("Studies/Gaming/Civ6")
