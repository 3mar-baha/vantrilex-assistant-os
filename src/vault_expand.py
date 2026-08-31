"""Dynamic vault taxonomy expansion (sprint-3 §3.2, master directive M5).

The vault taxonomy is dynamic: new domains grow sub-directories + tag ontologies as
emergent structure, landed as ONE auditable commit through ``VaultClient.commit_files``.
The PARA backbone is expansion-only — this module has no delete/move code path, and any
request touching a backbone name is refused pre-flight (zero API calls). Vault state IS
the memory: existence is read from the backend, never cached locally.
"""

from __future__ import annotations

from datetime import UTC, datetime

import yaml
from loguru import logger
from pydantic import BaseModel

from src.vault import (
    INDEX_NOTE_NAME,
    PARA,
    VaultClient,
    _sanitize_component,
    write_frontmatter,
    zettel_link,
)

PARA_BACKBONE = frozenset(
    {
        "01_Projects/",
        "02_Areas/",
        "03_Resources/",
        "04_Archives/",
        "Contacts/",
        "Call_Transcripts/",
        "Studies/",
        "Voice_Memos/",
        "Daily_Logs/",
    }
)


class BackboneImmutableError(RuntimeError):
    """The requested change touches the expansion-only PARA backbone."""


class ExpansionResult(BaseModel):
    created_dirs: list[str]
    created_files: list[str]
    commit_sha: str


def _dir_components(entry: str) -> list[str]:
    """Split a relative dir entry into sanitized components; empties refused."""
    comps = [_sanitize_component(part) for part in entry.split("/")]
    if any(not comp for comp in comps):
        raise ValueError(f"invalid expansion dir entry (residual separator?): {entry!r}")
    return comps


class VaultExpander:
    def __init__(self, vault: VaultClient, *, backbone: frozenset[str] = PARA_BACKBONE):
        self._vault = vault
        self._backbone = backbone

    async def expand(self, domain: str, *, dirs: list[str], tags: list[str]) -> ExpansionResult:
        title = _sanitize_component(domain)
        if f"{title}/" in self._backbone:
            raise BackboneImmutableError(
                f"{title!r} is PARA backbone — expansion-only, never renamed/deleted/moved"
            )
        if not dirs and not tags:
            raise ValueError("expansion needs at least one directory or one tag")
        root = f"{PARA['projects']}/{title}"  # para_path() is note-shaped (.md); dirs need the bare root

        dir_paths = [root]
        for entry in dirs:
            path = root
            for comp in _dir_components(entry):
                path = f"{path}/{comp}"
                if path not in dir_paths:
                    dir_paths.append(path)

        changes: dict[str, str] = {}
        created_dirs: list[str] = []
        created_files: list[str] = []
        home = zettel_link(title)
        for dir_path in dir_paths:
            index_path = f"{dir_path}/{INDEX_NOTE_NAME}"
            try:
                await self._vault.read(index_path)
                continue  # existing dirs/notes are left untouched (idempotency)
            except FileNotFoundError:
                pass
            name = dir_path.rsplit("/", 1)[-1]
            created_dirs.append(dir_path)
            created_files.append(index_path)
            changes[index_path] = write_frontmatter(
                {"type": "vault-index", "dir": dir_path}, f"# {name}\n\n{home}\n"
            )

        tags_path = f"{root}/_tags.yaml"
        try:
            await self._vault.read(tags_path)
        except FileNotFoundError:
            created_files.append(tags_path)
            changes[tags_path] = yaml.safe_dump(
                {"domain": title, "created": datetime.now(UTC), "tags": list(tags)},
                allow_unicode=True,
                sort_keys=False,
            )

        if not changes:
            return ExpansionResult(created_dirs=[], created_files=[], commit_sha="")
        sha = await self._vault.commit_files(changes, message=f"sara: expand vault — {title}")
        logger.info(
            "vault expanded: domain={domain} files={count}", domain=title, count=len(changes)
        )
        return ExpansionResult(
            created_dirs=created_dirs, created_files=created_files, commit_sha=sha
        )
