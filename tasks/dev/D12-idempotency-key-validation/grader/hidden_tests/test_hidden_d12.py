import pytest

from tests.conftest import chat


@pytest.mark.parametrize("key", ["", "   ", "k" * 256, "schlüssel-1".encode(), "tab\there"])
async def test_unusable_keys_are_rejected_before_anything_is_recorded(env, key):
    ws, h = await env.workspace()
    r = await env.client.post("/v1/chat/completions", json=chat("hello"), headers={**h, "Idempotency-Key": key})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["type"] == "invalid_idempotency_key"
    async with env.db.tenant(ws) as conn:
        assert await conn.fetchval("SELECT count(*) FROM mrp.usage") == 0


@pytest.mark.parametrize("key", ["k" * 255, "order-42/retry:1"])
async def test_usable_keys_work_and_replay(env, key):
    _, h = await env.workspace()
    a = await env.client.post("/v1/chat/completions", json=chat("hello"), headers={**h, "Idempotency-Key": key})
    b = await env.client.post("/v1/chat/completions", json=chat("hello"), headers={**h, "Idempotency-Key": key})
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["choices"] == b.json()["choices"]


async def test_no_header_still_works(env):
    _, h = await env.workspace()
    assert (await env.client.post("/v1/chat/completions", json=chat("hello"), headers=h)).status_code == 200
