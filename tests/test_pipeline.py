"""The whole loop on a toy target with a fake agent: proofs, runs, budget, crash recovery."""

import asyncio
import json

import pytest

from tests.conftest import needs_db

pytestmark = [pytest.mark.db, needs_db()]


def test_the_toy_grader_is_proven(toy):
    from aeh.prove import prove

    r = asyncio.run(prove("toyset", judge=True))
    s = r["summary"]
    assert s["proven"] == 1 and s["mutants_caught"] == 1
    assert s["unmergeable_rejected_by"]["judge"] == 1 and s["judge_passes_references"] == "1/1"


def test_a_run_grades_every_attempt_and_keeps_the_books(toy):
    from aeh import store
    from aeh.orchestrate import run
    from aeh.tasks import load_set

    r = asyncio.run(
        run("toy-ok", "toyset", ["haiku-solo", "haiku-review", "haiku-best2"], 2, 50.0, tasks=load_set("toyset"))
    )
    conn = store.connect()
    rows = store.attempts(conn, "toy-ok")
    assert len(rows) == 6 and all(a["state"] == "done" for a in rows)
    assert all(a["grade"]["accepted"] for a in rows)
    assert r["ledger"]["within_budget"] and r["ledger"]["open_reservations_match"] and r["ledger"]["settled_match"]
    review = next(a for a in rows if a["setup"] == "haiku-review")
    assert [x["role"] for x in review["outcome"]["sessions"]] == ["executor", "reviewer"]
    best = next(a for a in rows if a["setup"] == "haiku-best2")
    assert best["outcome"]["notes"]["choice"] in (1, 2)
    # running the same run again does nothing: every attempt is already recorded
    again = asyncio.run(
        run("toy-ok", "toyset", ["haiku-solo", "haiku-review", "haiku-best2"], 2, 50.0, tasks=load_set("toyset"))
    )
    assert again["ledger"]["committed_usd"] == r["ledger"]["committed_usd"]


def test_attempts_wait_for_budget_and_stop_when_it_is_spent(toy, monkeypatch):
    from aeh import store
    from aeh.orchestrate import reservation, run
    from aeh.tasks import load_set

    budget = reservation("haiku-solo") * 1.5  # room for one attempt's worst case, not two
    r = asyncio.run(run("toy-budget", "toyset", ["haiku-solo"], 3, budget, tasks=load_set("toyset")))
    conn = store.connect()
    assert [a["state"] for a in store.attempts(conn, "toy-budget")] == ["done"] * 3  # cheap attempts: one at a time
    log = conn.execute("SELECT kind FROM aeh.spend WHERE run_id = 'toy-budget' ORDER BY id").fetchall()
    assert [x["kind"] for x in log] == ["reserve", "settle", "release"] * 3  # never two reservations open at once
    assert r["ledger"]["within_budget"]

    monkeypatch.setenv("AEH_FAKE_COST", "1.0")  # every session now spends a dollar
    r = asyncio.run(run("toy-spent", "toyset", ["haiku-solo"], 3, budget, tasks=load_set("toyset")))
    states = [a["state"] for a in store.attempts(conn, "toy-spent")]
    assert states == ["done", "skipped", "skipped"]
    assert r["ledger"]["within_budget"] and r["skipped_for_budget"] == 2


def test_a_dead_worker_is_taken_over_and_its_reservation_counted(toy):
    from aeh import store
    from aeh.orchestrate import plan, reservation, run
    from aeh.tasks import load_set

    tasks = load_set("toyset")
    conn = store.connect()
    store.migrate(conn)
    store.create_run(conn, "toy-crash", "toyset", 50.0, plan(tasks, ["haiku-solo"], 1, 7), {})
    dead = store.claim(conn, "toy-crash", "dead-worker", reservation, lease_s=0)  # lease already expired
    assert dead is not None
    r = asyncio.run(run("toy-crash", "toyset", ["haiku-solo"], 1, 50.0, tasks=tasks))
    row = store.attempts(conn, "toy-crash")[0]
    assert row["state"] == "done" and row["tries"] == 2
    assert float(row["abandoned_usd"]) == pytest.approx(float(dead.reserved))
    assert r["ledger"]["within_budget"] and r["ledger"]["open_reservations_match"]
    # the dead worker coming back cannot overwrite the result
    assert not store.finish(conn, "toy-crash", dead, "dead-worker", "done", 0.0, 0.0, patch="late")


def test_the_spend_log_is_append_only(toy):
    import psycopg

    from aeh import store
    from aeh.orchestrate import plan, reservation
    from aeh.tasks import load_set

    conn = store.connect()
    store.migrate(conn)
    store.create_run(conn, "toy-log", "toyset", 50.0, plan(load_set("toyset"), ["haiku-solo"], 1, 7), {})
    assert store.claim(conn, "toy-log", "w", reservation, lease_s=60) is not None
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("UPDATE aeh.spend SET amount_usd = 0")
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("DELETE FROM aeh.spend")


def test_a_wrong_patch_is_not_accepted(toy):
    from aeh import store
    from aeh.orchestrate import run
    from aeh.tasks import load_set

    toy["script"].write_text(json.dumps({"patches": {"discount": str(toy["mutant"])}}))
    asyncio.run(run("toy-wrong", "toyset", ["haiku-solo"], 1, 50.0, tasks=load_set("toyset")))
    row = store.attempts(store.connect(), "toy-wrong")[0]
    assert row["state"] == "done" and not row["grade"]["resolved"] and not row["grade"]["accepted"]


def test_regrading_keeps_the_first_grade_and_the_books(toy):
    from aeh import store
    from aeh.orchestrate import regrade, run
    from aeh.tasks import load_set

    asyncio.run(run("toy-regrade", "toyset", ["haiku-solo"], 2, 50.0, tasks=load_set("toyset")))
    r = asyncio.run(regrade("toy-regrade", failed_suite_only=False))
    assert r["regraded"] == 2 and r["acceptance_changed"] == 0
    assert r["ledger"]["settled_match"] and r["ledger"]["within_budget"]
    rows = store.attempts(store.connect(), "toy-regrade")
    assert all(a["grade"]["previous"]["accepted"] is True for a in rows)


def test_a_failed_attempt_can_run_again_and_its_spend_still_counts(toy):
    from aeh import store
    from aeh.orchestrate import plan, reservation, run
    from aeh.tasks import load_set

    tasks = load_set("toyset")
    conn = store.connect()
    store.migrate(conn)
    store.create_run(conn, "toy-requeue", "toyset", 50.0, plan(tasks, ["haiku-solo"], 1, 7), {})
    c = store.claim(conn, "toy-requeue", "w", reservation, lease_s=60)
    assert store.finish(conn, "toy-requeue", c, "w", "failed", 0.5, 0.0, error="harness fault")
    assert store.requeue_failed(conn, "toy-requeue") == 1
    r = asyncio.run(run("toy-requeue", "toyset", ["haiku-solo"], 1, 50.0, tasks=tasks))
    row = store.attempts(conn, "toy-requeue")[0]
    assert row["state"] == "done" and float(row["abandoned_usd"]) == 0.5
    assert row["outcome"]["sessions"] and r["ledger"]["settled_match"] and r["ledger"]["open_reservations_match"]
    assert r["ledger"]["committed_usd"] >= 0.5
