"""grade(): apply a patch to a fresh task state and decide whether it would be merged.

Order matters for cost: the free checks run first, and the review judge (a model call) runs only on
patches that are resolved without regressions, which is the only place its answer changes anything.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .. import agent
from ..config import load, prompt
from ..services import Slot, locked, mypy_cache
from ..tasks import Task, apply, checkout, git
from . import diffcheck
from .files import grader_files

# Caches written into every grading copy would cost disk and change nothing.
QUIET = {"RUFF_NO_CACHE": "true", "PYTHONDONTWRITEBYTECODE": "1"}
_sems: dict[int, asyncio.Semaphore] = {}


def _limit() -> asyncio.Semaphore:
    """One limit per event loop (tests run several loops in one process)."""
    loop = id(asyncio.get_running_loop())
    if loop not in _sems:
        _sems[loop] = asyncio.Semaphore(int(load("grading").get("concurrency", 2)))
    return _sems[loop]


@dataclass
class Grade:
    applied: bool
    resolved: bool = False
    hidden: dict = field(default_factory=dict)  # passed / failed / errors
    regression: dict = field(default_factory=dict)
    static: dict = field(default_factory=dict)  # check -> ok
    diff: dict = field(default_factory=dict)
    judge: dict = field(default_factory=dict)
    accepted: bool = False
    reasons: list[str] = field(default_factory=list)
    judge_cost_usd: float = 0.0

    def to_json(self) -> dict:
        return asdict(self)


def _env(slot: Slot, task: Task) -> dict[str, str]:
    return {
        "HOME": os.environ.get("HOME", "/root"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        **QUIET,
        "MYPY_CACHE_DIR": str(mypy_cache(task.target.name)),
        **task.target.env_for(slot.database_url, slot.redis_url),
    }


async def _cmd(cmd: list[str], cwd: Path, env: dict[str, str], timeout: float = 900) -> tuple[int, str]:
    p = await asyncio.create_subprocess_exec(
        *cmd, cwd=cwd, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    try:
        out, _ = await asyncio.wait_for(p.communicate(), timeout)
    except TimeoutError:
        p.kill()
        return 124, "timeout"
    return p.returncode or 0, out.decode(errors="replace")


def _junit(path: Path) -> dict[str, dict[str, int]]:
    """Per test file: passed / failed counts from a JUnit report."""
    per: dict[str, dict[str, int]] = {}
    if not path.exists():
        return per
    for case in ET.parse(path).getroot().iter("testcase"):
        parts = (case.get("classname") or "").split(".")
        mod = next((i for i, x in enumerate(parts) if x.startswith("test_")), len(parts) - 1)
        key = "/".join(parts[: mod + 1]) + ".py"
        bad = any(child.tag in ("failure", "error") for child in case)
        skipped = any(child.tag == "skipped" for child in case)
        d = per.setdefault(key, {"passed": 0, "failed": 0, "skipped": 0})
        d["skipped" if skipped else ("failed" if bad else "passed")] += 1
    return per


def _sum(per: dict[str, dict[str, int]], pred) -> dict[str, int]:
    out = {"passed": 0, "failed": 0, "skipped": 0}
    for k, v in per.items():
        if pred(k):
            for x in out:
                out[x] += v[x]
    return out


async def judge(task: Task, patch: str, findings: list[str], cwd: Path, home: Path) -> dict:
    cfg = load("grading")["judge"]
    text = prompt("judge").format(
        agents_md=(cwd / "AGENTS.md").read_text() if (cwd / "AGENTS.md").exists() else "(none)",
        findings="; ".join(findings) or "nothing",
        brief=task.brief,
        diff=patch[:60_000],
    )
    votes = []
    cost = 0.0
    for i in range(int(cfg.get("samples", 1))):
        v = None
        for attempt in range(1 + int(cfg.get("retries", 1))):  # a stalled or unparseable answer is asked again
            s = await agent.run(
                text,
                cwd,
                cfg["model"],
                {},
                home / f"judge-{i}-{attempt}.jsonl",
                cfg["max_budget_usd"],
                cfg["timeout_seconds"],
                "judge",
            )
            cost += s.cost_usd
            v = agent.last_json(s.result) if s.ok else None
            if v is not None and "mergeable" in v:
                break
        votes.append(
            {
                "mergeable": bool(v.get("mergeable")) if v else None,
                "blocking": (v or {}).get("blocking", []),
                "ok": v is not None,
            }
        )
    valid = [v for v in votes if v["mergeable"] is not None]
    mergeable = bool(valid) and all(v["mergeable"] for v in valid)
    return {
        "mergeable": mergeable,
        "votes": votes,
        "agree": len({v["mergeable"] for v in valid}) <= 1,
        "unavailable": not valid,
        "cost_usd": round(cost, 6),
    }


async def grade(
    task: Task, patch: str, slot: Slot, home: Path, run_judge: bool = True, allow_empty: bool = False
) -> Grade:
    try:
        async with _limit():
            return await _grade(task, patch, slot, home, run_judge, allow_empty)
    finally:
        shutil.rmtree(home / "grade", ignore_errors=True)


async def _grade(task: Task, patch: str, slot: Slot, home: Path, run_judge: bool, allow_empty: bool) -> Grade:
    gf = grader_files(task)
    cfg = load("grading")
    repo = checkout(task, home / "grade")
    if (not patch.strip() and not allow_empty) or not apply(repo, patch):
        return Grade(applied=False, reasons=["empty patch" if not patch.strip() else "patch does not apply"])
    g = Grade(applied=True)
    env = _env(slot, task)
    g.diff = diffcheck.check(patch, cfg["diff_checks"]["max_files_changed"])
    for name in ("format", "lint", "types"):
        if name == "types":
            async with locked(mypy_cache(task.target.name) / ".lock"):
                code, out = await _cmd(task.target.commands[name], repo, env, 600)
        else:
            code, out = await _cmd(task.target.commands[name], repo, env, 600)
        g.static[name] = {"ok": code == 0, "tail": out.strip().splitlines()[-1:] if out.strip() else []}
    # run the task state's own test files, not the agent's edits of them, plus the hidden tests
    originals = sorted(p for p in git(repo, "ls-files", "tests").split() if p.endswith(".py") and "/test_" in "/" + p)
    git(repo, "checkout", "HEAD", "--", "tests")
    for t in gf.hidden_tests:
        shutil.copy(t, repo / "tests" / t.name)
    hidden = [f"tests/{t.name}" for t in gf.hidden_tests]
    report = home / "junit.xml"
    code, out = await _cmd([*task.target.commands["tests"], "--junitxml", str(report), *originals, *hidden], repo, env)
    per = _junit(report)
    hidden_names = set(hidden)
    g.hidden = _sum(per, lambda k: k in hidden_names)
    g.regression = _sum(per, lambda k: k not in hidden_names)
    if not per:
        g.reasons.append(f"tests did not run: {out.strip().splitlines()[-1:] if out.strip() else code}")
    g.resolved = g.hidden["passed"] > 0 and g.hidden["failed"] == 0
    no_regression = bool(per) and g.regression["failed"] == 0
    static_ok = all(v["ok"] for v in g.static.values())
    blocking_diff = [f for f in g.diff["findings"] if f.split(":")[0] in cfg["diff_checks"]["blocking"]]
    if not g.resolved:
        g.reasons.append(f"hidden tests: {g.hidden['failed']} failed of {g.hidden['passed'] + g.hidden['failed']}")
    if not no_regression and per:
        g.reasons.append(f"regression: {g.regression['failed']} existing tests failed")
    if not static_ok:
        g.reasons.append("static: " + ", ".join(k for k, v in g.static.items() if not v["ok"]))
    g.reasons += blocking_diff
    if g.resolved and no_regression and run_judge:
        findings = list(g.diff["findings"]) + [f"{k} check failed" for k, v in g.static.items() if not v["ok"]]
        g.judge = await judge(task, patch, findings, repo, home)
        g.judge_cost_usd = g.judge["cost_usd"]
        if not g.judge["mergeable"]:
            blocking = [b for v in g.judge["votes"] for b in v.get("blocking", [])]
            g.reasons.append(
                "review: judge unavailable"
                if g.judge["unavailable"]
                else "review: " + ("; ".join(map(str, blocking))[:400] or "not mergeable")
            )
    g.accepted = (
        g.resolved
        and no_regression
        and static_ok
        and not blocking_diff
        and (not run_judge or bool(g.judge.get("mergeable")))
    )
    return g
