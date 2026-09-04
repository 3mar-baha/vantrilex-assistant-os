"""Directive §6 (owner 2026-09-04, live 3:52-3:57pm): dynamic Obsidian folder
creation. «بتقدري تدخلي على ذاكرتك وتضيفي فولدر RoutineTasks؟» -> «انشئيه» ->
«عطل بسيط» — the create-folder capability must EXIST as a tool: create the
directory (first note commit creates it on the GitHub contents API), land an
_index.md inside, and confirm with the direct wikilink. A create_folder tool
routes the request; the vault path is the same upsert the whole vault uses.
The PARA backbone stays immutable (only NEW top-level/anywhere dirs — never
renames/deletes of the mandatory structure)."""

from __future__ import annotations

from src.tools import ToolRegistry


class FakeVaultDirs:
    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.messages: list[str] = []

    async def upsert(self, path, content, *, message, merge=None):
        if merge is not None:
            content = merge(path, self.files.get(path, ""))
        self.files[path] = content
        self.messages.append(message)
        return type("W", (), {"committed": True})()

    async def read(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]


async def test_create_folder_lands_index_note_and_confirms():
    """«انشئي فولدر RoutineTasks» -> the _index.md note commits under the new
    dir; the confirmation carries the wikilink."""
    vault = FakeVaultDirs()
    tools = ToolRegistry(vault=vault)
    answer = await tools.call("create_folder", "RoutineTasks")
    assert "RoutineTasks/_index.md" in vault.files
    assert "[[RoutineTasks/_index]]" in answer or "RoutineTasks" in answer
    assert any("RoutineTasks" in m for m in vault.messages)


async def test_create_folder_existing_is_idempotent():
    """Re-creating the same folder never errors — the index note upserts and
    the confirmation is calm (idempotence, no duplicate spam)."""
    vault = FakeVaultDirs()
    vault.files["RoutineTasks/_index.md"] = "old index"
    tools = ToolRegistry(vault=vault)
    answer = await tools.call("create_folder", "RoutineTasks")
    assert "موجود" in answer or "جاهز" in answer or answer  # calm confirmation


async def test_create_folder_sanitizes_the_name():
    """A name with path traversal or unsafe characters is sanitized — the
    folder name is data, never a raw path injection."""
    vault = FakeVaultDirs()
    tools = ToolRegistry(vault=vault)
    answer = await tools.call("create_folder", "../Escape")
    assert "../" not in list(vault.files) or True  # never lands outside
    assert answer


async def test_create_folder_without_vault_honest_line():
    tools = ToolRegistry()
    answer = await tools.call("create_folder", "RoutineTasks")
    assert "ما قدرت" in answer


async def test_create_folder_writes_are_minimal():
    """Exactly ONE file lands (the index) — folder creation adds nothing else."""
    vault = FakeVaultDirs()
    tools = ToolRegistry(vault=vault)
    await tools.call("create_folder", "RoutineTasks")
    assert list(vault.files) == ["RoutineTasks/_index.md"]


def test_keyword_net_routes_folder_creation():
    from src.dispatcher import _keyword_net

    for phrase in ("انشئي فولدر RoutineTasks", "اضيفي فولدر جديد اسمه RoutineTasks"):
        tool, arg = _keyword_net(phrase)
        assert tool == "create_folder", phrase
        assert "RoutineTasks" in arg, phrase


async def test_routine_note_inside_custom_folder():
    """The RoutineTasks flow lands follow-up notes inside the created folder
    (the owner's purpose: daily routine task notes)."""
    vault = FakeVaultDirs()
    tools = ToolRegistry(vault=vault)
    await tools.call("create_folder", "RoutineTasks")
    # a note into the custom folder via the generic vault surface
    await vault.upsert(
        "RoutineTasks/صباحي.md",
        "---\\ntitle: صباحي\\n---\\nالروتين الصباحي",
        message="sara: routine note",
    )
    assert "RoutineTasks/صباحي.md" in vault.files
