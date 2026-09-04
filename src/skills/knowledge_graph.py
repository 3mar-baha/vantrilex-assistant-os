"""Pass-2 knowledge graph (v2.0 §3-و): the wikilink web over the vault's markdown.
Nodes are note paths; edges are [[wikilinks]] (alias-aware, direction-preserved).
The graph is PURE: build from a {path: content} snapshot the caller fetches (the
vault client lists the tree and reads notes); queries are deterministic, zero-IO,
zero-LLM — the "why/relations" layer under the brain, not another model call.
Ponytail ceiling: linear rebuild per snapshot; fine for a personal vault (hundreds
of notes). Re-index incrementally if it ever grows past that."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

_WIKILINK_RE = re.compile(r"\[\[(?P<target>[^\]|]+?)(?:\|(?P<alias>[^\]]+))?\]\]")


@dataclass
class KnowledgeGraph:
    """Adjacency over vault notes. Outbound = links I emit; inbound = backlinks."""

    _outbound: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    _inbound: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    _nodes: set[str] = field(default_factory=set)

    # -- build --------------------------------------------------------------

    def add_note(self, path: str, content: str, *, resolver: dict[str, str] | None = None) -> None:
        """One note's links join the graph (deduped; frontmatter not special).
        `resolver` maps wikilink targets (often extension-less) to real note
        paths; unresolved targets still become nodes — a dangling link is an
        honest part of the web."""
        self._nodes.add(path)
        for match in _WIKILINK_RE.finditer(content):
            target = match.group("target").strip()
            if resolver:
                target = resolver.get(target, target)
            if not target or target == path:
                continue
            self._nodes.add(target)  # a linked-but-unread note is still a node
            self._outbound[path].add(target)
            self._inbound[target].add(path)

    # -- queries ------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(targets) for targets in self._outbound.values())

    def backlinks(self, path: str) -> list[str]:
        """Who references this note — the «مين بيحكي عن هالموضوع؟» answer."""
        return sorted(self._inbound.get(path, ()))

    def outbound(self, path: str) -> list[str]:
        """The links this note emits."""
        return sorted(self._outbound.get(path, ()))

    def inbound(self, path: str) -> list[str]:
        return self.backlinks(path)

    def neighbors(self, path: str) -> list[str]:
        """Union of in+out edges — the note's direct relation web."""
        return sorted(self._outbound.get(path, set()) | self._inbound.get(path, set()))

    def orphans(self) -> list[str]:
        """Notes with no links in either direction — invisible to the web."""
        return sorted(
            p for p in self._nodes if not self._outbound.get(p) and not self._inbound.get(p)
        )

    def has_edge(self, source: str, target: str) -> bool:
        return target in self._outbound.get(source, ())

    def brief_ar(self, path: str) -> str:
        """Compact DATA block for the tool lane: backlinks + neighbors. The
        model phrases it; these lines are the ground truth it must quote."""
        lines = [f"المفكرة: {path}"]
        back = self.backlinks(path)
        out = self.outbound(path)
        if back:
            lines.append("بيحكوا عنها: " + "، ".join(back))
        else:
            lines.append("ما حدا بيحكي عنها لهلق")
        if out:
            lines.append("هي بتحكي عن: " + "، ".join(out))
        return "\n".join(lines)


def build_graph(snapshot: dict[str, str]) -> KnowledgeGraph:
    """Index a {path: content} snapshot into the graph. Obsidian wikilinks may
    omit the .md extension — targets are resolved against the snapshot's real
    paths first, so [[Note]] and [[Note.md]] are the SAME node."""
    graph = KnowledgeGraph()
    # resolution map: both the bare stem suffix and the full path of every note
    resolve: dict[str, str] = {}
    for path in snapshot:
        resolve[path] = path
        if path.endswith(".md"):
            resolve.setdefault(path[:-3], path)  # shortest-wins: first note wins ties
    for path, content in snapshot.items():
        graph.add_note(path, content, resolver=resolve)
    return graph
