"""Running a benchmark: many attempts, several at once, within a budget, resumable after a crash.

Every attempt is (task, setup, sample). Attempts launch in an interleaved order (sample 1 of every
task under every setup first, in a seeded shuffle), so a run that stops early, or runs out of
budget, still compares setups on the same tasks.
"""

from __future__ import annotations

import asyncio
import random
import shutil
import socket
import uuid
from pathlib import Path

from . import flows, store
from .config import load, workdir
from .grade import grade
from .services import Slots, prepare
from .tasks import Task, load_set


def plan(tasks: list[Task], setup_names: list[str], samples: int, seed: int) -> list[tuple[str, str, int]]:
    rng = random.Random(seed)
    out: list[tuple[str, str, int]] = []
    for s in range(1, samples + 1):
        block = [(t.id, name, s) for t in tasks for name in setup_names]
        rng.shuffle(block)
        out += block
    return out


def reservation(setup_name: str) -> float:
    return flows.reservation(flows.setups()[setup_name]) + float(load("grading")["judge"]["max_budget_usd"])


async def _attempt(conn, run_id: str, c: store.Claim, task: Task, slots: Slots, worker: str, keep: bool) -> None:
    home = workdir() / "runs" / run_id / task.id / c.setup / f"s{c.sample}"
    lease_s = int(load("harness")["lease_seconds"])
    alive = True

    async def beat() -> None:
        nonlocal alive
        while alive:
            await asyncio.sleep(min(60, lease_s / 3))
            if not await asyncio.to_thread(store.heartbeat, conn, c.id, worker, lease_s):
                alive = False

    hb = asyncio.create_task(beat())
    cost = judge_cost = 0.0
    try:
        outcome = await flows.work(task, c.setup, home, slots)
        cost = outcome.cost_usd
        async with slots.lease() as slot:
            g = await grade(task, outcome.patch, slot, home)
        judge_cost = g.judge_cost_usd
        ok = await asyncio.to_thread(
            store.finish,
            conn,
            run_id,
            c,
            worker,
            "done",
            cost,
            judge_cost,
            outcome={"sessions": outcome.sessions, "notes": outcome.notes},
            grade=g.to_json(),
            patch=outcome.patch,
        )
        if not ok:
            print(f"lost the lease on attempt {c.id}; its result was discarded")
    except Exception as e:  # an attempt that crashes is recorded, and its spend still counts
        await asyncio.to_thread(
            store.finish, conn, run_id, c, worker, "failed", cost, judge_cost, error=f"{type(e).__name__}: {e}"[:2000]
        )
    finally:
        alive = False
        hb.cancel()
        if not keep:
            for p in home.glob("repo*"):
                shutil.rmtree(p, ignore_errors=True)
            shutil.rmtree(home / "select", ignore_errors=True)


async def run(
    run_id: str,
    task_set: str,
    setup_names: list[str],
    samples: int,
    budget: float,
    seed: int = 7,
    tasks: list[Task] | None = None,
    keep: bool = False,
) -> dict:
    cfg = load("harness")
    tasks = tasks if tasks is not None else load_set(task_set)
    if not tasks:
        raise SystemExit(f"no tasks in set {task_set}")
    unknown = set(setup_names) - set(flows.setups())
    if unknown:
        raise SystemExit(f"unknown setups: {sorted(unknown)}")
    by_id = {t.id: t for t in tasks}
    url = cfg["services"]["record_url"]
    store.ensure_database(url)
    conn = store.connect(url)
    store.migrate(conn)
    store.create_run(
        conn,
        run_id,
        task_set,
        budget,
        plan(tasks, setup_names, samples, seed),
        {"setups": setup_names, "samples": samples, "seed": seed},
    )
    slots = Slots()
    prepare(slots.n, tasks[0].target.database_extensions)
    worker = f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"
    lease_s = int(cfg["lease_seconds"])
    running: set[asyncio.Task] = set()
    while True:
        while len(running) < int(cfg["concurrency"]):
            c = await asyncio.to_thread(store.claim, conn, run_id, worker, reservation, lease_s)
            if c is None:  # nothing left, or nothing that fits the budget until running attempts settle
                break
            print(f"start {c.task_id} {c.setup} s{c.sample} (reserved ${c.reserved})", flush=True)
            # each attempt gets its own connection: the heartbeat and the result must not wait on others
            running.add(
                asyncio.create_task(_attempt(store.connect(url), run_id, c, by_id[c.task_id], slots, worker, keep))
            )
        if not running:
            break
        done, _ = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
        running -= done
    queued_left = sum(a["state"] == "queued" for a in store.attempts(conn, run_id))
    skipped = (
        store.skip_rest(conn, run_id)
        if queued_left and not any(a["state"] == "running" for a in store.attempts(conn, run_id))
        else 0
    )
    return {"run": run_id, "skipped_for_budget": skipped, "ledger": store.ledger_check(conn, run_id)}


def cleanup(run_id: str) -> None:
    shutil.rmtree(Path(workdir()) / "runs" / run_id, ignore_errors=True)
