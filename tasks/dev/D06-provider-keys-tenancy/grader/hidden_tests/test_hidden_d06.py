import pytest

pytestmark = pytest.mark.invariant


async def test_a_workspace_lists_only_its_own_provider_keys(env):
    _, ha = await env.workspace(plan="team", name="a")
    _, hb = await env.workspace(plan="team", name="b")
    assert (await env.client.put("/v1/provider-keys/closed-a", json={"api_key": "sk-aaaaaaaaaaaa"}, headers=ha)).status_code == 200
    assert (await env.client.put("/v1/provider-keys/closed-b", json={"api_key": "sk-bbbbbbbbbbbb"}, headers=hb)).status_code == 200
    a = (await env.client.get("/v1/provider-keys", headers=ha)).json()
    b = (await env.client.get("/v1/provider-keys", headers=hb)).json()
    assert [k["provider"] for k in a] == ["closed-a"]
    assert [k["provider"] for k in b] == ["closed-b"]


async def test_a_workspace_without_keys_lists_none(env):
    _, ha = await env.workspace(plan="team", name="a")
    _, hc = await env.workspace(plan="team", name="c")
    await env.client.put("/v1/provider-keys/closed-a", json={"api_key": "sk-aaaaaaaaaaaa"}, headers=ha)
    assert (await env.client.get("/v1/provider-keys", headers=hc)).json() == []
