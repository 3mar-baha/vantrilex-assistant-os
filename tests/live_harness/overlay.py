"""OverlayVault: copy-on-write vault seam for harness runs.

Writes always land under the shadow root (parents created); reads check the
shadow first and fall back to the real vault. Production call sites are
untouched — only harness bootstraps wrap paths in this resolver.
"""

from __future__ import annotations

from pathlib import Path


class OverlayVault:
    def __init__(self, real_root: str | Path, shadow_root: str | Path) -> None:
        self._real = Path(real_root)
        self._shadow = Path(shadow_root)

    def _rel(self, relpath: str) -> Path:
        cleaned = str(relpath or "").replace("\\", "/").strip("/")
        if not cleaned or cleaned in (".", "..") or ".." in cleaned.split("/"):
            raise ValueError(f"refusing unsafe overlay path: {relpath!r}")
        return Path(cleaned)

    def resolve(self, relpath: str) -> Path:
        """Readable location: shadow copy when present, else the real file."""
        rel = self._rel(relpath)
        shadowed = self._shadow / rel
        return shadowed if shadowed.is_file() else self._real / rel

    def read_text(self, relpath: str) -> str:
        target = self.resolve(relpath)
        if not target.is_file():
            raise FileNotFoundError(str(target))
        return target.read_text(encoding="utf-8")

    def write_text(self, relpath: str, text: str) -> Path:
        """Always shadow: the real vault is never written through this seam."""
        target = self._shadow / self._rel(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text or "", encoding="utf-8")
        return target

    def shadowed(self) -> list[str]:
        """Session write manifest, relative POSIX paths, sorted."""
        if not self._shadow.exists():
            return []
        return sorted(
            p.relative_to(self._shadow).as_posix() for p in self._shadow.rglob("*") if p.is_file()
        )
