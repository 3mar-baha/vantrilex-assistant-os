"""Phase-0 spike: Fish Audio expressive-tag calibration (offline probe, read-only).

Synthesizes 6 short Arabic lines on the tester voice covering: control (no
tag), 4 core [bracket] tags, and 1 (paren) paralanguage cue. Records HTTP
status / OggS validity / byte size / latency per variant plus a go/no-go
verdict on paren-cue passthrough (OpenRouter normalization behavior is
unverified). Single attempt per variant — a 429 is recorded as THROTTLED,
never retried here.

Usage (repo root):
    .venv/Scripts/python.exe scripts/fish_calibration_spike.py

Output: tests/reports/FISH_TAG_CALIBRATION.md (no secrets recorded).
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TESTER_VOICE = "e04e83de2aac43058cf3d07fa5aaaea8"

VARIANTS: tuple[tuple[str, str], ...] = (
    ("control", "مرحبا عمر، هاي تجربة صوتية قصيرة"),
    ("laughing", "[laughing] هههه يا زلمة هاي نكتة حلوة كتير"),
    ("sigh", "تعبنا اليوم كتير [sigh] بس خلصنا كل الشغل الحمد لله"),
    ("whispering", "[whispering] اسمعني منيح، هاد سر بيني وبينك"),
    ("excited", "[excited] فزنا! جبنا أعلى علامة بالصف يا عمر"),
    ("paren-sigh", "يا الله شو هالنهار الطويل (sigh) الحمد لله على كل حال"),
)

REPORT_PATH = Path("tests/reports/FISH_TAG_CALIBRATION.md")


async def probe_variant(fish, text: str) -> dict:
    """One synthesis + transcode; never raises — outcome recorded as data."""
    from src.fish_voice import FishVoiceError
    from src.voice import transcode_mp3_to_opus

    t0 = time.perf_counter()
    try:
        mp3 = await fish.synthesize(text)
    except FishVoiceError as exc:
        msg = str(exc)
        status = "THROTTLED" if "429" in msg else f"FAIL: {msg[:120]}"
        return {"status": status, "ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001 — record, don't hang the spike
        return {
            "status": f"ERROR: {type(exc).__name__}",
            "ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    try:
        opus = await transcode_mp3_to_opus(mp3)
    except Exception as exc:  # noqa: BLE001 — transcode failure is data too
        return {
            "status": f"TRANSCODE_FAIL: {type(exc).__name__}",
            "ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    ms = round((time.perf_counter() - t0) * 1000, 1)
    if opus[:4] != b"OggS":
        return {"status": "BAD_HEADER", "ms": ms}
    return {"status": "OK", "ms": ms, "bytes": len(opus)}


async def main() -> int:
    from src.config import get_settings
    from src.fish_voice import FishVoice

    settings = get_settings()
    if not settings.fish_audio_key:
        print("ABORT: no Fish audio key configured (fish_audio_key empty)")
        return 2
    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        commit = proc.stdout.strip() or "unknown"
    except OSError:
        commit = "unknown"

    fish = FishVoice(
        model=settings.fish_audio_model,
        voice_ref=TESTER_VOICE,
        api_key=settings.fish_audio_key,
        speed=settings.fish_audio_speed,
        endpoint=settings.fish_audio_endpoint,
    )
    rows: list[tuple[str, str, dict]] = []
    try:
        for name, text in VARIANTS:
            print(f"--- {name} ---", flush=True)
            outcome = await probe_variant(fish, text)
            print(f"    {outcome['status']} ms={outcome['ms']}", flush=True)
            rows.append((name, text, outcome))
            await asyncio.sleep(3)  # free-pool courtesy gap
    finally:
        await fish.aclose()

    ok = [r for r in rows if r[2]["status"] == "OK"]
    paren = next(r for r in rows if r[0] == "paren-sigh")
    paren_live = paren[2]["status"] == "OK"
    lines = [
        "# Fish Audio Tag Calibration (Phase-0 spike)",
        "",
        f"Date: {time.strftime('%Y-%m-%dT%H:%M:%S%z')} · commit: {commit}",
        f"Model: `{settings.fish_audio_model}` · endpoint: `{settings.fish_audio_endpoint}`",
        "Voice: tester lane (Sara ref untouched) · key source: "
        + (
            "dedicated FISH_AUDIO_API_KEY"
            if getattr(settings, "fish_audio_api_key", None)
            else "shared OPENROUTER_API_KEY"
        ),
        "Note: shaped production path (shape_for_tts applied); no secrets recorded.",
        "",
        "## Results",
        "",
        "| Variant | Input | Status | ms | opus bytes |",
        "|---|---|---|---|---|",
    ]
    for name, text, outcome in rows:
        lines.append(
            f"| {name} | «{text}» | {outcome['status']} | {outcome['ms']} | {outcome.get('bytes', '—')} |"
        )
    lines += [
        "",
        "## Verdicts",
        "",
        f"- Bracket tags: **{'GO' if len(ok) >= 4 else 'NO-GO'}** ({len(ok)}/6 variants OK).",
        "- Paren cues `(sigh)`: **"
        + (
            "GO — passthrough live; set PARALANGUAGE_PAREN_ENABLED=True"
            if paren_live
            else "NO-GO — keep PARALANGUAGE_PAREN_ENABLED=False; brackets only"
        )
        + f"** (status: {paren[2]['status']}).",
        "- Throttled variants are pool state, not tag verdicts — rerun off-peak before downgrading any tag.",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE {REPORT_PATH} ({len(ok)}/6 OK)", flush=True)
    return 0 if len(ok) >= 4 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
