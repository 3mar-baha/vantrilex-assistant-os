"""Live candidate-model probe (phased): TTFT/latency/quality vs the OmniRoute pool.

Phase 1 (FAST): baseline vs candidate conversational quality (ar-JO +
masculine address) with precision TTFT timing. Later phases plug into
run_phase() — one phase per run, strictly sequential (storm etiquette:
6 s gaps, one retry max, fail-soft per model).

Usage: .venv/Scripts/python.exe scripts/probe_candidate_models.py --phase fast
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import httpx
from tabulate import tabulate

ROOT = Path(__file__).resolve().parent.parent
GATEWAY_URL = "http://localhost:20128/v1/chat/completions"
REPORT_PATH = ROOT / "benchmarks" / "CANDIDATE_MODELS_PROBE_REPORT.md"
RECORDS_PATH = ROOT / "benchmarks" / "candidate_probe_records.jsonl"
INTER_CALL_GAP_S = 6.0
FIRST_TOKEN_TIMEOUT_S = 30.0

FAST_BASELINE = "google/gemma-4-31b-it:free"
FAST_CANDIDATE = "google/gemma-4-26b-a4b:free"
FAST_CANDIDATE_ALT = "openrouter/google/gemma-4-26b-a4b-it:free"

FAST_PROMPTS = (
    "مرحبا سارة، كيفك اليوم؟ خبرني شو مسوية.",
    "طمني عن وضع البريد اليوم باختصار.",
)

MASCULINE_MARKERS = ("خبرني", "طمني", "احكيلي", "قلي", "شوف", "اسمع", "تفضل", "أهلا")
FEMININE_MARKERS = ("خبريني", "طمنيني", "احكيلك", "ساويتي", "عملتي", "انتي", "إنتِ")


def load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines); never prints values."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip("\"'")


def score_arabic_masculine(text: str) -> dict:
    masc = [m for m in MASCULINE_MARKERS if m in text]
    fem = [m for m in FEMININE_MARKERS if m in text]
    has_arabic = any("\u0600" <= ch <= "\u06ff" for ch in text)
    return {"arabic": has_arabic, "masculine_hits": masc, "feminine_hits": fem}


async def stream_probe(
    client: httpx.AsyncClient,
    model: str,
    prompt: str,
    max_tokens: int = 120,
    system: str | None = None,
) -> dict:
    """One streamed completion; returns timing + text (never raises)."""
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
    }
    started = time.perf_counter()
    first_token_ms: float | None = None
    chunks: list[str] = []
    status = "ok"
    try:
        async with client.stream(
            "POST", GATEWAY_URL, json=payload, timeout=FIRST_TOKEN_TIMEOUT_S + 30
        ) as response:
            if response.status_code != 200:
                body = (await response.aread())[:200].decode("utf-8", "replace")
                return {
                    "model": model,
                    "status": f"HTTP {response.status_code}",
                    "detail": body,
                }
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0].get("delta", {})
                except (ValueError, KeyError, IndexError):
                    continue
                content = delta.get("content")
                if content:
                    if first_token_ms is None:
                        first_token_ms = (time.perf_counter() - started) * 1000
                    chunks.append(content)
    except (httpx.HTTPError, TimeoutError) as exc:
        status = f"{type(exc).__name__}"
        return {"model": model, "status": status, "detail": str(exc)[:200]}
    total_ms = (time.perf_counter() - started) * 1000
    text = "".join(chunks)
    if not text:
        status = "empty"
    est_tokens = max(1, len(text) // 4)
    return {
        "model": model,
        "status": status,
        "ttft_ms": round(first_token_ms, 0) if first_token_ms else None,
        "total_ms": round(total_ms, 0),
        "chars": len(text),
        "tok_per_s": round(est_tokens / max(total_ms / 1000, 0.01), 1),
        "text": text,
        **score_arabic_masculine(text),
    }


MEDIUM_MODEL = "nex-agi/nex-n2.5-mini:free"
MEDIUM_REPS = 3

MEDIUM_SYSTEM = (
    "You are a tool router. Output ONLY one JSON object, no prose: "
    '{"tool": "<name>", "arg": "<string>"}. '
    "Allowed tools: calendar, gmail, tasks, telemetry."
)
MEDIUM_PROMPT = "سجليلي موعد بكرة الساعة 5 المسا: محاضرة مع الشباب"
MEDIUM_ALLOWED_TOOLS = ("calendar", "gmail", "tasks", "telemetry")


def score_tool_json(text: str) -> dict:
    """Strict verdict on a tool-call payload (Pydantic-shaped, no prose)."""
    try:
        payload = json.loads(text.strip())
    except (ValueError, AttributeError):
        return {"valid_json": False, "schema_ok": False, "hallucinated_keys": ["<unparseable>"]}
    if not isinstance(payload, dict):
        return {"valid_json": True, "schema_ok": False, "hallucinated_keys": ["<non-object>"]}
    extra = sorted(set(payload) - {"tool", "arg"})
    ok = (
        payload.get("tool") in MEDIUM_ALLOWED_TOOLS
        and isinstance(payload.get("arg"), str)
        and len(payload.get("arg", "")) > 0
        and not extra
    )
    return {"valid_json": True, "schema_ok": ok, "hallucinated_keys": extra}


async def run_medium(client: httpx.AsyncClient) -> list[dict]:
    results: list[dict] = []
    for _ in range(MEDIUM_REPS):
        record = await stream_probe(
            client, MEDIUM_MODEL, MEDIUM_PROMPT, max_tokens=150, system=MEDIUM_SYSTEM
        )
        if record.get("text"):
            record.update(score_tool_json(record["text"]))
        results.append(record)
        await asyncio.sleep(INTER_CALL_GAP_S)
    return results


def render_medium_table(results: list[dict]) -> str:
    rows = [
        [
            r["model"].split("/")[-1][:34],
            r.get("status"),
            r.get("ttft_ms", "--"),
            r.get("tok_per_s", "--"),
            r.get("valid_json", "--"),
            r.get("schema_ok", "--"),
            ",".join(r.get("hallucinated_keys", [])) or "--",
        ]
        for r in results
    ]
    return tabulate(
        rows,
        headers=["model", "status", "TTFTms", "tok/s~", "json?", "schema?", "extra_keys"],
        tablefmt="github",
    )


HEAVY_BASELINE = "nex-agi/nex-n2.5-pro:free"
HEAVY_ULTRA = "nvidia/nemotron-3-ultra:free"
HEAVY_ULTRA_ALT = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
HEAVY_LIGHTNING = "nvidia/nemotron-3.5-lightning:free"
HEAVY_LIGHTNING_ALT = "openrouter/nvidia/nemotron-3.5-lightning:free"

HEAVY_SYSTEM = (
    "You are a task planner. Output ONLY one JSON object, no prose: "
    '{"steps": [{"tool": "<name>", "arg": "<string>", "after": [<indices>]}]}. '
    "Allowed tools: gmail, calendar, tasks, telemetry, running_apps. "
    "`after` lists zero-based indices of prerequisite steps (empty for first steps)."
)
HEAVY_PROMPT = "جهز موجز المسا: شوف الإيميلات المهمة، مواعيد بكرة، وحالة الجهاز"
HEAVY_ALLOWED_TOOLS = ("gmail", "calendar", "tasks", "telemetry", "running_apps")


def score_dag(text: str) -> dict:
    """Depth rubric: parseable plan, valid tools, acyclic dependencies."""
    try:
        payload = json.loads(text.strip())
    except (ValueError, AttributeError):
        return {"valid_json": False, "steps": 0, "valid_tools": False, "acyclic": False}
    steps = payload.get("steps") if isinstance(payload, dict) else None
    if not isinstance(steps, list) or not steps:
        return {"valid_json": True, "steps": 0, "valid_tools": False, "acyclic": False}
    tools_ok = all(isinstance(s, dict) and s.get("tool") in HEAVY_ALLOWED_TOOLS for s in steps)
    try:
        order = [sorted(s.get("after", [])) for s in steps]
        acyclic = all(
            isinstance(deps, list) and all(0 <= d < i for d in deps) for i, deps in enumerate(order)
        )
    except (AttributeError, TypeError):
        acyclic = False
    return {"valid_json": True, "steps": len(steps), "valid_tools": tools_ok, "acyclic": acyclic}


async def _probe_once_with_fallback(client: httpx.AsyncClient, model: str, alt: str | None) -> dict:
    record = await stream_probe(client, model, HEAVY_PROMPT, max_tokens=300, system=HEAVY_SYSTEM)
    await asyncio.sleep(INTER_CALL_GAP_S)
    if record["status"] != "ok" and alt:
        record = await stream_probe(client, alt, HEAVY_PROMPT, max_tokens=300, system=HEAVY_SYSTEM)
        await asyncio.sleep(INTER_CALL_GAP_S)
    if record.get("text"):
        record.update(score_dag(record["text"]))
    return record


async def run_heavy(client: httpx.AsyncClient) -> list[dict]:
    return [
        await _probe_once_with_fallback(client, HEAVY_BASELINE, "openrouter/" + HEAVY_BASELINE),
        await _probe_once_with_fallback(client, HEAVY_ULTRA, HEAVY_ULTRA_ALT),
        await _probe_once_with_fallback(client, HEAVY_LIGHTNING, HEAVY_LIGHTNING_ALT),
    ]


def short_slug(model: str) -> str:
    """Last two slug segments — bare vs openrouter/ forms stay distinguishable."""
    return "/".join(model.split("/")[-2:])[:40]


def render_heavy_table(results: list[dict]) -> str:
    rows = [
        [
            short_slug(r["model"]),
            r.get("status"),
            r.get("ttft_ms", "--"),
            r.get("total_ms", "--"),
            r.get("steps", "--"),
            r.get("valid_tools", "--"),
            r.get("acyclic", "--"),
        ]
        for r in results
    ]
    return tabulate(
        rows,
        headers=["model", "status", "TTFTms", "totalMs", "steps", "tools?", "acyclic?"],
        tablefmt="github",
    )


async def run_fast(client: httpx.AsyncClient) -> list[dict]:
    models = [FAST_BASELINE, FAST_CANDIDATE]
    results: list[dict] = []
    for model in models:
        for prompt in FAST_PROMPTS:
            results.append(await stream_probe(client, model, prompt))
            await asyncio.sleep(INTER_CALL_GAP_S)
    if any(r["model"] == FAST_CANDIDATE and r["status"] != "ok" for r in results):
        results.append(await stream_probe(client, FAST_CANDIDATE_ALT, FAST_PROMPTS[0]))
    return results


def render_table(results: list[dict]) -> str:
    rows = [
        [
            r["model"].split("/")[-1][:34],
            r.get("status"),
            r.get("ttft_ms", "--"),
            r.get("total_ms", "--"),
            r.get("tok_per_s", "--"),
            ",".join(r.get("masculine_hits", [])) or "--",
            ",".join(r.get("feminine_hits", [])) or "--",
        ]
        for r in results
    ]
    return tabulate(
        rows,
        headers=["model", "status", "TTFTms", "totalMs", "tok/s~", "masc✓", "fem✗"],
        tablefmt="github",
    )


def append_report(phase: str, table: str, results: list[dict]) -> None:
    RECORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RECORDS_PATH.open("a", encoding="utf-8") as fh:
        for record in results:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    if not REPORT_PATH.exists():
        REPORT_PATH.write_text("# Candidate Models Probe Report\n", encoding="utf-8")
    texts = "\n".join(
        f"### {r['model']}\n> {(r.get('text') or r.get('detail', ''))[:400]}\n"
        for r in results
        if r.get("text") or r.get("detail")
    )
    with REPORT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## Phase: {phase} ({time.strftime('%Y-%m-%d %H:%M')})\n\n{table}\n\n{texts}\n")


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe candidate models live")
    parser.add_argument("--phase", choices=("fast", "medium", "heavy", "asr"), default="fast")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("OMNIROUTE_API_KEY", "")
    if not api_key:
        print("OMNIROUTE_API_KEY missing — aborting (no probes sent).")
        return 2
    if args.phase not in ("fast", "medium", "heavy"):
        print(f"Phase '{args.phase}' not wired yet — one phase per run.")
        return 3
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=FIRST_TOKEN_TIMEOUT_S + 30,
    ) as client:
        if args.phase == "medium":
            results = await run_medium(client)
            table = render_medium_table(results)
            append_report("MEDIUM tool-JSON", table, results)
        elif args.phase == "heavy":
            results = await run_heavy(client)
            table = render_heavy_table(results)
            append_report("HEAVY DAG decomposition", table, results)
        else:
            results = await run_fast(client)
            table = render_table(results)
            append_report("FAST conversational", table, results)
    print(table)
    print(f"\nReport: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
