"""The held-out set: tasks written blind, run once with the setups the dev benchmark chose between.

The first run is written to reports/heldout/first_run.json and never rewritten. If anyone studies its
failures to change the harness, the set becomes a regression set (tasks/heldout/STATUS) and a new
held-out set is written from tasks/WRITING_TASKS.md by someone who has not seen the harness.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from . import store
from .config import ROOT, reports_dir
from .orchestrate import run
from .prove import proven_ids
from .report import export
from .tasks import load_set


def first_path():
    return reports_dir() / "heldout" / "first_run.json"


STATUS = ROOT / "tasks" / "heldout" / "STATUS"


async def first_run(run_id: str, setups: list[str], budget: float) -> int:
    status = STATUS.read_text().strip() if STATUS.exists() else "heldout"
    if first_path().exists():
        print(f"{first_path()} exists; the first run is never rewritten")
        return 1
    if status != "heldout":
        print(f"set status is {status}; write a new held-out set first")
        return 1
    tasks = load_set("heldout")
    ok = proven_ids("heldout")
    missing = [t.id for t in tasks if t.id not in ok]
    if missing:
        print(f"unproven held-out tasks: {missing}")
        return 2
    result = await run(run_id, "heldout", setups, 1, budget, tasks=tasks)
    conn = store.connect()
    export(conn, run_id)
    rows = [r for r in store.attempts(conn, run_id) if r["state"] in ("done", "failed")]
    per = {}
    for s in setups:
        mine = [r for r in rows if r["setup"] == s]
        per[s] = {
            "attempts": len(mine),
            "accepted": sum(bool((r["grade"] or {}).get("accepted")) for r in mine),
            "tests_pass": sum(
                bool((r["grade"] or {}).get("resolved"))
                and not ((r["grade"] or {}).get("regression") or {}).get("failed")
                for r in mine
            ),
            "cost_usd": round(sum(float(r["cost_usd"] or 0) + float(r["judge_cost_usd"] or 0) for r in mine), 4),
            "per_task": {r["task_id"]: bool((r["grade"] or {}).get("accepted")) for r in mine},
        }
    first_path().parent.mkdir(parents=True, exist_ok=True)
    first_path().write_text(
        json.dumps(
            {
                "recorded_at": datetime.now(UTC).isoformat(),
                "run": run_id,
                "tasks": [t.id for t in tasks],
                "setups": per,
                "ledger": result["ledger"],
                "skipped_for_budget": result["skipped_for_budget"],
            },
            indent=1,
        )
    )
    print(json.dumps(per, indent=1))
    return 0
