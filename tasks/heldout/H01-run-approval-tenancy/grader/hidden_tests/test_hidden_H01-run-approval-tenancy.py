"""Hidden tests for H01: step decisions stay inside the workspace that owns the run."""

import uuid

import pytest

from mrp.agents import FakeConnectors, Runner
from mrp.catalog import load
from mrp.router import QualityTable

TABLE = QualityTable.load(__import__("mrp.app", fromlist=["DEFAULT_TABLE"]).DEFAULT_TABLE)
STEPS = [
    {"kind": "tool", "name": "slack.post", "args": {"channel": "#ops", "text": "draft ready"}},
    {"kind": "tool", "name": "gmail.send", "args": {"to": ["partner@other.org"], "subject": "Q3"}},
]


def runner(env, connectors=None):
    return Runner(env.db, load(), TABLE, env.providers, connectors or FakeConnectors(), worker_id="w-h01")


async def waiting_run(env):
    """Workspace A's run, paused on its external email (step 1)."""
    a, ha = await env.workspace(name="a")
    b, hb = await env.workspace(name="b")
    r = await env.client.post("/v1/agents/runs", json={"goal": "send Q3", "steps": STEPS}, headers=ha)
    assert r.status_code == 202, r.text
    run_id = r.json()["run_id"]
    conn = FakeConnectors()
    assert await runner(env, conn).run(uuid.UUID(a), "team", uuid.UUID(run_id)) == "waiting_approval"
    return a, ha, b, hb, run_id, conn


async def step_state(env, ws, run_id):
    async with env.db.tenant(ws) as conn:
        step = await conn.fetchrow(
            "SELECT status, decided_by FROM mrp.run_steps WHERE run_id = $1 AND step_no = 1",
            uuid.UUID(run_id),
        )
        run = await conn.fetchval("SELECT status FROM mrp.agent_runs WHERE id = $1", uuid.UUID(run_id))
    return step["status"], step["decided_by"], run


@pytest.mark.parametrize("decision", ["approve", "reject"])
async def test_another_workspace_gets_404_and_changes_nothing(env, decision):
    a, ha, b, hb, run_id, _ = await waiting_run(env)
    r = await env.client.post(
        f"/v1/agents/runs/{run_id}/steps/1/{decision}",
        headers={**hb, "X-MRP-User": "integration-bot"},
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "no such run"
    assert await step_state(env, a, run_id) == ("waiting_approval", None, "waiting_approval")


async def test_an_unknown_run_is_404(env):
    _, h = await env.workspace()
    r = await env.client.post(f"/v1/agents/runs/{uuid.uuid4()}/steps/0/approve", headers=h)
    assert r.status_code == 404 and r.json()["detail"] == "no such run"


async def test_the_owner_still_decides_and_gets_409_when_nothing_is_pending(env):
    a, ha, b, hb, run_id, conn = await waiting_run(env)
    nothing = await env.client.post(f"/v1/agents/runs/{run_id}/steps/0/approve", headers=ha)
    assert nothing.status_code == 409, nothing.text
    ok = await env.client.post(
        f"/v1/agents/runs/{run_id}/steps/1/approve", headers={**ha, "X-MRP-User": "lead@example.com"}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json() == {"run_id": run_id, "step": 1, "decision": "approve"}
    assert await step_state(env, a, run_id) == ("approved", "lead@example.com", "queued")
    again = await env.client.post(f"/v1/agents/runs/{run_id}/steps/1/approve", headers=ha)
    assert again.status_code == 409
    assert await runner(env, conn).run(uuid.UUID(a), "team", uuid.UUID(run_id)) == "succeeded"
    assert [e[0] for e in conn.effects] == ["slack.post", "gmail.send"]


async def test_the_owner_can_reject(env):
    a, ha, b, hb, run_id, conn = await waiting_run(env)
    r = await env.client.post(
        f"/v1/agents/runs/{run_id}/steps/1/reject", headers={**ha, "X-MRP-User": "lead@example.com"}
    )
    assert r.status_code == 200
    assert await runner(env, conn).run(uuid.UUID(a), "team", uuid.UUID(run_id)) == "rejected"
    assert [e[0] for e in conn.effects] == ["slack.post"]


@pytest.mark.parametrize("approve", [True, False])
async def test_runner_decide_with_the_wrong_workspace_raises_and_records_nothing(env, approve):
    a, ha, b, hb, run_id, _ = await waiting_run(env)
    with pytest.raises(Exception):  # noqa: B017 - the brief asks only that it raises
        await runner(env).decide(uuid.UUID(b), uuid.UUID(run_id), 1, approve, "integration-bot")
    assert await step_state(env, a, run_id) == ("waiting_approval", None, "waiting_approval")
