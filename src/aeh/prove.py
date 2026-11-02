"""Proving the graders before any agent is graded by them.

For every task:
  - the task state fails its hidden tests, and its own test suite passes (the task is real and fair);
  - the reference change is accepted (hidden tests, suite, static checks, review judge);
  - every wrong change (mutant) is caught by the hidden tests or the suite;
  - every unmergeable change passes the tests and is rejected by review (static, diff checks or judge).

A task whose first three hold is "proven" and may be used in a benchmark. The unmergeable changes and
the references together measure the review judge: how often it blocks what should be blocked and
passes what should pass.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .config import reports_dir, workdir
from .grade import grade
from .grade.files import grader_files
from .services import Slots, prepare
from .tasks import Task, load_set


def _layer(g) -> str:
    if not g.resolved or g.regression.get("failed"):
        return "tests"
    if not all(v["ok"] for v in g.static.values()):
        return "static"
    if any(
        r.split(":")[0] in ("deletes_test", "removes_assertions", "touches_invariant_marker", "skips_tests")
        for r in g.reasons
    ):
        return "diff"
    if g.judge and not g.judge.get("mergeable"):
        return "judge"
    return "none"


async def prove_task(task: Task, slots: Slots, judge: bool = True) -> dict:
    gf = grader_files(task)
    home = workdir() / "prove" / task.set / task.id

    async def one(name: str, patch: str, run_judge: bool, allow_empty: bool = False):
        async with slots.lease() as slot:
            return await grade(task, patch, slot, home / name, run_judge=run_judge, allow_empty=allow_empty)

    state, ref = await asyncio.gather(one("state", "", False, True), one("reference", gf.reference, judge))
    muts = await asyncio.gather(*(one(f"mutant-{v.name}", v.patch, False) for v in gf.mutants))
    unm = await asyncio.gather(*(one(f"unmergeable-{v.name}", v.patch, judge) for v in gf.unmergeable))
    out = {
        "task": task.id,
        "state": {
            "hidden_failed": state.hidden.get("failed", 0),
            "suite_failed": state.regression.get("failed", 0),
            "suite_passed": state.regression.get("passed", 0),
        },
        "reference": {
            "accepted": ref.accepted,
            "reasons": ref.reasons,
            "judge": ref.judge.get("mergeable") if ref.judge else None,
            "static": {k: v["ok"] for k, v in ref.static.items()},
        },
        "mutants": [
            {"name": v.name, "caught": not (g.resolved and not g.regression.get("failed")), "why": v.why}
            for v, g in zip(gf.mutants, muts, strict=True)
        ],
        "unmergeable": [
            {
                "name": v.name,
                "tests_pass": g.resolved and not g.regression.get("failed"),
                "rejected_by": _layer(g),
                "why": v.why,
                "judge_blocking": [b for x in g.judge.get("votes", []) for b in x.get("blocking", [])]
                if g.judge
                else [],
            }
            for v, g in zip(gf.unmergeable, unm, strict=True)
        ],
        "judge_cost_usd": round(ref.judge_cost_usd + sum(g.judge_cost_usd for g in unm), 6),
    }
    out["proven"] = (
        out["state"]["hidden_failed"] > 0
        and out["state"]["suite_failed"] == 0
        and out["state"]["suite_passed"] > 0
        and (ref.accepted or not judge and ref.resolved)
        and all(m["caught"] for m in out["mutants"])
    )
    return out


async def prove(set_name: str, judge: bool = True, only: list[str] | None = None) -> dict:
    tasks = [t for t in load_set(set_name) if not only or t.id in only]
    if not tasks:
        raise SystemExit(f"no tasks in set {set_name}")
    slots = Slots()
    prepare(slots.n, tasks[0].target.database_extensions)
    sem = asyncio.Semaphore(max(1, slots.n // 3))

    async def guarded(t: Task) -> dict:
        async with sem:
            r = await prove_task(t, slots, judge)
            print(f"proved {t.id}: {'proven' if r['proven'] else 'NOT proven'}", flush=True)
            return r

    results = await asyncio.gather(*(guarded(t) for t in tasks))
    refs = [r["reference"]["judge"] for r in results if r["reference"]["judge"] is not None]
    unm = [u for r in results for u in r["unmergeable"] if u["tests_pass"]]
    summary = {
        "set": set_name,
        "tasks": len(results),
        "proven": sum(r["proven"] for r in results),
        "mutants": sum(len(r["mutants"]) for r in results),
        "mutants_caught": sum(m["caught"] for r in results for m in r["mutants"]),
        "unmergeable": len(unm),
        "unmergeable_rejected": sum(u["rejected_by"] != "none" for u in unm),
        "unmergeable_rejected_by": {
            k: sum(u["rejected_by"] == k for u in unm) for k in ("static", "diff", "judge", "none")
        },
        "judge_passes_references": f"{sum(refs)}/{len(refs)}" if refs else "not run",
        "judge_cost_usd": round(sum(r["judge_cost_usd"] for r in results), 4),
        "with_judge": judge,
    }
    report = {"summary": summary, "tasks": results}
    out = reports_dir() / "proofs" / f"{set_name}.json"
    if judge and not only:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1))
    return report


def proven_ids(set_name: str) -> set[str]:
    p = reports_dir() / "proofs" / f"{set_name}.json"
    if not p.exists():
        return set()
    return {t["task"] for t in json.loads(Path(p).read_text())["tasks"] if t["proven"]}
