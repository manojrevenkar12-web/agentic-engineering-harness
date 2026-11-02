"""Hidden tests for H02: a cache hit is billed from the actual cost of the delivered call."""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from mrp.catalog import load
from mrp.ledger import CENT8
from tests.conftest import chat


async def post(env, h, body, key):
    r = await env.client.post("/v1/chat/completions", json=body, headers={**h, "Idempotency-Key": key})
    assert r.status_code == 200, r.text
    return r


async def usage(env, ws, key):
    async with env.db.tenant(ws) as conn:
        return await conn.fetchrow("SELECT * FROM mrp.usage WHERE idempotency_key = $1", key)


async def delivered_cost(env, ws, key) -> Decimal:
    async with env.db.tenant(ws) as conn:
        rows = await conn.fetch(
            "SELECT c.cost FROM mrp.provider_calls c JOIN mrp.usage u ON u.id = c.usage_id "
            "WHERE u.idempotency_key = $1 AND c.delivered",
            key,
        )
    assert len(rows) == 1
    return rows[0]["cost"]


def expected(cost: Decimal, plan: str) -> Decimal:
    cat = load()
    return (cost * cat.cached_answer_charge * (1 + cat.plans[plan].markup)).quantize(
        CENT8, rounding=ROUND_HALF_UP
    )


async def assert_hit_billed(env, ws, plan, hit, hit_key, original_key, kinds=("exact",)):
    assert hit.headers["x-mrp-cache"] in kinds
    row = await usage(env, ws, hit_key)
    want = expected(await delivered_cost(env, ws, original_key), plan)
    assert row["status"] == "cache_hit"
    assert row["billed_amount"] == want
    assert Decimal(hit.headers["x-mrp-billed"]) == want
    assert row["actual_cost"] == 0
    assert row["avoided_cost_est"] == Decimal(hit.headers["x-mrp-estimated-cost"])


@pytest.mark.parametrize("plan", ["team", "enterprise"])
async def test_an_exact_hit_is_billed_from_the_delivered_call(env, plan):
    ws, h = await env.workspace(plan=plan)
    body = chat("Summarize the release notes for version 2.4 in two lines.", temperature=0)
    first = await post(env, h, body, "orig")
    assert first.headers["x-mrp-cache"] == "miss"
    hit = await post(env, h, body, "again")
    await assert_hit_billed(env, ws, plan, hit, "again", "orig")


async def test_a_semantic_hit_is_billed_from_the_delivered_call(env):
    ws, h = await env.workspace(plan="team")
    await post(env, h, chat("What is the refund limit for orders above 500 EUR in Germany?"), "orig")
    hit = await post(env, h, chat("hi, what is the refund limit for orders above 500 EUR in Germany"), "near")
    await assert_hit_billed(env, ws, "team", hit, "near", "orig", kinds=("semantic",))


async def test_after_a_fallback_the_hit_is_billed_from_the_model_that_answered(env):
    ws, h = await env.workspace(plan="team")
    env.providers["closed-a"].down = {"frontier-mid"}
    body = chat("Summarize the board meeting.", model="frontier-mid", mrp={"fallbacks": ["general-b"]})
    first = await post(env, h, body, "orig")
    assert first.headers["x-mrp-model"] == "general-b" and first.headers["x-mrp-fallback"] == "true"
    hit = await post(env, h, body, "again")
    await assert_hit_billed(env, ws, "team", hit, "again", "orig")


async def test_after_an_escalation_only_the_answering_call_counts(env):
    ws, h = await env.workspace(plan="team")
    for i in range(60):
        body = chat(
            f"Extract the invoice id and amount as JSON: invoice {i} for {i}.50 EUR", mrp={"quality": "high"}
        )
        first = await post(env, h, body, f"orig-{i}")
        if first.headers["x-mrp-escalated"] == "true":
            break
    else:
        pytest.fail("no request escalated")
    row = await usage(env, ws, f"orig-{i}")
    delivered = await delivered_cost(env, ws, f"orig-{i}")
    assert row["actual_cost"] > delivered  # the escalated first try is in our spend
    hit = await post(env, h, body, f"again-{i}")
    await assert_hit_billed(env, ws, "team", hit, f"again-{i}", f"orig-{i}")
