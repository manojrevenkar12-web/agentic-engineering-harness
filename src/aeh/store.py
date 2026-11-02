"""The run record and the money: attempts are leased, and their spend is reserved before they start.

Invariant: for every run, settled spend + abandoned reservations + open reservations <= budget.
A reservation is the attempt's worst case (the sum of its sessions' hard caps, which Claude Code
enforces, plus the review judge's cap), so the budget holds even if every session hits its cap.
A worker that dies leaves its reservation open; whoever takes the attempt over later counts that
reservation as spent ("abandon"), because the money may have been spent and cannot be known.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from importlib import resources
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import load


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or load("harness")["services"]["record_url"], autocommit=True, row_factory=dict_row)


def ensure_database(url: str) -> None:
    base, name = url.rsplit("/", 1)
    with psycopg.connect(base + "/postgres", autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            c.execute(f'CREATE DATABASE "{name}"')


def migrate(conn: psycopg.Connection) -> None:
    conn.execute("SELECT pg_advisory_lock(733999)")
    try:
        for f in sorted(p for p in resources.files("aeh.sql").iterdir() if p.name.endswith(".sql")):
            conn.execute(f.read_text())
    finally:
        conn.execute("SELECT pg_advisory_unlock(733999)")


@dataclass
class Claim:
    id: int
    task_id: str
    setup: str
    sample: int
    reserved: Decimal
    tries: int


def create_run(
    conn, run_id: str, task_set: str, budget: float, plan: list[tuple[str, str, int]], config: dict[str, Any]
) -> None:
    """Idempotent: re-creating a run adds missing attempts and keeps everything already recorded."""
    with conn.transaction():
        conn.execute(
            "INSERT INTO aeh.runs (id, task_set, budget_usd, config) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET budget_usd = EXCLUDED.budget_usd",
            (run_id, task_set, Decimal(str(budget)), json.dumps(config)),
        )
        for pos, (task, setup, sample) in enumerate(plan):
            conn.execute(
                "INSERT INTO aeh.attempts (run_id, task_id, setup, sample, position) VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (run_id, task_id, setup, sample) DO NOTHING",
                (run_id, task, setup, sample, pos),
            )


def committed(conn, run_id: str) -> Decimal:
    r = conn.execute(
        "SELECT coalesce(sum(coalesce(cost_usd, 0) + coalesce(judge_cost_usd, 0) + abandoned_usd + reserved_usd), 0) AS c "
        "FROM aeh.attempts WHERE run_id = %s",
        (run_id,),
    ).fetchone()
    return Decimal(r["c"])


def claim(conn, run_id: str, worker: str, reservation_for, lease_s: int) -> Claim | None:
    """Lease the next attempt and reserve its worst-case spend, or None if nothing fits the budget."""
    with conn.transaction():
        run = conn.execute("SELECT budget_usd FROM aeh.runs WHERE id = %s FOR UPDATE", (run_id,)).fetchone()
        row = conn.execute(
            "SELECT id, task_id, setup, sample, reserved_usd, tries FROM aeh.attempts WHERE run_id = %s "
            "AND (state = 'queued' OR (state = 'running' AND lease_until < now())) ORDER BY position LIMIT 1 FOR UPDATE SKIP LOCKED",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        if row["reserved_usd"] > 0:  # a previous holder died: its reservation may have been spent
            conn.execute(
                "UPDATE aeh.attempts SET abandoned_usd = abandoned_usd + reserved_usd, reserved_usd = 0 WHERE id = %s",
                (row["id"],),
            )
            conn.execute(
                "INSERT INTO aeh.spend (run_id, attempt_id, kind, amount_usd) VALUES (%s, %s, 'abandon', %s)",
                (run_id, row["id"], row["reserved_usd"]),
            )
        need = Decimal(str(round(reservation_for(row["setup"]), 6)))
        if committed(conn, run_id) + need > Decimal(run["budget_usd"]):
            return None
        conn.execute(
            "UPDATE aeh.attempts SET state = 'running', worker = %s, lease_until = now() + make_interval(secs => %s), "
            "tries = tries + 1, reserved_usd = %s, started_at = now() WHERE id = %s",
            (worker, lease_s, need, row["id"]),
        )
        conn.execute(
            "INSERT INTO aeh.spend (run_id, attempt_id, kind, amount_usd) VALUES (%s, %s, 'reserve', %s)",
            (run_id, row["id"], need),
        )
        return Claim(row["id"], row["task_id"], row["setup"], row["sample"], need, row["tries"] + 1)


def heartbeat(conn, attempt_id: int, worker: str, lease_s: int) -> bool:
    r = conn.execute(
        "UPDATE aeh.attempts SET lease_until = now() + make_interval(secs => %s) WHERE id = %s AND worker = %s AND state = 'running'",
        (lease_s, attempt_id, worker),
    )
    return r.rowcount == 1


def finish(conn, run_id: str, c: Claim, worker: str, state: str, cost: float, judge_cost: float, **fields: Any) -> bool:
    """Settle an attempt. Fenced by the lease: a worker that lost its lease cannot overwrite the result."""
    with conn.transaction():
        r = conn.execute(
            "UPDATE aeh.attempts SET state = %s, cost_usd = %s, judge_cost_usd = %s, reserved_usd = 0, lease_until = NULL, "
            "outcome = %s, grade = %s, patch = %s, error = %s, finished_at = now() WHERE id = %s AND worker = %s AND state = 'running'",
            (
                state,
                Decimal(str(round(cost, 6))),
                Decimal(str(round(judge_cost, 6))),
                json.dumps(fields.get("outcome")) if fields.get("outcome") is not None else None,
                json.dumps(fields.get("grade")) if fields.get("grade") is not None else None,
                fields.get("patch"),
                fields.get("error"),
                c.id,
                worker,
            ),
        )
        if r.rowcount != 1:
            return False
        conn.execute(
            "INSERT INTO aeh.spend (run_id, attempt_id, kind, amount_usd) VALUES (%s, %s, 'settle', %s), (%s, %s, 'release', %s)",
            (run_id, c.id, Decimal(str(round(cost + judge_cost, 6))), run_id, c.id, -c.reserved),
        )
        return True


def skip_rest(conn, run_id: str) -> int:
    """Attempts that will not fit the budget are recorded as skipped, not silently dropped."""
    return conn.execute(
        "UPDATE aeh.attempts SET state = 'skipped' WHERE run_id = %s AND state = 'queued'", (run_id,)
    ).rowcount


def attempts(conn, run_id: str) -> list[dict]:
    return conn.execute("SELECT * FROM aeh.attempts WHERE run_id = %s ORDER BY position", (run_id,)).fetchall()


def ledger_check(conn, run_id: str) -> dict:
    """The spend log must agree with the attempts table, and the budget must hold."""
    log = conn.execute(
        "SELECT kind, coalesce(sum(amount_usd), 0) AS s FROM aeh.spend WHERE run_id = %s GROUP BY kind", (run_id,)
    ).fetchall()
    by = {r["kind"]: Decimal(r["s"]) for r in log}
    open_res = by.get("reserve", Decimal(0)) + by.get("release", Decimal(0)) - by.get("abandon", Decimal(0))
    settled = by.get("settle", Decimal(0)) + by.get("reverse", Decimal(0))
    abandoned = by.get("abandon", Decimal(0)) + by.get("requeued", Decimal(0))
    table = conn.execute(
        "SELECT coalesce(sum(reserved_usd), 0) AS r, coalesce(sum(coalesce(cost_usd, 0) + coalesce(judge_cost_usd, 0)), 0) AS s, "
        "coalesce(sum(abandoned_usd), 0) AS a FROM aeh.attempts WHERE run_id = %s",
        (run_id,),
    ).fetchone()
    budget = Decimal(conn.execute("SELECT budget_usd FROM aeh.runs WHERE id = %s", (run_id,)).fetchone()["budget_usd"])
    total = Decimal(table["s"]) + Decimal(table["a"]) + Decimal(table["r"])
    return {
        "open_reservations_match": open_res == Decimal(table["r"]),
        "settled_match": settled == Decimal(table["s"]) and abandoned == Decimal(table["a"]),
        "abandoned_usd": float(table["a"]),
        "committed_usd": float(total),
        "budget_usd": float(budget),
        "within_budget": total <= budget,
    }


def regraded(conn, run_id: str, attempt_id: int, grade: dict, extra_judge_cost: float) -> None:
    """Replace a finished attempt's grade (same patch, fixed grading environment); extra judge spend is settled."""
    extra = Decimal(str(round(extra_judge_cost, 6)))
    with conn.transaction():
        conn.execute(
            "UPDATE aeh.attempts SET grade = %s, judge_cost_usd = coalesce(judge_cost_usd, 0) + %s WHERE id = %s AND state = 'done'",
            (json.dumps(grade), extra, attempt_id),
        )
        if extra:
            conn.execute(
                "INSERT INTO aeh.spend (run_id, attempt_id, kind, amount_usd) VALUES (%s, %s, 'settle', %s)",
                (run_id, attempt_id, extra),
            )


def requeue_failed(conn, run_id: str) -> int:
    """Run failed attempts again (a harness fault, not the agent's). What they spent stays counted."""
    with conn.transaction():
        rows = conn.execute(
            "SELECT id, coalesce(cost_usd, 0) + coalesce(judge_cost_usd, 0) AS spent FROM aeh.attempts "
            "WHERE run_id = %s AND state = 'failed' FOR UPDATE",
            (run_id,),
        ).fetchall()
        for r in rows:
            if r["spent"]:
                conn.execute(
                    "INSERT INTO aeh.spend (run_id, attempt_id, kind, amount_usd) VALUES (%s, %s, 'reverse', %s), (%s, %s, 'requeued', %s)",
                    (run_id, r["id"], -r["spent"], run_id, r["id"], r["spent"]),
                )
            conn.execute(
                "UPDATE aeh.attempts SET state = 'queued', abandoned_usd = abandoned_usd + %s, cost_usd = NULL, judge_cost_usd = NULL, "
                "outcome = jsonb_build_object('previous_error', error), error = NULL WHERE id = %s",
                (r["spent"], r["id"]),
            )
        return len(rows)
