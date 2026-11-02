"""Hidden tests for H05: cancelling agent runs."""

import uuid
from decimal import Decimal

import pytest

from mrp.agents import FakeConnectors, Runner
from mrp.catalog import load
from mrp.router import QualityTable

TABLE = QualityTable.load(__import__("mrp.app", fromlist=["DEFAULT_TABLE"]).DEFAULT_TABLE)
SLACK = {"kind": "tool", "name": "slack.post", "args": {"channel": "#ops", "text": "starting"}}
MODEL = {"kind": "model", "prompt": "Summarize this week's incidents in three bullets.", "task": "summarization"}
CAL = {"kind": "tool", "name": "calendar.create", "args": {"title": "review", "attendees": ["a@example.com"]}}
MAIL = {"kind": "tool", "name": "gmail.send", "args": {"to": ["partner@other.org"], "subject": "update"}}


def runner(env, connectors):
    return Runner(env.db, load(), TABLE, env.providers, connectors, worker_id=f"w-{uuid.uuid4().hex[:6]}")


async def create(env, h, steps):
    r = await env.client.post("/v1/agents/runs", json={"goal": "ops", "steps": steps}, headers=h)
    assert r.status_code == 202, r.text
    return r.json()["run_id"]


async def status(env, h, run_id):
    return (await env.client.get(f"/v1/agents/runs/{run_id}", headers=h)).json()


def provider_calls(env):
    return sum(p.calls for p in env.providers.values())


async def test_cancel_a_queued_run(env):
    ws, h = await env.workspace()
    run_id = await create(env, h, [SLACK, MODEL])
    r = await env.client.post(f"/v1/agents/runs/{run_id}/cancel", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"run_id": run_id, "status": "cancelled"}
    assert (await status(env, h, run_id))["status"] == "cancelled"
    conn = FakeConnectors()
    assert await runner(env, conn).run(uuid.UUID(ws), "team", uuid.UUID(run_id)) == "not_runnable"
    assert conn.effects == [] and provider_calls(env) == 0
    assert (await status(env, h, run_id))["status"] == "cancelled"


async def test_cancel_a_run_waiting_for_approval_and_approvals_are_refused(env):
    ws, h = await env.workspace()
    run_id = await create(env, h, [SLACK, MAIL, CAL])
    conn = FakeConnectors()
    assert await runner(env, conn).run(uuid.UUID(ws), "team", uuid.UUID(run_id)) == "waiting_approval"
    r = await env.client.post(f"/v1/agents/runs/{run_id}/cancel", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    for decision in ("approve", "reject"):
        d = await env.client.post(f"/v1/agents/runs/{run_id}/steps/1/{decision}", headers=h)
        assert d.status_code == 409, d.text
    body = await status(env, h, run_id)
    assert body["status"] == "cancelled"
    assert [(s["step_no"], s["status"]) for s in body["steps"]] == [(0, "done"), (1, "waiting_approval")]
    assert await runner(env, conn).run(uuid.UUID(ws), "team", uuid.UUID(run_id)) == "not_runnable"
    assert [e[0] for e in conn.effects] == ["slack.post"]


class CancellingConnectors(FakeConnectors):
    """Cancels the run through the API while the first tool call is in flight."""

    def __init__(self, env, headers):
        super().__init__()
        self.env, self.headers, self.run_id, self.answer = env, headers, None, None

    async def call(self, name, args, idempotency_key):
        if self.answer is None:
            self.answer = await self.env.client.post(f"/v1/agents/runs/{self.run_id}/cancel", headers=self.headers)
        return await super().call(name, args, idempotency_key)


async def test_a_running_run_stops_before_its_next_step(env):
    ws, h = await env.workspace()
    run_id = await create(env, h, [SLACK, MODEL, CAL])
    conn = CancellingConnectors(env, h)
    conn.run_id = run_id
    assert await runner(env, conn).run(uuid.UUID(ws), "team", uuid.UUID(run_id)) == "cancelled"
    assert conn.answer.status_code == 200, conn.answer.text
    assert [e[0] for e in conn.effects] == ["slack.post"]  # the step in flight finished, nothing after
    assert provider_calls(env) == 0
    body = await status(env, h, run_id)
    assert body["status"] == "cancelled"
    assert [(s["step_no"], s["status"]) for s in body["steps"]] == [(0, "done")]
    assert await runner(env, FakeConnectors()).run(uuid.UUID(ws), "team", uuid.UUID(run_id)) == "not_runnable"


@pytest.mark.parametrize("ending", ["succeeded", "rejected", "cancelled"])
async def test_a_run_that_has_ended_cannot_be_cancelled(env, ending):
    ws, h = await env.workspace()
    conn = FakeConnectors()
    if ending == "succeeded":
        run_id = await create(env, h, [SLACK])
        assert await runner(env, conn).run(uuid.UUID(ws), "team", uuid.UUID(run_id)) == "succeeded"
    elif ending == "rejected":
        run_id = await create(env, h, [MAIL])
        await runner(env, conn).run(uuid.UUID(ws), "team", uuid.UUID(run_id))
        assert (await env.client.post(f"/v1/agents/runs/{run_id}/steps/0/reject", headers=h)).status_code == 200
        assert await runner(env, conn).run(uuid.UUID(ws), "team", uuid.UUID(run_id)) == "rejected"
    else:
        run_id = await create(env, h, [SLACK])
        assert (await env.client.post(f"/v1/agents/runs/{run_id}/cancel", headers=h)).status_code == 200
    r = await env.client.post(f"/v1/agents/runs/{run_id}/cancel", headers=h)
    assert r.status_code == 409, r.text
    assert (await status(env, h, run_id))["status"] == ending


async def test_another_workspace_cannot_cancel(env):
    a, ha = await env.workspace(name="a")
    b, hb = await env.workspace(name="b")
    run_id = await create(env, ha, [SLACK, MODEL])
    r = await env.client.post(f"/v1/agents/runs/{run_id}/cancel", headers=hb)
    assert r.status_code == 404 and r.json()["detail"] == "no such run"
    assert (await status(env, ha, run_id))["status"] == "queued"
    unknown = await env.client.post(f"/v1/agents/runs/{uuid.uuid4()}/cancel", headers=ha)
    assert unknown.status_code == 404 and unknown.json()["detail"] == "no such run"
    conn = FakeConnectors()
    assert await runner(env, conn).run(uuid.UUID(a), "team", uuid.UUID(run_id)) == "succeeded"


async def test_a_run_with_a_cost_limit_still_completes_normally(env):
    ws, h = await env.workspace()
    r = await env.client.post(
        "/v1/agents/runs", json={"goal": "x", "steps": [MODEL, SLACK], "cost_limit": "0.50"}, headers=h
    )
    run_id = r.json()["run_id"]
    conn = FakeConnectors()
    assert await runner(env, conn).run(uuid.UUID(ws), "team", uuid.UUID(run_id)) == "succeeded"
    body = await status(env, h, run_id)
    assert body["status"] == "succeeded" and Decimal(body["cost_spent"]) > 0
