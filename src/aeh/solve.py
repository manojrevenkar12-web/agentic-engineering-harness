"""Daily use: run the adopted setup on one new issue, and hand a person a patch plus its review."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from . import flows
from .config import load, workdir
from .grade import diffcheck
from .services import Slots, prepare
from .tasks import Task


async def solve(issue: Path, setup: str | None, out: Path, target: str = "model-router-platform") -> int:
    setup = setup or load("setups")["default"]
    d = workdir() / "issues" / uuid.uuid4().hex[:10]
    d.mkdir(parents=True)
    (d / "brief.md").write_text(issue.read_text())
    (d / "task.yaml").write_text(f"id: {d.name}\ntitle: {issue.stem}\nkind: issue\ntarget: {target}\n")
    task = Task(d.name, "issues", issue.stem, "issue", target, d)
    slots = Slots()
    prepare(slots.n, task.target.database_extensions)
    outcome = await flows.work(task, setup, d / "work", slots)
    out.write_text(outcome.patch)
    checks = diffcheck.check(outcome.patch, int(load("grading")["diff_checks"]["max_files_changed"]))
    print(
        json.dumps(
            {"setup": setup, "patch": str(out), "cost_usd": outcome.cost_usd, "diff": checks, "notes": outcome.notes},
            indent=1,
        )
    )
    shutil.rmtree(d / "work", ignore_errors=True)
    return 0 if outcome.patch.strip() else 1
