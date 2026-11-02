"""The setups being compared: how sessions are combined to work one task.

A flow only sees what an engineer on the team would see: the brief, the repository at the task
state, and the repository's own tests. It never reads a task's grader directory.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from . import agent
from .config import load, prompt
from .services import Slot, Slots, mypy_cache
from .tasks import Task, checkout, diff


@dataclass
class Outcome:
    patch: str
    sessions: list[dict] = field(default_factory=list)
    notes: dict = field(default_factory=dict)

    @property
    def cost_usd(self) -> float:
        return round(sum(s["cost_usd"] for s in self.sessions), 6)


def setups() -> dict[str, dict]:
    return load("setups")["setups"]


def reservation(setup: dict) -> float:
    """The most an attempt with this setup can spend: the sum of its sessions' hard caps."""
    caps = {k: v["max_budget_usd"] for k, v in load("harness")["sessions"].items()}
    if setup["flow"] == "solo":
        return caps["executor"]
    if setup["flow"] == "review":
        return caps["executor"] * (1 + setup.get("max_revisions", 1)) + caps["reviewer"]
    if setup["flow"] == "best_of":
        return caps["executor"] * setup.get("n", 2) + caps["selector"]
    raise ValueError(f"unknown flow {setup['flow']}")


async def _session(role: str, text: str, repo: Path, model: str, slot: Slot, task: Task, log: Path) -> agent.Session:
    cap = load("harness")["sessions"][role]
    return await agent.run(
        text,
        repo,
        model,
        {"MYPY_CACHE_DIR": str(mypy_cache(task.target.name)), **task.target.env_for(slot.database_url, slot.redis_url)},
        log,
        cap["max_budget_usd"],
        cap["timeout_seconds"],
        role,
    )


async def _executor(task: Task, model: str, repo: Path, slot: Slot, log: Path) -> agent.Session:
    return await _session("executor", prompt("executor").format(brief=task.brief), repo, model, slot, task, log)


async def solo(task: Task, setup: dict, home: Path, slots: Slots) -> Outcome:
    repo = checkout(task, home / "repo")
    async with slots.lease() as slot:
        s = await _executor(task, setup["model"], repo, slot, home / "executor.jsonl")
    return Outcome(diff(repo), [s.to_json() | {"role": "executor"}])


async def review(task: Task, setup: dict, home: Path, slots: Slots) -> Outcome:
    repo = checkout(task, home / "repo")
    sessions, rounds = [], []
    async with slots.lease() as slot:
        s = await _executor(task, setup["model"], repo, slot, home / "executor.jsonl")
        sessions.append(s.to_json() | {"role": "executor"})
        for i in range(setup.get("max_revisions", 1)):
            if not diff(repo).strip():
                break
            r = await _session(
                "reviewer",
                prompt("reviewer").format(brief=task.brief),
                repo,
                setup["reviewer_model"],
                slot,
                task,
                home / f"reviewer-{i}.jsonl",
            )
            sessions.append(r.to_json() | {"role": "reviewer"})
            verdict = agent.last_json(r.result) or {}
            issues = [str(x) for x in verdict.get("issues", [])]
            rounds.append({"approve": bool(verdict.get("approve")), "issues": issues, "parsed": bool(verdict)})
            if verdict.get("approve") or not issues:
                break
            text = prompt("revise").format(brief=task.brief, issues="\n".join(f"- {x}" for x in issues))
            s = await _session("executor", text, repo, setup["model"], slot, task, home / f"revise-{i}.jsonl")
            sessions.append(s.to_json() | {"role": "revise"})
    return Outcome(diff(repo), sessions, {"review": rounds})


async def _visible_tests(task: Task, repo: Path, slot: Slot) -> tuple[bool, str]:
    """The repository's own test suite on a candidate: what any engineer can run."""
    env = {**_base_env(), **task.target.env_for(slot.database_url, slot.redis_url)}
    proc = await asyncio.create_subprocess_exec(
        *task.target.commands["tests"],
        cwd=repo,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    tail = out.decode(errors="replace").strip().splitlines()[-1:] or [""]
    return proc.returncode == 0, tail[0][:200]


def _base_env() -> dict[str, str]:
    import os

    return {
        "HOME": os.environ.get("HOME", "/root"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


async def best_of(task: Task, setup: dict, home: Path, slots: Slots) -> Outcome:
    n = setup.get("n", 2)
    repos = [checkout(task, home / f"repo-{i + 1}") for i in range(n)]

    async def one(i: int) -> agent.Session:
        async with slots.lease() as slot:
            return await _executor(task, setup["model"], repos[i], slot, home / f"executor-{i + 1}.jsonl")

    runs = await asyncio.gather(*(one(i) for i in range(n)))
    sessions = [r.to_json() | {"role": f"executor-{i + 1}"} for i, r in enumerate(runs)]
    patches = [diff(r) for r in repos]
    live = [i for i, p in enumerate(patches) if p.strip()]
    if len(live) <= 1:
        pick = live[0] if live else 0
        return Outcome(patches[pick], sessions, {"choice": pick + 1, "reason": "only one candidate changed anything"})
    results = []
    async with slots.lease() as slot:
        for i in live:
            ok, tail = await _visible_tests(task, repos[i], slot)
            results.append(f"Candidate {i + 1}: test suite {'passed' if ok else 'FAILED'} ({tail})")
        work = checkout(task, home / "select")
        names = []
        for i in live:
            name = f"candidate-{i + 1}.diff"
            (work / name).write_text(patches[i])
            names.append(name)
        text = prompt("selector").format(
            brief=task.brief, candidates=" and ".join(names), test_results="\n".join(results)
        )
        s = await _session("selector", text, work, setup["selector_model"], slot, task, home / "selector.jsonl")
    sessions.append(s.to_json() | {"role": "selector"})
    verdict = agent.last_json(s.result) or {}
    choice = verdict.get("choice")
    pick = int(choice) - 1 if isinstance(choice, int) and 1 <= choice <= n and (int(choice) - 1) in live else live[0]
    return Outcome(
        patches[pick], sessions, {"choice": pick + 1, "reason": str(verdict.get("reason", ""))[:300], "tests": results}
    )


FLOWS = {"solo": solo, "review": review, "best_of": best_of}


async def work(task: Task, setup_name: str, home: Path, slots: Slots) -> Outcome:
    setup = setups()[setup_name]
    return await FLOWS[setup["flow"]](task, setup, home, slots)
