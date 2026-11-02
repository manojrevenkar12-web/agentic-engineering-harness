"""One headless Claude Code session in one worktree.

The session runs with a clean environment (HOME and PATH, plus the slot's service URLs), least
privilege (config/agent.yaml) and a hard spend cap. Every event is kept as a transcript, so cost,
tool calls and refused actions can be audited after the fact.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import load


@dataclass
class Session:
    ok: bool
    result: str = ""
    cost_usd: float = 0.0
    turns: int = 0
    duration_s: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0
    denials: list[dict] = field(default_factory=list)
    error: str = ""
    transcript: str = ""

    def to_json(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "result"} | {"result": self.result[-2000:]}


def command(model: str, max_budget_usd: float, role: str) -> list[str]:
    cfg = load("agent")
    allowed = cfg["reviewer_allowed"] if role in ("reviewer", "selector") else cfg["allowed"]
    tools = cfg["tools"] if role == "executor" else [t for t in cfg["tools"] if t not in ("Edit", "Write")]
    if role == "judge":  # reads the repository to check the change, runs and edits nothing
        tools = allowed = ["Read", "Glob", "Grep"]
    cmd = [  # the prompt goes on stdin: command lines are visible to every process on the machine
        cfg["binary"],
        "-p",
        "--model",
        model,
        "--output-format",
        "stream-json",
        "--verbose",
        "--restricted",
        "--tools",
        ",".join(tools) if tools else "",
        "--permission-mode",
        cfg["permission_mode"],
        "--max-budget-usd",
        f"{max_budget_usd:.2f}",
        "--no-session-persistence",
        "--strict-mcp-config",
    ]
    if allowed:
        cmd += ["--allowedTools", *allowed]
    return cmd


def parse(lines: list[str]) -> Session:
    s = Session(ok=False)
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    s.tool_calls += 1
        elif ev.get("type") == "result":
            u = ev.get("usage") or {}
            s.ok = ev.get("subtype") == "success" and not ev.get("is_error")
            s.result = ev.get("result") or ""
            s.cost_usd = float(ev.get("total_cost_usd") or 0.0)
            s.turns = int(ev.get("num_turns") or 0)
            s.tokens_in = (
                int(u.get("input_tokens", 0))
                + int(u.get("cache_creation_input_tokens", 0))
                + int(u.get("cache_read_input_tokens", 0))
            )
            s.tokens_out = int(u.get("output_tokens", 0))
            s.denials = list(ev.get("permission_denials") or [])
            if not s.ok:
                s.error = str(ev.get("subtype"))
    return s


async def run(
    prompt_text: str,
    cwd: Path,
    model: str,
    env: dict[str, str],
    transcript: Path,
    max_budget_usd: float,
    timeout_s: float,
    role: str = "executor",
) -> Session:
    clean = {
        "HOME": os.environ.get("HOME", "/root"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
        **env,
    }
    for k in ("AEH_FAKE_SCRIPT", "AEH_FAKE_COST"):  # the fake agent in tests reads these
        if k in os.environ:
            clean[k] = os.environ[k]
    transcript.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *command(model, max_budget_usd, role),
        cwd=cwd,
        env=clean,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    assert proc.stdin
    proc.stdin.write(prompt_text.encode())
    await proc.stdin.drain()
    proc.stdin.close()
    lines: list[str] = []
    timed_out = False

    async def pump() -> None:
        assert proc.stdout
        with transcript.open("w") as f:
            async for raw in proc.stdout:
                line = raw.decode(errors="replace")
                f.write(line)
                lines.append(line)

    try:
        await asyncio.wait_for(asyncio.gather(pump(), proc.wait()), timeout_s)
    except TimeoutError:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()
    err = (await proc.stderr.read()).decode(errors="replace")[-2000:] if proc.stderr else ""
    s = parse(lines)
    s.duration_s = round(time.monotonic() - start, 1)
    s.transcript = str(transcript)
    if timed_out:
        s.ok, s.error = False, "timeout"
        # a killed session reports no cost; count the whole cap so the budget is never understated
        s.cost_usd = max(s.cost_usd, max_budget_usd)
    elif not lines:
        s.ok, s.error = False, f"no output (exit {proc.returncode}): {err.strip()[:300]}"
    return s


def last_json(text: str) -> dict | None:
    """The last top-level JSON object in a model's final message."""
    end = text.rfind("}")
    while end != -1:
        depth = 0
        for i in range(end, -1, -1):
            if text[i] == "}":
                depth += 1
            elif text[i] == "{":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[i : end + 1])
                        return obj if isinstance(obj, dict) else None
                    except ValueError:
                        break
        end = text.rfind("}", 0, end)
    return None
