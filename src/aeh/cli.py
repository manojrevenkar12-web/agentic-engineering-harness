"""aeh: the command line.

aeh prove  --set dev                       prove the graders (hidden tests, mutants, review judge)
aeh bench  --set dev --run dev-1 --setups haiku-solo,sonnet-solo --samples 2 --budget 40
aeh status --run dev-1                     progress, spend and the budget check
aeh heldout --setups haiku-solo,sonnet-review --budget 15   the held-out set, once; the first run is kept
aeh report                                 reports/results.json and docs/REPORT.md
aeh solve  --issue issue.md --setup sonnet-review     daily use: one issue, the adopted setup
aeh serve                                  read-only API over the record
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aeh")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prove")
    p.add_argument("--set", default="dev")
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--task", action="append")
    b = sub.add_parser("bench")
    b.add_argument("--set", default="dev")
    b.add_argument("--run", required=True)
    b.add_argument("--setups", required=True)
    b.add_argument("--samples", type=int, default=1)
    b.add_argument("--budget", type=float, required=True)
    b.add_argument("--task", action="append")
    b.add_argument("--seed", type=int, default=7)
    b.add_argument("--allow-unproven", action="store_true")
    s = sub.add_parser("status")
    s.add_argument("--run", required=True)
    h = sub.add_parser("heldout")
    h.add_argument("--run", default="heldout-1")
    h.add_argument("--setups", required=True)
    h.add_argument("--budget", type=float, required=True)
    sub.add_parser("report")
    v = sub.add_parser("solve")
    v.add_argument("--issue", required=True, type=Path)
    v.add_argument("--setup", default=None)
    v.add_argument("--out", type=Path, default=Path("change.patch"))
    sub.add_parser("serve")
    a = ap.parse_args(argv)

    if a.cmd == "prove":
        from .prove import prove

        r = asyncio.run(prove(a.set, judge=not a.no_judge, only=a.task))
        print(json.dumps(r["summary"], indent=1))
        return 0 if r["summary"]["proven"] == r["summary"]["tasks"] else 1
    if a.cmd == "bench":
        from .orchestrate import run
        from .prove import proven_ids
        from .tasks import load_set

        tasks = [t for t in load_set(a.set) if not a.task or t.id in a.task]
        ok = proven_ids(a.set)
        if not a.allow_unproven:
            missing = [t.id for t in tasks if t.id not in ok]
            if missing:
                print(f"tasks without a proven grader (run aeh prove --set {a.set}): {missing}")
                return 2
        r = asyncio.run(run(a.run, a.set, a.setups.split(","), a.samples, a.budget, a.seed, tasks))
        from . import store
        from .report import export

        r["export"] = str(export(store.connect(), a.run))
        print(json.dumps(r, indent=1))
        return 0
    if a.cmd == "status":
        from . import store

        conn = store.connect()
        rows = store.attempts(conn, a.run)
        states: dict[str, int] = {}
        for r in rows:
            states[r["state"]] = states.get(r["state"], 0) + 1
        print(
            json.dumps({"attempts": len(rows), "states": states, "ledger": store.ledger_check(conn, a.run)}, indent=1)
        )
        return 0
    if a.cmd == "heldout":
        from .heldout import first_run

        return asyncio.run(first_run(a.run, a.setups.split(","), a.budget))
    if a.cmd == "report":
        from .report import write

        write()
        return 0
    if a.cmd == "solve":
        from .solve import solve

        return asyncio.run(solve(a.issue, a.setup, a.out))
    if a.cmd == "serve":
        import uvicorn

        uvicorn.run("aeh.api:app", host="127.0.0.1", port=8020)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
