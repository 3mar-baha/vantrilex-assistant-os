"""Pass-2 knowledge graph (v2.0 §3-و): a wikilink graph over the vault's markdown —
nodes are notes, edges are [[wikilinks]] (either direction). Sara answers the WHY
questions: backlinks («مين بيحكي عن هالموضوع؟»), orphans, neighbors, and the relation
web between ideas — instead of blind text search. The index builds from a snapshot
of {path: content} fetched by the caller (the vault client lists + reads); the graph
itself is PURE — no I/O, no LLM, deterministic."""

from __future__ import annotations

from src.skills.knowledge_graph import KnowledgeGraph, build_graph

VAULT_SNAPSHOT = {
    "Daily_Logs/2026-09-01.md": (
        "---\ntitle: يوم الأول\ntags: [day]\n---\n"
        "حكينا اليوم عن [[02_Areas/Profile/User_Info|بروفايلي]] "
        "وبلشنا مشروع [[01_Projects/Sara-OS]]"
    ),
    "01_Projects/Sara-OS.md": (
        "---\ntitle: مشروع سارة\n---\n"
        "المرجع الأساسي [[02_Areas/Profile/User_Info]] والدراسة بتبدأ من "
        "[[Studies/Algorithms]]"
    ),
    "Studies/Algorithms.md": ("---\ntitle: الخوارزميات\n---\n\nشرح مبسط بدون روابط."),
    "Contacts/Khaled.md": ("---\ntitle: خالد\n---\n\nصاحب [[01_Projects/Sara-OS]] وصاحب مود Civ6."),
}


def _graph() -> KnowledgeGraph:
    return build_graph(VAULT_SNAPSHOT)


def test_build_graph_counts_nodes_and_edges():
    g = _graph()
    # 4 real notes + 1 dangling target (User_Info is linked but not in the
    # snapshot — an honest part of the web, its own node)
    assert g.node_count == 5
    # 5 outbound edges: DailyLog->User_Info, DailyLog->Sara-OS, Sara-OS->User_Info,
    # Sara-OS->Algorithms, Khaled->Sara-OS
    assert g.edge_count == 5


def test_backlinks_answer_who_references():
    g = _graph()
    back = g.backlinks("02_Areas/Profile/User_Info")
    assert "Daily_Logs/2026-09-01.md" in back
    assert "01_Projects/Sara-OS.md" in back


def test_neighbors_of_a_node():
    g = _graph()
    nbrs = g.neighbors("01_Projects/Sara-OS.md")
    assert "Studies/Algorithms.md" in nbrs
    assert "Contacts/Khaled.md" in nbrs  # inbound edge counts as a neighbor


def test_orphans_are_notes_without_links():
    g = _graph()
    assert g.orphans() == []  # every fixture note has at least one edge
    # a note nobody links and that links nobody IS an orphan — prove detection
    snapshot = dict(VAULT_SNAPSHOT)
    snapshot["Voice_Memos/isolated.md"] = "ملاحظة وحيدة بدون أي رابط"
    g2 = build_graph(snapshot)
    assert "Voice_Memos/isolated.md" in g2.orphans()


def test_wikilink_with_alias_resolves_to_target():
    """[[path|alias]] edges land on the PATH node — aliases never create nodes."""
    g = _graph()
    assert g.has_edge("Daily_Logs/2026-09-01.md", "02_Areas/Profile/User_Info")


def test_link_direction_is_outbound_from_source():
    g = _graph()
    assert "02_Areas/Profile/User_Info" in g.outbound("Daily_Logs/2026-09-01.md")
    assert "Daily_Logs/2026-09-01.md" in g.inbound("02_Areas/Profile/User_Info")


def test_graph_answers_as_arabic_brief():
    """The graph renders a compact Arabic answer block for the brain/tool lane:
    backlinks + neighbors — DATA, not prose (the model phrases it)."""
    g = _graph()
    brief = g.brief_ar("02_Areas/Profile/User_Info")
    assert "02_Areas/Profile/User_Info" in brief
    assert "Daily_Logs/2026-09-01.md" in brief


def test_unknown_node_is_honest_empty():
    g = _graph()
    assert g.backlinks("No/Such/Note.md") == []
    assert g.neighbors("No/Such/Note.md") == []
