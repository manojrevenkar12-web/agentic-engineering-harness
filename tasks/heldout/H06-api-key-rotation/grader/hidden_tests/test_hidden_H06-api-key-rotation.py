"""Hidden tests for H06: customers manage their own API keys."""

import hashlib
import logging
import uuid

from tests.conftest import chat


def bearer(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


async def create_key(env, h):
    r = await env.client.post("/v1/api-keys", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"id", "api_key", "prefix"}
    assert body["api_key"].startswith("mrp_") and body["prefix"] == body["api_key"][:8]
    uuid.UUID(body["id"])
    return body


async def test_a_new_key_works_and_is_listed_without_secrets(env, caplog):
    caplog.set_level(logging.DEBUG)
    ws, h = await env.workspace()
    new = await create_key(env, h)
    r = await env.client.post("/v1/chat/completions", json=chat("Hello there"), headers=bearer(new["api_key"]))
    assert r.status_code == 200, r.text
    listed = await env.client.get("/v1/api-keys", headers=bearer(new["api_key"]))
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 2 and all(set(i) == {"id", "prefix", "created_at", "revoked_at"} for i in items)
    assert items[1]["id"] == new["id"] and items[1]["prefix"] == new["prefix"]
    assert items[0]["prefix"] == h["Authorization"].removeprefix("Bearer ")[:8]
    assert all(i["revoked_at"] is None for i in items)
    text = listed.text
    assert new["api_key"] not in text and hashlib.sha256(new["api_key"].encode()).hexdigest() not in text
    assert new["api_key"] not in caplog.text
    async with env.db.owner() as conn:
        stored = await conn.fetchrow("SELECT * FROM mrp.api_keys WHERE id = $1", uuid.UUID(new["id"]))
    assert stored["key_hash"] == hashlib.sha256(new["api_key"].encode()).hexdigest()
    assert str(stored["workspace_id"]) == ws
    assert new["api_key"] not in str(dict(stored))


async def test_revoking_a_key_locks_it_out_and_keeps_it_listed(env):
    _, h = await env.workspace()
    new = await create_key(env, h)
    r = await env.client.delete(f"/v1/api-keys/{new['id']}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"id": new["id"], "revoked": True}
    assert (await env.client.get("/v1/models", headers=bearer(new["api_key"]))).status_code == 401
    assert (
        await env.client.post("/v1/chat/completions", json=chat("hi"), headers=bearer(new["api_key"]))
    ).status_code == 401
    items = (await env.client.get("/v1/api-keys", headers=h)).json()
    by_id = {i["id"]: i for i in items}
    assert by_id[new["id"]]["revoked_at"] is not None and len(items) == 2
    assert (await env.client.get("/v1/models", headers=h)).status_code == 200


async def test_rotation_revoke_the_original_with_the_new_key(env):
    _, h = await env.workspace()
    original = (await env.client.get("/v1/api-keys", headers=h)).json()[0]
    new = await create_key(env, h)
    r = await env.client.delete(f"/v1/api-keys/{original['id']}", headers=bearer(new["api_key"]))
    assert r.status_code == 200
    assert (await env.client.get("/v1/models", headers=h)).status_code == 401
    assert (await env.client.get("/v1/models", headers=bearer(new["api_key"]))).status_code == 200


async def test_the_key_in_use_cannot_revoke_itself(env):
    _, h = await env.workspace()
    me = (await env.client.get("/v1/api-keys", headers=h)).json()[0]
    r = await env.client.delete(f"/v1/api-keys/{me['id']}", headers=h)
    assert r.status_code == 409, r.text
    assert (await env.client.get("/v1/models", headers=h)).status_code == 200
    assert (await env.client.get("/v1/api-keys", headers=h)).json()[0]["revoked_at"] is None


async def test_workspaces_never_see_or_revoke_each_others_keys(env):
    a, ha = await env.workspace(name="a")
    b, hb = await env.workspace(name="b")
    a_new = await create_key(env, ha)
    b_items = (await env.client.get("/v1/api-keys", headers=hb)).json()
    assert len(b_items) == 1 and a_new["id"] not in {i["id"] for i in b_items}
    r = await env.client.delete(f"/v1/api-keys/{a_new['id']}", headers=hb)
    assert r.status_code == 404 and r.json()["detail"] == "no such key"
    assert (await env.client.get("/v1/models", headers=bearer(a_new["api_key"]))).status_code == 200
    unknown = await env.client.delete(f"/v1/api-keys/{uuid.uuid4()}", headers=ha)
    assert unknown.status_code == 404 and unknown.json()["detail"] == "no such key"
    b_new = await create_key(env, hb)
    async with env.db.tenant(b) as conn:
        assert {str(r["id"]) for r in await conn.fetch("SELECT id FROM mrp.api_keys")} == {
            b_items[0]["id"],
            b_new["id"],
        }


async def test_a_revoked_key_cannot_manage_keys(env):
    _, h = await env.workspace()
    new = await create_key(env, h)
    await env.client.delete(f"/v1/api-keys/{new['id']}", headers=h)
    assert (await env.client.post("/v1/api-keys", headers=bearer(new["api_key"]))).status_code == 401
    assert (await env.client.get("/v1/api-keys", headers=bearer(new["api_key"]))).status_code == 401
