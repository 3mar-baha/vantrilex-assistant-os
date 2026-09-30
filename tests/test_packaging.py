"""Sprint-4 §4.4b: the ONE container (ADR-15) — Dockerfile/Space contract, secrets
kept out of the build context, single-tree supervision of OmniRoute + core, the
keep-alive cron, the durable-state audit, and the v1.0 no-live-call artifact grep.

Artifacts are asserted by content; the supervisor and the $PORT entry are exercised
for behavior with real child processes and a real socket."""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import supervise

PY = sys.executable


def _read(*parts: str) -> str:
    return (REPO.joinpath(*parts)).read_text(encoding="utf-8")


def _loop_child(alive: Path) -> list[str]:
    """A child that writes its marker then loops until killed, proving liveness."""
    return [
        PY,
        "-c",
        (
            "import pathlib, time\n"
            f"a = pathlib.Path({str(alive)!r})\n"
            "while True:\n"
            "    a.write_text('alive')\n"
            "    time.sleep(0.05)\n"
        ),
    ]


def _exit_child(marker: Path, delay_s: float, code: int) -> list[str]:
    return [
        PY,
        "-c",
        (
            "import pathlib, sys, time\n"
            f"m = pathlib.Path({str(marker)!r})\n"
            f"time.sleep({delay_s})\n"
            "m.write_text('started')\n"
            f"sys.exit({code})\n"
        ),
    ]


async def test_supervision_both_children_pinned(tmp_path):
    """AC3 — both configured children launch; the FIRST exit propagates as the
    container exit code; the surviving child is torn down (no half-alive tree)."""
    alive_a = tmp_path / "core.alive"
    marker_b = tmp_path / "omniroute.started"
    children = {
        "core": _loop_child(alive_a),
        "omniroute": _exit_child(marker_b, delay_s=1.0, code=3),
    }
    code = await supervise.supervise(children)
    assert marker_b.exists(), "the omniroute child never launched"
    assert alive_a.exists(), "the core child never launched"
    assert code == 3
    frozen = (alive_a.read_text(), alive_a.stat().st_mtime)
    await asyncio.sleep(0.5)
    assert (alive_a.read_text(), alive_a.stat().st_mtime) == frozen, (
        "surviving child was not torn down — half-alive tree"
    )


async def test_supervision_cancel_leaves_no_orphans(tmp_path):
    """AC3 — cancelling the supervisor tears down BOTH children."""
    alive_a = tmp_path / "a.alive"
    alive_b = tmp_path / "b.alive"
    task = asyncio.create_task(
        supervise.supervise({"core": _loop_child(alive_a), "omniroute": _loop_child(alive_b)})
    )
    await asyncio.sleep(0.7)
    assert alive_a.exists() and alive_b.exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    frozen_a = (alive_a.read_text(), alive_a.stat().st_mtime)
    frozen_b = (alive_b.read_text(), alive_b.stat().st_mtime)
    await asyncio.sleep(0.5)
    assert (alive_a.read_text(), alive_a.stat().st_mtime) == frozen_a, "orphaned core child"
    assert (alive_b.read_text(), alive_b.stat().st_mtime) == frozen_b, "orphaned gateway child"


def test_supervise_requires_both_children():
    """Support — the supervisor refuses to boot without the OmniRoute command; the
    core command has a sane default (python -m src.main)."""
    with pytest.raises(ValueError):
        supervise.build_children({})
    children = supervise.build_children({"OMNIROUTE_CMD": "npm start --prefix scripts/omniroute"})
    assert set(children) == {"omniroute", "core"}
    assert "src.main" in " ".join(children["core"])
    assert children["omniroute"][0] == "npm"


def test_dockerfile_contract():
    """AC1 — base pin, ffmpeg, non-root USER sara, TZ, $PORT-aware supervised entry;
    v1.0.1: a Node >=22 runtime + global omniroute install (the gateway is an npm
    app — OmniRoute engines require node >=22.22) with a zero-config default command."""
    dockerfile = _read("Dockerfile")
    assert "FROM python:3.12-slim" in dockerfile
    assert "ffmpeg" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "COPY requirements.txt" in dockerfile
    for tree in ("src/", "common/", "scripts/omniroute/", "04_Resources/"):
        assert f"COPY {tree}" in dockerfile, f"the image must carry {tree}"
    assert "useradd" in dockerfile and "sara" in dockerfile
    assert re.search(r"^USER sara\s*$", dockerfile, re.MULTILINE), "container must run non-root"
    assert "ENV TZ=Asia/Amman" in dockerfile
    assert "$PORT" in dockerfile, "the Space contract: the container listens on $PORT"
    assert re.search(r'^CMD \["python", "scripts/supervise\.py"\]$', dockerfile, re.MULTILINE), (
        "entrypoint is the supervised tree, not a bare child"
    )
    assert "setup_24.x" in dockerfile, (
        "OmniRoute engines demand node >=22.22 — Debian's stock nodejs is far older; "
        "the image must install Node 24 via NodeSource"
    )
    assert "npm install -g /app/scripts/omniroute" in dockerfile, (
        "the vendored clone pins the gateway version and must be installed globally"
    )
    assert 'ENV OMNIROUTE_CMD="omniroute run"' in dockerfile, (
        "zero-config default: the supervisor finds its gateway command without variables"
    )


def test_dockerignore_keeps_secrets_out_of_context():
    """AC2 — secrets, tests, docs and local state never enter the build context; the
    two runtime needs are re-included AFTER the scripts/ exclusion (order matters)."""
    lines = [
        line.strip()
        for line in _read(".dockerignore").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    required = [
        ".git",
        ".venv",
        ".env",
        ".env.*",
        "tests/",
        "docs/",
        ".github/",
        ".claude/",
        ".ingest/",
        "*.docx",
        "config/google_oauth_client.json",
        "*.session",
        "__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".coverage",
        "htmlcov/",
        "scripts/",
    ]
    for entry in required:
        assert entry in lines, f".dockerignore must exclude {entry}"
    assert lines.index("!scripts/supervise.py") > lines.index("scripts/")
    assert lines.index("!scripts/omniroute/") > lines.index("scripts/")


def test_docker_build_succeeds():
    """AC4 — the image builds on the dev machine. Skips when docker is absent or the
    OmniRoute clone (external repo — RUNBOOK §1) has not been fetched."""
    if shutil.which("docker") is None:
        pytest.skip("docker not installed on this machine")
    if not (REPO / "scripts" / "omniroute").is_dir():
        pytest.skip("OmniRoute clone not fetched beside scripts/omniroute (RUNBOOK §1)")
    result = subprocess.run(
        ["docker", "build", "-q", str(REPO)],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_keepalive_cron_contract():
    """AC5 — keep-alive workflow pings the Space /health every 10 minutes, loudly."""
    yml = _read(".github", "workflows", "keepalive.yml")
    assert re.search(r"cron:\s*['\"]?\*/10 \* \* \* \*['\"]?", yml), (
        "keep-alive must run every 10 minutes"
    )
    assert "/health" in yml, "the ping targets the Space health endpoint"
    assert "exit 1" in yml or "::error::" in yml, "failures must be loud, not silent"


def test_durable_state_only_in_vault():
    """AC6 — every disk write in runtime code targets an ADR-15-justified store (the
    vault mirror, the OAuth token cache, sealed credentials, re-derivable caches). A
    new write site must join the allowlist with a justification or route through
    the vault client."""
    disk_write = re.compile(r"write_text\(|write_bytes\(|\.open\([^)]*['\"][wa]")
    justified = {
        "src/gmail.py": "sweep-state cache — re-derivable, settings-pathed",
        "src/google_auth.py": "OAuth token cache (ADR-15 explicit allowlist member)",
        "src/app_indexer.py": "config/whitelist.json merge — git-tracked owner config (v1.0.2), not durable state",
        "src/evolution.py": "self-evolution backlog State/evolution_backlog.jsonl (blueprint §3.1) — the ADR-15 vault-mirror State/ dir, already a mandatory scaffold entry. Deliberately NOT routed through VaultClient.upsert: upsert rewrites the whole document, and a rewrite destroys the torn-line residue the append-only contract exists to preserve. NOT covered by .gitignore — flagged in docs/10-CHECKPOINT.md as an open item",
        "src/skills/evening_journaler.py": "journal state + Daily_Logs ledger (vault mirror)",
        "src/skills/proactive_outreach.py": "outreach cadence state (cooldown/cap) — same vault-mirror State/ pattern as the journaler (remediation 3.2)",
        "src/skills/social_enrollment.py": "sealed voiceprint vectors + dossiers (encrypted at rest)",
        "src/skills/voice_biometric_auth.py": "sealed owner voiceprint (ADR-17) + tempfile model cache",
        "src/skills/voice_to_vault_transcriber.py": "Voice_Memos notes — this IS the vault",
        "bridge/app_sessions.py": "PC-local per-minute usage JSON (v2.0 pass-1 §3-د/3) — machine-scoped telemetry state under data/app_sessions/, describes the PC it lives on, gitignored like vault/",
        "src/task_orchestrator.py": "reminder timers state (§5 2026-09-04) — vault-mirror State/ pattern, gitignored; re-armed on restart so a registered reminder can never vanish",
        "src/vault.py": "04_Resources boot mirror into the vault (audit 2026-09-14) — this IS the vault mirror VaultIndex reads; idempotent, never deletes",
    }
    offenders = []
    for tree in ("src", "bridge", "common"):
        for path in sorted((REPO / tree).rglob("*.py")):
            rel = path.relative_to(REPO).as_posix()
            if "__pycache__" in rel:
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.strip().startswith("#"):
                    continue
                if disk_write.search(line) and rel not in justified:
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, "durable-state writes outside the allowlist:\n" + "\n".join(offenders)
    assert "src/google_auth.py" in justified, "the OAuth cache is the explicit allowlist member"
    source = (REPO / "src" / "skills" / "voice_biometric_auth.py").read_text(encoding="utf-8")
    assert "tempfile" in source, "transient audio/model buffers go through tempfile, never disk"


def test_no_live_call_stack_in_artifacts():
    """AC9 — v1.0 ships ZERO live-call code (ADR-07): the deploy artifacts never
    mention the PyTgCalls/Telethon/Pyrogram stacks."""
    pattern = re.compile(r"pytgcalls|telethon|pyrogram", re.IGNORECASE)
    for name in ("Dockerfile", "requirements.txt"):
        assert not pattern.search(_read(name)), f"live-call stack leaked into {name}"


def test_space_metadata_in_readme():
    """Support — the Space README metadata pins sdk: docker + app_port (deploy-blocking)."""
    readme = _read("README.md")
    assert re.search(r"sdk:\s*docker", readme)
    assert re.search(r"app_port:\s*\d+", readme)


async def test_space_port_serves_health(make_settings):
    """Support — the $PORT entry: one public port answers GET /health (keep-alive
    target) alongside the bridge WSS."""
    from src.main import start_public_port

    settings = make_settings()
    bridge, port = await start_public_port(settings, 0, host="127.0.0.1")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{port}/health")
        assert response.status_code == 200
    finally:
        await bridge.close()
