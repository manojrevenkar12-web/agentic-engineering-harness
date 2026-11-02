"""Hidden tests for H04: a monthly spend budget per workspace."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tests.conftest import chat

AMOUNT = re.compile(r"^\d+\.\d{8}$")


async def ask(env, h, text="Summarize the weekly status report."):
    return await env.client.post("/v1/chat/completions", json=chat(text), headers=h)


async def billed_row(env, ws, billed, actual=None, created_at=None):
    """A settled usage row written directly, as an earlier request would have left it."""
    async with env.db.owner() as conn:
        await conn.execute(
            "INSERT INTO mrp.usage (id, workspace_id, idempotency_key, request_hash, status, task, model, "
            "actual_cost, billed_amount, created_at, settled_at) "
            "VALUES ($1, $2, $3, 'h', 'ok', 'chat', 'open-70b', $4, $5, $6, $6)",
            uuid.uuid4(),
            uuid.UUID(ws),
            f"seed-{uuid.uuid4()}",
            Decimal(actual if actual is not None else billed),
            Decimal(billed),
            created_at or datetime.now(UTC),
        )


async def usage_count(env, ws):
    async with env.db.tenant(ws) as conn:
        return await conn.fetchval("SELECT count(*) FROM mrp.usage")


async def test_set_read_and_remove_a_budget(env):
    _, h = await env.workspace()
    r = await env.client.get("/v1/budget", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["monthly_limit"] is None and Decimal(body["spent"]) == 0 and AMOUNT.match(body["spent"])
    assert body["month"] == datetime.now(UTC).strftime("%Y-%m")
    r = await env.client.put("/v1/budget", json={"monthly_limit": "25.00"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["monthly_limit"] == "25.00000000"
    assert (await env.client.get("/v1/budget", headers=h)).json()["monthly_limit"] == "25.00000000"
    r = await env.client.put("/v1/budget", json={"monthly_limit": 7.5}, headers=h)
    assert r.json()["monthly_limit"] == "7.50000000"
    r = await env.client.put("/v1/budget", json={"monthly_limit": None}, headers=h)
    assert r.status_code == 200 and r.json()["monthly_limit"] is None
    assert (await env.client.get("/v1/budget", headers=h)).json()["monthly_limit"] is None


@pytest.mark.parametrize("bad", ["0", "-1.00", "lots"])
async def test_a_limit_must_be_a_positive_amount(env, bad):
    _, h = await env.workspace()
    r = await env.client.put("/v1/budget", json={"monthly_limit": bad}, headers=h)
    assert r.status_code == 422


async def test_spent_is_this_months_billed_amount(env):
    ws, h = await env.workspace()
    assert (await ask(env, h)).status_code == 200
    await billed_row(env, ws, "2.00000000", actual="1.50000000")
    await billed_row(env, ws, "100.00000000", created_at=datetime.now(UTC) - timedelta(days=40))
    async with env.db.tenant(ws) as conn:
        want = await conn.fetchval(
            "SELECT sum(billed_amount) FROM mrp.usage WHERE created_at >= date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'"
        )
    body = (await env.client.get("/v1/budget", headers=h)).json()
    assert AMOUNT.match(body["spent"]) and Decimal(body["spent"]) == want
    assert Decimal("2") < want < Decimal("3")


async def test_requests_are_refused_once_the_budget_is_reached(env):
    ws, h = await env.workspace()
    await env.client.put("/v1/budget", json={"monthly_limit": "0.00000100"}, headers=h)
    first = await ask(env, h)  # nothing billed yet: answered, whatever it is estimated to cost
    assert first.status_code == 200, first.text
    before = sum(p.calls for p in env.providers.values())
    rows = await usage_count(env, ws)
    r = await ask(env, h, "Summarize the incident timeline.")
    assert r.status_code == 402, r.text
    err = r.json()["error"]
    assert err["type"] == "entitlement" and "budget" in err["message"].lower()
    assert sum(p.calls for p in env.providers.values()) == before
    assert await usage_count(env, ws) == rows
    stream = await env.client.post(
        "/v1/chat/completions", json=chat("Tell me a story.", stream=True), headers=h
    )
    assert stream.status_code == 402
    await env.client.put("/v1/budget", json={"monthly_limit": "50"}, headers=h)
    assert (await ask(env, h, "Summarize the incident timeline.")).status_code == 200


async def test_reaching_the_limit_exactly_is_reached(env):
    ws, h = await env.workspace()
    await billed_row(env, ws, "1.00000000", actual="0.50000000")
    await env.client.put("/v1/budget", json={"monthly_limit": "1.00"}, headers=h)
    assert (await ask(env, h)).status_code == 402


async def test_the_bill_counts_not_our_provider_cost(env):
    ws, h = await env.workspace()
    await billed_row(env, ws, "1.15000000", actual="1.00000000")
    await env.client.put("/v1/budget", json={"monthly_limit": "1.10"}, headers=h)
    assert (await ask(env, h)).status_code == 402


async def test_earlier_months_do_not_count(env):
    ws, h = await env.workspace()
    await billed_row(env, ws, "80.00000000", created_at=datetime.now(UTC) - timedelta(days=40))
    await env.client.put("/v1/budget", json={"monthly_limit": "5"}, headers=h)
    assert (await ask(env, h)).status_code == 200


async def test_budgets_and_spend_are_per_workspace(env):
    a, ha = await env.workspace(name="a")
    b, hb = await env.workspace(name="b")
    await billed_row(env, b, "9.00000000")
    await env.client.put("/v1/budget", json={"monthly_limit": "0.00000001"}, headers=hb)
    await env.client.put("/v1/budget", json={"monthly_limit": "5"}, headers=ha)
    assert (await ask(env, ha)).status_code == 200  # B's spend does not count against A's budget
    assert (await ask(env, hb)).status_code == 402
    body = (await env.client.get("/v1/budget", headers=ha)).json()
    assert body["monthly_limit"] == "5.00000000" and Decimal(body["spent"]) < 1
    _, hc = await env.workspace(name="c")
    assert (await env.client.get("/v1/budget", headers=hc)).json()["monthly_limit"] is None
    assert (await ask(env, hc)).status_code == 200
