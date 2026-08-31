"""Single-tree supervisor for the HF Space container (sprint-4 4.4b): runs the
OmniRoute gateway child and the core child as ONE process tree — the first child
to exit becomes the container exit, and the surviving child is torn down first.
No half-alive states: the Space supervisor restarts the whole container.

Commands come from the environment (HF Space variables / local shell):
  OMNIROUTE_CMD  required — how to start the gateway (e.g. `npm start --prefix scripts/omniroute`)
  CORE_CMD       optional — defaults to `python -m src.main`
The core child reads $PORT itself (Space contract: one public port, /health + bridge WSS).
"""

from __future__ import annotations

import asyncio
import os
import shlex
import sys

from loguru import logger

TEARDOWN_GRACE_S = 5.0


def build_children(env: dict[str, str] | None = None) -> dict[str, list[str]]:
    env = os.environ if env is None else env
    omniroute = env.get("OMNIROUTE_CMD", "").strip()
    if not omniroute:
        raise ValueError(
            "OMNIROUTE_CMD is required — the supervisor runs OmniRoute + core as one tree "
            "(RUNBOOK §4)"
        )
    core = env.get("CORE_CMD", "").strip() or "python -m src.main"
    return {"omniroute": shlex.split(omniroute), "core": shlex.split(core)}


async def _reap(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=TEARDOWN_GRACE_S)
    except TimeoutError:
        proc.kill()
        await proc.wait()


async def supervise(children: dict[str, list[str]]) -> int:
    procs: dict[str, asyncio.subprocess.Process] = {}
    try:
        for name, cmd in children.items():
            procs[name] = await asyncio.create_subprocess_exec(*cmd)
            logger.info("supervisor started {name}: {cmd}", name=name, cmd=" ".join(cmd))
        waiters = {asyncio.create_task(proc.wait()): name for name, proc in procs.items()}
        done, _pending = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        first = waiters[next(iter(done))]
        code = procs[first].returncode
        logger.warning(
            "child {name} exited (code {code}) — tearing down the tree", name=first, code=code
        )
        return code
    except Exception as error:  # noqa: BLE001 — spawn failure must tear down the tree and exit the container, never hang
        logger.critical("supervisor could not start the tree: {error}", error=error)
        return 2
    finally:
        await asyncio.gather(*(_reap(proc) for proc in procs.values()))


def main() -> int:
    try:
        children = build_children()
    except ValueError as error:
        logger.critical("supervisor boot refused: {error}", error=error)
        return 2
    return asyncio.run(supervise(children))


if __name__ == "__main__":
    sys.exit(main())
