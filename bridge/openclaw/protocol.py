"""OpenClaw shared wire schemas (Phase 2) — CANONICAL definitions.

The tunnel boundary speaks ONLY these Pydantic shapes. `src/openclaw/`
re-exports them (Single-Brain policy: one vocabulary, two importers).
Zero src/bridge imports here — this module must load on the bare PC
interpreter with nothing but pydantic.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class OpKind(StrEnum):
    """Closed action enum (sandcastle invariant): an action this enum cannot
    name cannot travel the wire — there is deliberately NO run_command,
    shell, exec, or script member. New members need an ADR + breaker row."""

    FOCUS = "focus"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE_TEXT = "type_text"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    NAVIGATE = "navigate"
    EXTRACT = "extract"
    SCREENSHOT = "screenshot"
    INSPECT_TREE = "inspect_tree"


class ElementHandle(BaseModel):
    """One resolved UI element: stable id, accessible role/name, optional
    bounding box + hotkey accelerator, and which perception tier produced it."""

    id: str
    role: str
    name: str
    bbox: tuple[int, int, int, int] | None = None
    hotkey: str | None = None
    source: Literal["uia", "dom", "vision"] = "uia"


class Op(BaseModel):
    """One mechanical step. `reversibility` is the CORE's claim only — the
    daemon-side breaker recomputes the verdict and ignores the claim."""

    op: OpKind
    target: str | None = None
    value: str | None = None
    reversibility: Literal["reversible", "irreversible"] = "reversible"
    verify: str | None = None


class ActionDAG(BaseModel):
    """A planned turn: goal, ordered ops, task weight, stable plan id."""

    goal: str
    ops: list[Op] = Field(default_factory=list)
    weight: int = 1
    plan_id: str


class ActionTranscript(BaseModel):
    """The audit artifact: what ran, per-op observations, every audit code."""

    plan_id: str
    success: bool
    observations: list[dict] = Field(default_factory=list)
    audit_codes: list[str] = Field(default_factory=list)
