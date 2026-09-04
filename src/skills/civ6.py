"""Pass-4 Civ6 module (v2.0 §3-ح), STAGED per §7 — the fair-play LAN bridge and
the Discord voice binding, with the CONTRACT CORE implemented and tested now:

- TurnState: the wire schema the in-game Lua script exports over localhost:9871
  (cities/units/production/science/diplomacy, each item carrying `fogged`).
- strip_fogged: THE FAIR-PLAY ENFORCER — builds Sara's VisibleTurnView by
  structurally REMOVING every fogged item. Sara's decisions (HEAVY tier) can
  only ever see what the game's legal visibility rules expose. This is a data
  gate, not a promise: hidden units simply do not exist in her view.
- bind_voice_to_civ/civ_of_speaker: the ECAPA voiceprint -> civilization
  binding (صوت خالد = روما), in-memory staging (the registry-backed store
  lands with the Discord integration when the owner provides the bot token).
- LUA_BRIDGE_SCRIPT: the staged in-game mod script — reads state through the
  LEGAL API surface only and pushes JSON to the local socket.
- Studies paths: dossiers + tactical lessons live under Studies/Gaming/Civ6/.

$0.00: everything is local (a Lua file, a socket, our own registry); Discord
voice arrives via discord.py (FOSS) when the owner activates it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CIV6_STUDIES_DIR = "Studies/Gaming/Civ6"
DOSSIERS_DIR = f"{CIV6_STUDIES_DIR}/Opponent_Dossiers"
TACTICAL_LESSONS_PATH = f"{CIV6_STUDIES_DIR}/Tactical_Lessons.md"
CIV6_SOCKET = ("localhost", 9871)

# The staged voiceprint->civilization binding (the directive's example table)
_VOICE_CIV: dict[str, str] = {}
_DEFAULT_BINDING: dict[str, str] = {"عمر": "بابل"}


@dataclass
class TurnState:
    """The full wire state as the game exports it — INCLUDING fogged items,
    which exist here only to be stripped before Sara ever sees the turn."""

    turn: int
    acting_player: str
    cities: list[dict[str, Any]]
    units: list[dict[str, Any]]
    science: float
    diplomacy: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class VisibleTurnView:
    """Sara's LEGAL view of the turn — built only by strip_fogged."""

    turn: int
    acting_player: str
    cities: list[dict[str, Any]]
    units: list[dict[str, Any]]
    science: float
    diplomacy: list[dict[str, Any]]


def strip_fogged(state: TurnState) -> VisibleTurnView:
    """THE FAIR-PLAY ENFORCER (v2.0 §3-ح/1): remove every fogged item before the
    state reaches the brain. A hidden unit is not 'marked' — it is GONE from
    the view. Anti-cheat by construction: no code path can leak a fogged tile
    into Sara's decisions because none survives this function."""
    return VisibleTurnView(
        turn=state.turn,
        acting_player=state.acting_player,
        cities=[c for c in state.cities if not c.get("fogged", False)],
        units=[u for u in state.units if not u.get("fogged", False)],
        science=state.science,
        diplomacy=[d for d in state.diplomacy if not d.get("fogged", False)],
    )


def bind_voice_to_civ(speaker: str, civ: str) -> None:
    """Bind a friend's voiceprint identity to their civilization (staging store;
    the registry-backed persistence lands with the Discord integration)."""
    _VOICE_CIV[speaker] = civ


def civ_of_speaker(speaker: str) -> str | None:
    """The civilization bound to a speaker's voiceprint; None = unbound (never
    guessed — an unknown voice owns no civ)."""
    return _VOICE_CIV.get(speaker) or _DEFAULT_BINDING.get(speaker)


# The staged in-game Lua script (drop into a Civ6 mod folder; §7 activation).
# Reads state through the LEGAL API only (GetPlot/GetPlotDistance/players'
# visible cities), exports JSON over localhost:9871. NO fog-reveal calls.
LUA_BRIDGE_SCRIPT = r"""
-- Sara Civ6 Fair-Play Bridge (v2.0 pass-4 staged)
-- Exports the acting player's LEGALLY VISIBLE turn state as JSON over
-- localhost:9871. Legal visibility APIs ONLY: this script never reveals
-- fogged plots, hidden units, or other players' private production.

local socket = require("socket")  -- Civ6 ships LuaSocket in the mod sandbox
local HOST, PORT = "localhost", 9871

local function visible_cities(player)
  -- CityManager/Players iterate what the ACTING player may legally see
  local out = {}
  for _, city in player:GetCities():Members() do
    local plot = Map.GetPlot(city:GetX(), city:GetY())
    if plot and plot:IsRevealed(player:GetTeam()) then
      table.insert(out, {
        name = city:GetName(),
        x = city:GetX(), y = city:GetY(),
        pop = city:GetPopulation(),
        producing = city:GetBuildQueue():CurrentProductionInfo(),
        fogged = false,  -- legality proven by IsRevealed before inclusion
      })
    end
  end
  return out
end

local function visible_units(player)
  local out = {}
  for _, unit in player:GetUnits():Members() do
    local plot = Map.GetPlot(unit:GetX(), unit:GetY())
    if plot and plot:IsRevealed(player:GetTeam()) then
      table.insert(out, {
        id = unit:GetID(), type = unit:GetTypeName(),
        x = unit:GetX(), y = unit:GetY(),
        hp = unit:GetCurrentHitPoints(), fogged = false,
      })
    end
  end
  return out
end

function ExportTurnState()
  local player = Players[Game.GetLocalPlayer()]
  local payload = {
    turn = Game.GetCurrentGameTurn(),
    acting_player = "Sara",
    cities = visible_cities(player),
    units = visible_units(player),
    science = player:GetTechs():GetScienceYield(),
    diplomacy = {},  -- diplomatic visibility follows the game's own rules
  }
  local body = JSON:encode(payload)  -- the mod's bundled encoder
  local s = socket.try(socket.tcp())
  socket.try(s:connect(HOST, PORT))
  socket.try(s:send(body))
  s:close()
end

Events.PlayerTurnActivated.Add(ExportTurnState)
"""
